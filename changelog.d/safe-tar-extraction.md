---
type: fix
---
將 tar 解壓統一改走 `policy_check._safe_tar.extract_all_data_filtered`，一律套用 `data` 過濾；Python 3.11.4 以前不再退回未過濾的 `extractall`，改為拒絕解壓。
