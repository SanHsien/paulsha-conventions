from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from policy_check.runtime_bundle import manager


def _release(root: Path, version: str) -> Path:
    release = root / "releases" / version
    runtime = release / "artifact" / "runtime" / "runtime_manager.py"
    runtime.parent.mkdir(parents=True)
    runtime.write_text(f"# test runtime manager {version}\n", encoding="utf-8")
    (release / "artifact" / "skills" / "preflight-ci").mkdir(parents=True)
    (release / "artifact" / "manifest.json").write_text(
        json.dumps(
            {"runtime": {"path": "runtime/runtime_manager.py", "sha256": manager._sha256(runtime)}},
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return release


def _canonical_state(version: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "current": version,
        "previous": None,
        "installed": [version],
    }


def test_canonical_snapshot_records_metadata_not_raw_file_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "runtime"
    old = _release(root, "1.0.13")
    skill = tmp_path / "skills" / "preflight-ci"
    manager._write_json_atomic(root / "state.json", _canonical_state(old.name))
    manager._install_launcher(root, old)
    monkeypatch.setattr(manager, "_verified_release", lambda *_args: old)
    monkeypatch.setattr(
        manager,
        "_snapshot_current_release",
        lambda *_args: old,
        raising=False,
    )

    snapshot = manager._activation_snapshot(root, skill)

    assert "content" not in json.dumps(snapshot, sort_keys=True)


def test_noncanonical_state_is_rejected_before_journal_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "runtime"
    root.mkdir()
    (root / "state.json").write_text(
        json.dumps({**_canonical_state("1.0.13"), "secret": "sentinel"}),
        encoding="utf-8",
    )
    skill = tmp_path / "skills" / "preflight-ci"

    def journal_write(*_args, **_kwargs):
        raise AssertionError("a rejected snapshot must not create a journal")

    monkeypatch.setattr(manager, "_append_activation_event", journal_write)
    with pytest.raises(manager.RuntimeBundleError, match="activation state snapshot"):
        manager._switch_active_release(root, skill, root / "new-release", {})
    assert not (root / "activation.journal").exists()


@pytest.mark.parametrize("schema_version", (True, 1.0))
def test_non_integer_schema_version_is_rejected_before_journal_write(
    tmp_path: Path,
    schema_version: object,
) -> None:
    root = tmp_path / "runtime"
    root.mkdir()
    state = _canonical_state("1.0.13")
    state["schema_version"] = schema_version
    (root / "state.json").write_text(json.dumps(state), encoding="utf-8")
    with pytest.raises(manager.RuntimeBundleError, match="activation state snapshot"):
        manager._snapshot_activation_state(root / "state.json")

    assert not (root / "activation.journal").exists()


def test_noncanonical_launcher_is_rejected_before_journal_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "runtime"
    old = _release(root, "1.0.13")
    manager._write_json_atomic(root / "state.json", _canonical_state(old.name))
    manager._install_launcher(root, old)
    launcher = root / "bin" / "policy-preflight"
    launcher.write_text("#!/bin/sh\necho sentinel\n", encoding="utf-8")
    monkeypatch.setattr(manager, "_verified_release", lambda *_args: old)
    monkeypatch.setattr(
        manager,
        "_snapshot_current_release",
        lambda *_args: old,
        raising=False,
    )
    skill = tmp_path / "skills" / "preflight-ci"

    def journal_write(*_args, **_kwargs):
        raise AssertionError("a rejected snapshot must not create a journal")

    monkeypatch.setattr(manager, "_append_activation_event", journal_write)
    with pytest.raises(manager.RuntimeBundleError, match="managed launcher"):
        manager._switch_active_release(root, skill, root / "new-release", {})
    assert not (root / "activation.journal").exists()


def test_existing_skill_link_must_match_current_release(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "runtime"
    old = _release(root, "1.0.13")
    skill = tmp_path / "skills" / "preflight-ci"
    manager._write_json_atomic(root / "state.json", _canonical_state(old.name))
    manager._install_launcher(root, old)
    original_is_symlink = Path.is_symlink

    def is_symlink(path: Path) -> bool:
        return path == skill or original_is_symlink(path)

    monkeypatch.setattr(Path, "is_symlink", is_symlink)
    monkeypatch.setattr(manager, "_verified_release", lambda *_args: old)
    monkeypatch.setattr(manager, "_snapshot_current_release", lambda *_args: old)
    monkeypatch.setattr(manager, "_symlink_points_to", lambda *_args: False)

    with pytest.raises(manager.RuntimeBundleError, match="managed skill link"):
        manager._activation_snapshot(root, skill)


def test_legacy_raw_snapshot_journal_is_rejected_fail_closed(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    root.mkdir()
    unsigned = {
        "schema_version": 1,
        "sequence": 1,
        "previous_digest": "0" * 64,
        "event": "begin",
        "payload": {"snapshots": {"state": {"content": "c2VudGluZWw="}}},
    }
    digest = hashlib.sha256(manager._canonical_json(unsigned)).hexdigest()
    record = {**unsigned, "digest": digest}
    (root / "activation.journal").write_bytes(manager._canonical_json(record) + b"\n")
    (root / "activation.journal.anchor").write_text(digest + "\n", encoding="ascii")

    with pytest.raises(manager.RuntimeBundleError, match="schema is unsupported"):
        manager._read_activation_records(root)


def test_metadata_snapshot_rebuilds_the_old_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "runtime"
    old = _release(root, "1.0.13")
    state = _canonical_state(old.name)
    skill = tmp_path / "skills" / "preflight-ci"
    links: list[tuple[Path, Path]] = []
    restored_links: list[tuple[Path, str | None]] = []
    launchers: list[tuple[Path, Path]] = []

    monkeypatch.setattr(manager, "_verified_release", lambda *_args: old)
    monkeypatch.setattr(
        manager,
        "_atomic_symlink",
        lambda target, link: links.append((target, link)),
    )
    monkeypatch.setattr(
        manager,
        "_restore_symlink",
        lambda path, target: restored_links.append((path, target)),
    )
    monkeypatch.setattr(
        manager,
        "_install_launcher",
        lambda root_path, release, *, only=None: launchers.append(
            (root_path, release, only)
        ),
    )

    manager._restore_activation_snapshot(
        root,
        skill,
        {
            "state": state,
            "current_version": old.name,
            "launchers": {"preflight": old.name, "lifecycle": old.name},
            "skill_version": old.name,
        },
    )

    assert json.loads((root / "state.json").read_text(encoding="utf-8")) == state
    assert launchers == [(root, old, "preflight"), (root, old, "lifecycle")]
    assert restored_links == [
        (skill, str(old / "artifact" / "skills" / "preflight-ci"))
    ]
    assert links == [(old, root / "current")]


@pytest.mark.parametrize("stray", ("launcher", "skill"))
def test_first_install_rejects_stray_managed_path_before_journal_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stray: str,
) -> None:
    root = tmp_path / "runtime"
    root.mkdir()
    release = _release(root, "1.0.13")
    skill = tmp_path / "skills" / "preflight-ci"
    path = root / "bin" / "policy-preflight" if stray == "launcher" else skill
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("do not remove\n", encoding="utf-8")

    def journal_write(*_args, **_kwargs):
        raise AssertionError("a rejected first install must not create a journal")

    monkeypatch.setattr(manager, "_append_activation_event", journal_write)
    with pytest.raises(manager.RuntimeBundleError, match="first-install snapshot"):
        manager._switch_active_release(root, skill, release, _canonical_state(release.name))

    assert path.read_text(encoding="utf-8") == "do not remove\n"
    assert not (root / "activation.journal").exists()


def test_first_install_rejects_dangling_managed_skill_link_before_journal_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "runtime"
    root.mkdir()
    release = _release(root, "1.0.13")
    skill = tmp_path / "skills" / "preflight-ci"
    original_is_symlink = Path.is_symlink

    def is_symlink(path: Path) -> bool:
        return path == skill or original_is_symlink(path)

    def journal_write(*_args, **_kwargs):
        raise AssertionError("a rejected first install must not create a journal")

    monkeypatch.setattr(Path, "is_symlink", is_symlink)
    monkeypatch.setattr(manager, "_append_activation_event", journal_write)
    with pytest.raises(manager.RuntimeBundleError, match="first-install snapshot"):
        manager._switch_active_release(root, skill, release, _canonical_state(release.name))

    assert not (root / "activation.journal").exists()


def test_failed_switch_restores_missing_launcher_and_skill_link(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "runtime"
    old = _release(root, "1.0.13")
    new = _release(root, "1.0.14")
    skill = tmp_path / "skills" / "preflight-ci"
    state = _canonical_state(old.name)
    manager._write_json_atomic(root / "state.json", state)
    manager._install_launcher(root, old, only="preflight")
    successful_links: list[Path] = []
    skill_attempts = 0

    def link(target: Path, destination: Path) -> None:
        nonlocal skill_attempts
        if destination == skill:
            skill_attempts += 1
            if skill_attempts == 1:
                raise OSError("simulated skill-link interruption")
        successful_links.append(destination)

    monkeypatch.setattr(manager, "_verified_release", lambda *_args: old)
    monkeypatch.setattr(manager, "_snapshot_current_release", lambda *_args: old)
    monkeypatch.setattr(manager, "_atomic_symlink", link)

    with pytest.raises(OSError, match="simulated skill-link interruption"):
        manager._switch_active_release(
            root,
            skill,
            new,
            {
                "schema_version": 1,
                "current": new.name,
                "previous": old.name,
                "installed": [old.name, new.name],
            },
        )

    assert (root / "bin" / "policy-preflight").read_bytes() == manager._launcher_contents(
        root, old
    )["preflight"][1].encode("utf-8")
    assert not (root / "bin" / "policy-runtime-bundle").exists()
    assert skill not in successful_links


def test_activate_without_state_creates_canonical_registry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "runtime"
    root.mkdir()
    release = _release(root, "1.0.13")
    skill = tmp_path / "skills" / "preflight-ci"
    captured: list[dict[str, object]] = []

    monkeypatch.setattr(manager, "recover", lambda *_args: False)
    monkeypatch.setattr(manager, "_verified_release", lambda *_args: release)
    monkeypatch.setattr(manager, "_ensure_skill_target", lambda *_args: None)
    monkeypatch.setattr(
        manager,
        "_switch_active_release",
        lambda _root, _skill, _release, state: captured.append(state),
    )

    manager.activate(root, skill, release.name)

    assert captured == [_canonical_state(release.name)]


@pytest.mark.parametrize("current_present", (True, False))
def test_snapshot_preserves_independent_verified_managed_resource_versions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, current_present: bool
) -> None:
    root = tmp_path / "runtime"
    old = _release(root, "1.0.13")
    new = _release(root, "1.0.14")
    skill = tmp_path / "skills" / "preflight-ci"
    state = {**_canonical_state(new.name), "previous": old.name, "installed": [old.name, new.name]}
    manager._write_json_atomic(root / "state.json", state)
    manager._install_launcher(root, new)
    monkeypatch.setattr(manager, "_verified_release", lambda _root, version: {old.name: old, new.name: new}[version])
    monkeypatch.setattr(manager, "_snapshot_current_release", lambda _root: new if current_present else None)
    monkeypatch.setattr(
        manager,
        "_symlink_points_to",
        lambda link, target: link == skill and target == old / "artifact" / "skills" / "preflight-ci",
    )
    original_is_symlink = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda path: path == skill or original_is_symlink(path))

    snapshot = manager._activation_snapshot(root, skill)

    assert snapshot["current_version"] == (new.name if current_present else None)
    assert snapshot["skill_version"] == old.name
    assert snapshot["launchers"] == {"preflight": new.name, "lifecycle": new.name}
