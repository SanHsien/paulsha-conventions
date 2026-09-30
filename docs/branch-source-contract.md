# R-12 分支來源契約與遷移

## 發布狀態與設定範本

此契約是 [issue 87](https://github.com/hamanpaul/paulsha-conventions/issues/87)
的 v1.0.18 變更；v1.0.17 不支援。使用前須確認正式 tag、release assets 與
[RELEASES.md](../RELEASES.md) 譜系一致，不把未合併工作分支 SHA 當成合法
下游 release pin。發行流程依該文件的升版傳播 SOP 執行。

下游 `.project-policy.yml` 的 opt-in 範本：

```yaml
# policy_version 與所有 engine pins 必須先同步到正式 v1.0.18 或後續支援版本。
branch_source:
  allowed_prefixes: [feature, fix]
```

- 完全省略 `branch_source`：預設只有 `feature`，不自動接受 `fix` 或 `hotfix`
- 顯式 `allowed_prefixes: [feature]`：與預設接受集合相同
- 顯式 `[feature, fix]` 或 `[fix, feature]`：接受兩種分支，次序只影響訊息
- `feature` 必填，以免設定意外移除既有 feature/worktree 流程
- 不支援其他前綴（含 `hotfix`）、regex、glob 或任意自訂名稱
- 若宣告此區塊，必須是只含 `allowed_prefixes` 的 mapping；該值必須為非空、
  不重複的字串 list。null、空 mapping/list、錯誤型別、未知 key/prefix 都由
  R-08 判 FAIL；R-12 在適用的 PR context 也獨立 fail-closed，不回退成較寬規則
- canonical/legacy manifest 的解析沿用既有規則；錯誤診斷顯示有效接受集合及
  `.project-policy.yml:branch_source.allowed_prefixes`（或 legacy alias）來源，
  未設定時顯示 built-in default

## GitHub 分支語意

`<slug>` 與 `<subtask>` 都完整匹配 `[a-z0-9][a-z0-9-]*`：不得為空、含大寫、
底線、斜線或以連字號開頭。延續原文法，數字、連續連字號與尾端連字號可用。
issue-id 建議放在 slug 開頭，但不是 R-12 必填欄位。

| PR base | PR head | 結果 |
|---|---|---|
| main | feature/87-branch-contract | 預設及 opt-in 都 PASS |
| main | fix/setup-preserve-remote-socket-path | 啟用 fix 才 PASS |
| main | hotfix/example、fix/Bad_Name、wt/example/task | FAIL |
| feature/example | wt/example/tests | PASS |
| fix/example（已啟用） | wt/example/tests | PASS |
| fix/example（已啟用） | wt/another/tests、feature/example、fix/example | FAIL |
| feature/Bad_Name 或 fix/Bad_Name（已啟用） | 任意來源 | FAIL，不落入 outside-scope |

worktree head 不含前綴，只配對 slug；feature/example 與 fix/example 都要求
wt/example/task。缺少 PR base/head 的非 PR context、GitLab provider、真實
`policy-exempt:branch-name` label 的既有 PASS／NA／SKIP 語意不變。

其他 base 仍維持 applicability 行為，例如 develop、release/1.0，及**未啟用**
fix 時的 fix/example，R-12 顯示 outside scope。這不表示已驗證該類分支。
啟用 fix 後，fix base 及其錯誤命名一定進入檢查。既有 malformed feature base
以前可能落入 outside scope，現在明確 FAIL；這是針對已啟用前綴的 fail-open 修正。
未改任何其他 provider 規則，也不從 CLAUDE.md 文字推導有效政策。

## Event labels 與 preflight／CI

CLI 建立 PR context 時，實際 GitHub event 的 labels 優先；`labels: []` 也是
已知值，會壓過命令列 `--pr-labels`。CLI labels 只在沒有 event label 值時 fallback。
因此在 workflow 裡注入 `policy-exempt:branch-name` 不是正式命名支援，也不能
當作已生效的豁免。此變更保留優先序，沒有擴大 CLI 覆蓋權。

本機 preflight 以其解析的 PR metadata 產生相同 event context，再呼叫同一個
policy engine；使用同一 manifest、版本、base/head 及真實 labels，R-12 結果應一致。
PR 尚未建立時可用 canonical preflight-ci skill 的手動 metadata 模式；PR 已建立時
應用 `--pr <number>` 取真實 context。其他 selected gates 照常執行。

## 正式 release 與 serialwrap 遷移驗收

1. 中央功能 PR 完成完整 pytest、packaging smoke、policy 與 canonical preflight，
   審查後由獲授權者合併。非 release PR 的 VERSION 保持與 latest tag 一致
2. 立即完成 release bump：VERSION、pyproject、policy_version、canonical agent
   文件、managed-by、workflow version、CHANGELOG 與 RELEASES ledger 都同步；
   release tag 必須是經核可且已審查的 clean annotated tag
3. 推送 tag 會觸發 release workflow；等待 Python 3.11／3.12 bundle build、離線
   安裝 smoke、publish 與 asset digest 驗證全過，記錄 tag 解參照的完整 commit SHA
4. 在 serialwrap 的獨立變更同步所有 engine pins 與版本註記、policy_version、
   agent 文件及分支文件，加入上方 opt-in。保留 R-23 engine pin attestation，
   移除自動 fix/hotfix exemption workaround；不使用未合併工作分支 SHA
5. 以 [serialwrap PR 223](https://github.com/hamanpaul/serialwrap/pull/223) 的
   fix/setup-preserve-remote-socket-path → main 真實 event（無 branch-name label）
   跑 preflight 與 CI；R-12 必須原生 PASS，完整 selected gates 也須通過
6. 比對非法 slug、未允許 hotfix 及錯誤 worktree slug 都仍 FAIL。保留 CI run、
   release tag/SHA、實際 PR head 作為驗收證據；pytest 綠不能代替 policy 全綠

在正式 release 與下游 CI 證據出現之前，issue 的下游驗收仍為待完成；不得將
source checkout 的成功測試描述成 serialwrap 已使用新版本。
