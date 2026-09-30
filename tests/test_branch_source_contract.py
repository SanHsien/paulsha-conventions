"""R-12 opt-in branch prefixes and their independent R-08 schema contract."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from policy_check.rules.base import RuleContext, Status
from policy_check.rules.r08_policy_config_schema import R08PolicyConfigSchema
from policy_check.rules.r12_branch_source import R12BranchSource


_OMITTED = object()
_EXEMPT = "policy-exempt:branch-name"
_ENABLED = {"allowed_prefixes": ["feature", "fix"]}


def _context(
    repo: Path,
    *,
    branch_source: object = _OMITTED,
    base: str | None = "main",
    head: str | None = "feature/87-branch-contract",
    provider: str | None = "github",
    labels: tuple[str, ...] = (),
) -> RuleContext:
    config = {"policy_profile": "flat", "policy_version": "1.0.17"}
    if branch_source is not _OMITTED:
        config["branch_source"] = branch_source
    (repo / ".project-policy.yml").write_text(
        yaml.safe_dump(config), encoding="utf-8"
    )
    return RuleContext(
        repo_root=repo,
        profile="flat",
        policy_version="1.0.17",
        config=config,
        pr_base_ref=base,
        pr_head_ref=head,
        provider=provider,
        pr_labels=list(labels),
    )


@pytest.mark.parametrize(
    "branch_source",
    [_OMITTED, {"allowed_prefixes": ["feature"]}],
    ids=["omitted-default", "explicit-feature-only"],
)
@pytest.mark.parametrize(
    "head,expected",
    [
        ("feature/87-branch-contract", Status.PASS),
        ("fix/87-branch-contract", Status.FAIL),
        ("hotfix/87-branch-contract", Status.FAIL),
        ("wt/87-branch-contract/tests", Status.FAIL),
    ],
)
def test_feature_only_contract_is_backward_compatible(
    tmp_path, branch_source, head, expected
):
    result = R12BranchSource().check(
        _context(tmp_path, branch_source=branch_source, head=head)
    )
    assert result.status == expected


@pytest.mark.parametrize(
    "prefixes", [["feature", "fix"], ["fix", "feature"]]
)
@pytest.mark.parametrize("prefix", ["feature", "fix"])
@pytest.mark.parametrize("slug", ["a", "0", "87-fix", "multi-word-branch", "x--y"])
def test_explicit_opt_in_accepts_supported_heads_into_main(
    tmp_path, prefixes, prefix, slug
):
    result = R12BranchSource().check(
        _context(
            tmp_path,
            branch_source={"allowed_prefixes": prefixes},
            head=f"{prefix}/{slug}",
        )
    )
    assert result.status == Status.PASS


@pytest.mark.parametrize("prefix", ["feature", "fix"])
@pytest.mark.parametrize(
    "slug", ["", "Upper", "has_underscore", "has.dot", "-starts-with-dash", "a/b", "a b", "a\nb", "修正"]
)
def test_enabled_main_head_requires_the_exact_slug_grammar(tmp_path, prefix, slug):
    result = R12BranchSource().check(
        _context(tmp_path, branch_source=_ENABLED, head=f"{prefix}/{slug}")
    )
    assert result.status == Status.FAIL
    assert "feature/<slug>" in result.message
    assert "fix/<slug>" in result.message


@pytest.mark.parametrize(
    "head", ["bugfix/87-test", "hotfix/87-test", "Feature/87-test", "FIX/87-test", "refs/heads/fix/87-test", "fix", "feature"]
)
def test_opt_in_does_not_accept_arbitrary_or_similar_prefixes(tmp_path, head):
    assert R12BranchSource().check(
        _context(tmp_path, branch_source=_ENABLED, head=head)
    ).status == Status.FAIL


@pytest.mark.parametrize("prefix", ["feature", "fix"])
@pytest.mark.parametrize("subtask", ["a", "0", "add-tests", "r12-schema"])
def test_enabled_base_accepts_only_its_matching_worktree_slug(tmp_path, prefix, subtask):
    assert R12BranchSource().check(
        _context(
            tmp_path,
            branch_source=_ENABLED,
            base=f"{prefix}/87-branch-contract",
            head=f"wt/87-branch-contract/{subtask}",
        )
    ).status == Status.PASS


@pytest.mark.parametrize("prefix", ["feature", "fix"])
@pytest.mark.parametrize(
    "head",
    [
        "wt/another-slug/tests",
        "wt/87-branch-contract",
        "wt/87-branch-contract/",
        "wt/87-branch-contract/Upper",
        "wt/87-branch-contract/has_underscore",
        "wt/87-branch-contract/-starts-with-dash",
        "wt/87-branch-contract/tests/extra",
        "wt/87-branch-contract/a\nb",
        "feature/87-branch-contract",
        "fix/87-branch-contract",
    ],
)
def test_enabled_base_rejects_wrong_or_malformed_worktree_head(tmp_path, prefix, head):
    result = R12BranchSource().check(
        _context(
            tmp_path,
            branch_source=_ENABLED,
            base=f"{prefix}/87-branch-contract",
            head=head,
        )
    )
    assert result.status == Status.FAIL
    assert "wt/87-branch-contract/<subtask>" in result.message
    assert "branch_source.allowed_prefixes" in result.message


@pytest.mark.parametrize("prefix", ["feature", "fix"])
@pytest.mark.parametrize("slug", ["", "Upper", "has_underscore", "-bad", "a/b", "a b"])
def test_malformed_enabled_prefix_base_cannot_escape_applicability(tmp_path, prefix, slug):
    result = R12BranchSource().check(
        _context(
            tmp_path,
            branch_source=_ENABLED,
            base=f"{prefix}/{slug}",
            head="anything",
        )
    )
    assert result.status == Status.FAIL
    assert f"{prefix}/<slug>" in result.message


@pytest.mark.parametrize(
    "branch_source,base",
    [
        (_OMITTED, "feature"),
        (_OMITTED, "feature/Upper"),
        (_OMITTED, "feature/"),
        (_ENABLED, "feature"),
        (_ENABLED, "fix"),
    ],
)
def test_bare_or_malformed_enabled_base_fails_even_with_default_contract(
    tmp_path, branch_source, base
):
    result = R12BranchSource().check(
        _context(tmp_path, branch_source=branch_source, base=base, head="anything")
    )
    assert result.status == Status.FAIL
    assert "feature/<slug>" in result.message


@pytest.mark.parametrize(
    "branch_source,base",
    [
        (_OMITTED, "fix/87-branch-contract"),
        (_OMITTED, "fix/Upper"),
        ({"allowed_prefixes": ["feature"]}, "fix/87-branch-contract"),
        (_ENABLED, "release/1.0"),
        (_ENABLED, "develop"),
        (_ENABLED, "hotfix/87-branch-contract"),
        (_ENABLED, "feature-ish/87-branch-contract"),
    ],
)
def test_other_bases_preserve_existing_applicability(tmp_path, branch_source, base):
    result = R12BranchSource().check(
        _context(tmp_path, branch_source=branch_source, base=base, head="anything")
    )
    assert result.status == Status.PASS
    assert "applicability" in result.message.lower() or "scope" in result.message.lower()


def test_omitted_block_reports_default_effective_pattern(tmp_path):
    result = R12BranchSource().check(_context(tmp_path, head="fix/87-branch-contract"))
    assert result.status == Status.FAIL
    assert "feature/<slug>" in result.message
    assert "fix/<slug>" not in result.message
    assert "default" in result.message.lower()


def test_configured_block_reports_both_patterns_and_configuration_source(tmp_path):
    result = R12BranchSource().check(
        _context(tmp_path, branch_source=_ENABLED, head="bugfix/87-branch-contract")
    )
    assert result.status == Status.FAIL
    assert "feature/<slug>" in result.message
    assert "fix/<slug>" in result.message
    assert "branch_source.allowed_prefixes" in result.message


def test_configured_contract_reports_the_actual_legacy_manifest_source(tmp_path):
    context = _context(tmp_path, branch_source=_ENABLED, head="bugfix/87-test")
    (tmp_path / ".project-policy.yml").rename(tmp_path / ".paul-project.yml")
    result = R12BranchSource().check(context)
    assert result.status == Status.FAIL
    assert ".paul-project.yml:branch_source.allowed_prefixes" in result.message
    assert ".project-policy.yml:branch_source.allowed_prefixes" not in result.message
    assert R08PolicyConfigSchema().check(context).status == Status.WARN


_INVALID_BLOCKS = [
    pytest.param(None, id="null-block"),
    pytest.param({}, id="empty-block"),
    pytest.param([], id="list-block"),
    pytest.param("feature", id="string-block"),
    pytest.param(True, id="boolean-block"),
    pytest.param(1, id="numeric-block"),
    pytest.param({"unknown": ["feature"]}, id="missing-allowed-prefixes"),
    pytest.param({"allowed_prefixes": ["feature"], "unknown": True}, id="unknown-subkey"),
    pytest.param({"allowed_prefixes": ["feature"], 1: True}, id="nonstring-subkey"),
    pytest.param({"allowed_prefixes": None}, id="null-prefixes"),
    pytest.param({"allowed_prefixes": []}, id="empty-prefixes"),
    pytest.param({"allowed_prefixes": "feature"}, id="scalar-prefixes"),
    pytest.param({"allowed_prefixes": {"feature": True}}, id="mapping-prefixes"),
    pytest.param({"allowed_prefixes": ["fix"]}, id="feature-missing"),
    pytest.param({"allowed_prefixes": ["feature", "feature"]}, id="duplicate-feature"),
    pytest.param({"allowed_prefixes": ["feature", "fix", "fix"]}, id="duplicate-fix"),
    pytest.param({"allowed_prefixes": ["feature", "hotfix"]}, id="unsupported-prefix"),
    pytest.param({"allowed_prefixes": ["feature", "*"]}, id="wildcard-prefix"),
    pytest.param({"allowed_prefixes": ["feature", "fix/"]}, id="slash-prefix"),
    pytest.param({"allowed_prefixes": ["feature", "FIX"]}, id="case-sensitive-prefix"),
    pytest.param({"allowed_prefixes": ["feature", " fix"]}, id="whitespace-prefix"),
    pytest.param({"allowed_prefixes": ["feature", ""]}, id="empty-prefix"),
    pytest.param({"allowed_prefixes": ["feature", None]}, id="null-entry"),
    pytest.param({"allowed_prefixes": ["feature", True]}, id="boolean-entry"),
    pytest.param({"allowed_prefixes": ["feature", 1]}, id="numeric-entry"),
    pytest.param({"allowed_prefixes": ["feature", ["fix"]]}, id="list-entry"),
    pytest.param({"allowed_prefixes": ["feature", {"fix": True}]}, id="mapping-entry"),
]


@pytest.mark.parametrize("branch_source", _INVALID_BLOCKS)
def test_r08_rejects_every_invalid_branch_source_shape_without_a_pr(tmp_path, branch_source):
    result = R08PolicyConfigSchema().check(
        _context(tmp_path, branch_source=branch_source, base=None, head=None)
    )
    assert result.status == Status.FAIL
    assert "branch_source" in result.message


@pytest.mark.parametrize("branch_source", _INVALID_BLOCKS)
def test_active_r12_fails_closed_on_invalid_branch_source(tmp_path, branch_source):
    result = R12BranchSource().check(_context(tmp_path, branch_source=branch_source))
    assert result.status == Status.FAIL
    assert "branch_source" in result.message


@pytest.mark.parametrize(
    "branch_source",
    [_OMITTED, {"allowed_prefixes": ["feature"]}, _ENABLED, {"allowed_prefixes": ["fix", "feature"]}],
    ids=["omitted", "feature-only", "feature-and-fix", "reversed-order"],
)
def test_r08_accepts_supported_configurations(tmp_path, branch_source):
    assert R08PolicyConfigSchema().check(
        _context(tmp_path, branch_source=branch_source)
    ).status == Status.PASS


def test_r08_validates_the_manifest_even_if_context_config_is_stale(tmp_path):
    context = _context(tmp_path, branch_source=None, base=None, head=None)
    context.config = {"branch_source": _ENABLED}
    result = R08PolicyConfigSchema().check(context)
    assert result.status == Status.FAIL
    assert "branch_source" in result.message


@pytest.mark.parametrize("branch_source", [_ENABLED, None])
@pytest.mark.parametrize(
    "overrides,expected",
    [
        ({"provider": "gitlab", "base": "main", "head": "arbitrary"}, Status.PASS),
        ({"base": None, "head": None}, Status.PASS),
        ({"base": None, "head": "arbitrary"}, Status.PASS),
        ({"base": "main", "head": None}, Status.PASS),
        ({"head": "arbitrary", "labels": (_EXEMPT,)}, Status.SKIP),
    ],
)
def test_r12_retains_gitlab_missing_pr_and_exemption_semantics(
    tmp_path, branch_source, overrides, expected
):
    context = _context(tmp_path, branch_source=branch_source, **overrides)
    result = R12BranchSource().check(context)
    assert result.status == expected
    if expected == Status.SKIP:
        assert result.exempt_label == _EXEMPT
    if branch_source is None:
        # R-12 applicability/exemption must never suppress independent schema failure.
        assert R08PolicyConfigSchema().check(context).status == Status.FAIL
