# Fork 說明

本 repo 是 [hamanpaul/paulsha-conventions](https://github.com/hamanpaul/paulsha-conventions) 的維護 fork。上游由 `hamanpaul` 持有並維護，policy 引擎的設計與原始程式歸上游作者。授權狀態見 [NOTICE.md](NOTICE.md)。

## 來源

| 項目 | 內容 |
| --- | --- |
| 上游 | `hamanpaul/paulsha-conventions`，公開 repo，預設分支 `main` |
| 上游授權 | 未宣告（`gh api repos/hamanpaul/paulsha-conventions/license` 回 404，根目錄沒有 `LICENSE` 檔）；細節見 [NOTICE.md](NOTICE.md) |
| 目前同步點 | commit `572cd48abaea38e176eeed2464abf85e5925c6f9`（`tools/upstream_baseline.json` 的 `reviewed_through`，審查日 2026-11-02），版本 `1.0.19`，與上游目前 `main` 同版 |
| 歷史 | 與上游沒有共同祖先（`docs/DECISIONS.md` 2026-10-24 條），同步時把差異當補丁套用 |

## 與上游的差異

以 2026-11-08 對上游 `main` 的檔案清單與 blob SHA 比對。

### 只有本 fork 有的檔案

| 檔案 | 用途 |
| --- | --- |
| `ROADMAP.md` | 本 fork 的維護路線圖，單一真相源 |
| `.cursor/rules/no-upstream-pr.mdc` | PR、push、release 一律指向 `SanHsien/paulsha-conventions`，不指向上游 |
| `tools/check_upstream_updates.py`、`tools/upstream_baseline.json`、`.github/workflows/upstream-check.yml` | 追蹤上游，見下節 |
| `tools/check_dependency_freshness.py`、`.github/dependency-deferrals.json`、`.github/workflows/dependency-freshness.yml`、`tests/test_dependency_freshness.py` | 依賴新鮮度檢查與延後升級的理由 |
| `.github/dependabot.yml`、`.github/workflows/codeql.yml` | Dependabot 與 CodeQL |
| `policy_check/_safe_tar.py`、`tests/test_safe_tar.py`、`tests/test_runtime_bundle_journal_security.py` | tar 解壓一律套用 `data` 過濾、journal 改 schema v2，見 `docs/DECISIONS.md` 2026-10-24「CodeQL 4 個 high 的處理」 |
| `docs/DECISIONS.md`、`tests/test_check_upstream_updates.py`、`changelog.d/` 下六個 fork 專屬 fragment | 決策記錄、檢查器測試與變更說明 |

### 只有上游有的檔案

| 檔案 | 說明 |
| --- | --- |
| `CLAUDE.md`、`GEMINI.md` | 上游的 `CLAUDE.md` 是 canonical 真檔，`AGENTS.md` 與 `GEMINI.md` 是指向它的 symlink（git mode 120000）。本 fork 以 `AGENTS.md` 為 canonical 真檔，不放 `CLAUDE.md`、`GEMINI.md`（`docs/DECISIONS.md` 2026-10-24 條：上游改 `CLAUDE.md` 時，本 fork 只手動更新 `AGENTS.md` 的版本字樣） |

### 兩邊都有但內容不同的檔案

比對結果共 27 個檔案內容不同；下列是已讀過差異內容的項目。

| 檔案 | 差異 |
| --- | --- |
| `AGENTS.md`、`.project-policy.yml` | 本 fork 的 canonical 設定與 symlink 說明，並加上「路線圖」段落 |
| `.github/workflows/release.yml`、`self-test.yml` | 本 fork 把 action 釘到 commit SHA 並加版本尾註；`self-test.yml` 另加綁定 PR head 的步驟 |
| `.github/workflows/policy-check.yml`、`reusable-policy-check.yml` | 新增 `policy_engine_repo` 參數，讓 fork 的自我檢查取用 fork 自己的引擎 |
| `policy_check/identity.py`、`policy_check/preflight.py`、`policy_check/data/distribution.yml` | 新增 `source_checkout_repos`（`SanHsien/paulsha-conventions`），只供 source-checkout 的 preflight 使用 |
| `policy_check/runtime_bundle/builder.py`、`integrity.py`、`manager.py`、`policy_check/doc_drift/symbols.py` | 套用 `_safe_tar` 與 journal schema v2（見上） |
| `pyproject.toml`、`README.md` | 測試依賴 `pytest>=9.1.1` 下限；README 的 Python 版本寫 3.11.4+ |

其餘（`policy_check/rules/` 的 r08／r13／r14、數個 `tests/`、`docs/runtime-bundle-runbook.md`）內容也不同，本檔未逐行比對，不在此歸因。

## 如何追蹤上游

- `tools/upstream_baseline.json`：`track: commit`，`reviewed_through` 為上游 commit `572cd48`，`reviewed_pr_through` 94、`reviewed_issue_through` 95，審查日 2026-11-02。
- `.github/workflows/upstream-check.yml`：每週一 03:00 UTC 以及手動觸發，執行 `tools/check_upstream_updates.py`，列出水位之後尚未審查的 commit、PR 與 issue。
- 採用與略過的逐項判斷寫在 `docs/DECISIONS.md`，驗證後才推進水位。
- 因為沒有共同祖先，同步靠 `git apply --3way` 套用上游補丁；上游若修改 tar、journal 或 `VERIFIED` 驗證邊界，要手動合併並保留 `extract_all_data_filtered` 呼叫（`docs/DECISIONS.md` 2026-10-24 條）。

## 對外規則

本 fork 的分支與 PR 流程依 [AGENTS.md](AGENTS.md)：先開 `feature/<slug>` 分支，不直接 commit 到 `main`。PR、push、release 一律指向 `SanHsien/paulsha-conventions`，不指向上游。
