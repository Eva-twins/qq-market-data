# qq-market-data
「類全委同業觀測平台」使用的公開市場資料，由 GitHub Actions 每天自動更新（台北時間約 09:17）。

| 檔案 | 內容 | 來源 |
| --- | --- | --- |
| data/ins.json | 投資型保險初年度保費、帳戶價值（月，億元） | 保發中心壽險統計樞紐 |
| data/mk.json | 投信類全委規模（月，億元，依投信） | 投信投顧公會 全權委託業務統計 |
| data/lia.json | 初年度保費依險別、依通路（累計，百萬元） | 壽險公會「壽險業績統計」PDF |
| data/lia_seed.json | 通路年報歷史（2005–2016、2022） | 使用者提供之整理檔 |

程式在 `scripts/`，排程在 `.github/workflows/update.yml`。手動重跑：Actions → update-data → Run workflow。
