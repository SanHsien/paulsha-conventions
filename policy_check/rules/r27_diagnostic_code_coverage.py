"""R-27 — diagnostic code doc coverage（OD-06，opt-in）。

repo 以 `diagnostic_codes` 宣告抽取命令與說明文件；規則不內建任何碼。
"""
from __future__ import annotations

import re
import subprocess
from pathlib import PurePosixPath

from policy_check.rules._marker_sync import run_command
from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register

_MAX_LISTED = 50
_REQUIRED_GROUPS = {"code", "meaning", "action"}


@register
class R27DiagnosticCodeCoverage:
    rule_id = "R-27"
    exempt_label = None

    def check(self, ctx: RuleContext) -> RuleResult:
        entries = (ctx.config or {}).get("diagnostic_codes")
        if entries is None:
            return RuleResult(self.rule_id, Status.PASS, "No diagnostic_codes declared (not applicable).")
        problems = self._validate(entries)
        if problems:
            return RuleResult(self.rule_id, Status.FAIL, "diagnostic_codes is misconfigured.", detail="\n".join(problems))

        missing: list[str] = []
        total = 0
        for entry in entries:
            codes, err = self._extract(entry, ctx)
            if err:
                return RuleResult(self.rule_id, Status.FAIL, "diagnostic code extraction failed.", detail=err)
            total += len(codes)
            doc_err, entry_missing = self._missing(entry, codes, ctx)
            if doc_err:
                return RuleResult(self.rule_id, Status.FAIL, "document file missing or unreadable.", detail=doc_err)
            missing.extend(entry_missing)

        if missing:
            missing.sort()
            listed = missing[:_MAX_LISTED]
            if len(missing) > _MAX_LISTED:
                listed.append(f"... and {len(missing) - _MAX_LISTED} more")
            return RuleResult(
                self.rule_id,
                Status.FAIL,
                "emitted diagnostic codes lack documented meaning/action.",
                detail="\n".join(listed),
            )
        return RuleResult(
            self.rule_id,
            Status.PASS,
            f"{total} code(s) across {len(entries)} namespace(s) documented.",
        )

    def _validate(self, entries: object) -> list[str]:
        problems: list[str] = []
        if not isinstance(entries, list):
            return ["diagnostic_codes must be a list of mappings."]
        if not entries:
            return ["diagnostic_codes must not be empty if declared."]
        seen_namespaces: set[str] = set()
        for idx, entry in enumerate(entries, start=1):
            if not isinstance(entry, dict):
                problems.append(f"entry[{idx}] is not a mapping")
                continue

            ns = entry.get("namespace")
            if not isinstance(ns, str) or not ns.strip():
                problems.append(f"entry[{idx}]: namespace must be a non-empty string")
            elif ns in seen_namespaces:
                problems.append(f"entry[{idx}]: duplicate namespace {ns!r}")
            else:
                seen_namespaces.add(ns)

            extract = entry.get("extract")
            if not isinstance(extract, str) or not extract.strip():
                problems.append(f"entry[{idx}]: extract must be a non-empty string command")

            docs = entry.get("docs")
            if not isinstance(docs, list) or not docs or not all(isinstance(d, str) and d.strip() for d in docs):
                problems.append(f"entry[{idx}]: docs must be a non-empty list of string paths")
            else:
                for d in docs:
                    posix_path = PurePosixPath(d)
                    if posix_path.is_absolute() or ".." in posix_path.parts or "\\" in d:
                        problems.append(f"entry[{idx}]: doc path {d!r} must be repo-relative and not contain '..'")

            pattern_str = entry.get("entry_pattern")
            if not isinstance(pattern_str, str) or not pattern_str.strip():
                problems.append(f"entry[{idx}]: entry_pattern must be a non-empty regex string")
            else:
                try:
                    compiled = re.compile(pattern_str)
                    if not _REQUIRED_GROUPS.issubset(compiled.groupindex.keys()):
                        problems.append(
                            f"entry[{idx}]: entry_pattern must define named groups 'code', 'meaning', and 'action'"
                        )
                except re.error as exc:
                    problems.append(f"entry[{idx}]: entry_pattern regex compilation error: {exc}")

            if "require_in" in entry:
                req = entry.get("require_in")
                if not isinstance(req, str) or req not in ("all", "any"):
                    problems.append(f"entry[{idx}]: require_in must be 'all' or 'any'")

            if "timeout_seconds" in entry:
                timeout = entry.get("timeout_seconds")
                if not isinstance(timeout, int) or isinstance(timeout, bool) or not (1 <= timeout <= 300):
                    problems.append(f"entry[{idx}]: timeout_seconds must be an integer between 1 and 300")

        return problems

    def _extract(self, entry: dict, ctx: RuleContext) -> tuple[list[str], str]:
        cmd = entry["extract"]
        ns = entry["namespace"]
        timeout = entry.get("timeout_seconds", 30)
        try:
            res = run_command(cmd, ctx.repo_root, timeout=timeout)
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            return [], f"namespace '{ns}': extraction command failed to run: {exc}"

        if res.returncode != 0:
            err_msg = res.stderr.strip() or res.stdout.strip()
            return [], f"namespace '{ns}': extraction command exited with code {res.returncode}: {err_msg}"

        codes: list[str] = []
        for line in res.stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if any(ch.isspace() for ch in line):
                return [], f"namespace '{ns}': diagnostic code contains whitespace: {line!r}"
            if line not in codes:
                codes.append(line)
        return codes, ""

    def _missing(self, entry: dict, codes: list[str], ctx: RuleContext) -> tuple[str, list[str]]:
        ns = entry["namespace"]
        docs = entry["docs"]
        pattern = re.compile(entry["entry_pattern"], re.MULTILINE)
        require_in = entry.get("require_in", "all")

        doc_codes: dict[str, set[str]] = {}
        for doc_rel in docs:
            doc_path = ctx.repo_root / doc_rel
            if not doc_path.is_file():
                return f"namespace '{ns}': document does not exist: {doc_rel}", []
            try:
                text = doc_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                return f"namespace '{ns}': document is not readable: {doc_rel}: {exc}", []
            covered: set[str] = set()
            for match in pattern.finditer(text):
                gd = match.groupdict()
                code = gd.get("code") or ""
                meaning = (gd.get("meaning") or "").strip()
                action = (gd.get("action") or "").strip()
                if meaning and action and code:
                    covered.add(code)
            doc_codes[doc_rel] = covered

        missing: list[str] = []
        for code in codes:
            missing_in_docs = [doc_rel for doc_rel in docs if code not in doc_codes[doc_rel]]
            if require_in == "all":
                for doc_rel in missing_in_docs:
                    missing.append(f"{ns}: {code} missing in {doc_rel}")
            else:
                if len(missing_in_docs) == len(docs):
                    for doc_rel in docs:
                        missing.append(f"{ns}: {code} missing in {doc_rel}")

        return "", missing
