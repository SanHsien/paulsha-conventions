# 路線圖

> 本 repo 後續工作的單一真相源。做完一項，就在同一個 commit 刪掉那一列；新工作只加在這裡。
> 現況段的數字是 2026-11-08 快照（依 main `323dc49`），開工前先重查 GitHub。

## 現況
這是跨 repo 文件、版本、分支與變更完整性的 policy 檢查引擎 fork（[README.md:1](README.md)）。2026-11-08 `gh` 實查顯示開啟安全告警（Dependabot 與 Code Scanning）皆為 0 筆、無 fork release；issues 停用而未查到 issue。Python 支援政策已於 2026-11-08 裁決維持 `>=3.11` 相容宣告，並明確限制 R-22 doc-drift 符號提取與 runtime bundle 嚴格需要 Python >= 3.11.4 並 fail-closed，其餘靜態檢查規則推斷支援 3.11.0+（[docs/DECISIONS.md](docs/DECISIONS.md)）。journal 與 tar 邊界已修並通過 Linux CI；Windows 全套仍有基線環境缺漏失敗（缺少 bash、symlink 等，實跑 85 failed 皆為 Windows baseline 失敗，892 passed，tests/test_safe_tar.py 5 通過）。

## 近期：可以直接動手
目前無直接可動手項目（「決定 Python 最低版本與早期版本支援範圍」已於 2026-11-08 裁決維持 `>=3.11` 並界定功能分級，見 [docs/DECISIONS.md](docs/DECISIONS.md)）。

## 中期：等條件成立再做
| 項目 | 觸發條件 | 驗收方式 | 建議執行者 | 證據 |
| --- | --- | --- | --- | --- |
| 在最低支援環境驗證 Python 3.11 早期版本安裝與拒絕行為 | 取得 Python 3.11.0–3.11.3 環境或把它加入 CI 矩陣 | 在最低支援環境驗證安裝與拒絕行為一致，任何選擇都不能退回無過濾解壓 | 維護者 | [pyproject.toml:9](pyproject.toml)、[policy_check/_safe_tar.py:17](policy_check/_safe_tar.py)、[docs/DECISIONS.md](docs/DECISIONS.md) |
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
