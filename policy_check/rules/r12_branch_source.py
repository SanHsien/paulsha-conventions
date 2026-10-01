from __future__ import annotations

import re

from policy_check import config as policy_config
from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register


@register
class R12BranchSource:
    rule_id = "R-12"
    exempt_label = "policy-exempt:branch-name"

    _branch_pattern = re.compile(r"(?P<prefix>feature|fix)/(?P<slug>[a-z0-9][a-z0-9-]*)")
    _worktree_pattern = re.compile(r"^wt/(?P<slug>[a-z0-9][a-z0-9-]*)/(?P<subtask>[a-z0-9][a-z0-9-]*)$")

    def check(self, ctx: RuleContext) -> RuleResult:
        if self.exempt_label in ctx.pr_labels:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.SKIP,
                message=f"R-12 exempted by label: {self.exempt_label}",
                exempt_label=self.exempt_label,
            )

        if ctx.provider == "gitlab":
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.PASS,
                message="GitLab provider: branch-source convention (hamanpaul-specific) not applicable.",
            )

        if not ctx.pr_base_ref or not ctx.pr_head_ref:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.PASS,
                message="Missing PR base/head ref; treat as non-PR context.",
            )

        source = (
            f"{policy_config.config_path(ctx.repo_root).name}:branch_source.allowed_prefixes"
            if "branch_source" in ctx.config
            else "built-in default (branch_source omitted)"
        )
        try:
            prefixes = policy_config.branch_source_prefixes(ctx.config)
        except policy_config.ConfigError as exc:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message=f"Invalid R-12 contract ({source}): {exc}",
            )
        allowed = " or ".join(f"{prefix}/<slug>" for prefix in prefixes)
        contract = f"Effective main sources: {allowed}; source: {source}."
        base = ctx.pr_base_ref.strip()
        head = ctx.pr_head_ref.strip()

        if base == "main":
            head_branch = self._branch_pattern.fullmatch(head)
            if head_branch and head_branch.group("prefix") in prefixes:
                return RuleResult(
                    rule_id=self.rule_id,
                    status=Status.PASS,
                    message=f"Branch naming is valid for PR into main. {contract}",
                )
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message=f"When base is main, head must be {allowed}. {contract}",
            )

        # A configured prefix also owns its base branches. Malformed names must
        # not fall through to the legacy outside-scope path.
        if base.split("/", 1)[0] in prefixes:
            base_branch = self._branch_pattern.fullmatch(base)
            if not base_branch:
                return RuleResult(
                    rule_id=self.rule_id,
                    status=Status.FAIL,
                    message=f"Base branch must be {allowed} with a valid slug. {contract}",
                )
            expected_slug = base_branch.group("slug")
            worktree_head = self._worktree_pattern.fullmatch(head)
            if not worktree_head or worktree_head.group("slug") != expected_slug:
                return RuleResult(
                    rule_id=self.rule_id,
                    status=Status.FAIL,
                    message=(
                        f"When base is {base}, "
                        f"head must be wt/{expected_slug}/<subtask>. {contract}"
                    ),
                )
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.PASS,
                message=f"Branch naming is valid for worktree PR into {base}. {contract}",
            )

        return RuleResult(
            rule_id=self.rule_id,
            status=Status.PASS,
            message=f"Base branch is outside R-12 scope; skipped by applicability. {contract}",
        )
