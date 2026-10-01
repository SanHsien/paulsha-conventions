# 決策記錄

## 上游審視 baseline 初始化（2026-09-30）

- 對象：`hamanpaul/paulsha-conventions`（`main`）。
- `tools/upstream_baseline.json` 於 2026-09-30 初始化，三個水位都設在當日的上游現況：
  commit `7539d52`、PR `#89`、issue `#87`。
- 初始化時**沒有**逐項審視水位之前的 commit、PR 與 issue；它們不是「已審視後決定不採用」，而是
  「未審視」。日後要回頭評估某一項，從上游直接查，不要當作已有結論。
- 之後每週的上游檢查（`.github/workflows/upstream-check.yml`）只列出水位之後的新項目。處理完一批，
  在本檔記錄採用或略過的理由，再調高 baseline 的水位。

## 2026-10-01：同步上游 v1.0.18

- 採用上游 `v1.0.17..65d9e43`（8 個 commit、16 個檔案）：R-12 分支契約支援明確 opt-in 的修復分支
  （PR #88，issue #87）、1.0.18 發版（#89）與 release ledger 補登（#90）。
- 本 fork 壓縮過歷史，與上游沒有共同祖先，所以把這段差異當補丁套用（`git apply --3way`）；只有
  `RELEASES.md` 需要手動解（加上 1.0.18 那一列）。fork 自己的 `agent_files` 設定保留。
- 驗證：pytest 的失敗集合前後相同（64 個，皆為 Windows 環境既有失敗），上游新增的 197 個測試通過；
  CI 的 `self-test` 在把上游 tag `v1.0.18` 推到本 fork 後轉綠（ledger 測試會解析該 tag）。
- 水位：commit `65d9e43`、PR `#90`、issue `#87`。
