from __future__ import annotations

from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register

AGENT_FILES = [
    "CLAUDE.md",
    "AGENTS.md",
    "GEMINI.md",
    ".github/copilot-instructions.md",
]

DEFAULT_CANONICAL = "CLAUDE.md"


def agent_files_settings(config: dict | None) -> tuple[str, list[str]]:
    """回傳 (canonical, required)。

    `agent_files.canonical` 預設 `CLAUDE.md`；`agent_files.required` 預設全部四檔。
    兩者皆未設定時行為與上游相同。型別錯誤交由 R-08 報告，這裡退回預設值。
    """
    cfg = config.get("agent_files") if isinstance(config, dict) else None
    if not isinstance(cfg, dict):
        cfg = {}
    canonical = cfg.get("canonical")
    if not isinstance(canonical, str) or canonical not in AGENT_FILES:
        canonical = DEFAULT_CANONICAL
    required = cfg.get("required")
    if not isinstance(required, list) or not all(name in AGENT_FILES for name in required):
        required = list(AGENT_FILES)
    return canonical, list(required)


@register
class R13AgentFilesExist:
    rule_id = "R-13"
    exempt_label = "policy-exempt:agent-files"

    def check(self, ctx: RuleContext) -> RuleResult:
        if self.exempt_label in ctx.pr_labels:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.SKIP,
                message=f"R-13 exempted by label: {self.exempt_label}",
                exempt_label=self.exempt_label,
            )

        _, required = agent_files_settings(ctx.config)
        missing = [name for name in required if not (ctx.repo_root / name).is_file()]
        if missing:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message=f"missing agent convention files: {missing}",
            )

        return RuleResult(
            rule_id=self.rule_id,
            status=Status.PASS,
            message="all agent convention files present",
        )
