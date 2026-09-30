---
type: fixed
scope: R-12
issue: 87
---
新增明確 opt-in 的 `branch_source.allowed_prefixes: [feature, fix]`，修復中央分支規則與下游修復分支契約不一致；省略設定維持 feature-only，啟用前綴的 base 強制 worktree slug 配對並拒絕非法設定與命名。
