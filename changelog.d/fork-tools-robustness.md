---
type: fix
---
修正 fork 排程檢查的三個缺陷：upstream baseline 格式錯誤時改為回報而非崩潰；workflow pin 的尾註不是版本時仍保留 ref 的版本下限（且不再把數字開頭的 SHA 當版本）；deferral 檔案形狀錯誤時視同缺檔。
