"""Provider labels are authoritative, including [], in CI and preflight."""

from __future__ import annotations

import json
import subprocess
from argparse import Namespace
from pathlib import Path

import pytest
import yaml

from policy_check import cli, preflight, pr_context
from policy_check.rules.base import Status
from policy_check.rules.r12_branch_source import R12BranchSource


_EXEMPT = "policy-exempt:branch-name"


@pytest.fixture(autouse=True)
def isolate_provider_context(monkeypatch):
    monkeypatch.delenv("CI_MERGE_REQUEST_IID", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    monkeypatch.setattr(pr_context, "changed_files", lambda *_args: [])
    monkeypatch.setattr(pr_context, "latest_tag", lambda *_args: None)


def _write_config(repo: Path, *, allow_fix: bool = False) -> None:
    config = {"policy_profile": "flat", "policy_version": "1.0.17"}
    if allow_fix:
        config["branch_source"] = {"allowed_prefixes": ["feature", "fix"]}
    (repo / ".project-policy.yml").write_text(yaml.safe_dump(config), encoding="utf-8")


def _args(repo: Path, **overrides) -> Namespace:
    values = {
        "repo": str(repo),
        "pr_title": None,
        "pr_body": None,
        "pr_labels": None,
        "pr_base_ref": "main",
        "pr_head_ref": "bugfix/87-branch-contract",
        "repo_visibility": None,
        "only": None,
    }
    values.update(overrides)
    return Namespace(**values)


def _event(labels: list[str], *, base: str = "main", head: str = "bugfix/87-branch-contract") -> dict:
    return {
        "pull_request": {
            "title": "fix: enforce branch contract",
            "body": "Closes #87\n- [x] tests",
            "labels": [{"name": label} for label in labels],
            "base": {"ref": base},
            "head": {"ref": head},
        },
        "repository": {"visibility": "public"},
    }


def _install_event(monkeypatch, repo: Path, event: dict) -> None:
    path = repo / "github-event.json"
    path.write_text(json.dumps(event), encoding="utf-8")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(path))


@pytest.mark.parametrize(
    "event_labels,cli_labels,expected",
    [
        ([], _EXEMPT, Status.FAIL),
        (["wip"], _EXEMPT, Status.FAIL),
        ([_EXEMPT], None, Status.SKIP),
        ([_EXEMPT], "", Status.SKIP),
        ([_EXEMPT], "unrelated", Status.SKIP),
    ],
)
def test_github_event_labels_override_cli_even_when_empty(
    monkeypatch, tmp_path, event_labels, cli_labels, expected
):
    _write_config(tmp_path)
    _install_event(monkeypatch, tmp_path, _event(event_labels))
    context = cli.build_context(_args(tmp_path, pr_labels=cli_labels))
    assert context.pr_labels == event_labels
    assert R12BranchSource().check(context).status == expected


def test_existing_pr_with_no_label_field_is_authoritatively_unlabelled(monkeypatch, tmp_path):
    _write_config(tmp_path)
    event = _event([])
    del event["pull_request"]["labels"]
    _install_event(monkeypatch, tmp_path, event)
    context = cli.build_context(_args(tmp_path, pr_labels=_EXEMPT))
    assert context.pr_labels == []
    assert R12BranchSource().check(context).status == Status.FAIL


@pytest.mark.parametrize("event", [None, {}, {"repository": {"visibility": "public"}}])
def test_cli_labels_are_used_when_no_pr_metadata_exists(monkeypatch, tmp_path, event):
    _write_config(tmp_path)
    if event is not None:
        _install_event(monkeypatch, tmp_path, event)
    context = cli.build_context(_args(tmp_path, pr_labels=f"{_EXEMPT},wip"))
    assert context.pr_labels == [_EXEMPT, "wip"]
    assert R12BranchSource().check(context).status == Status.SKIP


@pytest.mark.parametrize("cli_labels", [None, ""])
def test_no_provider_and_no_cli_labels_produces_an_empty_list(tmp_path, cli_labels):
    _write_config(tmp_path)
    context = cli.build_context(_args(tmp_path, pr_labels=cli_labels))
    assert context.pr_labels == []
    assert R12BranchSource().check(context).status == Status.FAIL


@pytest.mark.parametrize("labels", [None, "", "wip"])
def test_gitlab_label_metadata_also_prevents_cli_exemption_injection(
    monkeypatch, tmp_path, labels
):
    _write_config(tmp_path)
    monkeypatch.setenv("CI_MERGE_REQUEST_IID", "87")
    if labels is None:
        monkeypatch.delenv("CI_MERGE_REQUEST_LABELS", raising=False)
    else:
        monkeypatch.setenv("CI_MERGE_REQUEST_LABELS", labels)
    context = cli.build_context(_args(tmp_path, pr_labels=_EXEMPT))
    assert context.provider == "gitlab"
    assert context.pr_labels == (["wip"] if labels == "wip" else [])
    # GitLab's existing not-applicable result must not become an exemption.
    assert R12BranchSource().check(context).status == Status.PASS


@pytest.mark.parametrize(
    "allow_fix,base,head,labels,expected",
    [
        (False, "main", "feature/87-branch-contract", (), Status.PASS),
        (False, "main", "fix/87-branch-contract", (), Status.FAIL),
        (True, "main", "fix/87-branch-contract", (), Status.PASS),
        (True, "fix/87-branch-contract", "wt/87-branch-contract/tests", (), Status.PASS),
        (True, "fix/87-branch-contract", "wt/another/tests", (), Status.FAIL),
        (True, "main", "bugfix/87-branch-contract", (_EXEMPT,), Status.SKIP),
    ],
)
def test_local_preflight_and_ci_build_identical_branch_rule_context(
    monkeypatch, tmp_path, allow_fix, base, head, labels, expected
):
    _write_config(tmp_path, allow_fix=allow_fix)
    event = _event(list(labels), base=base, head=head)
    _install_event(monkeypatch, tmp_path, event)
    ci_context = cli.build_context(_args(tmp_path, pr_labels=_EXEMPT))

    body_path = tmp_path / "body.md"
    body_path.write_text(event["pull_request"]["body"], encoding="utf-8")
    local_context = preflight._manual_context(
        Namespace(
            pr_title=event["pull_request"]["title"],
            pr_body_file=str(body_path),
            pr_labels=",".join(labels),
            base=base,
            head=head,
            repo_visibility="public",
        ),
        tmp_path,
    )
    captured = []

    def run_policy_with_generated_event(argv, **kwargs):
        # Read the generated event while its temporary directory still exists.
        with monkeypatch.context() as child:
            child.setenv("GITHUB_EVENT_PATH", kwargs["env"]["GITHUB_EVENT_PATH"])
            context = cli.build_context(_args(tmp_path, pr_labels=_EXEMPT))
        captured.append(context)
        result = R12BranchSource().check(context)
        return subprocess.CompletedProcess(
            argv, 1 if result.status == Status.FAIL else 0, result.message, ""
        )

    monkeypatch.setattr(preflight, "_run_command", run_policy_with_generated_event)
    assert preflight._run_policy(
        tmp_path,
        local_context,
        preflight.EngineIdentity("source", "test", tmp_path),
    ) is (expected != Status.FAIL)
    assert len(captured) == 1
    assert captured[0] == ci_context
    assert ci_context.pr_labels == list(labels)
    assert R12BranchSource().check(ci_context).status == expected
