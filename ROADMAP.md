# 路線圖

> 本 repo 後續工作的單一真相源。做完一項，就在同一個 commit 刪掉那一列；新工作只加在這裡。
> 現況段的數字是 2026-10-29 依 `main` `d3412119ac7c` 查的快照，開工前先重查 GitHub。

## 現況
這是跨 repo 文件、版本、分支與變更完整性的 policy 檢查引擎 fork（[README.md:1](README.md)）。2026-10-29 `gh` 查詢顯示 self-test、CodeQL、Dependency freshness、Upstream check 最近結果成功、開啟安全告警為 0、無 fork release；issues 停用而未查到 issue（2026-10-29 `gh` 查詢）。journal 與 tar 邊界已修並通過 Linux CI；Windows 全套仍有基線環境失敗，且套件宣告允許的 Python 版本與安全解壓所需版本有落差（接續開發報告與深掃報告，2026-10-2x；[docs/DECISIONS.md:33](docs/DECISIONS.md)、[pyproject.toml:9](pyproject.toml)）。

## 近期：可以直接動手
| 項目 | 為什麼 | 驗收方式 | 建議執行者 | 證據 |
| --- | --- | --- | --- | --- |
| 決定 Python 最低版本與早期版本支援範圍 | 套件可安裝不代表 runtime bundle／doc-drift 解壓功能可用 | 明確選擇提高 `requires-python`，或保留舊版但清楚限制功能；在最低支援環境驗證安裝與拒絕行為一致，任何選擇都不能退回無過濾解壓 | 維護者 | [pyproject.toml:9](pyproject.toml)、[policy_check/_safe_tar.py:17](policy_check/_safe_tar.py)、[docs/DECISIONS.md:37](docs/DECISIONS.md) |

## 中期：等條件成立再做
| 項目 | 觸發條件 | 驗收方式 | 建議執行者 | 證據 |
| --- | --- | --- | --- | --- |
| 建立正式 Windows 全套支援 | 維護者要求 Windows 跑完整 policy 與 runtime 測試 | 先補齊 symlink、bash、ctags 條件並固定基線，逐類修正剩餘差異；Windows pytest、policy 與 canonical preflight 通過，Linux 不退步 | Codex | 接續開發報告（2026-10-2x）「Windows 測試修補」；[AGENTS.md:43](AGENTS.md) |
| 收斂 snapshot 驗證的 release 範圍 | 已證實無關舊 release 損壞會阻塞正常 lifecycle，且維護者要求改善 | 先用隔離 runtime root 重現；只重驗必要版本前，證明 journal 所有引用、current 與 managed repair 仍受驗證，crash recovery 與 rollback 測試通過 | Claude Opus | [docs/runtime-bundle-runbook.md:111](docs/runtime-bundle-runbook.md)、[docs/DECISIONS.md:43](docs/DECISIONS.md) |
| 改善 preflight 失敗摘要 | stderr 警告遮住 stdout 的測試失敗摘要 | 用同時輸出警告與失敗摘要的假命令重現；兩流摘要皆可見、長度仍有上限，退出碼及 gate 判定不變 | Codex | [policy_check/preflight.py:856](policy_check/preflight.py)；接續開發報告（2026-10-2x）「刻意不做／延後」 |
| 收斂上游等效安全修正 | 上游修改 tar、journal 或 VERIFIED 驗證邊界 | 比對行為與來源信任；上游修法等效才移除本地補丁，惡意 archive、symlink 標記與 journal 復原測試仍通過 | Codex | [docs/DECISIONS.md:39](docs/DECISIONS.md)；commit `9afd20d`；[tools/upstream_baseline.json:4](tools/upstream_baseline.json) |

## 刻意不做
| 不做什麼 | 理由 | 什麼情況下重新考慮 |
| --- | --- | --- |
| 為相容舊 Python 恢復未過濾 tar 解壓 | 安全取捨見 [docs/DECISIONS.md:33](docs/DECISIONS.md) | 有同等安全且可測的替代實作 |
| 自動接受 v1 raw-snapshot journal 或未知 VERIFIED 標記 | journal 與安裝信任邊界見 [docs/DECISIONS.md:43](docs/DECISIONS.md) 及 runbook | 依已驗證舊 manager 完成復原，或另立明確遷移規格 |
| 為未授權回貢或上游限定 release 流程額外發布 | fork 尚無發布需求；上游限定流程失敗是既定邊界，非產品缺陷 | 維護者在當次任務明確授權回貢，或制定 fork 發行身份 |
| 因無共同祖先改寫歷史、重審全部初始化前票據 | 已有差量套用方式；初始化前未審不等於已拒絕，見 [docs/DECISIONS.md:8](docs/DECISIONS.md) | 有具體需求命中舊項，才針對該項補審 |

## 維護方式
每週依 [tools/upstream_baseline.json](tools/upstream_baseline.json) 的 commit 水位查增量，以基準差量套用並保留安全補丁；判斷留在 [docs/DECISIONS.md](docs/DECISIONS.md)。依賴更新沿用 freshness；程式變更依 repo 分支規範、fragment、Linux self-test、policy 與 canonical preflight 驗收，Windows 證據另列，不以相同失敗集合宣稱全綠。
