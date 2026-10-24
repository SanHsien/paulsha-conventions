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

## 2026-10-24：同步上游 v1.0.19
- 採用上游 `65d9e43..572cd48`（8 個 commit、20 個檔案）：新增 opt-in 規則 R-27（診斷碼文件說明覆蓋，PR #91）、
  1.0.19 發版（#93）與 release ledger 補登（#94）。fork 沒有啟用 `diagnostic_codes`，行為不變。
- 做法同上次：歷史無共同祖先，把差異當補丁套用（`git apply --3way`）。上游改的 `CLAUDE.md` 在本 fork
  已由 `AGENTS.md` 取代（canonical），所以那份只手動更新版本字樣。
- 水位：commit `572cd48`、PR `#94`、issue `#92`。上游仍開著的 issue（#83、#84、#85、#92）與本 fork 的
  行為無關或尚未有解法，沒有採用。
- 本次同步沒有碰上游的 CodeQL 告警檔（`policy_check/runtime_bundle/*`、`doc_drift/symbols.py`）；
  上游 v1.0.19 也沒有修，處理另記。

## 2026-10-24：CodeQL 4 個 high 的處理
- `py/tarslip`（`runtime_bundle/builder.py`、`runtime_bundle/integrity.py`、`doc_drift/symbols.py`）：這三處都是
  「Python 3.11.4 以上用 `filter="data"`，更舊的版本退回未過濾的 `extractall`」。上游 v1.0.19 沒有修，fork 端
  直接改：新增 `policy_check/_safe_tar.py`，統一一律套用 `data` 過濾；3.11.4 以前不再退回未過濾解壓，而是
  拒絕解壓（fail closed）；doc-drift 的 symbol 分析在這些版本上會直接拋錯而不是悄悄無過濾解壓。`requires-python` 仍是 `>=3.11`，要不要提高由維護者決定。原本的成員路徑預檢（絕對路徑、`..`、重複成員、非一般檔案類型）完全保留，
  新增 `tests/test_safe_tar.py` 覆蓋路徑跳脫、符號連結跳脫、無過濾器時拒絕。
- 這三個檔案原本與上游逐位元組相同；fork 與上游自此在這三處分歧，下次同步上游時這三處需要手動合併
  （保留 `extract_all_data_filtered` 呼叫）。上游尚未修，要不要回報由維護者決定。
- `py/clear-text-storage-sensitive-data`（`runtime_bundle/manager.py:280`）：資料流從啟用日誌的 `trusted`
  記錄（SHA-256 摘要與事件）經快照還原寫回原本的啟動器／技能檔，沒有任何憑證；屬誤判，已在 GitHub 上以
  「false positive」關閉並附說明，程式碼不改。
