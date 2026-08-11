<p align="right">
  <strong>語言 / Language：</strong>
  <a href="#chinese-version">繁體中文</a> · <a href="#english-version">English</a>
</p>

<hr>

<a id="chinese-version"></a>

# 📊 投資績效分析軟體 v1.0.0（Desktop Edition）

一款基於 **Python + Flask + pywebview + yfinance** 的 Windows 桌面投資績效分析軟體，完整支援**台股、美股、港股、A股、指數、大宗商品與匯率**等全球金融數據，提供多投資組合管理、績效回測、風險指標、投資組合可視圖、個股基本面／技術／新聞分析，以及報告匯出等功能。

> **快速跳轉：** [安裝與設置](#安裝與設置) · [使用指南](#使用指南) · [投資組合可視圖](#投資組合可視圖portfolio-dashboard) · [English](#english-version)

---

## 目錄（繁體中文版）

1. [專案簡介](#1-專案簡介)
2. [開發過程](#2-開發過程)
3. [設計原因](#3-設計原因)
4. [功能特色](#4-功能特色)
5. [達到效果](#5-達到效果)
6. [技術架構](#6-技術架構)
7. [安裝與設置](#7-安裝與設置)
8. [使用指南](#8-使用指南)
9. [投資組合可視圖（Portfolio Dashboard）](#9-投資組合可視圖portfolio-dashboard)
10. [數據源與快取機制](#10-數據源與快取機制)
11. [支援標的](#11-支援標的)
12. [注意事項與常見問題](#12-注意事項與常見問題)
13. [License](#license)

---

## 1. 專案簡介

本專案是一套**單機版**投資績效分析工具，目的是讓投資者不需依賴雲端平台，即可在本地電腦快速掌握：

- 資產的**總市值、投入成本、損益**與**現金水位**
- 投資組合的**資產類別／市場區域／產業**分散程度
- 近一年／近三年的**績效曲線、定期報酬**與**年化報酬率（CAGR）**
- 標準**風險指標**（最大回撤、波動率、夏普、索提諾、貝塔）
- 標的之間的**相關性矩陣**

所有數據皆儲存於本地，投資組合檔案以 JSON 格式保存，報價與歷史 K 線透過 Yahoo Finance（yfinance）取得，並以本地快取加速重複載入。

---

## 2. 開發過程

### 2.1 需求階段：為什麼要做？

- 想要一套**免雲端、資料留在自己電腦**的投資追蹤工具，避免把持倉資料上傳到第三方。
- 需要同時涵蓋**台股、美股、港股、A股**，且不花錢訂閱行情源。
- 除了看即時市值，更需要**績效與風險量化分析**（夏普、最大回撤、相關性等），這類功能多在 Portfolio Visualizer 等收費網站，本專案希望能免費在地端重現。

### 2.2 技術選型

- **Python**：資料處理（pandas / numpy）生態成熟，適合金融運算。
- **yfinance（Yahoo Finance）**：免費且涵蓋全球主要市場（股票／指數／ETF／商品／匯率），作為主要資料源。
- **FastHTML（初版）**：快速建立 Server-rendered 網頁介面，做出第一版 `app.py` 與模組化 `src/` 結構。
- **Flask + pywebview（現行桌面版）**：因使用者希望「像一般桌面軟體一樣雙擊即可開啟」，改以 Flask 提供 REST API，再用 pywebview 開啟原生視窗載入介面，**不需額外開瀏覽器**。

### 2.3 開發歷程（重點里程碑）

1. **模組化版本**（`app.py` + `src/`）：建立 config / data / business / charts / export / cache / utils 等模組，確立資料層與業務層分離。
2. **桌面化版本**（`desktop_app.py`）：將核心功能收斂為單一檔案，方便打包成 exe；啟動 Flask（127.0.0.1:8765）並以 pywebview 開啟原生視窗。
3. **投資組合可視圖強化**：新增四種配置甜甜圈（資產類別／市場區域／股票產業／前五大持股）、績效曲線、每月／年度報酬長條圖、3 年 CAGR、風險指標卡與相關性熱圖。
4. **資料正確性修正**：
   - 修正甜甜圈單一類別（100%）時 SVG 無法繪製完整圓環的問題。
   - 修正長條圖數值被柱子遮擋的問題，讓報酬數字與柱子分離顯示。
   - 統一「前五大持股權重」與持倉明細表的權重計算，兩處數字一致。
   - 修正 3 年 CAGR 年化公式，改用 **252 個交易日／年** 的正確年化，避免高估。
   - 比例總和校正為**剛好 100%**（最大餘數法），不再出現 101%。

---

## 3. 設計原因

| 設計決策 | 原因 |
|----------|------|
| 本地 JSON 儲存投資組合 | 資料不離開電腦、易於備份與遷移 |
| yfinance 為單一資料源 | 免費、覆蓋範圍廣、免 API Key |
| Flask 提供 REST API | 前端與資料邏輯分離，方便日後擴充 |
| pywebview 原生視窗 | 使用者不必操作瀏覽器，接近傳統桌面軟體體驗 |
| 多重幣別＋自動匯率換算 | 投資組合可能混有台幣／美元／港幣／人民幣，需以基準幣別統一計算損益 |
| 本地快取（報價 1 小時、歷史 48 小時、產業 7 天） | 降低 API 呼叫量、加快頁面載入 |
| 投資組合可視圖 | 一眼掌握配置分散度與風險，避免權重過度集中 |
| 可設定買賣手續費與稅率 | 讓損益貼近真實交易成本 |

---

## 4. 功能特色

### 4.1 資產總覽（Overview）
- 總資產價值、總投入資金、總損益（金額＋％）、持倉數、現金餘額。
- 持倉明細表：標的、數量、成本價、現價、市值、損益、損益率、權重。
- **投資組合可視圖**（見第 9 節）。

### 4.2 市場行情（Market）
- 全部支援標的的即時報價（現價、漲跌、漲跌幅）。
- 依類別篩選：股票／ETF／指數／商品／匯率。
- 每檔標的的 3 年貝塔、夏普、索提諾指標。

### 4.3 持倉管理（Portfolio）
- 建立／刪除投資組合（最多 **8 組**），可設定基準幣別與比較基準（Benchmark）。
- 新增／刪除持倉，設定數量、成本價、買賣手續費率與稅率。
- 支援多幣別持倉與自動匯率換算。
- 支援現金（CASH）持倉或現金餘額設定。

### 4.4 績效分析（Performance）
- 區間選擇：半年前至今、一年前至今、自訂起始日。
- 總報酬、基準（Benchmark）報酬、超額報酬、年化報酬、期末市值。
- 最大回撤、波動率，以及組合與基準的績效曲線對比。
- 完整風險指標：夏普、索提諾、貝塔（1 年／3 年）。

### 4.5 歷史分析（Analysis）— 個股深入
- **基本面（Fund）**：財務報表（資產負債表、損益、現金流）摘要、關鍵財務指標。
- **技術面（Tech）**：K 線圖、成交量、技術指標（MA / MACD / RSI / 布林帶）、1／5 年區間。
- **新聞（News）**：Yahoo 個股新聞列表。

### 4.6 標的管理（Symbols）
- 檢視、新增、刪除自訂標的（寫入 `custom_symbols.json`）。
- 整合 `Indexing.json` 標的索引，支援代碼搜尋。

### 4.7 報告匯出（Reports）
- 選擇投資組合後，一鍵匯出**績效報告 CSV**。

### 4.8 系統設置（Settings）
- 快取狀態檢視與「清除快取」。
- **多語系介面**：於「介面語言」切換**繁體中文／简体中文／English**，即時生效並自動記憶。

### 4.9 其他
- **多語系支援**：整個介面（導覽、表格、基本面、投資組合可視圖、匯出報告）皆可切換為繁中／簡中／英文。
- 深色專業主題介面。
- 連線狀態指示、手動刷新。
- 報價延遲警示（行情約延遲 15~20 分鐘）。

---

## 5. 達到效果

- **雙擊即用**：`yfInvestment.bat` 一鍵啟動，開啟原生視窗，不需瀏覽器。
- **跨市場覆蓋**：台／美／港／陸＋商品＋匯率，一處看全部。
- **多幣別統一損益**：以基準幣別（TWD／USD／CNY／HKD／JPY）換算並計算損益，持股跨市場也不會算錯。
- **專業量化指標**：夏普、索提諾、貝塔、最大回撤、波動率、相關性矩陣、3 年 CAGR，媲美 Portfolio Visualizer 的核心功能。
- **配置視覺化**：資產類別／區域／產業／前五大持股四張甜甜圈，秒懂分散程度。
- **快取加速**：重複開啟頁面不需反覆抓取 Yahoo，歷史資料可離線重看。
- **數據自主**：所有資料只在本機，投資組合可直接備份 JSON 檔。

---

## 6. 技術架構

```
yfInvestment/
├── desktop_app.py          # ★ 主程式（桌面版：Flask + pywebview）
├── app.py                  # FastHTML 網頁版（歷史版本）
├── yfInvestment.bat        # 一鍵啟動桌面版（python desktop_app.py）
├── config.yaml             # 應用配置（主題／手續費／匯率／匯出等）
├── custom_symbols.json     # 使用者自訂標的
├── Indexing.json           # 標的索引（代碼搜尋用）
├── news.py / run8.py / tradingView.py   # 早期獨立工具／原型
├── requirements.txt        # 依賴清單
├── src/                    # 模組化版本原始碼（FastHTML 時代結構）
│   ├── config/ data/ business/ ui/ charts/ export/ cache/ utils/
├── tests/                  # 測試目錄（目前為佔位）
├── data_cache/             # 本地快取（報價／歷史／產業）
│   ├── settings.json       # ★ 介面語言等應用設定
│   └── portfolios/         # ★ 投資組合 JSON（請務必保留）
└── README.md               # 本說明文件（繁中＋英文）
```

**桌面版資料流：**

```
瀏覽器 / pywebview 視窗
   │  HTTP（REST）
   ▼
Flask（desktop_app.py，127.0.0.1:8765）
   │
   ├──► yfinance（Yahoo Finance）→ 報價 / 歷史K線 / 個股新聞 / 財報
   ├──► data_cache（JSON 快取：報價 1h、歷史 48h、產業 7d）
   ├──► Indexing.json + custom_symbols.json（標的索引）
   └──► data_cache/portfolios/*.json（投資組合儲存）
```

---

## 7. 安裝與設置

### 7.1 環境需求

- Windows 10 / 11（桌面版以 pywebview 開啟視窗）
- Python **3.10 以上**
- 可連線網際網路（取行情用，歷史資料有快取後可離線重看）

### 7.2 下載專案

```bash
git clone https://github.com/aneterw/yfInvestment.git
cd yfInvestment
```

### 7.3 安裝依賴

在專案根目錄開啟命令提示字元：

```bash
pip install -r requirements.txt
```

> **注意**：`requirements.txt` 未包含桌面版所需的 `flask` 與 `pywebview`，請一併安裝：

```bash
pip install flask pywebview
```

（FastHTML 版的正確 PyPI 安裝套件名為 `python-fasthtml`，請執行 `pip install python-fasthtml`；程式碼中導入（Import）時才使用 `import fasthtml`。）

### 7.4 確認資料檔

初次執行時程式會自動建立必要目錄與檔案：

- `data_cache/`（自動建立）
- `data_cache/settings.json`（自動建立，儲存介面語言等設定）
- `data_cache/portfolios/`（自動建立，存放投資組合）
- `Indexing.json`、`custom_symbols.json`（若有則直接使用）

### 7.5 啟動應用

雙擊 `yfInvestment.bat`，或在命令列執行：

```bash
python desktop_app.py
```

啟動後會自動開啟一個**原生桌面視窗**，無需瀏覽器。若視窗未自動跳出，可手動開啟瀏覽器訪問：

```
http://127.0.0.1:8765
```

### 7.6 首次使用建議流程

1. 前往 **持倉管理**，點「＋ 新增組合」，輸入名稱、選擇基準幣別與比較基準（Benchmark）。
2. 點「＋ 新增標的」，輸入代碼（如 `2330.TW`、`AAPL`、`0700.HK`）、數量與成本價（可調整手續費／稅率）。
3. 回到 **資產總覽** 檢視統計、持倉與投資組合可視圖。
4. 前往 **績效分析** 檢視區間績效與風險指標。
5. 在 **報告匯出** 一鍵下載 CSV。

---

## 8. 使用指南

### 8.1 資產總覽（Overview）

- 頂部五張統計卡：**總資產價值、總投入資金、總損益、持倉數、現金餘額**。
- **持倉明細表**：每檔標的的數量、成本、現價、市值、損益率與權重（權重為淨市值 ÷ 總市值）。
- **投資組合可視圖**：詳細內容見第 9 節。

### 8.2 市場行情（Market）

- 點上方按鈕篩選類別（全部／股票／ETF／指數／商品／匯率）。
- 表格顯示代碼、名稱、現價、漲跌、漲跌幅與 3 年貝塔／夏普／索提諾。
- 點「🔄 刷新」重新抓取。

### 8.3 持倉管理（Portfolio）

- 左上下拉選單切換投資組合。
- **新增組合**：名稱、基準幣別（TWD／USD／CNY／HKD／JPY）、Benchmark（`^TWII`、`^GSPC`、`^IXIC`、`^HSI`、`000001.SS`、`SPY`、`QQQ`）。
- **新增標的**：代碼、名稱、數量、成本價；預設買賣手續費 0.1425%、稅率 0.3%，可依實際調整。
- **刪除標的／刪除組合**：注意刪除組合會一併移除其所有持倉。

### 8.4 績效分析（Performance）

- 選擇「半年前至今／一年前至今／自訂日期」。
- 檢視總報酬、Benchmark 報酬、超額報酬、年化報酬、最大回撤與波動率。
- 下方的曲線圖顯示**組合 vs 基準**的累計報酬走勢。

### 8.5 歷史分析（Analysis）

1. 輸入標的代碼（如 `2330.TW`）。
2. 切換分頁：**基本面／技術面／新聞**。
   - 基本面：財務報表摘要、關鍵指標（EPS、殖利率、PE 等）。
   - 技術面：K 線＋成交量＋MA／MACD／RSI／布林帶，可切換 1 年／5 年。
   - 新聞：Yahoo 個股新聞。

### 8.6 標的管理（Symbols）

- 瀏覽現有標的，可新增自訂標的、刪除不需要的標的。
- 自訂標的會寫入 `custom_symbols.json`。

### 8.7 報告匯出（Reports）

- 選取投資組合 → 點「匯出 CSV」，即下載 `report_<組合名>_<時間戳>.csv`。

### 8.8 系統設置（Settings）

- 檢視快取狀態（已快取的標的與筆數）。
- 點「清除快取」釋放空間（不影響投資組合資料）。
- **切換介面語言**：下拉選單選擇「繁體中文／简体中文／English」，套用後頁面會自動重新載入並以所選語言顯示；下次啟動時會記住上次的語言設定。

---

## 9. 投資組合可視圖（Portfolio Dashboard）

在**資產總覽**頁下方的「📊 投資組合可視圖」區塊，包含：

### 9.1 四張配置甜甜圈

| 甜甜圈 | 內容 |
|--------|------|
| 資產類別配置 | 股票／ETF／指數／商品／匯率／現金 的比重 |
| 市場區域配置 | 台股／美股／港股／A股／商品／匯率／現金 |
| 股票產業配置 | 依 Yahoo **sector → industry → 公司名** 分組的產業比重（不含「其他」兜底） |
| 前五大持股權重 | 前五大標的的權重（與持倉明細一致） |

每張甜甜圈中心顯示總計，比例經**最大餘數法**校正後**總和剛好 100%**。

### 9.2 績效區塊

- **近一年績效曲線 vs 基準**：組合與 Benchmark 的累計報酬折線，附總報酬徽章。
- **近一年每月報酬**（長條圖）：每月的絕對報酬率，數值標於柱子上／下方，清楚可見。
- **近三年年度報酬**（長條圖）：逐年報酬，並顯示 **3 年 CAGR** 徽章。
  - CAGR 公式：`(期末價值 / 期初價值) ^ (1 / 年數) − 1`
  - 程式以 **252 個交易日/年** 正確年化，避免高估。

### 9.3 風險指標區塊

- 最大回撤（全期／近 1 年）、波動率（1 年／3 年）、夏普、索提諾、貝塔（1 年／3 年）。

### 9.4 相關性矩陣

- 以熱圖顯示近一年各標的日報酬的相關係數（−1～＋1），數值與色階並存。

---

## 10. 數據源與快取機制

| 資料 | 來源 | 快取期限 |
|------|------|----------|
| 即時報價 | Yahoo Finance（yfinance） | 1 小時 |
| 歷史 K 線 | Yahoo Finance（yfinance） | 48 小時 |
| 產業分類（sector / industry） | Yahoo Finance（yfinance） | 7 天 |
| 匯率 | Yahoo Finance FX | 依報價快取 |
| 個股新聞／財報 | Yahoo Finance | 依呼叫即時抓取 |

- 快取檔案存放於 `data_cache/`，可在**系統設置**手動清除。
- 行情為延遲資料（約 15~20 分鐘），僅供參考，實際交易請以券商報價為準。

---

## 11. 支援標的

| 市場 | 指數 | 個股／ETF 範例 |
|------|------|----------------|
| 台股（TW） | `^TWII` | `2330.TW` 台積電、`2317.TW` 鴻海、`2454.TW` 聯發科、`0050.TW`、`0056.TW`、`00878.TW` |
| 美股（US） | `^GSPC`、`^IXIC`、`^DJI` | `AAPL`、`MSFT`、`GOOGL`、`NVDA`、`TSLA`、`SPY`、`QQQ` |
| 港股（HK） | `^HSI` | `0700.HK` 騰訊、`9988.HK` 阿里巴巴、`3690.HK` 美團 |
| A股（CN） | `000001.SS`、`399001.SZ` | `600519.SS` 貴州茅台、`000858.SZ` 五糧液、`300750.SZ` 寧德時代 |
| 大宗商品 | — | `GC=F` 黃金、`CL=F` 原油 |
| 匯率 | — | `USDTWD=X`、`USDCNY=X`、`USDHKD=X`、`USDJPY=X` |

> 標的代碼為 Yahoo Finance 格式。也支援在「標的管理」新增自訂標的。

---

## 12. 注意事項與常見問題

1. **需要網路**才能取得最新行情；歷史 K 線快取後可離線重看（48 小時內）。
2. **報價有延遲**（約 15~20 分鐘），僅供參考，不構成投資建議。
3. **投資組合檔案**位於 `data_cache/portfolios/*.json`，請勿誤刪；刪除整個 `data_cache` 會清空投資組合。
4. **匯率換算**以 Yahoo 匯率為準，與券商牌告可能略有差異。
5. 若視窗未跳出，請直接以瀏覽器開啟 `http://127.0.0.1:8765`。
6. 最多可建立 **8 組**投資組合。
7. 建議使用 Python 3.10 以上版本。
8. **介面語言**可在「系統設置 → 介面語言」切換（繁中／簡中／英文），切換後立即生效並自動記憶。

---

## License

本專案採用 **MIT License**。詳細條款請參閱專案中的 `LICENSE` 檔（若尚未建立，即代表使用者可依 MIT 慣例自由使用、修改與散布）。

---

<hr>
<p align="center">
  <strong><a href="#chinese-version">↑ 回到繁體中文版</a></strong>
</p>
<hr>

<a id="english-version"></a>

# 📊 Investment Performance Analyzer v1.0.0 (Desktop Edition)

A Windows desktop investment performance analysis tool built on **Python + Flask + pywebview + yfinance**, with full support for **Taiwan, US, Hong Kong and China A-shares, indices, commodities and FX** global market data. It provides multi-portfolio management, performance backtesting, risk analytics, a portfolio dashboard, per-stock fundamental/technical/news analysis, and report export.

> **Quick links:** [Installation & Setup](#installation--setup) · [User Guide](#user-guide) · [Portfolio Dashboard](#portfolio-dashboard) · [繁體中文](#chinese-version)

---

## Table of Contents (English)

1. [Project Overview](#1-project-overview)
2. [Development Process](#2-development-process)
3. [Design Rationale](#3-design-rationale)
4. [Features](#4-features)
5. [Results & Effects](#5-results--effects)
6. [Technical Architecture](#6-technical-architecture)
7. [Installation & Setup](#7-installation--setup)
8. [User Guide](#8-user-guide)
9. [Portfolio Dashboard](#9-portfolio-dashboard)
10. [Data Sources & Caching](#10-data-sources--caching)
11. [Supported Instruments](#11-supported-instruments)
12. [Notes & FAQ](#12-notes--faq)
13. [License](#license-1)

---

## 1. Project Overview

This is a **standalone, local-only** investment performance analysis tool. Its goal is to let investors quickly understand, without relying on cloud platforms:

- Total **market value, invested cost, profit/loss** and **cash position**
- The portfolio's **asset-class / market-region / industry** diversification
- **Performance curves, periodic returns** and **CAGR** over the past 1–3 years
- Standard **risk metrics** (max drawdown, volatility, Sharpe, Sortino, beta)
- The **correlation matrix** between holdings

All data is stored locally. Portfolios are saved as JSON files, quotes and historical K-lines are fetched from Yahoo Finance (yfinance), and a local cache speeds up repeated loads.

---

## 2. Development Process

### 2.1 Requirements — Why this project?

- A **cloud-free** portfolio tracker that keeps holdings data **on your own computer**.
- Coverage of **Taiwan, US, Hong Kong and China A-shares** without paying for a data feed.
- Beyond live market value, it needed **quantified performance and risk analysis** (Sharpe, max drawdown, correlation, etc.) — features usually found on paid sites like Portfolio Visualizer, recreated here for free on the local machine.

### 2.2 Technology Choices

- **Python**: mature data-processing ecosystem (pandas / numpy), ideal for financial computation.
- **yfinance (Yahoo Finance)**: free, covers major global markets (stocks / indices / ETFs / commodities / FX) — the primary data source.
- **FastHTML (first version)**: quickly built a server-rendered web UI (`app.py` + modular `src/`).
- **Flask + pywebview (current desktop version)**: since the user wanted a "double-click like a normal desktop app" experience, Flask provides the REST API and pywebview opens a native window — **no separate browser required**.

### 2.3 Development Milestones

1. **Modular version** (`app.py` + `src/`): config / data / business / charts / export / cache / utils modules, separating data layer from business logic.
2. **Desktop version** (`desktop_app.py`): consolidated the core into a single file for easy packaging to exe; starts Flask (127.0.0.1:8765) and opens a native pywebview window.
3. **Portfolio dashboard enhancement**: added four allocation donuts (asset class / market region / industry / top-5 holdings), performance curves, monthly/annual return bars, 3-year CAGR, risk metric cards and a correlation heatmap.
4. **Correctness fixes**:
   - Fixed SVG failing to draw a full donut ring when there is a single 100% category.
   - Separated bar-chart value labels from the bars so numbers are always visible.
   - Unified "top-5 holding weights" with the holdings-table weight calculation so both match.
   - Fixed the 3-year CAGR annualization to use the correct **252 trading days per year**, avoiding overstatement.
   - Normalized percentage sums to **exactly 100%** (largest-remainder method) — no more 101%.

---

## 3. Design Rationale

| Decision | Reason |
|----------|--------|
| Local JSON portfolio storage | Data never leaves your machine; easy to back up / migrate |
| Single data source via yfinance | Free, broad coverage, no API key required |
| Flask REST API | Separates frontend from data logic; easy to extend later |
| pywebview native window | Users don't operate a browser; close to a traditional desktop app |
| Multi-currency + automatic FX | A portfolio may mix TWD/USD/HKD/CNY; P&L must be unified in the base currency |
| Local cache (quotes 1h, history 48h, sector 7d) | Fewer API calls, faster page loads |
| Portfolio dashboard | Instantly grasp allocation diversification and risk, avoid over-concentration |
| Configurable fees and tax | P&L reflects real trading costs |

---

## 4. Features

### 4.1 Overview
- Total asset value, total invested, total P&L (amount + %), position count, cash balance.
- Holdings table: instrument, quantity, cost price, current price, market value, P&L, P&L %, weight.
- **Portfolio Dashboard** (see Section 9).

### 4.2 Market
- Live quotes for all supported instruments (price, change, change %).
- Filter by category: stocks / ETFs / indices / commodities / FX.
- 3-year beta, Sharpe, Sortino per instrument.

### 4.3 Portfolio Management
- Create / delete portfolios (max **8**), set base currency and comparison benchmark.
- Add / remove positions with quantity, cost price, buy/sell fee rates and tax rate.
- Multi-currency positions with automatic FX conversion.
- Support for CASH positions or a cash balance.

### 4.4 Performance
- Period selection: past 6 months / past 1 year / custom start date.
- Total return, benchmark return, excess return, annualized return, ending market value.
- Max drawdown, volatility, and a portfolio-vs-benchmark equity curve.
- Full risk ratios: Sharpe, Sortino, beta (1-year / 3-year).

### 4.5 Analysis (per stock)
- **Fundamentals**: financial-statement summary, key financial metrics.
- **Technical**: candlestick chart, volume, indicators (MA / MACD / RSI / Bollinger), 1y / 5y ranges.
- **News**: Yahoo per-stock news list.

### 4.6 Symbols
- View, add, delete custom instruments (saved to `custom_symbols.json`).
- Searchable index integrated with `Indexing.json`.

### 4.7 Reports
- Select a portfolio and export a **performance report CSV** in one click.

### 4.8 Settings
- Cache status view and "clear cache".
- **Multi-language UI**: switch between **繁體中文 / 简体中文 / English** under "Interface Language" — takes effect immediately and is remembered automatically.

### 4.9 Other
- **Multi-language support**: the entire UI (navigation, tables, fundamentals, portfolio dashboard, exported reports) can switch between Traditional Chinese / Simplified Chinese / English.
- Professional dark theme.
- Connection status indicator, manual refresh.
- Quote delay notice (quotes are delayed ~15–20 minutes).

---

## 5. Results & Effects

- **Double-click to run**: `yfInvestment.bat` launches a native window; no browser needed.
- **Cross-market coverage**: TW / US / HK / CN + commodities + FX in one place.
- **Unified multi-currency P&L**: converts to the base currency (TWD/USD/CNY/HKD/JPY), so cross-market holdings are never miscounted.
- **Professional quantitative metrics**: Sharpe, Sortino, beta, max drawdown, volatility, correlation matrix, 3-year CAGR — comparable to Portfolio Visualizer's core.
- **Visualized allocation**: four donuts (asset class / region / industry / top-5) — instantly see diversification.
- **Cache speed-up**: repeated page loads don't re-fetch Yahoo; cached history can be viewed offline.
- **Data ownership**: everything stays on your machine; portfolios can be backed up as JSON files.

---

## 6. Technical Architecture

```
yfInvestment/
├── desktop_app.py          # ★ Main program (Desktop: Flask + pywebview)
├── app.py                  # FastHTML web version (legacy)
├── yfInvestment.bat        # One-click launch of the desktop version
├── config.yaml             # App config (theme / fees / FX / export, etc.)
├── custom_symbols.json     # User-defined instruments
├── Indexing.json           # Instrument index (for symbol search)
├── news.py / run8.py / tradingView.py   # Early standalone tools / prototypes
├── requirements.txt        # Dependency list
├── src/                    # Modular version source (FastHTML-era structure)
│   ├── config/ data/ business/ ui/ charts/ export/ cache/ utils/
├── tests/                  # Tests directory (currently a placeholder)
├── data_cache/             # Local cache (quotes / history / sector)
│   ├── settings.json       # ★ App settings such as UI language
│   └── portfolios/         # ★ Portfolio JSON (keep this!)
└── README.md               # This document (Traditional Chinese + English)
```

**Desktop data flow:**

```
Browser / pywebview window
   │  HTTP (REST)
   ▼
Flask (desktop_app.py, 127.0.0.1:8765)
   │
   ├──► yfinance (Yahoo Finance) → quotes / history / news / financials
   ├──► data_cache (JSON cache: quotes 1h, history 48h, sector 7d)
   ├──► Indexing.json + custom_symbols.json (instrument index)
   └──► data_cache/portfolios/*.json (portfolio storage)
```

---

## 7. Installation & Setup

### 7.1 Requirements

- Windows 10 / 11 (the desktop version opens a pywebview window)
- Python **3.10+**
- Internet access (for live quotes; cached history can be viewed offline)

### 7.2 Clone the Repository

```bash
git clone https://github.com/aneterw/yfInvestment.git
cd yfInvestment
```

### 7.3 Install Dependencies

Open a terminal in the project root:

```bash
pip install -r requirements.txt
```

> **Note**: `requirements.txt` does not include the `flask` and `pywebview` packages needed by the desktop version — install them too:

```bash
pip install flask pywebview
```

(The correct PyPI package name for the FastHTML version is `python-fasthtml` — run `pip install python-fasthtml`; use `import fasthtml` only in Python code.)

### 7.4 Verify Data Files

On first run the program creates the required directories automatically:

- `data_cache/` (auto-created)
- `data_cache/settings.json` (auto-created, stores settings such as the UI language)
- `data_cache/portfolios/` (auto-created, stores portfolios)
- `Indexing.json`, `custom_symbols.json` (used as-is if present)

### 7.5 Launch

Double-click `yfInvestment.bat`, or run in a terminal:

```bash
python desktop_app.py
```

A **native desktop window** opens automatically — no browser needed. If the window doesn't appear, open a browser manually at:

```
http://127.0.0.1:8765
```

### 7.6 Recommended First-Run Flow

1. Go to **Portfolio**, click "+ New Portfolio", enter a name, choose the base currency and benchmark.
2. Click "+ Add Instrument", enter the code (e.g. `2330.TW`, `AAPL`, `0700.HK`), quantity and cost price (fees/tax are adjustable).
3. Return to **Overview** to review stats, holdings and the portfolio dashboard.
4. Go to **Performance** to review period performance and risk metrics.
5. In **Reports**, download the CSV in one click.

---

## 8. User Guide

### 8.1 Overview
- Five stat cards on top: **total asset value, total invested, total P&L, position count, cash balance**.
- **Holdings table**: quantity, cost, current price, market value, P&L % and weight (net market value ÷ total value) for each instrument.
- **Portfolio Dashboard**: see Section 9.

### 8.2 Market
- Use the buttons to filter categories (All / Stocks / ETFs / Indices / Commodities / FX).
- The table shows code, name, current price, change, change % and 3-year beta / Sharpe / Sortino.
- Click "🔄 Refresh" to re-fetch.

### 8.3 Portfolio Management
- Use the dropdown on the left to switch portfolios.
- **New portfolio**: name, base currency (TWD/USD/CNY/HKD/JPY), benchmark (`^TWII`, `^GSPC`, `^IXIC`, `^HSI`, `000001.SS`, `SPY`, `QQQ`).
- **Add instrument**: code, name, quantity, cost price; default buy/sell fee 0.1425%, tax 0.3%, adjustable.
- **Delete instrument / portfolio**: note that deleting a portfolio removes all its positions.

### 8.4 Performance
- Choose "past 6 months / past 1 year / custom date".
- Review total return, benchmark return, excess return, annualized return, max drawdown and volatility.
- The chart below shows the **portfolio vs benchmark** cumulative return curve.

### 8.5 Analysis
1. Enter an instrument code (e.g. `2330.TW`).
2. Switch tabs: **Fundamentals / Technical / News**.
   - Fundamentals: financial-statement summary, key metrics (EPS, yield, P/E, etc.).
   - Technical: candlestick + volume + MA/MACD/RSI/Bollinger, switchable 1y / 5y.
   - News: Yahoo per-stock news.

### 8.6 Symbols
- Browse existing instruments; add custom ones or delete unneeded ones.
- Custom instruments are written to `custom_symbols.json`.

### 8.7 Reports
- Select a portfolio → click "Export CSV" to download `report_<portfolio>_<timestamp>.csv`.

### 8.8 Settings
- View cache status (cached instruments and counts).
- Click "Clear cache" to free space (does not affect portfolio data).
- **Switch UI language**: choose "繁體中文 / 简体中文 / English" from the dropdown; the page reloads automatically in the selected language and the choice is remembered for the next launch.

---

## 9. Portfolio Dashboard

Located under "📊 Portfolio Dashboard" at the bottom of the **Overview** page:

### 9.1 Four Allocation Donuts

| Donut | Content |
|-------|---------|
| Asset Class Allocation | Weight of stocks / ETFs / indices / commodities / FX / cash |
| Market Region Allocation | Taiwan / US / HK / China A / commodities / FX / cash |
| Stock Industry Allocation | Grouped by Yahoo **sector → industry → company name** (no "Other" bucket) |
| Top-5 Holdings Weight | Weights of the top five instruments (identical to the holdings table) |

The center of each donut shows the total; percentages are normalized with the **largest-remainder method** so they sum to **exactly 100%**.

### 9.2 Performance Section

- **1-year equity curve vs benchmark**: cumulative-return lines for the portfolio and benchmark, with total-return badges.
- **1-year monthly returns** (bar chart): absolute monthly returns; values are placed above/below the bars so they are clearly visible.
- **3-year annual returns** (bar chart): year-by-year returns plus a **3-year CAGR** badge.
  - CAGR formula: `(Ending Value / Starting Value) ^ (1 / years) − 1`
  - Implemented with the correct **252 trading days per year** annualization to avoid overstatement.

### 9.3 Risk Metrics Section
- Max drawdown (all-time / 1y), volatility (1y / 3y), Sharpe, Sortino, beta (1y / 3y).

### 9.4 Correlation Matrix
- A heatmap of the last-year daily-return correlations (−1 to +1) among all holdings, with both values and a color scale.

---

## 10. Data Sources & Caching

| Data | Source | Cache TTL |
|------|--------|-----------|
| Live quotes | Yahoo Finance (yfinance) | 1 hour |
| Historical K-lines | Yahoo Finance (yfinance) | 48 hours |
| Sector / industry | Yahoo Finance (yfinance) | 7 days |
| FX rates | Yahoo Finance FX | per quote cache |
| News / financials | Yahoo Finance | fetched on demand |

- Cache files live in `data_cache/` and can be cleared manually in **Settings**.
- Quotes are delayed (~15–20 min) and are for reference only; use broker quotes for actual trading.

---

## 11. Supported Instruments

| Market | Indices | Stock / ETF examples |
|--------|---------|----------------------|
| Taiwan (TW) | `^TWII` | `2330.TW` TSMC, `2317.TW` Hon Hai, `2454.TW` MediaTek, `0050.TW`, `0056.TW`, `00878.TW` |
| US | `^GSPC`, `^IXIC`, `^DJI` | `AAPL`, `MSFT`, `GOOGL`, `NVDA`, `TSLA`, `SPY`, `QQQ` |
| Hong Kong (HK) | `^HSI` | `0700.HK` Tencent, `9988.HK` Alibaba, `3690.HK` Meituan |
| China A (CN) | `000001.SS`, `399001.SZ` | `600519.SS` Kweichow Moutai, `000858.SZ` Wuliangye, `300750.SZ` CATL |
| Commodities | — | `GC=F` Gold, `CL=F` Crude Oil |
| FX | — | `USDTWD=X`, `USDCNY=X`, `USDHKD=X`, `USDJPY=X` |

> Instrument codes follow Yahoo Finance format. Custom instruments can also be added under "Symbols".

---

## 12. Notes & FAQ

1. **Internet is required** for the latest quotes; cached history can be viewed offline (within 48h).
2. **Quotes are delayed** (~15–20 min) and for reference only — not investment advice.
3. **Portfolio files** are at `data_cache/portfolios/*.json` — don't delete them; deleting the whole `data_cache` clears your portfolios.
4. **FX conversion** uses Yahoo rates and may differ slightly from broker rates.
5. If the window doesn't appear, open `http://127.0.0.1:8765` in a browser.
6. Up to **8 portfolios** can be created.
7. Python 3.10+ is recommended.
8. **UI language** can be switched under "Settings → Interface Language" (Traditional Chinese / Simplified Chinese / English); it applies immediately and is remembered automatically.

---

## License

This project is released under the **MIT License**. See the project's `LICENSE` file for the full terms (if not yet present, it means the code may be freely used, modified and distributed under MIT conventions).

---

<hr>
<p align="center">
  <strong><a href="#chinese-version">↑ Back to 繁體中文版</a></strong>
</p>
