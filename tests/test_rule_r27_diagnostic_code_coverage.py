"""R-27 診斷碼文件覆蓋規則測試（OD-06）。

repo 以 `diagnostic_codes` 宣告抽取命令與說明文件；規則不內建任何碼。
沿用 `tests/test_rule_r25_doc_coverage.py` 的 `_init_repo`／`_write` 寫法。
"""

from __future__ import annotations

import copy
import re
import sys
from pathlib import Path

import pytest
import yaml

from policy_check import config as cfg
from policy_check.rules import families, registry
from policy_check.rules.base import RuleContext, Status

PATTERN = r'^\| `(?P<code>[^`]+)` \| (?P<meaning>[^|\n]*\S[^|\n]*) \| (?P<action>[^|\n]*\S[^|\n]*) \|$'

# 與 serialwrap `.project-policy.yml` 的 diagnostic_codes.entry_pattern 逐字相同
# （即 serialwrap tests/test_contracts_validate.py 的 `_ENTRY_PATTERN`）。
# parity fixture 必須能在兩邊逐字使用，因此文件列採五欄格式，與 serialwrap 一致。
PARITY_PATTERN = (
    r"^\| `(?P<code>[^`]+)` \| [^|\n]* \| [^|\n]* \| "
    r"(?P<meaning>[^|\n]*\S[^|\n]*) \| (?P<action>[^|\n]*\S[^|\n]*) \|$"
)

ROOT = Path(__file__).resolve().parents[1]
PARITY_DIR = Path(__file__).resolve().parent / "fixtures" / "r27_parity"
PARITY_FIXTURES = sorted(PARITY_DIR.glob("*.yaml"))


def get_rule():
    loaded = {r.rule_id: r for r in registry.load_all()}
    assert "R-27" in loaded, "R-27 is not registered"
    return loaded["R-27"]


def _repo(tmp_path: Path, codes: list[str], doc: str, extra: str = "") -> Path:
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "emit.py").write_text("print(%r)\n" % "\n".join(codes), encoding="utf-8")
    (tmp_path / "SKILL.md").write_text(doc, encoding="utf-8")
    (tmp_path / ".project-policy.yml").write_text(
        "policy_profile: flat\npolicy_version: 1.0.18\n"
        "diagnostic_codes:\n"
        "  - namespace: error_code\n"
        f"    extract: \"{sys.executable} tools/emit.py\"\n"
        "    docs: [SKILL.md]\n"
        f"    entry_pattern: '{PATTERN}'\n" + extra,
        encoding="utf-8")
    return tmp_path


def _write(repo: Path, rel: str, text: str) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _write_repo(
    tmp_path: Path,
    codes: list[str],
    files: dict[str, str],
    *,
    doc_names: list[str] | None = None,
    entry: dict | None = None,
    entries: list[dict] | None = None,
    pattern: str = PATTERN,
    extract: str | None = None,
) -> Path:
    """通用 fixture repo：可自訂 docs 清單（允許列出不存在的檔）、entry 覆寫與多項 entries。"""
    _write(tmp_path, "tools/emit.py", "print(%r)\n" % "\n".join(codes))
    for name, text in files.items():
        _write(tmp_path, name, text)
    base = {
        "namespace": "error_code",
        "extract": extract or f"{sys.executable} tools/emit.py",
        "docs": doc_names if doc_names is not None else list(files),
        "entry_pattern": pattern,
    }
    if entries is None:
        entries = [{**base, **(entry or {})}]
    data = {"policy_profile": "flat", "policy_version": "1.0.18", "diagnostic_codes": entries}
    (tmp_path / ".project-policy.yml").write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return tmp_path


def _ctx(repo: Path) -> RuleContext:
    return RuleContext(repo_root=repo, profile="flat", policy_version="1.0.18", config=cfg.load(repo))


def _section(text: str, heading: str) -> str:
    """回傳自 heading 起至下一個 `### ` 或 `## ` 標題（不含）之間的內文。"""
    lines = text.splitlines()
    start = lines.index(heading)
    body: list[str] = []
    for line in lines[start + 1:]:
        if line.startswith("### ") or line.startswith("## "):
            break
        body.append(line)
    return "\n".join(body)


def _missing_codes(detail: str) -> set[str]:
    pat = re.compile(r"^[^:\n]+: (?P<code>\S+) missing in ")
    return {m.group("code") for line in detail.splitlines() if (m := pat.match(line))}


def test_not_applicable_without_config(tmp_path):
    (tmp_path / ".project-policy.yml").write_text("policy_profile: flat\npolicy_version: 1.0.18\n", encoding="utf-8")
    assert get_rule().check(_ctx(tmp_path)).status == Status.PASS


def test_all_documented_passes(tmp_path):
    repo = _repo(tmp_path, ["A_ONE", "B_TWO"], "| `A_ONE` | 意義 | 處置 |\n| `B_TWO` | 意義 | 處置 |\n")
    assert get_rule().check(_ctx(repo)).status == Status.PASS


def test_missing_code_fails_and_names_it(tmp_path):
    repo = _repo(tmp_path, ["A_ONE", "B_TWO"], "| `A_ONE` | 意義 | 處置 |\n")
    result = get_rule().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "B_TWO" in result.detail


def test_rule_has_no_builtin_code_list():
    import ast

    import policy_check.rules.r27_diagnostic_code_coverage as mod

    tree = ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))
    docstrings = {id(n.body[0].value) for n in ast.walk(tree)
                  if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body
                  and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
    offenders = [n.value for n in ast.walk(tree)
                 if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings
                 and re.fullmatch(r"[A-Z][A-Z0-9]*_[A-Z0-9_]+", n.value)]
    assert offenders == []


def test_empty_action_counts_as_missing(tmp_path):
    repo = _repo(tmp_path, ["A_ONE", "B_TWO"], "| `A_ONE` | 意義 | 處置 |\n| `B_TWO` | 意義 |  |\n")
    result = get_rule().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "B_TWO" in result.detail


def test_require_in_all_needs_every_doc(tmp_path):
    repo = _write_repo(
        tmp_path,
        ["A_ONE", "B_TWO"],
        {
            "SKILL.md": "| `A_ONE` | 來源 | 行號 | 意義 A | 處置 A |\n| `B_TWO` | 來源 | 行號 | 意義 B | 處置 B |\n",
            "SKILL_WINDOWS.md": "| `A_ONE` | 來源 | 行號 | 意義 A | 處置 A |\n",
        },
        entry={"require_in": "all", "entry_pattern": PARITY_PATTERN},
    )
    result = get_rule().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "B_TWO" in result.detail


def test_require_in_any_accepts_one_doc(tmp_path):
    repo = _write_repo(
        tmp_path,
        ["A_ONE", "B_TWO"],
        {
            "SKILL.md": "| `A_ONE` | 來源 | 行號 | 意義 A | 處置 A |\n| `B_TWO` | 來源 | 行號 | 意義 B | 處置 B |\n",
            "SKILL_WINDOWS.md": "| `A_ONE` | 來源 | 行號 | 意義 A | 處置 A |\n",
        },
        entry={"require_in": "any", "entry_pattern": PARITY_PATTERN},
    )
    assert get_rule().check(_ctx(repo)).status == Status.PASS


def test_extract_nonzero_exit_fails(tmp_path):
    repo = _write_repo(
        tmp_path,
        ["A_ONE"],
        {"SKILL.md": "| `A_ONE` | 意義 | 處置 |\n"},
        extract=f'{sys.executable} -c "import sys; sys.exit(3)"',
    )
    result = get_rule().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "3" in result.detail


def test_extract_null_byte_fails(tmp_path):
    repo = _write_repo(
        tmp_path,
        ["A_ONE"],
        {"SKILL.md": "| `A_ONE` | 意義 | 處置 |\n"},
        extract="echo \x00 invalid",
    )
    result = get_rule().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "extraction command failed to run" in result.detail


def test_missing_doc_fails(tmp_path):
    repo = _write_repo(tmp_path, ["A_ONE"], {}, doc_names=["NOPE.md"])
    result = get_rule().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "document does not exist" in result.detail


def test_unreadable_or_invalid_utf8_doc_fails(tmp_path):
    repo = _write_repo(tmp_path, ["A_ONE"], {"SKILL.md": "placeholder"})
    (repo / "SKILL.md").write_bytes(b"| `A_ONE` | \xff | \xfe |\n")
    result = get_rule().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "document is not readable" in result.detail
    assert result.message == "document file missing or unreadable."


def test_pattern_without_named_groups_fails(tmp_path):
    repo = _write_repo(tmp_path, [], {"SKILL.md": ""}, pattern="^x$")
    result = get_rule().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert result.message == "diagnostic_codes is misconfigured."
    assert "entry_pattern must define named groups" in result.detail


def test_duplicate_namespace_fails(tmp_path):
    base = {
        "namespace": "error_code",
        "extract": f"{sys.executable} tools/emit.py",
        "docs": ["SKILL.md"],
        "entry_pattern": PATTERN,
    }
    repo = _write_repo(
        tmp_path,
        ["A_ONE"],
        {"SKILL.md": "| `A_ONE` | 意義 | 處置 |\n"},
        entries=[copy.deepcopy(base), copy.deepcopy(base)],
    )
    assert get_rule().check(_ctx(repo)).status == Status.FAIL


def test_absolute_doc_path_rejected(tmp_path):
    repo = _write_repo(tmp_path, [], {}, doc_names=["/etc/passwd"])
    result = get_rule().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert result.message == "diagnostic_codes is misconfigured."
    assert "must be repo-relative" in result.detail


def test_doc_path_with_parent_or_backslash_rejected(tmp_path):
    repo = _write_repo(tmp_path, [], {}, doc_names=["../outside.md"])
    result = get_rule().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert result.message == "diagnostic_codes is misconfigured."
    assert "must be repo-relative and not contain '..'" in result.detail

    repo2 = _write_repo(tmp_path / "win", [], {}, doc_names=[r"nested\doc.md"])
    result2 = get_rule().check(_ctx(repo2))
    assert result2.status == Status.FAIL
    assert "must be repo-relative and not contain '..'" in result2.detail


@pytest.mark.parametrize("invalid_req", [["all"], {"a": 1}, 1, None, "ALL"])
def test_require_in_invalid_type_or_value_fails(tmp_path, invalid_req):
    repo = _write_repo(
        tmp_path,
        [],
        {"SKILL.md": ""},
        entry={"require_in": invalid_req},
    )
    result = get_rule().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert result.message == "diagnostic_codes is misconfigured."
    assert "require_in must be 'all' or 'any'" in result.detail


@pytest.mark.parametrize("invalid_to", [0, 301, True, "30", 1.5, None])
def test_timeout_seconds_validation(tmp_path, invalid_to):
    repo = _write_repo(
        tmp_path,
        [],
        {"SKILL.md": ""},
        entry={"timeout_seconds": invalid_to},
    )
    result = get_rule().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert result.message == "diagnostic_codes is misconfigured."
    assert "timeout_seconds must be an integer between 1 and 300" in result.detail


def test_empty_diagnostic_codes_list_fails(tmp_path):
    (tmp_path / ".project-policy.yml").write_text(
        "policy_profile: flat\npolicy_version: 1.0.18\ndiagnostic_codes: []\n",
        encoding="utf-8",
    )
    result = get_rule().check(_ctx(tmp_path))
    assert result.status == Status.FAIL
    assert "diagnostic_codes must not be empty if declared." in result.detail


def test_code_with_whitespace_fails(tmp_path):
    repo = _write_repo(
        tmp_path,
        ["A ONE"],
        {"SKILL.md": "| `A ONE` | 意義 | 處置 |\n"},
    )
    result = get_rule().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "diagnostic code contains whitespace" in result.detail


def test_duplicate_emitted_codes_counted_once(tmp_path):
    repo = _write_repo(
        tmp_path,
        ["A_ONE", "A_ONE"],
        {"SKILL.md": "| `A_ONE` | 意義 | 處置 |\n"},
    )
    result = get_rule().check(_ctx(repo))
    assert result.status == Status.PASS
    assert result.message.startswith("1 code(s)")


def test_empty_action_with_lenient_pattern_fails(tmp_path):
    lenient_pattern = r'^\| `(?P<code>[^`]+)` \| (?P<meaning>[^|\n]*) \| (?P<action>[^|\n]*) \|$'
    repo = _write_repo(
        tmp_path,
        ["A_ONE"],
        {"SKILL.md": "| `A_ONE` | 意義 A |    |\n"},
        entry={"entry_pattern": lenient_pattern},
    )
    result = get_rule().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "A_ONE missing in SKILL.md" in result.detail


def test_multiple_namespaces_pass_message(tmp_path):
    _write(tmp_path, "tools/emit1.py", "print('A_ONE')\n")
    _write(tmp_path, "tools/emit2.py", "print('B_TWO')\n")
    _write(tmp_path, "SKILL1.md", "| `A_ONE` | 意義 1 | 處置 1 |\n")
    _write(tmp_path, "SKILL2.md", "| `B_TWO` | 意義 2 | 處置 2 |\n")
    data = {
        "policy_profile": "flat",
        "policy_version": "1.0.18",
        "diagnostic_codes": [
            {
                "namespace": "ns1",
                "extract": f"{sys.executable} tools/emit1.py",
                "docs": ["SKILL1.md"],
                "entry_pattern": PATTERN,
            },
            {
                "namespace": "ns2",
                "extract": f"{sys.executable} tools/emit2.py",
                "docs": ["SKILL2.md"],
                "entry_pattern": PATTERN,
            },
        ],
    }
    (tmp_path / ".project-policy.yml").write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    result = get_rule().check(_ctx(tmp_path))
    assert result.status == Status.PASS
    assert result.message == "2 code(s) across 2 namespace(s) documented."


def test_missing_detail_is_sorted(tmp_path):
    repo = _write_repo(
        tmp_path,
        ["Z_CODE", "A_CODE", "M_CODE"],
        {"SKILL.md": "# empty\n"},
    )
    result = get_rule().check(_ctx(repo))
    assert result.status == Status.FAIL
    lines = result.detail.splitlines()
    assert lines == sorted(lines)


def test_comment_and_blank_lines_ignored(tmp_path):
    repo = _write_repo(
        tmp_path,
        ["# x", "", "A_ONE"],
        {"SKILL.md": "| `A_ONE` | 來源 | 行號 | 意義 A | 處置 A |\n"},
        pattern=PARITY_PATTERN,
    )
    result = get_rule().check(_ctx(repo))
    assert result.status == Status.PASS
    assert "1 code(s)" in result.message


def test_detail_truncated_after_50(tmp_path):
    codes = [f"E_{i:02d}_CODE" for i in range(60)]
    repo = _write_repo(tmp_path, codes, {"SKILL.md": "# 無任何碼說明\n"})
    result = get_rule().check(_ctx(repo))
    assert result.status == Status.FAIL
    lines = result.detail.splitlines()
    assert len(lines) == 51
    assert lines[-1] == "... and 10 more"
    assert all("missing in" in line for line in lines[:-1])
    assert lines[0].startswith("error_code: E_00_CODE ")


def test_family_registration():
    assert families.family_of("R-27") == "DOC-ALIGN"


def test_readme_both_rule_tables_list_r27():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    headings = ["### Rules (R-01 ~ R-27)", "### 規則總覽（R-01 ~ R-27）"]
    for heading in headings:
        assert heading in readme, f"README 缺少標題：{heading}"
        section = _section(readme, heading)
        assert any(line.startswith("| R-27 |") for line in section.splitlines()), (
            f"{heading} 底下的表格缺少 R-27 列"
        )


def test_parity_fixtures_present():
    """守門測試：確保 parity fixture 存在且至少有 7 個，防止空集無聲 SKIP。"""
    assert len(PARITY_FIXTURES) >= 7
    expected_stems = {
        "01_all_documented",
        "02_one_missing",
        "03_empty_action",
        "04_require_in_all_two_docs",
        "05_require_in_any_one_doc",
        "06_comments_and_blank_lines",
        "07_require_in_any_both_missing",
        "08_padded_code_cell",
    }
    assert expected_stems.issubset({p.stem for p in PARITY_FIXTURES})


@pytest.mark.parametrize("fixture", PARITY_FIXTURES, ids=lambda p: p.stem)
def test_parity_fixtures(tmp_path, fixture):
    spec = yaml.safe_load(fixture.read_text(encoding="utf-8"))
    expected = spec["expected"]
    repo = _write_repo(
        tmp_path,
        spec["codes"],
        spec["docs"],
        entry={"require_in": spec.get("require_in", "all")},
        pattern=PARITY_PATTERN,
    )
    result = get_rule().check(_ctx(repo))
    assert result.status.name == expected["status"]
    assert _missing_codes(result.detail) == set(expected["missing"])
