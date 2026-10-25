---
type: fix
---
將 runtime activation journal 改為只保存受驗證的 state metadata、release version 與 managed 路徑存在狀態，拒絕非 canonical state／launcher／skill link 與首次安裝殘留路徑，並在 recovery 時精準重建舊世代；舊版 raw-snapshot journal 改為 fail-closed。
