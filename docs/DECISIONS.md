# 決策記錄

## 上游審視 baseline 初始化（2026-09-30）

- 對象：`hamanpaul/paulsha-conventions`（`main`）。
- `tools/upstream_baseline.json` 於 2026-09-30 初始化，三個水位都設在當日的上游現況：
  commit `7539d52`、PR `#89`、issue `#87`。
- 初始化時**沒有**逐項審視水位之前的 commit、PR 與 issue；它們不是「已審視後決定不採用」，而是
  「未審視」。日後要回頭評估某一項，從上游直接查，不要當作已有結論。
- 之後每週的上游檢查（`.github/workflows/upstream-check.yml`）只列出水位之後的新項目。處理完一批，
  在本檔記錄採用或略過的理由，再調高 baseline 的水位。
