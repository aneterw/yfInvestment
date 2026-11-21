"""
投資績效分析軟體 - 桌面版
使用 pywebview 打包成獨立 exe
"""
import sys
import os
import io
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np
import yfinance as yf
from loguru import logger

# 檢查 pywebview
try:
    import webview as pywebview
    HAS_WEBVIEW = True
except ImportError:
    HAS_WEBVIEW = False
    logger.error("pywebview 未安裝，請執行: pip install pywebview")
    sys.exit(1)

# 檢查 flask
try:
    from flask import Flask, jsonify, request, Response
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False
    logger.error("flask 未安裝，請執行: pip install flask")
    sys.exit(1)

# ========== 配置 ==========
ROOT = Path(__file__).parent
CACHE = ROOT / "data_cache"
CACHE.mkdir(exist_ok=True)
PORTFOLIO_DIR = CACHE / "portfolios"
PORTFOLIO_DIR.mkdir(exist_ok=True)
INDEX_FILE = ROOT / "Indexing.json"

# 使用絕對路徑確保 Flask 能找檔案
APP_DIR = Path(__file__).parent.resolve()
HTML_FILE = APP_DIR / "index.html"

THEME = {
    "bg": "#0f1419", "bg2": "#1a2332", "bg3": "#243044", "card": "#1e2a3a",
    "border": "#2d3e50", "text": "#e8eaf0", "text2": "#8b95a5", "muted": "#5c6775",
    "up": "#4ade80", "down": "#f87171", "accent": "#3b82f6", "gold": "#fbbf24",
    "purple": "#a78bfa", "cyan": "#22d3ee",
}

# ========== 多語系 (i18n) ==========
SUPPORTED_LANGS = ["zh-TW", "zh-CN", "en"]
SETTINGS_FILE = CACHE / "settings.json"


def load_settings() -> Dict[str, Any]:
    """讀取本機設定檔"""
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def save_settings(s: Dict[str, Any]) -> None:
    """寫入本機設定檔"""
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"儲存設定失敗: {e}")


def get_lang() -> str:
    """取得目前介面語言"""
    lang = load_settings().get("language", "zh-TW")
    return lang if lang in SUPPORTED_LANGS else "zh-TW"


def set_lang(lang: str) -> bool:
    """設定介面語言"""
    if lang not in SUPPORTED_LANGS:
        return False
    s = load_settings()
    s["language"] = lang
    save_settings(s)
    return True


# 翻譯表：(繁體中文, 简体中文, English)
# 長字串需在短字串之前比對（apply_lang 會依長度排序），避免錯誤的局部取代。
_UI_STRINGS = [
    # --- 應用程式/導覽 ---
    ("投資績效分析軟體", "投资绩效分析软件", "Investment Performance Analyzer"),
    ("資產總覽", "资产总览", "Asset Overview"),
    ("市場行情", "市场行情", "Market Quotes"),
    ("持倉管理", "持仓管理", "Portfolio Management"),
    ("績效分析", "绩效分析", "Performance"),
    ("歷史分析", "历史分析", "Historical Analysis"),
    ("標的管理", "标的管理", "Symbol Library"),
    ("標的庫管理", "标的管理", "Symbol Library"),
    ("報告匯出", "报告导出", "Report Export"),
    ("系統設置", "系统设置", "Settings"),
    ("刷新", "刷新", "Refresh"),
    ("就緒", "就绪", "Ready"),
    ("管理持倉 →", "管理持仓 →", "Manage →"),

    # --- 資產總覽頁 ---
    ("總資產價值", "总资产价值", "Total Assets"),
    ("總投入資金", "总投入资金", "Total Invested"),
    ("總損益", "总损益", "Total P&L"),
    ("持倉數", "持仓数", "Positions"),
    ("現金餘額", "现金余额", "Cash Balance"),
    ("持倉明細", "持仓明细", "Position Details"),
    ("投資組合可視圖", "投资组合可视图", "Portfolio Dashboard"),

    # --- 市場行情頁 ---
    ("報價資訊延遲至少15~20分鐘。所有資訊僅供參考，實際交易價格請以券商或交易所為準。",
     "报价信息延迟至少15~20分钟。所有信息仅供参考，实际交易价格请以券商或交易所为准。",
     "Quotes are delayed by at least 15-20 minutes. All information is for reference only; actual trading prices are subject to your broker or exchange."),
    ("3年貝塔", "3年贝塔", "3Y Beta"),
    ("3年夏普", "3年夏普", "3Y Sharpe"),
    ("3年索提諾", "3年索提诺", "3Y Sortino"),
    ("漲跌幅", "涨跌幅", "Change %"),
    ("漲跌", "涨跌", "Change"),

    # --- 持倉管理頁 ---
    ("🗑 刪除組合", "🗑 删除组合", "🗑 Delete Portfolio"),
    ("+ 新增組合", "+ 新增组合", "+ New Portfolio"),
    ("+ 新增標的", "+ 新增标的", "+ Add Symbol"),
    ("此組合尚無持倉", "此组合尚无持仓", "This portfolio has no positions"),
    ("尚無持倉，請點擊「新增標的」", "暂无持仓，请点击「新增标的」", "No positions yet. Click \"Add Symbol\"."),
    ("總資產", "总资产", "Total Assets"),
    ("總投入", "总投入", "Total Invested"),
    ("損益率", "损益率", "P&L %"),
    ("相關資訊", "相关信息", "Info"),

    # --- 績效分析頁 ---
    ("半年前至今", "半年前至今", "Since 6 months ago"),
    ("一年前至今", "一年前至今", "Since 1 year ago"),
    ("特定日期至今", "特定日期至今", "Since custom date"),
    ("選擇區間以顯示績效與 Benchmark 對比曲線", "选择区间以显示绩效与 Benchmark 对比曲线", "Select a range to show performance against the benchmark"),
    ("投資組合期間風險指標", "投资组合期间风险指标", "Portfolio Period Risk Metrics"),
    ("組合期間報酬", "组合期间报酬", "Portfolio Return"),
    ("Benchmark 報酬", "Benchmark 报酬", "Benchmark Return"),
    ("超額報酬", "超额报酬", "Excess Return"),
    ("期末總資產", "期末总资产", "Ending Value"),
    ("組合年化報酬", "组合年化报酬", "Annualized Return"),
    ("組合最大回撤", "组合最大回撤", "Max Drawdown"),
    ("組合波動率", "组合波动率", "Volatility"),
    ("統計區間", "统计区间", "Period"),
    ("1年貝塔比率", "1年贝塔比率", "1Y Beta"),
    ("3年貝塔比率", "3年贝塔比率", "3Y Beta"),
    ("1年夏普比率", "1年夏普比率", "1Y Sharpe"),
    ("3年夏普比率", "3年夏普比率", "3Y Sharpe"),
    ("1年索提諾比率", "1年索提诺比率", "1Y Sortino"),
    ("3年索提諾比率", "3年索提诺比率", "3Y Sortino"),
    ("1年貝塔(β)", "1年贝塔(β)", "1Y Beta (β)"),
    ("3年貝塔(β)", "3年贝塔(β)", "3Y Beta (β)"),
    ("基準指數", "基准指数", "Benchmark"),

    # --- 歷史分析頁 ---
    ("🔍 分析", "🔍 分析", "🔍 Analyze"),
    ("標的代碼", "标的代码", "Symbol"),
    ("選擇標的並點擊分析", "选择标的后点击分析", "Select a symbol and click Analyze"),
    ("無法獲取數據", "无法获取数据", "Failed to load data"),
    ("期間報酬", "期间报酬", "Period Return"),
    ("最高價", "最高价", "Highest"),
    ("最低價", "最低价", "Lowest"),
    ("最大回撤", "最大回撤", "Max Drawdown"),
    ("波動率", "波动率", "Volatility"),
    ("數據點", "数据点", "Data Points"),

    # --- 標的管理頁 ---
    ("加入持倉", "加入持仓", "Add to Portfolio"),
    ("請填寫代碼與名稱", "请填写代码与名称", "Please enter symbol and name"),
    ("確定刪除標的", "确定删除标的", "Delete symbol"),

    # --- 報告匯出頁 ---
    ("選擇組合與格式後匯出", "选择组合与格式后导出", "Select a portfolio and format to export"),
    ("請選擇投資組合", "请选择投资组合", "Please select a portfolio"),

    # --- 系統設置頁 ---
    ("語言", "语言", "Language"),
    ("介面語言", "界面语言", "Interface Language"),
    ("數據緩存", "数据缓存", "Data Cache"),
    ("清除緩存", "清除缓存", "Clear Cache"),
    ("查看狀態", "查看状态", "View Status"),
    ("手續費設定", "手续费设置", "Fee Settings"),
    ("買入手續費率 (%)", "买入手续费率 (%)", "Buy Fee Rate (%)"),
    ("賣出手續費率 (%)", "卖出手续费率 (%)", "Sell Fee Rate (%)"),
    ("交易稅率 (%)", "交易税率 (%)", "Tax Rate (%)"),
    ("關於", "关于", "About"),
    ("技術棧: Python + pywebview + yfinance", "技术栈: Python + pywebview + yfinance", "Stack: Python + pywebview + yfinance"),
    ("數據來源: Yahoo Finance", "数据来源: Yahoo Finance", "Data Source: Yahoo Finance"),
    ("所有數據存儲於本地", "所有数据存储于本地", "All data is stored locally"),

    # --- 模態框 ---
    ("新增投資組合", "新增投资组合", "New Portfolio"),
    ("新增組合模態框", "新增组合模态框", "New Portfolio"),
    ("新增標的模態框", "新增标的模态框", "Add Symbol"),
    ("新增標的庫模態框", "新增标的管理模态框", "Add Symbol"),
    ("相關資訊模態框", "相关信息模态框", "Information"),
    ("組合名稱", "组合名称", "Portfolio Name"),
    ("計價貨幣", "计价货币", "Base Currency"),
    ("基準指標", "基准指标", "Benchmark"),
    ("標的搜尋", "标的搜索", "Search"),
    ("輸入代碼或名稱搜尋...", "输入代码或名称搜索...", "Search by code or name..."),
    ("例：AAPL、2330.TW", "例：AAPL、2330.TW", "e.g. AAPL, 2330.TW"),
    ("例：蘋果", "例：苹果", "e.g. Apple"),
    ("類別", "类别", "Category"),
    ("貨幣", "货币", "Currency"),
    ("成本價", "成本价", "Cost Price"),
    ("持有數量", "持有数量", "Quantity"),
    ("現金金額", "现金金额", "Cash Amount"),
    ("輸入現金金額", "输入现金金额", "Enter cash amount"),
    ("現金將作為一項標的加入投資組合（無手續費、無損益）。", "现金将作为一项标的加入投资组合（无手续费、无损益）。", "Cash will be added as a position (no fees, no P&L)."),
    ("取消", "取消", "Cancel"),
    ("確認新增", "确认新增", "Confirm"),
    ("建立組合", "建立组合", "Create"),
    ("關閉", "关闭", "Close"),
    ("📊 基本面", "📊 基本面", "📊 Fundamentals"),
    ("📈 技術圖", "📈 技术图", "📈 Technicals"),
    ("📰 相關新聞", "📰 相关新闻", "📰 News"),
    ("基本面", "基本面", "Fundamentals"),
    ("技術圖", "技术图", "Technicals"),
    ("相關新聞", "相关新闻", "News"),
    ("台股加權指數", "台股加权指数", "TAIEX"),
    ("標普500", "标普500", "S&P 500"),
    ("納斯達克", "纳斯达克", "NASDAQ"),
    ("恆生指數", "恒生指数", "Hang Seng"),
    ("上證指數", "上证指数", "SSE Composite"),
    ("SPY ETF", "SPY ETF", "SPY ETF"),

    # --- 通用表格標題 ---
    ("標的", "标的", "Symbol"),
    ("代碼", "代码", "Code"),
    ("名稱", "名称", "Name"),
    ("成本", "成本", "Cost"),
    ("數量", "数量", "Qty"),
    ("現價", "现价", "Price"),
    ("總成本", "总成本", "Total Cost"),
    ("淨市值", "净市值", "Net Value"),
    ("市值", "市值", "Market Value"),
    ("損益", "损益", "P&L"),
    ("權重", "权重", "Weight"),
    ("操作", "操作", "Actions"),
    ("刪除", "删除", "Delete"),
    ("類型", "类型", "Type"),
    ("格式", "格式", "Format"),
    ("期間", "期间", "Period"),
    ("投資組合", "投资组合", "Portfolio"),
    ("無資料", "无资料", "N/A"),
    ("無數據", "无数据", "No data"),
    ("載入中...", "加载中...", "Loading..."),
    ("載入中", "加载中", "Loading"),
    ("數據不足", "数据不足", "Insufficient data"),
    ("區間內數據不足", "区间内数据不足", "Insufficient data in range"),
    ("未知錯誤", "未知错误", "Unknown error"),
    ("載入失敗", "加载失败", "Load failed"),
    ("新增失敗", "新增失败", "Add failed"),
    ("建立失敗", "创建失败", "Create failed"),
    ("刪除失敗", "删除失败", "Delete failed"),
    ("匯出失敗", "导出失败", "Export failed"),
    ("已匯出: ", "已导出: ", "Exported: "),
    ("尚無投資組合", "暂无投资组合", "No portfolio"),
    ("暫無投資組合", "暂无投资组合", "No portfolio"),
    ("請先建立投資組合", "请先创建投资组合", "Please create a portfolio first"),
    ("尚無投資組合可刪除", "暂无投资组合可删除", "No portfolio to delete"),

    # --- 通知/確認對話框 ---
    ("確定刪除此投資組合？此操作無法復原。", "确定删除此投资组合？此操作无法恢复。", "Delete this portfolio? This cannot be undone."),
    ("確定刪除此持倉？", "确定删除此持仓？", "Delete this position?"),
    ("確定刪除標的", "确定删除标的", "Delete symbol"),
    ("確定清除緩存？", "确定清除缓存？", "Clear cache?"),
    ("緩存已清除", "缓存已清除", "Cache cleared"),
    ("請輸入現金金額", "请输入现金金额", "Please enter a cash amount"),
    ("請填寫完整資訊", "请填写完整信息", "Please fill in all required fields"),
    ("請輸入標的代碼", "请输入标的代码", "Please enter a symbol code"),
    ("請選擇統計起始日期", "请选择统计起始日期", "Please select a start date"),
    ("提款", "提款", "Withdraw"),

    # --- 技術圖 ---
    ("無法載入圖表庫（需網路）", "无法加载图表库（需网络）", "Unable to load chart library (network required)"),
    ("日線", "日线", "Daily"),
    ("週線", "周线", "Weekly"),
    ("月線", "月线", "Monthly"),
    ("無技術數據", "无技术数据", "No technical data"),
    ("滑鼠移至圖表查看 開高低收、成交量、KD/MACD、MA5/MA20", "鼠标移至图表查看 开高低收、成交量、KD/MACD、MA5/MA20", "Hover the chart to view OHLC, volume, KD/MACD, MA5/MA20"),
    ("載入基本面資料...", "加载基本面资料...", "Loading fundamentals..."),
    ("載入新聞...", "加载新闻...", "Loading news..."),
    ("暫無相關新聞", "暂无相关新闻", "No related news"),
    ("財報季度", "财报季度", "Report Period"),

    # --- 儀表板 (DASHBOARD_JS) ---
    ("資產類別配置", "资产类别配置", "Asset Allocation"),
    ("市場區域配置", "市场区域配置", "Region Allocation"),
    ("股票產業配置", "股票行业配置", "Sector Allocation"),
    ("前五大持股權重", "前五大持股权重", "Top 5 Holdings"),
    ("近一年績效曲線 vs ", "近一年绩效曲线 vs ", "1Y Performance vs "),
    ("近一年每月報酬（絕對）", "近一年每月报酬（绝对）", "Monthly Returns (1Y)"),
    ("近三年年度報酬", "近三年年度报酬", "Annual Returns (3Y)"),
    ("3年CAGR ", "3年CAGR ", "3Y CAGR "),
    ("組合 ", "组合 ", "Portfolio "),
    ("基準 ", "基准 ", "Benchmark "),
    ("風險指標（最大回撤 / 波動 / 夏普 / 索提諾 / 貝塔）", "风险指标（最大回撤 / 波动 / 夏普 / 索提诺 / 贝塔）", "Risk Metrics (Max DD / Volatility / Sharpe / Sortino / Beta)"),
    ("資產相關性矩陣（近一年日報酬）", "资产相关性矩阵（近一年日回报）", "Asset Correlation Matrix (1Y daily returns)"),
    ("最大回撤（全期）", "最大回撤（全期）", "Max Drawdown (All)"),
    ("最大回撤（近1年）", "最大回撤（近1年）", "Max Drawdown (1Y)"),
    ("波動率（1年）", "波动率（1年）", "Volatility (1Y)"),
    ("波動率（3年）", "波动率（3年）", "Volatility (3Y)"),
    ("夏普（1年）", "夏普（1年）", "Sharpe (1Y)"),
    ("夏普（3年）", "夏普（3年）", "Sharpe (3Y)"),
    ("索提諾（1年）", "索提诺（1年）", "Sortino (1Y)"),
    ("索提諾（3年）", "索提诺（3年）", "Sortino (3Y)"),
    ("貝塔（1年）", "贝塔（1年）", "Beta (1Y)"),
    ("貝塔（3年）", "贝塔（3年）", "Beta (3Y)"),
    ("需至少 2 檔標的才能計算相關性", "需至少 2 个标的才能计算相关性", "At least 2 symbols are required to compute correlation"),
    ("無足夠數據計算投資組合可視圖", "无足够数据计算投资组合可视图", "Not enough data to compute the portfolio dashboard"),

    # --- 英文/簡體 標籤列（保持一致的短標籤）---
    ("全部", "全部", "All"),
    ("股票", "股票", "Stocks"),
    ("商品", "商品", "Commodities"),
    ("匯率", "汇率", "FX"),
    ("指數", "指数", "Indices"),
    ("績效指標", "绩效指标", "Metrics"),
    ("基準指數", "基准指数", "Benchmark"),
    ("基準", "基准", "Benchmark"),
    ("現金", "现金", "Cash"),

    # --- 基本面 (get_fundamental) ---
    ("估值指標", "估值指标", "Valuation"),
    ("獲利指標", "获利指标", "Profitability"),
    ("殖利率與風險", "股息率与风险", "Yield & Risk"),
    ("52 週區間", "52 周区间", "52-Week Range"),
    ("現金流", "现金流", "Cash Flow"),
    ("營收與成長", "营收与成长", "Revenue & Growth"),
    ("分析師與持股", "分析师与持股", "Analysts & Ownership"),
    ("總市值", "总市值", "Market Cap"),
    ("本益比 (PE)", "市盈率 (PE)", "P/E"),
    ("預期本益比 (Forward PE)", "预期市盈率 (Forward PE)", "Forward P/E"),
    ("本益成長比 (PEG)", "市盈增长比 (PEG)", "PEG"),
    ("股價淨值比 (PB)", "股价净值比 (PB)", "P/B"),
    ("資產報酬率 (ROA)", "资产报酬率 (ROA)", "ROA"),
    ("股東權益報酬率 (ROE)", "股东权益报酬率 (ROE)", "ROE"),
    ("營業利潤率", "营业利润率", "Operating Margin"),
    ("純利潤率", "纯利润率", "Net Margin"),
    ("每股盈餘 (EPS)", "每股盈余 (EPS)", "EPS"),
    ("現金殖利率", "现金股息率", "Dividend Yield"),
    ("FCF 殖利率", "FCF 股息率", "FCF Yield"),
    ("放空比例", "放空比例", "Short % of Float"),
    ("貝他值 (Beta)", "贝他值 (Beta)", "Beta"),
    ("速動比率", "速动比率", "Quick Ratio"),
    ("52 週高點", "52 周高点", "52-Week High"),
    ("52 週低點", "52 周低点", "52-Week Low"),
    ("區間位置", "区间位置", "Range Position"),
    ("自由現金流 (FCF)", "自由现金流 (FCF)", "Free Cash Flow"),
    ("營業現金流 (OCF)", "营业现金流 (OCF)", "Operating Cash Flow"),
    ("FCF 股利覆蓋倍數", "FCF 股利覆盖倍数", "FCF Dividend Cover"),
    ("單季總營收", "单季总营收", "Quarterly Revenue"),
    ("總現金", "总现金", "Total Cash"),
    ("總負債", "总负债", "Total Debt"),
    ("營收年成長率", "营收年成长率", "Revenue Growth (YoY)"),
    ("盈餘年成長率", "盈余年成长率", "Earnings Growth (YoY)"),
    ("分析師平均目標價", "分析师平均目标价", "Avg Target Price"),
    ("分析師中位目標價", "分析师中位目标价", "Median Target Price"),
    ("分析師人數", "分析师人数", "# Analysts"),
    ("券商推薦均值", "券商推荐均值", "Analyst Rating"),
    ("內部人持股", "内部人持股", "Insider Ownership"),
    ("機構持股", "机构持股", "Institutional Ownership"),
    ("無法獲取基本面資料", "无法获取基本面资料", "Failed to load fundamentals"),
    ("無法獲取技術數據", "无法获取技术数据", "Failed to load technical data"),
]

# 建構 lang -> {繁: 目標} 對照表
_I18N_MAP: Dict[str, Dict[str, str]] = {}
for _tw, _sc, _en in _UI_STRINGS:
    _I18N_MAP.setdefault("zh-CN", {})[_tw] = _sc
    _I18N_MAP.setdefault("en", {})[_tw] = _en


def apply_lang(text: str, lang: str = None) -> str:
    """將整段文字（HTML / JS / API 回應）由繁體中文字串翻譯為目標語言"""
    lang = lang or get_lang()
    if lang == "zh-TW":
        return text
    mapping = _I18N_MAP.get(lang, {})
    if not mapping:
        return text
    for tw in sorted(mapping.keys(), key=len, reverse=True):
        text = text.replace(tw, mapping[tw])
    return text


def _t(s: str, lang: str = None) -> str:
    """翻譯單一字串"""
    return apply_lang(s, lang)

# 全局標的字典
_symbols: Dict[str, Dict] = {
    "^TWII": {"symbol": "^TWII", "name": "台股加權指數", "category": "INDEX", "currency": "TWD"},
    "2330.TW": {"symbol": "2330.TW", "name": "台積電", "category": "STOCK", "currency": "TWD"},
    "2317.TW": {"symbol": "2317.TW", "name": "鴻海", "category": "STOCK", "currency": "TWD"},
    "2454.TW": {"symbol": "2454.TW", "name": "聯發科", "category": "STOCK", "currency": "TWD"},
    "1301.TW": {"symbol": "1301.TW", "name": "台塑", "category": "STOCK", "currency": "TWD"},
    "2881.TW": {"symbol": "2881.TW", "name": "富邦金", "category": "STOCK", "currency": "TWD"},
    "2882.TW": {"symbol": "2882.TW", "name": "國泰金", "category": "STOCK", "currency": "TWD"},
    "2412.TW": {"symbol": "2412.TW", "name": "中華電", "category": "STOCK", "currency": "TWD"},
    "3008.TW": {"symbol": "3008.TW", "name": "大立光", "category": "STOCK", "currency": "TWD"},
    "2303.TW": {"symbol": "2303.TW", "name": "聯電", "category": "STOCK", "currency": "TWD"},
    "3711.TW": {"symbol": "3711.TW", "name": "日月光投控", "category": "STOCK", "currency": "TWD"},
    "0050.TW": {"symbol": "0050.TW", "name": "元大台灣50", "category": "ETF", "currency": "TWD"},
    "0056.TW": {"symbol": "0056.TW", "name": "元大高股息", "category": "ETF", "currency": "TWD"},
    "00878.TW": {"symbol": "00878.TW", "name": "國泰永續高股息", "category": "ETF", "currency": "TWD"},
    "AAPL": {"symbol": "AAPL", "name": "蘋果", "category": "STOCK", "currency": "USD"},
    "MSFT": {"symbol": "MSFT", "name": "微軟", "category": "STOCK", "currency": "USD"},
    "GOOGL": {"symbol": "GOOGL", "name": "Alphabet", "category": "STOCK", "currency": "USD"},
    "AMZN": {"symbol": "AMZN", "name": "亞馬遜", "category": "STOCK", "currency": "USD"},
    "NVDA": {"symbol": "NVDA", "name": "輝達", "category": "STOCK", "currency": "USD"},
    "TSLA": {"symbol": "TSLA", "name": "特斯拉", "category": "STOCK", "currency": "USD"},
    "META": {"symbol": "META", "name": "Meta", "category": "STOCK", "currency": "USD"},
    "JPM": {"symbol": "JPM", "name": "摩根大通", "category": "STOCK", "currency": "USD"},
    "SPY": {"symbol": "SPY", "name": "SPDR標普500", "category": "ETF", "currency": "USD"},
    "QQQ": {"symbol": "QQQ", "name": "Invesco QQQ", "category": "ETF", "currency": "USD"},
    "^GSPC": {"symbol": "^GSPC", "name": "標普500指數", "category": "INDEX", "currency": "USD"},
    "^IXIC": {"symbol": "^IXIC", "name": "納斯達克", "category": "INDEX", "currency": "USD"},
    "^DJI": {"symbol": "^DJI", "name": "道瓊工業", "category": "INDEX", "currency": "USD"},
    "0700.HK": {"symbol": "0700.HK", "name": "騰訊控股", "category": "STOCK", "currency": "HKD"},
    "9988.HK": {"symbol": "9988.HK", "name": "阿里巴巴", "category": "STOCK", "currency": "HKD"},
    "3690.HK": {"symbol": "3690.HK", "name": "美團", "category": "STOCK", "currency": "HKD"},
    "1810.HK": {"symbol": "1810.HK", "name": "小米集團", "category": "STOCK", "currency": "HKD"},
    "0939.HK": {"symbol": "0939.HK", "name": "建設銀行", "category": "STOCK", "currency": "HKD"},
    "0941.HK": {"symbol": "0941.HK", "name": "中國移動", "category": "STOCK", "currency": "HKD"},
    "^HSI": {"symbol": "^HSI", "name": "恆生指數", "category": "INDEX", "currency": "HKD"},
    "600519.SS": {"symbol": "600519.SS", "name": "貴州茅台", "category": "STOCK", "currency": "CNY"},
    "000858.SZ": {"symbol": "000858.SZ", "name": "五糧液", "category": "STOCK", "currency": "CNY"},
    "601318.SS": {"symbol": "601318.SS", "name": "中國平安", "category": "STOCK", "currency": "CNY"},
    "600036.SS": {"symbol": "600036.SS", "name": "招商銀行", "category": "STOCK", "currency": "CNY"},
    "000333.SZ": {"symbol": "000333.SZ", "name": "美的集團", "category": "STOCK", "currency": "CNY"},
    "300750.SZ": {"symbol": "300750.SZ", "name": "寧德時代", "category": "STOCK", "currency": "CNY"},
    "000001.SS": {"symbol": "000001.SS", "name": "上證指數", "category": "INDEX", "currency": "CNY"},
    "399001.SZ": {"symbol": "399001.SZ", "name": "深證成指", "category": "INDEX", "currency": "CNY"},
    "GC=F": {"symbol": "GC=F", "name": "黃金期貨", "category": "COMMODITY", "currency": "USD"},
    "CL=F": {"symbol": "CL=F", "name": "原油期貨WTI", "category": "COMMODITY", "currency": "USD"},
    "BZ=F": {"symbol": "BZ=F", "name": "布倫特原油", "category": "COMMODITY", "currency": "USD"},
    "USDTWD=X": {"symbol": "USDTWD=X", "name": "美元/台幣", "category": "FX", "currency": "TWD"},
    "USDCNY=X": {"symbol": "USDCNY=X", "name": "美元/人民幣", "category": "FX", "currency": "CNY"},
    "USDHKD=X": {"symbol": "USDHKD=X", "name": "美元/港幣", "category": "FX", "currency": "HKD"},
    "USDJPY=X": {"symbol": "USDJPY=X", "name": "美元/日圓", "category": "FX", "currency": "JPY"},
}

if INDEX_FILE.exists():
    try:
        with open(INDEX_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for item in data.get("symbols", []):
            _symbols[item["symbol"]] = item
    except:
        pass

CUSTOM_SYMBOLS_FILE = ROOT / "custom_symbols.json"
if CUSTOM_SYMBOLS_FILE.exists():
    try:
        with open(CUSTOM_SYMBOLS_FILE, 'r', encoding='utf-8') as f:
            for item in json.load(f):
                _symbols[item["symbol"]] = item
    except:
        pass


def _save_symbols() -> None:
    try:
        with open(CUSTOM_SYMBOLS_FILE, 'w', encoding='utf-8') as f:
            json.dump(list(_symbols.values()), f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"儲存標的失敗: {e}")


# ========== 緩存管理 ==========
class Cache:
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, symbol: str, key: str) -> Path:
        safe = symbol.replace("/", "_").replace("^", "").replace(".", "_")
        return self.cache_dir / f"{safe}_{key}.json"

    def get(self, symbol: str, key: str, ttl_hours: int = 24) -> Optional[Any]:
        path = self._path(symbol, key)
        if not path.exists():
            return None
        if datetime.now() - datetime.fromtimestamp(path.stat().st_mtime) > timedelta(hours=ttl_hours):
            path.unlink(missing_ok=True)
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return None

    def set(self, symbol: str, key: str, data: Any) -> None:
        try:
            with open(self._path(symbol, key), 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"寫入緩存失敗: {e}")

    def clear(self, symbol: str = None, key: str = None) -> int:
        deleted = 0
        for f in self.cache_dir.glob("*.json"):
            if symbol and symbol.replace("/", "_") not in f.stem:
                continue
            if key and key not in f.stem:
                continue
            f.unlink(missing_ok=True)
            deleted += 1
        return deleted

    def count(self) -> int:
        return len(list(self.cache_dir.glob("*.json")))


cache = Cache(CACHE)


# ========== 數據獲取 ==========
class Fetcher:
    def get_quote(self, symbol: str) -> Optional[Dict]:
        cached = cache.get(symbol, "quote", ttl_hours=1)
        if cached:
            return cached
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            current = info.get('currentPrice') or info.get('regularMarketPrice') or 0
            prev = info.get('previousClose') or info.get('regularMarketPreviousClose') or 0
            change = current - prev if current and prev else 0
            change_pct = (change / prev * 100) if prev else 0
            quote = {
                "symbol": symbol,
                "name": info.get('shortName') or info.get('longName') or symbol,
                "price": float(current or 0),
                "open": float(info.get('open') or info.get('regularMarketOpen') or 0),
                "high": float(info.get('dayHigh') or info.get('regularMarketDayHigh') or 0),
                "low": float(info.get('dayLow') or info.get('regularMarketDayLow') or 0),
                "previous_close": float(prev or 0),
                "change": float(change),
                "change_pct": float(change_pct),
                "volume": int(info.get('volume') or info.get('regularMarketVolume') or 0),
                "market_cap": info.get('marketCap'),
                "pe_ratio": info.get('trailingPE') or info.get('forwardPE'),
                "eps": info.get('trailingEps'),
                "dividend_yield": info.get('dividendYield'),
                "beta": info.get('beta'),
                "currency": info.get('currency', 'USD'),
                "sector": info.get('sector'),
                "industry": info.get('industry'),
                "timestamp": datetime.now().isoformat(),
            }
            cache.set(symbol, "quote", quote)
            return quote
        except Exception as e:
            logger.error(f"獲取報價失敗 {symbol}: {e}")
            return None

    def get_sector(self, symbol: str) -> Dict:
        """取得標的的產業分類（sector / industry），獨立快取 7 天"""
        cached = cache.get(symbol, "sector", ttl_hours=24 * 7)
        if cached:
            return cached
        try:
            info = yf.Ticker(symbol).info
            out = {"symbol": symbol, "sector": info.get('sector'), "industry": info.get('industry')}
        except Exception as e:
            logger.error(f"獲取產業分類失敗 {symbol}: {e}")
            out = {"symbol": symbol, "sector": None, "industry": None}
        cache.set(symbol, "sector", out)
        return out

    def get_history(self, symbol: str, period: str = "1y", interval: str = "1d") -> Optional[pd.DataFrame]:
        cache_key = f"hist_{period}_{interval}"
        cached = cache.get(symbol, cache_key, ttl_hours=48)
        if cached:
            df = pd.DataFrame(cached)
            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)
            return df
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            if df.empty:
                return None
            df = df.reset_index()
            df['Date'] = df['Date'].dt.strftime('%Y-%m-%d %H:%M:%S')
            result = df.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'})
            result = result[['Date', 'open', 'high', 'low', 'close', 'volume']]
            cache.set(symbol, cache_key, result.to_dict('records'))
            return result.set_index('Date')
        except Exception as e:
            logger.error(f"獲取歷史數據失敗 {symbol}: {e}")
            return None


fetcher = Fetcher()


# ========== 績效計算 ==========
def get_fx_rate(from_ccy: str, to_ccy: str) -> float:
    """取得 from_ccy -> to_ccy 匯率，相同幣別或失敗時回傳 1.0"""
    if not from_ccy or not to_ccy or from_ccy.upper() == to_ccy.upper():
        return 1.0
    pair = f"{from_ccy.upper()}{to_ccy.upper()}=X"
    try:
        q = fetcher.get_quote(pair)
        price = q.get("price") if q else None
        return float(price) if price else 1.0
    except Exception as e:
        logger.error(f"獲取匯率失敗 {pair}: {e}")
        return 1.0


def calc_position_pnl(pos: Dict, current_price: float, fx: float = 1.0) -> Dict:
    cost = pos["cost_price"] * pos["quantity"]
    buy_fee = cost * pos.get("buy_fee_rate", 0.001425)
    total_cost = cost + buy_fee
    market_val = current_price * pos["quantity"]
    sell_fee = market_val * pos.get("sell_fee_rate", 0.001425)
    tax = market_val * pos.get("tax_rate", 0.003)
    net_market = market_val - sell_fee - tax
    total_cost_base = total_cost * fx
    net_market_base = net_market * fx
    pnl_base = net_market_base - total_cost_base
    pnl_pct = (pnl_base / total_cost_base * 100) if total_cost_base > 0 else 0
    breakeven = total_cost / pos["quantity"] / (1 - pos.get("sell_fee_rate", 0) - pos.get("tax_rate", 0)) \
        if pos["quantity"] > 0 and (1 - pos.get("sell_fee_rate", 0) - pos.get("tax_rate", 0)) > 0 \
        else total_cost / pos["quantity"] if pos["quantity"] > 0 else 0
    return {
        "id": pos.get("id", ""), "symbol": pos["symbol"], "name": pos["name"],
        "cost_price": pos["cost_price"], "quantity": pos["quantity"],
        "total_cost": total_cost_base, "market_value": market_val * fx,
        "net_market_value": net_market_base, "pnl": pnl_base, "pnl_pct": pnl_pct,
        "current_price": current_price * fx, "base_price": current_price,
        "fx": fx, "breakeven": breakeven, "weight": 0,
    }


def calc_portfolio_perf(portfolio: Dict, quotes: Dict[str, Dict]) -> Dict:
    if not portfolio:
        return {}
    positions = portfolio.get("positions", [])
    cash = portfolio.get("cash_balance", 0)
    base_currency = portfolio.get("base_currency", "TWD")
    has_cash_pos = any(p.get("symbol") == "CASH" for p in positions)
    if has_cash_pos:
        cash = 0.0  # 現金已以 CASH 持倉計入市值，避免重複計算
    results = []
    total_cost = total_market = total_pnl = 0.0
    for pos in positions:
        q = quotes.get(pos["symbol"], {})
        price = q.get("price", pos.get("current_price", pos["cost_price"]))
        sym_ccy = q.get("currency") or pos.get("currency") or base_currency
        fx = get_fx_rate(sym_ccy, base_currency)
        r = calc_position_pnl(pos, price, fx=fx)
        r["currency"] = sym_ccy
        r["base_currency"] = base_currency
        results.append(r)
        total_cost += r["total_cost"]
        total_market += r["net_market_value"]
        total_pnl += r["pnl"]
    cash_display = cash + sum(r["net_market_value"] for r in results if r["symbol"] == "CASH")
    total_value = total_market + cash
    total_invested = total_cost + cash
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0
    for r in results:
        r["weight"] = (r["net_market_value"] / total_value * 100) if total_value > 0 else 0
    return {
        "name": portfolio.get("name", "投資組合"), "base_currency": base_currency,
        "total_invested": total_invested, "total_value": total_value,
        "total_pnl": total_pnl, "total_pnl_pct": total_pnl_pct,
        "cash_balance": cash_display, "position_count": len(results),
        "positions": results, "updated_at": datetime.now().isoformat(),
    }


def calc_max_drawdown(prices: List[float]) -> float:
    if len(prices) < 2: return 0.0
    peak = prices[0]; max_dd = 0.0
    for p in prices:
        if p > peak: peak = p
        dd = (p - peak) / peak * 100
        if dd < max_dd: max_dd = dd
    return max_dd


def calc_volatility(prices: List[float]) -> float:
    if len(prices) < 2: return 0.0
    returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
    avg = sum(returns) / len(returns)
    var = sum((r - avg) ** 2 for r in returns) / (len(returns) - 1)
    return (var ** 0.5) * (252 ** 0.5) * 100


RISK_FREE_RATE = 0.02  # 年化無風險利率


def _pick_benchmark(symbol: str) -> str:
    """依標的挑選對應市場指數作為基準（台股→加權、美股→S&P500、港股→恆生、A股→上證、期貨→商品指數、匯率→美元指數）"""
    up = (symbol or "").upper()
    if up.endswith("=F"):
        return "^SPGSCI"
    if up.endswith("=X"):
        return "DX-Y.NYB"
    if ".TW" in up:
        return "^TWII"
    if ".HK" in up:
        return "^HSI"
    if up.endswith(".SS") or up.endswith(".SZ"):
        return "000001.SS"
    return "^GSPC"


def _ratios_from_returns(rs, rm) -> dict:
    """由對齊後的報酬率序列計算 1年/3年 Beta、夏普、索提諾比率"""
    sqrt252 = 252 ** 0.5
    out = {}
    for years in (1, 3):
        n = int(years * 252)
        rsw = rs.iloc[-n:]
        rmw = rm.iloc[-n:]
        if len(rsw) < 60:
            out[f"beta_{years}y"] = None
            out[f"sharpe_{years}y"] = None
            out[f"sortino_{years}y"] = None
            continue
        var_m = rmw.var(ddof=1)
        beta = rsw.cov(rmw) / var_m if var_m > 0 else None
        ann_ret = rsw.mean() * 252
        ann_vol = rsw.std(ddof=1) * sqrt252
        sharpe = (ann_ret - RISK_FREE_RATE) / ann_vol if ann_vol > 0 else None
        neg = rsw[rsw < 0]
        downside_ann = (neg ** 2).mean() ** 0.5 * sqrt252 if len(neg) else 0.0
        sortino = (ann_ret - RISK_FREE_RATE) / downside_ann if downside_ann > 0 else None
        out[f"beta_{years}y"] = round(beta, 2) if beta is not None else None
        out[f"sharpe_{years}y"] = round(sharpe, 2) if sharpe is not None else None
        out[f"sortino_{years}y"] = round(sortino, 2) if sortino is not None else None
    return out


def compute_risk_ratios(symbol: str) -> Optional[dict]:
    """計算 1年/3年 的 Beta、夏普比率、索提諾比率（相對於基準指數）"""
    bench = _pick_benchmark(symbol)
    sdf = fetcher.get_history(symbol, period="5y", interval="1d")
    bdf = fetcher.get_history(bench, period="5y", interval="1d")
    if sdf is None or bdf is None or sdf.empty or bdf.empty:
        return None
    idx = sdf.index.intersection(bdf.index)
    if len(idx) < 60:
        return None
    rs = sdf.loc[idx, "close"].pct_change().dropna()
    rm = bdf.loc[idx, "close"].pct_change().dropna()
    idx = rs.index.intersection(rm.index)
    rs, rm = rs.loc[idx], rm.loc[idx]
    if len(rs) < 60:
        return None
    out = {"benchmark": bench}
    out.update(_ratios_from_returns(rs, rm))
    return out


def compute_portfolio_risk_ratios(portfolio: Dict) -> Optional[dict]:
    """計算投資組合 1年/3年 的 Beta、夏普比率、索提諾比率（相對於組合基準指數）"""
    try:
        pid = portfolio.get("id", "pf")
        base_currency = portfolio.get("base_currency", "TWD")
        benchmark = portfolio.get("benchmark", "^TWII")
        positions = [p for p in portfolio.get("positions", [])
                     if p.get("symbol") and p["symbol"] != "CASH"]
        if not positions:
            return None

        sym_closes = {}
        for pos in positions:
            sym = pos["symbol"]
            df = fetcher.get_history(sym, period="5y", interval="1d")
            if df is None or df.empty:
                continue
            series = {}
            for d, close in df["close"].items():
                series[str(d)[:10]] = float(close)
            if series:
                sym_closes[sym] = series

        bench_closes = {}
        bench_df = fetcher.get_history(benchmark, period="5y", interval="1d")
        if bench_df is not None and not bench_df.empty:
            for d, close in bench_df["close"].items():
                bench_closes[str(d)[:10]] = float(close)

        if not sym_closes or len(bench_closes) < 60:
            return None

        fx_map = {}
        for pos in positions:
            sym = pos["symbol"]
            q = fetcher.get_quote(sym) or {}
            sym_ccy = q.get("currency") or pos.get("currency") or base_currency
            fx_map[sym] = get_fx_rate(sym_ccy, base_currency)

        all_dates = set(bench_closes.keys())
        for s in sym_closes.values():
            all_dates.update(s.keys())
        dates = sorted(all_dates)
        if len(dates) < 60:
            return None

        qty_map = {p["symbol"]: float(p["quantity"]) for p in positions}
        value_series = []
        fwd_vals = {}
        for d in dates:
            total = 0.0
            for sym, closes in sym_closes.items():
                v = closes.get(d)
                if v is None:
                    if sym not in fwd_vals:
                        continue
                    v = fwd_vals[sym]
                else:
                    fwd_vals[sym] = v
                total += v * qty_map[sym] * fx_map.get(sym, 1.0)
            if total <= 0:
                return None
            value_series.append(total)

        start_idx = 0
        while start_idx < len(value_series):
            if value_series[start_idx] > 0:
                break
            start_idx += 1
        if start_idx >= len(value_series):
            return None
        dates = dates[start_idx:]
        value_series = value_series[start_idx:]
        if len(dates) < 60:
            return None

        bench_series = [bench_closes.get(d) for d in dates]
        bench_vals = []
        last = None
        for b in bench_series:
            if b is None:
                bench_vals.append(last)
            else:
                last = b
                bench_vals.append(last)
        if any(b is None for b in bench_vals[:1]):
            return None

        import pandas as pd
        pidx = pd.Index(dates)
        rs = pd.Series(value_series, index=pidx).pct_change().dropna()
        rm = pd.Series(bench_vals, index=pidx).pct_change().dropna()
        idx = rs.index.intersection(rm.index)
        rs, rm = rs.loc[idx], rm.loc[idx]
        if len(rs) < 60:
            return None
        out = {"benchmark": benchmark, "pid": pid}
        out.update(_ratios_from_returns(rs, rm))
        return out
    except Exception as e:
        logger.error(f"計算組合風險指標失敗 {pid}: {e}")
        return None


_RISK_RATIO_TTL = 24 * 7  # 個股風險指標緩存 7 天


def _ratio_cache_valid(symbol: str, cached: dict) -> bool:
    """緩存有效：基準指數未變（避免基準修改後回傳舊值）"""
    return bool(cached) and cached.get("benchmark") == _pick_benchmark(symbol)


def compute_risk_ratios_cached(symbol: str) -> Optional[dict]:
    """帶緩存的個股風險指標（市場行情頁使用），TTL 7 天"""
    cached = cache.get(symbol, "risk_ratios", ttl_hours=_RISK_RATIO_TTL)
    if _ratio_cache_valid(symbol, cached):
        return cached
    ratios = compute_risk_ratios(symbol)
    if ratios is None:
        return None
    cache.set(symbol, "risk_ratios", ratios)
    return ratios


def _single_ratio_3y(symbol: str) -> Optional[dict]:
    cached = cache.get(symbol, "risk_ratios", ttl_hours=_RISK_RATIO_TTL)
    if _ratio_cache_valid(symbol, cached):
        return {k: cached.get(k) for k in ("beta_3y", "sharpe_3y", "sortino_3y")}
    ratios = compute_risk_ratios(symbol)
    if ratios is None:
        return None
    cache.set(symbol, "risk_ratios", ratios)
    return {k: ratios.get(k) for k in ("beta_3y", "sharpe_3y", "sortino_3y")}


def compute_market_risk_ratios(symbols: List[str]) -> Dict[str, dict]:
    """批量計算市場行情頁的 3年 貝塔/夏普/索提諾（並行、帶緩存）"""
    out: Dict[str, dict] = {}
    todo = []
    for s in symbols:
        cached = cache.get(s, "risk_ratios", ttl_hours=_RISK_RATIO_TTL)
        if _ratio_cache_valid(s, cached):
            out[s] = {k: cached.get(k) for k in ("beta_3y", "sharpe_3y", "sortino_3y")}
        else:
            todo.append(s)
    if todo:
        with ThreadPoolExecutor(max_workers=6) as ex:
            results = list(ex.map(_single_ratio_3y, todo))
        for s, ratios in zip(todo, results):
            if ratios:
                out[s] = ratios
    return out


_PERF_RANGE_CACHE = {}  # (pid, start_date) -> (timestamp, result)


def _resolve_perf_start(period: str, start_date: str = "") -> str:
    """解析統計起點日期：特定日期 / 一年前 / 半年前"""
    if start_date:
        return start_date[:10]
    today = datetime.now()
    if period == "1y":
        return (today - timedelta(days=365)).strftime("%Y-%m-%d")
    return (today - timedelta(days=180)).strftime("%Y-%m-%d")


def _fetch_period_for(start: str) -> str:
    """依統計起點決定 yfinance 需拉取的期間，確保能涵蓋起點之前的歷史"""
    try:
        days = (datetime.now() - datetime.strptime(start, "%Y-%m-%d")).days
    except Exception:
        return "1y"
    if days <= 180:
        return "6mo"
    if days <= 365:
        return "1y"
    if days <= 730:
        return "2y"
    if days <= 1825:
        return "5y"
    if days <= 3650:
        return "10y"
    return "max"


def build_performance_range(portfolio: Dict, period: str = "6m", start_date: str = "") -> Dict:
    """計算區間績效：組合與 benchmark 從統計開始點起的累計報酬率曲線與統計指標"""
    try:
        pid = portfolio.get("id", "pf")
        base_currency = portfolio.get("base_currency", "TWD")
        benchmark = portfolio.get("benchmark", "^TWII")
        start = _resolve_perf_start(period, start_date)
        ckey = (pid, start)
        if ckey in _PERF_RANGE_CACHE and time.time() - _PERF_RANGE_CACHE[ckey][0] < 120:
            return _PERF_RANGE_CACHE[ckey][1]

        positions = [p for p in portfolio.get("positions", [])
                     if p.get("symbol") and p["symbol"] != "CASH"]
        if not positions:
            return {"success": False, "error": "組合尚無持倉"}

        # 依統計起點決定需拉取的歷史長度
        fetch_period = _fetch_period_for(start)

        # 各標的歷史收盤價（以統計起點過濾）
        sym_closes = {}
        for pos in positions:
            sym = pos["symbol"]
            df = fetcher.get_history(sym, period=fetch_period, interval="1d")
            if df is None or df.empty:
                continue
            series = {}
            for d, close in df["close"].items():
                ds = str(d)[:10]
                if ds >= start:
                    series[ds] = float(close)
            if series:
                sym_closes[sym] = series

        # benchmark 歷史收盤價
        bench_closes = {}
        bench_df = fetcher.get_history(benchmark, period=fetch_period, interval="1d")
        if bench_df is not None and not bench_df.empty:
            for d, close in bench_df["close"].items():
                ds = str(d)[:10]
                if ds >= start:
                    bench_closes[ds] = float(close)

        if not sym_closes or len(bench_closes) < 2:
            return {"success": False, "error": "區間內歷史數據不足"}

        # 匯率近似（以當前即時匯率折算至 base_currency）
        fx_map = {}
        for pos in positions:
            sym = pos["symbol"]
            q = fetcher.get_quote(sym) or {}
            sym_ccy = q.get("currency") or pos.get("currency") or base_currency
            fx_map[sym] = get_fx_rate(sym_ccy, base_currency)

        # 對齊日期
        all_dates = set(bench_closes.keys())
        for s in sym_closes.values():
            all_dates.update(s.keys())
        dates = sorted(all_dates)
        if len(dates) < 2:
            return {"success": False, "error": "區間內數據不足"}

        def fwd_fill(series):
            last_v = None
            out = []
            for d in dates:
                v = series.get(d)
                if v is None:
                    out.append(last_v)
                else:
                    last_v = v
                    out.append(last_v)
            return out

        # 逐日組合市值
        qty_map = {p["symbol"]: float(p["quantity"]) for p in positions}
        value_series = []
        fwd_vals = {}
        for d in dates:
            total = 0.0
            for sym, closes in sym_closes.items():
                v = closes.get(d)
                if v is None:
                    if sym not in fwd_vals:
                        continue
                    v = fwd_vals[sym]
                else:
                    fwd_vals[sym] = v
                total += v * qty_map[sym] * fx_map.get(sym, 1.0)
            if total <= 0:
                return {"success": False, "error": "組合市值計算失敗"}
            value_series.append(total)

        bench_fwd = fwd_fill(bench_closes)

        # 找出組合與 benchmark 皆有值的起點
        start_idx = 0
        while start_idx < len(value_series):
            if value_series[start_idx] > 0 and bench_fwd[start_idx] is not None:
                break
            start_idx += 1
        if start_idx >= len(value_series):
            return {"success": False, "error": "區間內數據不足"}
        dates = dates[start_idx:]
        value_series = value_series[start_idx:]
        bench_fwd = bench_fwd[start_idx:]

        # 剔除尾部 NaN（Yahoo Finance 當日未結算導致 close=NaN）
        import math as _math
        while value_series and (_math.isnan(value_series[-1]) or not _math.isfinite(value_series[-1])):
            value_series.pop()
            dates.pop()
            bench_fwd.pop()
        if len(dates) < 2:
            return {"success": False, "error": "區間內數據不足"}

        # 以統計開始點計算累計報酬率（%）
        base_value = value_series[0]
        base_bench = bench_fwd[0]
        pf_ret = [(v / base_value - 1) * 100 for v in value_series]
        bench_ret = [(b / base_bench - 1) * 100 for b in bench_fwd]

        def annualize(total_ret_pct: float, d: int) -> float:
            if d <= 0:
                return 0.0
            r = 1 + total_ret_pct / 100
            if r <= 0:
                return -100.0
            return (r ** (252.0 / d) - 1) * 100

        pf_ret_total = pf_ret[-1]
        bench_ret_total = bench_ret[-1]
        result = {
            "success": True,
            "period": period,
            "start_date": dates[0],
            "end_date": dates[-1],
            "days": len(dates),
            "benchmark": benchmark,
            "stats": {
                "portfolio_return": round(pf_ret_total, 2),
                "benchmark_return": round(bench_ret_total, 2),
                "excess_return": round(pf_ret_total - bench_ret_total, 2),
                "portfolio_end_value": round(value_series[-1], 2),
                "portfolio_annualized": round(annualize(pf_ret_total, len(dates)), 2),
                "benchmark_annualized": round(annualize(bench_ret_total, len(dates)), 2),
                "portfolio_max_drawdown": round(calc_max_drawdown(value_series), 2),
                "benchmark_max_drawdown": round(calc_max_drawdown(bench_fwd), 2),
                "portfolio_volatility": round(calc_volatility(value_series), 2),
                "benchmark_volatility": round(calc_volatility(bench_fwd), 2),
            },
            "series": {
                "dates": dates,
                "portfolio": [round(x, 2) for x in pf_ret],
                "benchmark": [round(x, 2) for x in bench_ret],
            },
        }
        _PERF_RANGE_CACHE[ckey] = (time.time(), result)
        if len(_PERF_RANGE_CACHE) > 20:
            oldest = min(_PERF_RANGE_CACHE, key=lambda k: _PERF_RANGE_CACHE[k][0])
            _PERF_RANGE_CACHE.pop(oldest)
        return result
    except Exception as e:
        logger.error(f"計算區間績效失敗: {e}")
        return {"success": False, "error": "區間績效計算失敗"}


# ========== 投資組合可視圖 (Portfolio Dashboard) ==========
_DASHBOARD_CACHE = {}  # pid -> (timestamp, result)
_CAT_NAMES = {"STOCK": "股票", "ETF": "ETF", "INDEX": "指數", "COMMODITY": "商品", "FX": "匯率", "CASH": "現金"}


def _annualize_ret(total_pct: float, days: int) -> Optional[float]:
    if days <= 0:
        return None
    r = 1 + total_pct / 100
    if r <= 0:
        return -100.0
    return (r ** (252.0 / days) - 1) * 100


def _normalize_pcts(raw: List[float]) -> List[float]:
    """將一組百分比四捨五入至小數一位，並以最大餘數法調整，使總和剛好為 100"""
    vals = [round(x, 1) for x in raw]
    diff = round(100.0 - sum(vals), 1)
    if abs(diff) >= 0.1:
        step = 0.1 if diff > 0 else -0.1
        n = int(round(abs(diff) / 0.1))
        err = [abs(x - v) for x, v in zip(raw, vals)]
        idxs = sorted(range(len(vals)), key=lambda i: err[i], reverse=True)
        for k in range(n):
            i = idxs[k % len(vals)]
            vals[i] = round(vals[i] + step, 1)
    return vals


def _dash_ret_stats(returns: np.ndarray) -> dict:
    """由日報酬陣列計算年化報酬/波動/夏普/索提諾"""
    out = {"ret": None, "vol": None, "sharpe": None, "sortino": None}
    if len(returns) < 20:
        return out
    sqrt252 = 252 ** 0.5
    ann_ret = float(np.mean(returns)) * 252
    sd = float(np.std(returns, ddof=1)) * sqrt252
    sharpe = (ann_ret - RISK_FREE_RATE) / sd if sd > 0 else None
    neg = returns[returns < 0]
    downside = float(np.sqrt(np.mean(neg ** 2))) * sqrt252 if len(neg) else 0.0
    sortino = (ann_ret - RISK_FREE_RATE) / downside if downside > 0 else None
    out["ret"] = round(ann_ret * 100, 2)
    out["vol"] = round(sd * 100, 2)
    out["sharpe"] = round(sharpe, 2) if sharpe is not None else None
    out["sortino"] = round(sortino, 2) if sortino is not None else None
    return out


def build_portfolio_dashboard(pf: Dict) -> Optional[dict]:
    """建立投資組合可視圖資料：資產配置、績效曲線、定期報酬、風險指標、相關性矩陣"""
    try:
        pid = pf.get("id", "pf")
        base_currency = pf.get("base_currency", "TWD")
        benchmark = pf.get("benchmark", "^TWII")
        if pid in _DASHBOARD_CACHE and time.time() - _DASHBOARD_CACHE[pid][0] < 120:
            return _DASHBOARD_CACHE[pid][1]

        positions = [p for p in pf.get("positions", [])
                     if p.get("symbol") and p["symbol"] != "CASH"]
        if not positions:
            return None

        # 各標的 5y 收盤價
        sym_closes = {}
        for pos in positions:
            sym = pos["symbol"]
            df = fetcher.get_history(sym, period="5y", interval="1d")
            if df is None or df.empty:
                continue
            s = {}
            for d, close in df["close"].items():
                s[str(d)[:10]] = float(close)
            if s:
                sym_closes[sym] = s
        if not sym_closes:
            return None

        bench_closes = {}
        bdf = fetcher.get_history(benchmark, period="5y", interval="1d")
        if bdf is not None and not bdf.empty:
            for d, close in bdf["close"].items():
                bench_closes[str(d)[:10]] = float(close)

        fx_map, ccy_map, info_map = {}, {}, {}
        for pos in positions:
            sym = pos["symbol"]
            q = fetcher.get_quote(sym) or {}
            ccy = q.get("currency") or pos.get("currency") or base_currency
            ccy_map[sym] = ccy
            fx_map[sym] = get_fx_rate(ccy, base_currency)
            info_map[sym] = q

        qty_map = {p["symbol"]: float(p["quantity"]) for p in positions}

        # 逐日組合總值（5y，各標的 fwd-fill）
        all_dates = set(bench_closes.keys())
        for s in sym_closes.values():
            all_dates.update(s.keys())
        dates = sorted(all_dates)
        if not dates:
            return None
        fwd_vals = {}
        value_series = []
        for d in dates:
            total = 0.0
            for sym, closes in sym_closes.items():
                v = closes.get(d)
                if v is None:
                    if sym not in fwd_vals:
                        continue
                    v = fwd_vals[sym]
                else:
                    fwd_vals[sym] = v
                total += v * qty_map[sym] * fx_map.get(sym, 1.0)
            value_series.append(total)

        bench_fwd = []
        last_b = None
        for d in dates:
            v = bench_closes.get(d)
            if v is None:
                bench_fwd.append(last_b)
            else:
                last_b = v
                bench_fwd.append(last_b)

        start_idx = 0
        while start_idx < len(value_series):
            if value_series[start_idx] > 0 and bench_fwd[start_idx] is not None:
                break
            start_idx += 1
        if start_idx >= len(value_series):
            return None
        dates = dates[start_idx:]
        value_series = value_series[start_idx:]
        bench_fwd = bench_fwd[start_idx:]
        if len(dates) < 2:
            return None

        base_val, base_bench = value_series[0], bench_fwd[0]
        pf_cum = [(v / base_val - 1) * 100 for v in value_series]
        bench_cum = [(b / base_bench - 1) * 100 for b in bench_fwd]

        # ---- 資產配置（類別 / 區域 / 前五大） ----
        # 市值與權重沿用 calc_portfolio_perf，與上方「持倉明細」的權重一致
        quotes = {p["symbol"]: info_map.get(p["symbol"]) or {} for p in positions}
        perf_calc = calc_portfolio_perf(pf, quotes)
        net_mv = {r["symbol"]: r["net_market_value"] for r in perf_calc.get("positions", [])}
        total_value = perf_calc.get("total_value", 0) or 0
        cash_part = net_mv.pop("CASH", 0.0)
        if not cash_part:
            cash_part = float(pf.get("cash_balance", 0) or 0)

        category, region, industry, top = {}, {}, {}, []
        for pos in positions:
            sym = pos["symbol"]
            sym_info = _symbols.get(sym, {})
            cat = sym_info.get("category") or "STOCK"
            up = sym.upper()
            if ".TW" in up:
                reg = "台股"
            elif ".HK" in up:
                reg = "港股"
            elif up.endswith(".SS") or up.endswith(".SZ"):
                reg = "A股"
            elif cat == "COMMODITY":
                reg = "商品"
            elif cat == "FX":
                reg = "匯率"
            else:
                reg = "美股"
            mv = net_mv.get(sym, 0)
            category[cat] = category.get(cat, 0) + mv
            region[reg] = region.get(reg, 0) + mv
            if cat in ("STOCK", "ETF"):
                q = info_map.get(sym) or {}
                ind = q.get("sector") or q.get("industry")
                if not ind:
                    si = fetcher.get_sector(sym)
                    ind = si.get("sector") or si.get("industry")
                if not ind:
                    ind = (q.get("name") if cat == "STOCK" else None) or _CAT_NAMES.get(cat, cat)
                industry[ind] = industry.get(ind, 0) + mv
            top.append({"symbol": sym, "name": pos.get("name") or sym,
                        "weight": round(mv / total_value * 100, 1) if total_value else 0})
        if cash_part > 0:
            category["CASH"] = category.get("CASH", 0) + cash_part
            region["現金"] = region.get("現金", 0) + cash_part
        top.sort(key=lambda x: x["weight"], reverse=True)

        cat_pairs = sorted(category.items(), key=lambda x: -x[1])
        reg_pairs = sorted(region.items(), key=lambda x: -x[1])
        ind_pairs = sorted(industry.items(), key=lambda x: -x[1])
        cat_denom = sum(category.values()) or 1
        reg_denom = sum(region.values()) or 1
        ind_denom = sum(industry.values()) or 1
        cat_pcts = _normalize_pcts([v / cat_denom * 100 for _, v in cat_pairs])
        reg_pcts = _normalize_pcts([v / reg_denom * 100 for _, v in reg_pairs])
        ind_pcts = _normalize_pcts([v / ind_denom * 100 for _, v in ind_pairs])

        alloc = {
            "category": [{"name": _CAT_NAMES.get(k, k), "pct": p} for (k, _), p in zip(cat_pairs, cat_pcts)],
            "region": [{"name": k, "pct": p} for (k, _), p in zip(reg_pairs, reg_pcts)],
            "industry": [{"name": k, "pct": p} for (k, _), p in zip(ind_pairs, ind_pcts)],
            "top": top[:5],
        }

        # ---- 績效（近一年累計報酬曲線） ----
        n1 = int(1 * 252)
        seg1 = slice(max(len(dates) - n1, 0), len(dates))
        d1, v1, b1 = dates[seg1], value_series[seg1], bench_fwd[seg1]
        base_v1, base_b1 = v1[0], b1[0]
        p1_raw = [(v / base_v1 - 1) * 100 for v in v1]
        bm1_raw = [(v / base_b1 - 1) * 100 for v in b1]
        # 剔除目前日（Yahoo Finance 尚未結算，close=NaN 使最後一筆為 NaN）
        import math as _math
        def strip_trailing_nan(seq):
            while seq and (_math.isnan(seq[-1]) or not _math.isfinite(seq[-1])):
                seq.pop()
            return seq
        p1 = strip_trailing_nan(p1_raw[:])
        bm1 = strip_trailing_nan(bm1_raw[:])
        ret_1y = p1[-1] if p1 else 0.0
        ret_bm_1y = bm1[-1] if bm1 else 0.0

        # ---- 月度報酬（近12個月，絕對報酬率） ----
        month_last, month_first = {}, {}
        for d, v in zip(dates, value_series):
            m = d[:7]
            if m not in month_first:
                month_first[m] = v
            if _math.isnan(v) or not _math.isfinite(v):
                continue
            month_last[m] = v
        month_keys = sorted(month_last)[-12:]
        monthly = []
        if month_keys:
            all_months = sorted(month_last)
            idx0 = all_months.index(month_keys[0])
            prev_val = month_last[all_months[idx0 - 1]] if idx0 > 0 else month_first[month_keys[0]]
            for m in month_keys:
                ret = (month_last[m] / prev_val - 1) * 100 if prev_val else 0.0
                monthly.append({"label": m, "ret": round(ret, 2)})
                prev_val = month_last[m]

        # ---- 年度報酬（近3年）+ 三年 CAGR ----
        year_last, year_first = {}, {}
        for d, v in zip(dates, value_series):
            if _math.isnan(v) or not _math.isfinite(v):
                continue
            y = d[:4]
            if y not in year_first:
                year_first[y] = v
            year_last[y] = v
        last_year = dates[-1][:4]
        annual = []
        for y in [str(int(last_year) - 2), str(int(last_year) - 1), last_year]:
            if y not in year_last:
                continue
            base = year_last.get(str(int(y) - 1)) or year_first[y]
            if base:
                annual.append({"label": y, "ret": round((year_last[y] / base - 1) * 100, 2)})
        cagr_3y = None
        try:
            anchor = f"{int(last_year) - 3}-{dates[-1][5:]}"
            w_dates = [d for d in dates if d >= anchor]
            if w_dates:
                wv = value_series[len(dates) - len(w_dates)]
                cagr_3y = _annualize_ret((value_series[-1] / wv - 1) * 100, len(w_dates))
        except Exception:
            cagr_3y = None

        # ---- 風險指標（波動 / 夏普 / 索提諾 / 貝塔 / 最大回撤） ----
        def dret(arr):
            a = np.asarray(arr, dtype=float)
            if len(a) < 2:
                return np.array([])
            return a[1:] / a[:-1] - 1

        def _win(arr, n):
            return arr[-n:] if len(arr) >= n else arr

        pf_ret_all = dret(value_series)
        bm_ret_all = dret(bench_fwd)
        mlen = min(len(pf_ret_all), len(bm_ret_all))
        pr, br = pf_ret_all[-mlen:], bm_ret_all[-mlen:]

        def _beta(r_pf, r_bm):
            if len(r_pf) < 20 or len(r_bm) < 20:
                return None
            vm = float(np.var(r_bm, ddof=1))
            if vm <= 0:
                return None
            return round(float(np.cov(r_pf, r_bm)[0, 1]) / vm, 2)

        n3 = int(3 * 252)
        st1 = _dash_ret_stats(_win(pf_ret_all, n1))
        st3 = _dash_ret_stats(_win(pf_ret_all, n3))
        b1r, b3r = _win(br, n1), _win(br, n3)
        p1r, p3r = _win(pr, n1), _win(pr, n3)
        beta_1y = _beta(p1r, b1r) if len(p1r) >= 20 and len(b1r) >= 20 else None
        beta_3y = _beta(p3r, b3r) if len(p3r) >= 20 and len(b3r) >= 20 else None

        # ---- 相關性矩陣（近一年日報酬，成對對齊） ----
        corr_syms = list(sym_closes.keys())
        corr = {"symbols": corr_syms, "matrix": []}
        if len(corr_syms) >= 2 and len(dates) > 30:
            last_dt = datetime.strptime(dates[-1], "%Y-%m-%d")
            y1_anchor = (last_dt - timedelta(days=365)).strftime("%Y-%m-%d")
            wd = [d for d in dates if d >= y1_anchor]
            if len(wd) >= 30:
                P = np.full((len(corr_syms), len(wd)), np.nan)
                for i, sym in enumerate(corr_syms):
                    closes = sym_closes[sym]
                    lastv = None
                    for j, d in enumerate(wd):
                        v = closes.get(d)
                        if v is None:
                            if lastv is not None:
                                P[i, j] = lastv
                        else:
                            lastv = v
                            P[i, j] = lastv
                R = np.diff(P, axis=1) / P[:, :-1]
                mat = np.eye(len(corr_syms))
                for i in range(len(corr_syms)):
                    for j in range(i + 1, len(corr_syms)):
                        ok = ~(np.isnan(R[i]) | np.isnan(R[j]))
                        if ok.sum() >= 30:
                            c = float(np.corrcoef(R[i][ok], R[j][ok])[0, 1])
                            if np.isnan(c):
                                c = 0.0
                            mat[i, j] = mat[j, i] = round(c, 2)
                corr["matrix"] = [[round(float(x), 2) for x in row] for row in mat]

        result = {
            "success": True,
            "benchmark": benchmark,
            "base_currency": base_currency,
            "allocation": alloc,
            "performance": {
                "dates": d1,
                "portfolio": [round(x, 2) for x in p1],
                "benchmark": [round(x, 2) for x in bm1],
                "monthly": monthly,
                "annual": annual,
                "cagr_3y": round(cagr_3y, 2) if cagr_3y is not None else None,
                "total_return": round(ret_1y, 2),
                "benchmark_return": round(ret_bm_1y, 2),
            },
            "risk": {
                "max_drawdown": round(calc_max_drawdown(value_series), 2),
                "max_drawdown_1y": round(calc_max_drawdown(v1), 2),
                "volatility_1y": st1.get("vol"),
                "volatility_3y": st3.get("vol"),
                "sharpe_1y": st1.get("sharpe"),
                "sharpe_3y": st3.get("sharpe"),
                "sortino_1y": st1.get("sortino"),
                "sortino_3y": st3.get("sortino"),
                "beta_1y": beta_1y,
                "beta_3y": beta_3y,
                "correlation": corr,
            },
        }
        _DASHBOARD_CACHE[pid] = (time.time(), result)
        if len(_DASHBOARD_CACHE) > 20:
            _DASHBOARD_CACHE.pop(next(iter(_DASHBOARD_CACHE)))
        return result
    except Exception as e:
        logger.error(f"計算投資組合可視圖失敗 {pf.get('id', '?')}: {e}")
        return None


# ========== 基本面 / 技術面 / 新聞 ==========
def _num(v, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        if isinstance(v, (float, np.floating)) and (np.isnan(v) or np.isinf(v)):
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _fmt_bn(v: float) -> str:
    """大數字格式化：兆/億/萬"""
    v = _num(v)
    av = abs(v)
    if av >= 1e12:
        return f"{v/1e12:.2f}T"
    if av >= 1e8:
        return f"{v/1e8:.2f}億"
    if av >= 1e4:
        return f"{v/1e4:.2f}萬"
    return f"{v:,.0f}"


def _row(df, key: str) -> float:
    """從財報表以子字串比對取值（新版 yfinance 索引可能是 tuple）"""
    if df is None or df.empty:
        return 0.0
    for i in range(len(df.index)):
        label = df.index[i]
        if not isinstance(label, str):
            label = str(label)
        if key in label:
            try:
                return _num(df.iloc[i].iloc[0])
            except Exception:
                continue
    return 0.0


def get_fundamental(symbol: str, lang: str = None) -> Optional[Dict]:
    try:
        stock = yf.Ticker(symbol)
        info = stock.info
        if not info or 'currentPrice' not in info:
            return None
        current_price = _num(info.get('currentPrice') or info.get('regularMarketPrice'))
        prev = _num(info.get('previousClose') or info.get('regularMarketPreviousClose'))
        change = current_price - prev
        change_pct = (change / prev * 100) if prev else 0.0

        cash_flow = getattr(stock, 'cashflow', None)
        qis = getattr(stock, 'quarterly_income_stmt', None)
        qbs = getattr(stock, 'quarterly_balance_sheet', None)
        report_date = "無資料"
        if qbs is not None and not qbs.empty:
            try:
                report_date = str(qbs.columns[0])[:10]
            except Exception:
                pass

        market_cap = _num(info.get('marketCap'))
        ocf = _row(cash_flow, 'Operating Cash Flow')
        capex = _row(cash_flow, 'Capital Expenditure')
        fcf = ocf + capex
        div_paid = abs(_row(cash_flow, 'Dividends Paid')) or abs(_row(cash_flow, 'Dividend Paid'))
        div_yield = _num(info.get('dividendYield'))
        fcf_yield = (fcf / market_cap * 100) if market_cap else 0.0
        beta = _num(info.get('beta'))
        quick_ratio = _num(info.get('quickRatio'))
        short_ratio = _num(info.get('shortPercentOfFloat')) * 100

        high52 = _num(info.get('fiftyTwoWeekHigh'))
        low52 = _num(info.get('fiftyTwoWeekLow'))
        range_pos = ((current_price - low52) / (high52 - low52) * 100) if (high52 - low52) else 0.0

        revenue = _row(qis, 'Total Revenue')
        revenue_growth = _num(info.get('revenueGrowth')) * 100
        earnings_growth = _num(info.get('earningsGrowth')) * 100
        total_cash = _row(qbs, 'Cash Cash Equivalents And Short Term Investments')
        total_liab = _row(qbs, 'Total Liabilities')

        pe = _num(info.get('trailingPE'))
        fpe = _num(info.get('forwardPE'))
        peg = _num(info.get('pegRatio'))
        pb = _num(info.get('priceToBook'))
        ev_ebitda = _num(info.get('enterpriseToEbitda'))
        eps = _num(info.get('trailingEps'))
        roe = _num(info.get('returnOnEquity')) * 100
        roa = _num(info.get('returnOnAssets')) * 100
        om = _num(info.get('operatingMargins')) * 100
        pm = _num(info.get('profitMargins')) * 100

        target_mean = _num(info.get('targetMeanPrice'))
        target_median = _num(info.get('targetMedianPrice'))
        num_analysts = int(_num(info.get('numberOfAnalystOpinions')))
        rec = _num(info.get('recommendationMean'))
        held_insiders = _num(info.get('heldPercentInsiders')) * 100
        held_institutions = _num(info.get('heldPercentInstitutions')) * 100

        currency = info.get('currency') or 'USD'
        name = info.get('shortName') or info.get('longName') or symbol
        c = currency
        result = {
            "symbol": symbol, "name": name, "currency": currency,
            "price": current_price, "change": change, "change_pct": change_pct,
            "report_date": report_date,
            "cards": [
                {"title": "估值指標", "items": [
                    {"label": "總市值", "value": f"{_fmt_bn(market_cap)} {c}"},
                    {"label": "本益比 (PE)", "value": f"{pe:.2f}"},
                    {"label": "預期本益比 (Forward PE)", "value": f"{fpe:.2f}"},
                    {"label": "本益成長比 (PEG)", "value": f"{peg:.2f}"},
                    {"label": "股價淨值比 (PB)", "value": f"{pb:.2f}"},
                    {"label": "EV / EBITDA", "value": f"{ev_ebitda:.2f}"},
                ]},
                {"title": "獲利指標", "items": [
                    {"label": "每股盈餘 (EPS)", "value": f"{eps:.2f}"},
                    {"label": "資產報酬率 (ROA)", "value": f"{roa:.2f}%"},
                    {"label": "股東權益報酬率 (ROE)", "value": f"{roe:.2f}%"},
                    {"label": "營業利潤率", "value": f"{om:.2f}%"},
                    {"label": "純利潤率", "value": f"{pm:.2f}%"},
                ]},
                {"title": "殖利率與風險", "items": [
                    {"label": "現金殖利率", "value": f"{div_yield:.2f}%"},
                    {"label": "FCF 殖利率", "value": f"{fcf_yield:.2f}%"},
                    {"label": "放空比例", "value": f"{short_ratio:.2f}%"},
                    {"label": "貝他值 (Beta)", "value": f"{beta:.2f}"},
                    {"label": "速動比率", "value": f"{quick_ratio:.2f}"},
                ]},
                {"title": "52 週區間", "items": [
                    {"label": "52 週高點", "value": f"{high52:,.2f}"},
                    {"label": "52 週低點", "value": f"{low52:,.2f}"},
                    {"label": "區間位置", "value": f"{range_pos:.1f}%"},
                ]},
                {"title": "現金流", "items": [
                    {"label": "自由現金流 (FCF)", "value": _fmt_bn(fcf)},
                    {"label": "營業現金流 (OCF)", "value": _fmt_bn(ocf)},
                    {"label": "FCF 股利覆蓋倍數", "value": f"{(fcf/div_paid if div_paid else 0):.2f}"},
                ]},
                {"title": f"營收與成長（{report_date}）", "items": [
                    {"label": "單季總營收", "value": _fmt_bn(revenue)},
                    {"label": "總現金", "value": _fmt_bn(total_cash)},
                    {"label": "總負債", "value": _fmt_bn(total_liab)},
                    {"label": "營收年成長率", "value": f"{revenue_growth:.2f}%"},
                    {"label": "盈餘年成長率", "value": f"{earnings_growth:.2f}%"},
                ]},
                {"title": "分析師與持股", "items": [
                    {"label": "分析師平均目標價", "value": f"{target_mean:,.2f}"},
                    {"label": "分析師中位目標價", "value": f"{target_median:,.2f}"},
                    {"label": "分析師人數", "value": str(num_analysts)},
                    {"label": "券商推薦均值", "value": f"{rec:.2f}"},
                    {"label": "內部人持股", "value": f"{held_insiders:.2f}%"},
                    {"label": "機構持股", "value": f"{held_institutions:.2f}%"},
                ]},
            ],
        }
        if lang and lang != 'zh-TW':
            return json.loads(apply_lang(json.dumps(result, ensure_ascii=False), lang))
        return result
    except Exception as e:
        logger.error(f"獲取基本面失敗 {symbol}: {e}")
        return None


def calc_kdj(df):
    df = df.copy()
    high = df['High'].rolling(window=9).max()
    low = df['Low'].rolling(window=9).min()
    rsv = (df['Close'] - low) / (high - low) * 100
    df['K'] = rsv.ewm(span=3, adjust=False).mean()
    df['D'] = df['K'].ewm(span=3, adjust=False).mean()
    df[['K', 'D']] = df[['K', 'D']].fillna(0)
    return df


def calc_ma(df):
    df = df.copy()
    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df[['MA5', 'MA20']] = df[['MA5', 'MA20']].fillna(0)
    return df


def calc_macd(df):
    df = df.copy()
    df['EMA12'] = df['Close'].ewm(span=12, adjust=False).mean()
    df['EMA26'] = df['Close'].ewm(span=26, adjust=False).mean()
    df['DIF'] = df['EMA12'] - df['EMA26']
    df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
    df['MACD'] = (df['DIF'] - df['DEA']) * 2
    df[['DIF', 'DEA', 'MACD']] = df[['DIF', 'DEA', 'MACD']].fillna(0)
    return df


def _f(v):
    try:
        f = float(v)
        return 0.0 if (np.isnan(f) or np.isinf(f)) else f
    except (TypeError, ValueError):
        return 0.0


def pack_chart_data(df):
    kline_data, volume_data = [], []
    k_line, d_line = [], []
    ma5_data, ma20_data = [], []
    dif_data, dea_data, macd_data = [], [], []
    total_list = []
    for idx, row in df.iterrows():
        ts = int(row['timestamp'])
        o, h, l, c = _f(row['Open']), _f(row['High']), _f(row['Low']), _f(row['Close'])
        vol = _f(row['Volume'])
        k = _f(row['K']); d = _f(row['D'])
        ma5 = _f(row['MA5']); ma20 = _f(row['MA20'])
        dif = _f(row['DIF']); dea = _f(row['DEA']); macd = _f(row['MACD'])
        kline_data.append({"time": ts, "open": o, "high": h, "low": l, "close": c})
        volume_data.append({"time": ts, "value": vol, "color": "#4cd964" if c >= o else "#ff5e57"})
        k_line.append({"time": ts, "value": k})
        d_line.append({"time": ts, "value": d})
        ma5_data.append({"time": ts, "value": ma5})
        ma20_data.append({"time": ts, "value": ma20})
        dif_data.append({"time": ts, "value": dif})
        dea_data.append({"time": ts, "value": dea})
        macd_data.append({"time": ts, "value": macd, "color": "#4cd964" if macd >= 0 else "#ff5e57"})
        total_list.append({
            "idx": idx,
            "date": row['Date'].strftime("%Y-%m-%d"),
            "open": o, "high": h, "low": l, "close": c, "volume": vol,
            "K": k, "D": d, "MA5": ma5, "MA20": ma20,
            "DIF": dif, "DEA": dea, "MACD": macd
        })
    return {
        "kline": kline_data, "volume": volume_data,
        "K": k_line, "D": d_line, "MA5": ma5_data, "MA20": ma20_data,
        "DIF": dif_data, "DEA": dea_data, "MACD": macd_data,
        "source": total_list,
    }


def get_tech_data(symbol: str, cycle: str = "day") -> Optional[Dict]:
    try:
        ticker = yf.Ticker(symbol)
        if cycle == "week":
            raw = ticker.history(period="5y", interval="1wk")
        elif cycle == "month":
            raw = ticker.history(period="max", interval="1mo")
        else:
            raw = ticker.history(period="1y", interval="1d")
        if raw.empty:
            return None
        raw = raw.reset_index(names="Date")
        raw = calc_kdj(raw)
        raw = calc_ma(raw)
        raw = calc_macd(raw)
        raw['timestamp'] = (raw['Date'].astype(np.int64) // 10**9).astype(int)
        raw = raw.iloc[30:].reset_index(drop=True)
        return pack_chart_data(raw)
    except Exception as e:
        logger.error(f"獲取技術數據失敗 {symbol}/{cycle}: {e}")
        return None


def get_news(symbol: str, limit: int = 10) -> List[Dict]:
    news_result = []
    try:
        ticker = yf.Ticker(symbol)
        raw_news = ticker.news or []
        for item in raw_news[:limit]:
            content = item.get("content", {}) or {}
            title = content.get("title", "無標題")
            provider = (content.get("provider") or {}).get("displayName", "未知媒體")
            pub_date = content.get("pubDate", "")
            if "T" in pub_date:
                pub_date = pub_date.replace("T", " ").replace("Z", " UTC")
            link_info = content.get("clickThroughUrl") or {}
            news_url = link_info.get("url", "")
            summary = content.get("summary", "")
            news_result.append({
                "ticker": symbol, "publish_time": pub_date, "publisher": provider,
                "title": title, "summary": summary, "url": news_url,
            })
    except Exception as e:
        logger.error(f"獲取新聞失敗 {symbol}: {e}")
    return news_result


# ========== 投資組合管理 ==========
def load_portfolio(pid: str) -> Optional[Dict]:
    pf = PORTFOLIO_DIR / f"{pid}.json"
    if pf.exists():
        try:
            with open(pf, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return None
    return None


def save_portfolio(pid: str, pf: Dict) -> None:
    pf["updated_at"] = datetime.now().isoformat()
    with open(PORTFOLIO_DIR / f"{pid}.json", 'w', encoding='utf-8') as f:
        json.dump(pf, f, ensure_ascii=False, indent=2)


def list_portfolios() -> List[Dict]:
    result = []
    for pf in PORTFOLIO_DIR.glob("*.json"):
        try:
            with open(pf, 'r', encoding='utf-8') as f:
                data = json.load(f)
            result.append({
                "id": pf.stem, "name": data.get("name", ""),
                "base_currency": data.get("base_currency", "TWD"),
                "benchmark": data.get("benchmark", "^TWII"),
                "position_count": len(data.get("positions", [])),
                "created_at": data.get("created_at", ""),
                "updated_at": data.get("updated_at", data.get("created_at", "")),
            })
        except:
            pass
    result.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    return result


def create_portfolio(name: str = None, base_currency: str = "TWD", benchmark: str = "^TWII") -> Optional[str]:
    if len(list_portfolios()) >= 8:
        return None
    pid = f"pf_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    portfolio = {
        "id": pid, "name": name or f"投資組合 {len(list_portfolios()) + 1}",
        "base_currency": base_currency, "benchmark": benchmark,
        "positions": [], "cash_balance": 0,
        "created_at": datetime.now().isoformat(),
    }
    save_portfolio(pid, portfolio)
    return pid


def add_position(pid: str, symbol: str, name: str, cost_price: float, quantity: float,
                 buy_fee_rate: float = 0.001425, sell_fee_rate: float = 0.001425, tax_rate: float = 0.003) -> Optional[str]:
    pf = load_portfolio(pid)
    if not pf: return None
    for pos in pf.get("positions", []):
        if pos["symbol"] == symbol:
            total_qty = pos["quantity"] + quantity
            pos["cost_price"] = (pos["cost_price"] * pos["quantity"] + cost_price * quantity) / total_qty
            pos["quantity"] = total_qty
            pos["buy_fee_rate"] = buy_fee_rate
            pos["sell_fee_rate"] = sell_fee_rate
            pos["tax_rate"] = tax_rate
            save_portfolio(pid, pf)
            return pos["id"]
    pos_id = f"{pid}_{symbol}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    new_pos = {
        "id": pos_id, "symbol": symbol, "name": name,
        "cost_price": cost_price, "quantity": quantity,
        "buy_fee_rate": buy_fee_rate, "sell_fee_rate": sell_fee_rate, "tax_rate": tax_rate,
        "current_price": cost_price, "created_at": datetime.now().isoformat(),
    }
    pf.setdefault("positions", []).append(new_pos)
    save_portfolio(pid, pf)
    return pos_id


def remove_position(pid: str, pos_id: str) -> bool:
    pf = load_portfolio(pid)
    if not pf: return False
    pf["positions"] = [p for p in pf.get("positions", []) if p.get("id") != pos_id]
    save_portfolio(pid, pf)
    return True


def delete_portfolio(pid: str) -> bool:
    pf = PORTFOLIO_DIR / f"{pid}.json"
    if pf.exists():
        pf.unlink(missing_ok=True)
        return True
    return False


def refresh_quotes(pid: str) -> Dict[str, Dict]:
    pf = load_portfolio(pid)
    if not pf: return {}
    symbols = [p["symbol"] for p in pf.get("positions", []) if p["symbol"] != "CASH"]
    quotes = {s: fetcher.get_quote(s) for s in symbols}
    for pos in pf.get("positions", []):
        q = quotes.get(pos["symbol"], {})
        if q:
            pos["current_price"] = q.get("price", pos.get("current_price", pos["cost_price"]))
            pos["price_change"] = q.get("change", 0)
            pos["price_change_pct"] = q.get("change_pct", 0)
    save_portfolio(pid, pf)
    return quotes


# ========== Flask 應用程式 ==========
app = Flask(__name__, static_folder=str(APP_DIR), static_url_path='/static')

# 設定預設視窗大小
WINDOW_WIDTH = 1550
WINDOW_HEIGHT = 1000
WINDOW_MIN_WIDTH = 1200
WINDOW_MIN_HEIGHT = 800
PORT = 9876


@app.route('/')
def index():
    """返回主頁面"""
    try:
        html_file = APP_DIR / "index.html"
        if html_file.exists():
            with open(html_file, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            return generate_html()
    except Exception as e:
        logger.error(f"讀取 HTML 失敗: {e}")
        return generate_html()


@app.route('/api/symbols')
def api_symbols():
    return jsonify({"symbols": list(_symbols.values()), "total": len(_symbols)})


@app.route('/api/symbols', methods=['POST'])
def api_add_symbol():
    data = request.get_json() or {}
    symbol = (data.get('symbol') or '').strip().upper()
    name = (data.get('name') or '').strip()
    category = (data.get('category') or 'STOCK').strip().upper()
    currency = (data.get('currency') or 'TWD').strip().upper()
    if not symbol or not name:
        return jsonify({"success": False, "error": "代碼與名稱不可為空"})
    if symbol in _symbols:
        return jsonify({"success": False, "error": f"標的 {symbol} 已存在"})
    _symbols[symbol] = {"symbol": symbol, "name": name, "category": category, "currency": currency}
    _save_symbols()
    return jsonify({"success": True, "symbol": _symbols[symbol]})


@app.route('/api/symbols/<symbol>', methods=['DELETE'])
def api_delete_symbol(symbol):
    if symbol not in _symbols:
        return jsonify({"success": False, "error": f"找不到標的 {symbol}"})
    del _symbols[symbol]
    _save_symbols()
    return jsonify({"success": True})


@app.route('/api/search')
def api_search():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({"results": []})
    q_upper = q.upper()
    results = [dict(s, source="local") for s in _symbols.values()
               if q_upper in s["symbol"].upper() or q_upper in s["name"].upper()]
    seen_yahoo = set()
    try:
        sq = yf.Search(q, max_results=15)
        for item in (sq.quotes or []):
            sym = item.get('symbol')
            if not sym or sym in seen_yahoo:
                continue
            qtype = (item.get('quoteType') or '').upper()
            if qtype not in ("EQUITY", "ETF", "INDEX", "MUTUALFUND", "COMMODITY", "FUTURE", "CURRENCY"):
                continue
            name = item.get('shortname') or item.get('longname') or sym
            low = name.upper()
            if any(k in low for k in ("DRN", "TOKENIZED", "CRYPTO", "DIGITAL")):
                continue
            if qtype == "ETF":
                category = "ETF"
            elif qtype == "INDEX":
                category = "INDEX"
            elif qtype in ("COMMODITY", "FUTURE"):
                category = "COMMODITY"
            elif qtype == "CURRENCY":
                category = "FX"
            else:
                category = "STOCK"
            currency = "TWD" if ".TW" in sym else "HKD" if ".HK" in sym else "CNY" if (".SS" in sym or ".SZ" in sym) else "USD"
            results.append({
                "symbol": sym,
                "name": name,
                "category": category,
                "currency": currency,
                "source": "yahoo",
            })
            seen_yahoo.add(sym)
    except Exception as e:
        logger.error(f"Yahoo 搜尋失敗: {e}")
    return jsonify({"results": results[:25]})


@app.route('/api/quote/<symbol>')
def api_quote(symbol: str):
    quote = fetcher.get_quote(symbol)
    if quote:
        return jsonify({"success": True, "data": quote})
    return jsonify({"success": False, "error": "無法獲取報價"})


@app.route('/api/quotes')
def api_quotes():
    symbols = request.args.get('symbols', '')
    sym_list = [s.strip() for s in symbols.split(',') if s.strip()]
    quotes = {s: fetcher.get_quote(s) for s in sym_list if fetcher.get_quote(s)}
    return jsonify({"quotes": quotes})


@app.route('/api/history/<symbol>')
def api_history(symbol: str):
    period = request.args.get('period', '1y')
    interval = request.args.get('interval', '1d')
    df = fetcher.get_history(symbol, period=period, interval=interval)
    if df is None or df.empty:
        return jsonify({"success": False, "error": "無數據"})
    records = df.reset_index()[['Date', 'open', 'high', 'low', 'close', 'volume']].to_dict('records')
    return jsonify({"success": True, "data": records, "symbol": symbol, "period": period})


@app.route('/api/analysis/<symbol>')
def api_analysis(symbol: str):
    ratios = compute_risk_ratios(symbol)
    if ratios is None:
        return jsonify({"success": False, "error": "無足夠數據計算風險指標"})
    return jsonify({"success": True, **ratios})


@app.route('/api/risk_ratios')
def api_risk_ratios():
    symbols = request.args.get('symbols', '')
    sym_list = [s.strip() for s in symbols.split(',') if s.strip()]
    if not sym_list:
        return jsonify({"ratios": {}})
    ratios = compute_market_risk_ratios(sym_list)
    return jsonify({"ratios": ratios})


@app.route('/api/portfolios')
def api_portfolios():
    return jsonify({"portfolios": list_portfolios(), "active_id": None})


@app.route('/api/portfolios', methods=['POST'])
def api_create_portfolio():
    data = request.get_json() or {}
    pid = create_portfolio(name=data.get('name'), base_currency=data.get('base_currency', 'TWD'),
                          benchmark=data.get('benchmark', '^TWII'))
    if pid:
        return jsonify({"success": True, "id": pid, "portfolio": load_portfolio(pid)})
    return jsonify({"success": False, "error": "已達最大組合限制 (8組)"}), 400


@app.route('/api/portfolio/<pid>')
def api_portfolio(pid: str):
    pf = load_portfolio(pid)
    if pf:
        return jsonify({"success": True, "portfolio": pf})
    return jsonify({"success": False, "error": "組合不存在"}), 404


@app.route('/api/performance/<pid>')
def api_performance(pid: str):
    pf = load_portfolio(pid)
    if not pf:
        return jsonify({"error": "組合不存在"}), 404
    symbols = [p["symbol"] for p in pf.get("positions", []) if p["symbol"] != "CASH"]
    quotes = {s: fetcher.get_quote(s) for s in symbols if fetcher.get_quote(s)}
    result = calc_portfolio_perf(pf, quotes)
    period = request.args.get('period', '')
    start_date = request.args.get('start_date', '')
    if period or start_date:
        rng = build_performance_range(pf, period or '6m', start_date)
        result.update(rng)
    result["risk_ratios"] = compute_portfolio_risk_ratios(pf)
    result["success"] = True
    return jsonify(result)


@app.route('/api/export/<pid>')
def api_export(pid: str):
    fmt = request.args.get('format', 'csv')
    pf = load_portfolio(pid)
    if not pf:
        return jsonify({"error": "組合不存在"}), 404
    symbols = [p["symbol"] for p in pf.get("positions", []) if p["symbol"] != "CASH"]
    quotes = {s: fetcher.get_quote(s) for s in symbols if fetcher.get_quote(s)}
    perf = calc_portfolio_perf(pf, quotes)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_name = perf.get('name', 'report').replace('/', '_').replace('\\', '_')
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if fmt == 'json':
        content = json.dumps(perf, ensure_ascii=False, indent=2)
        filename = f"report_{safe_name}_{ts}.json"
        mime = 'application/json'
        enc = 'utf-8-sig'
    elif fmt == 'html':
        pf_full = load_portfolio(pid)
        dash = build_portfolio_dashboard(pf_full) if pf_full else None
        content = _build_html_report(perf, now_str, dash)
        filename = f"report_{safe_name}_{ts}.html"
        mime = 'text/html'
        enc = 'utf-8'
    else:
        headers = ['標的', '代碼', '數量', '成本價', '現價', '總成本', '淨市值', '損益', '損益率(%)', '權重(%)']
        rows = []
        for p in perf.get('positions', []):
            row = [p.get('name', ''), p.get('symbol', ''), p.get('quantity', ''),
                   p.get('cost_price', ''), p.get('current_price', ''),
                   p.get('total_cost', ''), p.get('net_market_value', ''),
                   p.get('pnl', ''), p.get('pnl_pct', ''), p.get('weight', '')]
            rows.append(','.join(str(v) for v in row))
        summary = [
            f'投資組合,{perf.get("name", "")}',
            f'報告時間,{now_str}',
            f'總資產,{perf.get("total_value", 0)}',
            f'總損益,{perf.get("total_pnl", 0)}',
            f'總損益率(%),{perf.get("total_pnl_pct", 0):.2f}',
            '',
            '持倉明細'
        ]
        content = '\ufeff' + '\n'.join(summary) + '\n' + ','.join(headers) + '\n' + '\n'.join(rows)
        filename = f"report_{safe_name}_{ts}.csv"
        mime = 'text/csv'
        enc = 'utf-8'
    return Response(
        content.encode(enc),
        mimetype=mime,
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )


def _build_html_report(perf: dict, now_str: str, dashboard_data: dict = None) -> str:
    """產生完整 HTML 投資報告：資產總覽 + 持倉明細 + 投資組合可視圖"""
    import re as _re
    positions = perf.get('positions', [])
    total_value = perf.get('total_value', 0)
    total_pnl = perf.get('total_pnl', 0)
    total_pnl_pct = perf.get('total_pnl_pct', 0)
    total_invested = perf.get('total_invested', 0)
    cash = perf.get('cash_balance', 0)
    name = perf.get('name', '投資組合')
    base_currency = perf.get('base_currency', 'TWD')
    pnl_sign = '+' if total_pnl >= 0 else ''
    pnl_cls = 'pos' if total_pnl >= 0 else 'neg'

    pos_rows = ''
    for p in positions:
        pp = p.get('pnl', 0)
        ppct = p.get('pnl_pct', 0)
        pc = 'pos' if pp >= 0 else 'neg'
        ps = '+' if pp >= 0 else ''
        pos_rows += (
            '<tr><td>' + str(p.get('name','')) + '</td>'
            '<td>' + str(p.get('symbol','')) + '</td>'
            '<td class="r">' + f"{p.get('quantity',0):,.2f}" + '</td>'
            '<td class="r">' + f"{p.get('cost_price',0):,.2f}" + '</td>'
            '<td class="r">' + f"{p.get('current_price',0):,.2f}" + '</td>'
            '<td class="r">' + f"{p.get('total_cost',0):,.2f}" + '</td>'
            '<td class="r">' + f"{p.get('net_market_value',0):,.2f}" + '</td>'
            '<td class="r ' + pc + '">' + ps + f"{pp:,.2f}" + '</td>'
            '<td class="r ' + pc + '">' + ps + f"{ppct:.2f}%" + '</td>'
            '<td class="r">' + f"{p.get('weight',0):.1f}%" + '</td></tr>\n'
        )

    # Dashboard 可視圖
    has_dash = dashboard_data and dashboard_data.get('success') != False
    dash_section = ''
    init_script = ''
    if has_dash:
        dd_json = json.dumps(dashboard_data, ensure_ascii=False)
        dash_section = (
            '<div class="section-title">投資組合可視圖</div>'
            '<div id="dash-body">'
            '<div class="dash-grid">'
            '<div class="dash-box"><div class="dash-title">資產類別配置</div><div id="dash-donut-cat" class="dash-canvas"></div></div>'
            '<div class="dash-box"><div class="dash-title">市場區域配置</div><div id="dash-donut-reg" class="dash-canvas"></div></div>'
            '<div class="dash-box"><div class="dash-title">股票產業配置</div><div id="dash-donut-ind" class="dash-canvas"></div></div>'
            '<div class="dash-box"><div class="dash-title">前五大持股權重</div><div id="dash-donut-top" class="dash-canvas"></div></div>'
            '</div>'
            '<div id="perf-section"></div>'
            '<div id="risk-section"></div>'
            '</div>'
        )
        init_script = (
            '<script>const D=' + dd_json + ';'
            'document.getElementById("perf-section").innerHTML=perfSection(D);'
            'document.getElementById("risk-section").innerHTML=riskSection(D);'
            'drawDonut("dash-donut-cat",D.allocation.category);'
            'drawDonut("dash-donut-reg",D.allocation.region);'
            'drawDonut("dash-donut-ind",D.allocation.industry||[]);'
            'drawDonut("dash-donut-top",(D.allocation.top||[]).map(t=>({name:t.symbol,sub:t.name,pct:t.weight})));'
            'drawEquity("dash-equity",D.performance);'
            'drawBars("dash-monthly",D.performance.monthly,true);'
            'drawBars("dash-annual",D.performance.annual,false);'
            'drawRiskCards("dash-risk",D.risk);'
            'drawCorr("dash-corr",D.risk.correlation);'
            '</script>'
        )

    # 從 DASHBOARD_JS 提取 CSS 和繪圖函數
    _dash = DASHBOARD_JS
    _style = _re.search(r'(<style>.*?</style>)', _dash, _re.DOTALL).group(1)
    _script = _re.search(r'(<script>.*?</script>)', _dash, _re.DOTALL).group(1)
    _script_clean = _re.sub(r'async function loadDashboard\(\)\{.*?\n\}\n', '', _script, flags=_re.DOTALL)
    _root_css = '<style>:root{' + ''.join('--' + k + ':' + v + ';' for k, v in THEME.items()) + '}</style>'

    return apply_lang((
        '<!DOCTYPE html><html lang="' + get_lang() + '"><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        '<title>' + name + ' - 投資績效報告</title>'
        '<style>'
        '*{margin:0;padding:0;box-sizing:border-box}'
        'body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#0f172a;color:#e2e8f0;padding:24px 32px}'
        '.container{max-width:1000px;margin:0 auto}'
        'h1{font-size:24px;margin-bottom:4px;color:#f8fafc}'
        '.subtitle{color:#94a3b8;font-size:13px;margin-bottom:24px}'
        '.section-title{font-size:16px;font-weight:600;color:#38bdf8;margin:28px 0 12px;border-bottom:1px solid #1e293b;padding-bottom:8px}'
        '.overview{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:20px}'
        '.s{background:#1e293b;border-radius:10px;padding:14px 16px}'
        '.s .l{font-size:12px;color:#94a3b8;margin-bottom:4px}'
        '.s .v{font-size:20px;font-weight:700;color:#f8fafc}'
        '.v.pos{color:#10b981}.v.neg{color:#ef4444}'
        '.stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:14px}'
        '.stat-card{background:#1e293b;border-radius:8px;padding:12px 14px}'
        '.stat-label{font-size:11px;color:#94a3b8;margin-bottom:2px}'
        '.stat-value{font-size:18px;font-weight:700;color:#f8fafc}'
        '.stat-value.up{color:#10b981}.stat-value.down{color:#ef4444}'
        'table{width:100%;border-collapse:collapse;font-size:13px}'
        'th{background:#1e293b;color:#94a3b8;font-weight:600;text-align:left;padding:10px 12px;position:sticky;top:0}'
        'td{padding:10px 12px;border-bottom:1px solid #1e293b}'
        'tr:hover td{background:#1e293b44}'
        '.r{text-align:right}'
        '.pos{color:#10b981;font-weight:600}.neg{color:#ef4444;font-weight:600}'
        '.ft{margin-top:32px;text-align:center;color:#475569;font-size:11px}'
        '@media print{body{background:#fff;color:#1e293b;padding:16px}h1{color:#0f172a}th{background:#f1f5f9;color:#475569}td{border-color:#e2e8f0}.s,.stat-card,.dash-box{background:#f8fafc;border:1px solid #e2e8f0}.s .v,.stat-value{color:#0f172a}.v.pos,.stat-value.up{color:#16a34a}.v.neg,.stat-value.down{color:#dc2626}}'
        '</style>'
        + _style +
        _root_css +
        '</head><body>'
        '<div class="container">'
        '<h1>' + name + '</h1>'
        '<div class="subtitle">投資績效報告 | ' + now_str + ' | 幣別 ' + base_currency + '</div>'
        '<div class="section-title">資產總覽</div>'
        '<div class="overview">'
        '<div class="s"><div class="l">總資產</div><div class="v">' + f'{total_value:,.2f}' + '</div></div>'
        '<div class="s"><div class="l">總投入</div><div class="v">' + f'{total_invested:,.2f}' + '</div></div>'
        '<div class="s"><div class="l">現金餘額</div><div class="v">' + f'{cash:,.2f}' + '</div></div>'
        '<div class="s"><div class="l">總損益</div><div class="v ' + pnl_cls + '">' + pnl_sign + f'{total_pnl:,.2f}' + '</div></div>'
        '<div class="s"><div class="l">總損益率</div><div class="v ' + pnl_cls + '">' + pnl_sign + f'{total_pnl_pct:.2f}%' + '</div></div>'
        '<div class="s"><div class="l">持倉數</div><div class="v">' + str(len(positions)) + '</div></div>'
        '</div>'
        '<div class="section-title">持倉明細</div>'
        '<table><thead><tr>'
        '<th>標的</th><th>代碼</th><th class="r">數量</th><th class="r">成本價</th>'
        '<th class="r">現價</th><th class="r">總成本</th><th class="r">淨市值</th>'
        '<th class="r">損益</th><th class="r">損益率</th><th class="r">權重</th>'
        '</tr></thead><tbody>' + pos_rows + '</tbody></table>'
        + dash_section +
        '<div class="ft">本報告由投資績效分析軟體自動產生 | ' + now_str + '</div>'
        '</div>'
        + _script_clean +
        init_script +
        '</body></html>'
    ), get_lang())


class Api:
    """pywebview JS Bridge — 讓 JavaScript 能呼叫 Python 存檔"""
    _window = None

    def save_report(self, pid: str, fmt: str = 'csv') -> dict:
        """呼叫 Flask endpoint 取得資料，再彈出存檔對話框寫入"""
        try:
            import urllib.request
            url = f'http://127.0.0.1:{PORT}/api/export/{pid}?format={fmt}'
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
                cd = resp.headers.get('Content-Disposition', '')
                fname = f'report.{fmt}'
                if 'filename="' in cd:
                    fname = cd.split('filename="')[1].rstrip('"')
            win = Api._window or pywebview.active_window()
            ext = fmt if fmt in ('csv', 'json', 'html') else 'csv'
            type_map = {
                'csv': ('CSV files (*.csv)',),
                'json': ('JSON files (*.json)',),
                'html': ('HTML files (*.html)',),
            }
            save_path = win.create_file_dialog(
                pywebview.SAVE_DIALOG,
                save_filename=fname,
                file_types=type_map.get(ext, (f'{ext.upper()} files (*.{ext})',)),
            )
            if not save_path:
                return {"success": False, "cancelled": True}
            path = save_path[0] if isinstance(save_path, (list, tuple)) else save_path
            with open(path, 'wb') as f:
                f.write(data)
            return {"success": True, "path": str(path)}
        except Exception as e:
            return {"success": False, "error": str(e)}


@app.route('/api/dashboard/<pid>')
def api_dashboard(pid: str):
    pf = load_portfolio(pid)
    if not pf:
        return jsonify({"success": False, "error": _t("組合不存在")}), 404
    data = build_portfolio_dashboard(pf)
    if not data:
        return jsonify({"success": False, "error": _t("無足夠數據計算投資組合可視圖")})
    return jsonify(json.loads(apply_lang(json.dumps(data, ensure_ascii=False))))


@app.route('/api/portfolio/<pid>/positions', methods=['POST'])
def api_add_position(pid: str):
    data = request.get_json() or {}
    pos_id = add_position(pid, data.get('symbol'), data.get('name'),
                         float(data.get('cost_price', 0)), float(data.get('quantity', 0)),
                         float(data.get('buy_fee_rate', 0.001425)),
                         float(data.get('sell_fee_rate', 0.001425)),
                         float(data.get('tax_rate', 0.003)))
    if pos_id:
        return jsonify({"success": True, "position_id": pos_id})
    return jsonify({"success": False, "error": "新增失敗"}), 400


@app.route('/api/portfolio/<pid>/positions/<pos_id>', methods=['DELETE'])
def api_remove_position(pid: str, pos_id: str):
    if remove_position(pid, pos_id):
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "移除失敗"}), 400


@app.route('/api/portfolios/<pid>', methods=['DELETE'])
def api_delete_portfolio(pid: str):
    if delete_portfolio(pid):
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "組合不存在"}), 404


@app.route('/api/portfolio/<pid>/refresh', methods=['POST'])
def api_refresh(pid: str):
    quotes = refresh_quotes(pid)
    return jsonify({"success": True, "quotes_count": len(quotes)})


@app.route('/api/fundamental/<symbol>')
def api_fundamental(symbol: str):
    data = get_fundamental(symbol, lang=get_lang())
    if data:
        return jsonify({"success": True, "data": data})
    return jsonify({"success": False, "error": _t("無法獲取基本面資料")})


@app.route('/api/techdata/<symbol>')
def api_techdata(symbol: str):
    cycle = request.args.get('cycle', 'day')
    data = get_tech_data(symbol, cycle)
    if data:
        return jsonify({"success": True, "data": data, "symbol": symbol, "cycle": cycle})
    return jsonify({"success": False, "error": "無法獲取技術數據"})


@app.route('/api/news/<symbol>')
def api_news(symbol: str):
    limit = int(request.args.get('limit', 10))
    news = get_news(symbol, limit)
    return jsonify({"success": True, "data": news})


@app.route('/api/cache/status')
def api_cache_status():
    return jsonify({
        "portfolio_count": len(list(PORTFOLIO_DIR.glob("*.json"))),
        "cache_count": cache.count()
    })


@app.route('/api/cache/clear', methods=['POST'])
def api_clear_cache():
    return jsonify({"success": True, "cleared": cache.clear()})


@app.route('/api/settings/lang/<code>', methods=['POST'])
def api_settings_lang(code: str):
    """切換介面語言"""
    if set_lang(code):
        return jsonify({"success": True, "language": code})
    return jsonify({"success": False, "error": "不支援的語言"}), 400


# 投資組合可視圖前端渲染腳本（注入於主要 script 之後）
DASHBOARD_JS = r"""
<style>
.dash-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px;margin-bottom:14px}
.dash-grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px}
@media(max-width:900px){.dash-grid2{grid-template-columns:1fr}}
.dash-box{background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:14px}
.dash-title{font-size:13px;font-weight:600;color:var(--text2);margin-bottom:10px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.dash-canvas{min-height:120px}
.dash-badge{font-size:11px;font-weight:600;padding:2px 8px;border-radius:10px;background:var(--bg3);color:var(--text)}
.dash-badge.up{color:var(--up)}.dash-badge.down{color:var(--down)}
.dash-legend{display:flex;flex-direction:column;gap:4px;font-size:12px;color:var(--text2)}
.dash-legend-item{display:flex;align-items:center;gap:6px;white-space:nowrap}
.dash-legend-item b{color:var(--text)}
.dash-dot{width:10px;height:10px;border-radius:50%;display:inline-block;flex:none}
.dash-list{display:flex;flex-direction:column;gap:4px}
.dash-row{display:flex;justify-content:space-between;align-items:center;padding:5px 0;border-bottom:1px dashed var(--border);font-size:12px;gap:8px}
.dash-row-name{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--text)}
.dash-row-val{font-weight:600;color:var(--accent);flex:none}
</style>
<script>
const DASH_COLORS = ['#f87171','#34d399','#60a5fa','#fbbf24','#c084fc','#22d3ee','#fb923c','#a3e635','#f472b6','#818cf8'];
function clsRatio(v){ return (v===null||v===undefined||isNaN(v)) ? '' : (v>=1 ? 'up' : 'down'); }

async function loadDashboard(){
  const body = document.getElementById('dash-body');
  if (!body) return;
  if (!activePF){ body.innerHTML = '<div class="empty-state"><div class="icon">📊</div><p>尚無投資組合</p></div>'; return; }
  body.innerHTML = '<div class="empty-state"><div class="icon">📊</div><p>載入中...</p></div>';
  let data = null;
  try { const res = await fetch('/api/dashboard/' + activePF); data = await res.json(); } catch(e){}
  if (!data || !data.success){
    body.innerHTML = '<div class="empty-state"><div class="icon">⚠️</div><p>無足夠數據計算投資組合可視圖</p></div>';
    return;
  }
  body.innerHTML = allocSection(data) + perfSection(data) + riskSection(data);
  drawDonut('dash-donut-cat', data.allocation.category);
  drawDonut('dash-donut-reg', data.allocation.region);
  drawDonut('dash-donut-ind', data.allocation.industry || []);
  drawDonut('dash-donut-top', (data.allocation.top||[]).map(t=>({name:t.symbol, sub:t.name, pct:t.weight})));
  drawEquity('dash-equity', data.performance);
  drawBars('dash-monthly', data.performance.monthly, true);
  drawBars('dash-annual', data.performance.annual, false);
  drawRiskCards('dash-risk', data.risk);
  drawCorr('dash-corr', data.risk.correlation);
}

function allocSection(d){
  return `<div class="dash-grid">
    <div class="dash-box"><div class="dash-title">資產類別配置</div><div id="dash-donut-cat" class="dash-canvas"></div></div>
    <div class="dash-box"><div class="dash-title">市場區域配置</div><div id="dash-donut-reg" class="dash-canvas"></div></div>
    <div class="dash-box"><div class="dash-title">股票產業配置</div><div id="dash-donut-ind" class="dash-canvas"></div></div>
    <div class="dash-box"><div class="dash-title">前五大持股權重</div><div id="dash-donut-top" class="dash-canvas"></div></div>
  </div>`;
}

function drawDonut(elId, items){
  const el = document.getElementById(elId);
  if (!el) return;
  const total = items.reduce((s,it)=>s+(it.pct||0),0);
  if (total <= 0){ el.innerHTML = '<div style="color:var(--muted);padding:20px">無資料</div>'; return; }
  const size=200, cx=size/2, cy=size/2, r0=52, r1=78;
  let svg = `<svg width="${size}" height="${size}" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${size} ${size}">`;
  if (items.length === 1){
    const mid=(r0+r1)/2, th=r1-r0;
    svg += `<circle cx="${cx}" cy="${cy}" r="${mid}" fill="none" stroke="${DASH_COLORS[0]}" stroke-width="${th}"/>`;
  } else {
    let a0 = -90;
    items.forEach((it,i)=>{
      const a1 = a0 + (it.pct/total)*360;
      const large = (a1-a0)>180?1:0;
      const x0=cx+r1*Math.cos(a0*Math.PI/180), y0=cy+r1*Math.sin(a0*Math.PI/180);
      const x1=cx+r1*Math.cos(a1*Math.PI/180), y1=cy+r1*Math.sin(a1*Math.PI/180);
      const xi0=cx+r0*Math.cos(a0*Math.PI/180), yi0=cy+r0*Math.sin(a0*Math.PI/180);
      const xi1=cx+r0*Math.cos(a1*Math.PI/180), yi1=cy+r0*Math.sin(a1*Math.PI/180);
      svg += `<path d="M${x0.toFixed(2)},${y0.toFixed(2)} A${r1},${r1} 0 ${large} 1 ${x1.toFixed(2)},${y1.toFixed(2)} L${xi1.toFixed(2)},${yi1.toFixed(2)} A${r0},${r0} 0 ${large} 0 ${xi0.toFixed(2)},${yi0.toFixed(2)} Z" fill="${DASH_COLORS[i%DASH_COLORS.length]}"/>`;
      a0 = a1;
    });
  }
  svg += `<text x="${cx}" y="${cy+5}" fill="var(--text)" font-size="15" font-weight="700" text-anchor="middle">${total.toFixed(0)}%</text>`;
  svg += '</svg>';
  const legend = '<div class="dash-legend">' + items.map((it,i)=>
    `<div class="dash-legend-item"><span class="dash-dot" style="background:${DASH_COLORS[i%DASH_COLORS.length]}"></span>${it.name}${it.sub?' <span style="color:var(--muted);font-size:10px">'+it.sub+'</span>':''} <b>${it.pct}%</b></div>`).join('') + '</div>';
  el.innerHTML = `<div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap">${svg}${legend}</div>`;
}

function perfSection(d){
  const p = d.performance;
  const rc = (p.total_return||0)>=0?'up':'down';
  const bc = (p.benchmark_return||0)>=0?'up':'down';
  const cagr = (p.cagr_3y===null||p.cagr_3y===undefined)?'':`<span class="dash-badge">3年CAGR ${p.cagr_3y}%</span>`;
  return `<div class="dash-box">
    <div class="dash-title">近一年績效曲線 vs ${d.benchmark}
      <span class="dash-badge ${rc}">組合 ${p.total_return>=0?'+':''}${p.total_return}%</span>
      <span class="dash-badge ${bc}">基準 ${p.benchmark_return>=0?'+':''}${p.benchmark_return}%</span>
    </div>
    <div id="dash-equity" class="dash-canvas"></div>
  </div>
  <div class="dash-grid2">
    <div class="dash-box"><div class="dash-title">近一年每月報酬（絕對）</div><div id="dash-monthly" class="dash-canvas"></div></div>
    <div class="dash-box"><div class="dash-title">近三年年度報酬 ${cagr}</div><div id="dash-annual" class="dash-canvas"></div></div>
  </div>`;
}

function drawEquity(elId, perf){
  const el = document.getElementById(elId);
  if (!el) return;
  const dates = (perf&&perf.dates)||[], pf = (perf&&perf.portfolio)||[], bm = (perf&&perf.benchmark)||[];
  if (dates.length < 2){ el.innerHTML = '<div style="color:var(--muted);padding:20px">數據不足</div>'; return; }
  const W=760,H=240,padL=55,padR=14,padT=14,padB=26;
  const all = pf.concat(bm);
  let maxV = Math.max(...all), minV = Math.min(...all,0);
  if (maxV===minV) maxV = minV+1;
  const range = maxV-minV, n=dates.length;
  const stepX = (W-padL-padR)/(n-1);
  const y = v => padT + (maxV-v)/range*(H-padT-padB);
  const x = i => padL + i*stepX;
  const path = s => s.map((v,i)=>`${i===0?'M':'L'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
  const y0 = y(0);
  let svg = `<svg width="${W}" height="${H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;background:var(--bg);border-radius:8px">`;
  svg += `<line x1="${padL}" y1="${y0}" x2="${W-padR}" y2="${y0}" stroke="var(--border)" stroke-width="1" stroke-dasharray="4,2"/>`;
  for (let g=0;g<=4;g++){ const v=maxV-g/4*range, yy=y(v);
    svg += `<line x1="${padL}" y1="${yy}" x2="${W-padR}" y2="${yy}" stroke="var(--bg3)" stroke-width="0.5"/>`;
    svg += `<text x="${padL-4}" y="${yy+3}" fill="var(--muted)" font-size="10" text-anchor="end">${v>=0?'+':''}${v.toFixed(1)}%</text>`; }
  svg += `<path d="${path(pf)}" fill="none" stroke="var(--accent)" stroke-width="2"/>`;
  svg += `<path d="${path(bm)}" fill="none" stroke="var(--gold)" stroke-width="2"/>`;
  svg += `<text x="${padL+4}" y="${padT+10}" fill="var(--accent)" font-size="10" font-weight="600">— 組合</text>`;
  svg += `<text x="${padL+70}" y="${padT+10}" fill="var(--gold)" font-size="10" font-weight="600">— 基準</text>`;
  [0,Math.floor((n-1)/2),n-1].forEach(i=>svg += `<text x="${x(i)}" y="${H-8}" fill="var(--muted)" font-size="10" text-anchor="middle">${dates[i]}</text>`);
  svg += '</svg>';
  el.innerHTML = svg;
}

function drawBars(elId, items, short){
  const el = document.getElementById(elId);
  if (!el) return;
  if (!items||!items.length){ el.innerHTML = '<div style="color:var(--muted);padding:20px">無資料</div>'; return; }
  const W=380,H=215,padL=46,padR=10,padT=22,padB=30;
  const vals = items.map(it=>it.ret);
  let maxV = Math.max(...vals,0), minV = Math.min(...vals,0);
  const span = (maxV-minV)||1;
  const gap = (W-padL-padR)/items.length;
  const bw = Math.min(30, gap*0.6);
  const y = v => padT + (maxV-v)/span*(H-padT-padB);
  const y0 = y(0);
  let svg = `<svg width="${W}" height="${H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;background:var(--bg);border-radius:8px">`;
  svg += `<line x1="${padL}" y1="${y0.toFixed(1)}" x2="${W-padR}" y2="${y0.toFixed(1)}" stroke="var(--border)" stroke-width="1"/>`;
  items.forEach((it,i)=>{
    const x0 = padL + i*gap + (gap-bw)/2;
    const yT = y(it.ret), yB = y0;
    const col = it.ret>=0 ? 'var(--up)' : 'var(--down)';
    const top = Math.min(yT,yB), hgt = Math.max(Math.abs(yB-yT),1);
    svg += `<rect x="${x0.toFixed(1)}" y="${top.toFixed(1)}" width="${bw.toFixed(1)}" height="${hgt.toFixed(1)}" fill="${col}" rx="2"/>`;
    const labelY = it.ret>=0 ? yT-7 : yT+13;
    svg += `<text x="${(x0+bw/2).toFixed(1)}" y="${labelY.toFixed(1)}" fill="${col}" font-size="9" font-weight="600" text-anchor="middle">${it.ret>=0?'+':''}${it.ret.toFixed(1)}</text>`;
    const lbl = (short && it.label.length>4) ? it.label.slice(2) : it.label;
    svg += `<text x="${(x0+bw/2).toFixed(1)}" y="${H-9}" fill="var(--muted)" font-size="9" text-anchor="middle">${lbl}</text>`;
  });
  svg += '</svg>';
  el.innerHTML = svg;
}

function riskSection(d){
  return `<div class="dash-box">
    <div class="dash-title">風險指標（最大回撤 / 波動 / 夏普 / 索提諾 / 貝塔）</div>
    <div id="dash-risk" class="stats-grid"></div>
  </div>
  <div class="dash-box">
    <div class="dash-title">資產相關性矩陣（近一年日報酬）</div>
    <div id="dash-corr" style="overflow-x:auto"></div>
  </div>`;
}

function drawRiskCards(elId, r){
  const el = document.getElementById(elId);
  if (!el) return;
  const f2 = v => v.toFixed(2);
  const card = (label, v, fmt, cls) => {
    const val = (v===null||v===undefined||isNaN(v)) ? '--' : fmt(v);
    return `<div class="stat-card"><div class="stat-label">${label}</div><div class="stat-value ${cls||''}" style="font-size:20px">${val}</div></div>`;
  };
  el.innerHTML =
    card('最大回撤（全期）', r.max_drawdown, v=>v.toFixed(1)+'%', 'down') +
    card('最大回撤（近1年）', r.max_drawdown_1y, v=>v.toFixed(1)+'%', 'down') +
    card('波動率（1年）', r.volatility_1y, v=>v.toFixed(1)+'%') +
    card('波動率（3年）', r.volatility_3y, v=>v.toFixed(1)+'%') +
    card('夏普（1年）', r.sharpe_1y, f2, clsRatio(r.sharpe_1y)) +
    card('夏普（3年）', r.sharpe_3y, f2, clsRatio(r.sharpe_3y)) +
    card('索提諾（1年）', r.sortino_1y, f2, clsRatio(r.sortino_1y)) +
    card('索提諾（3年）', r.sortino_3y, f2, clsRatio(r.sortino_3y)) +
    card('貝塔（1年）', r.beta_1y, f2, clsRatio(r.beta_1y)) +
    card('貝塔（3年）', r.beta_3y, f2, clsRatio(r.beta_3y));
}

function drawCorr(elId, corr){
  const el = document.getElementById(elId);
  if (!el) return;
  const syms = (corr&&corr.symbols)||[], mat = (corr&&corr.matrix)||[];
  if (syms.length < 2){ el.innerHTML = '<div style="color:var(--muted);padding:16px;font-size:12px;text-align:center">需至少 2 檔標的才能計算相關性</div>'; return; }
  const cell = 46, labelCol = 68, W = labelCol + cell*syms.length, H = 32 + cell*syms.length;
  const heat = v => {
    if (v===null||v===undefined||isNaN(v)) return 'var(--bg3)';
    const t = Math.max(-1, Math.min(1, v));
    return t>=0 ? `rgba(74,222,128,${(0.15+t*0.6).toFixed(2)})` : `rgba(248,113,113,${(0.15+(-t)*0.6).toFixed(2)})`;
  };
  let svg = `<svg width="${W}" height="${H}" xmlns="http://www.w3.org/2000/svg" style="display:block;max-width:100%;height:auto;background:var(--bg);border-radius:8px">`;
  syms.forEach((s,j)=>{
    svg += `<text x="${labelCol+j*cell+cell/2}" y="14" fill="var(--text2)" font-size="10" text-anchor="middle">${s}</text>`;
    svg += `<text x="${labelCol-9}" y="${32+j*cell+cell/2+4}" fill="var(--text2)" font-size="10" text-anchor="end">${s}</text>`;
  });
  for (let i=0;i<syms.length;i++){
    for (let j=0;j<syms.length;j++){
      const v = (mat[i]||[])[j];
      const x = labelCol+j*cell, y = 32+i*cell;
      svg += `<rect x="${x}" y="${y}" width="${cell}" height="${cell}" fill="${heat(v)}" stroke="var(--bg)" stroke-width="1"/>`;
      svg += `<text x="${x+cell/2}" y="${y+cell/2+4}" fill="var(--text)" font-size="10" text-anchor="middle">${(v===null||v===undefined||isNaN(v))?'--':v.toFixed(2)}</text>`;
    }
  }
  svg += '</svg>';
  el.innerHTML = `<div style="display:flex;justify-content:center;width:100%;padding:8px 0">${svg}</div>`;
}
</script>
"""


def generate_html():
    """生成 HTML 內容"""
    lang = get_lang()
    lang_selected_zh_TW = ' selected' if lang == 'zh-TW' else ''
    lang_selected_zh_CN = ' selected' if lang == 'zh-CN' else ''
    lang_selected_en = ' selected' if lang == 'en' else ''
    portfolios = list_portfolios()
    active_id = portfolios[0]["id"] if portfolios else None
    symbols_json = json.dumps({_k: {"symbol": _v["symbol"], "name": _v["name"], "category": _v["category"], "currency": _v["currency"]} for _k, _v in _symbols.items()}, default=str)

    css = f"""
<style>
:root {{
  --bg: {THEME['bg']}; --bg2: {THEME['bg2']}; --bg3: {THEME['bg3']}; --card: {THEME['card']};
  --border: {THEME['border']}; --text: {THEME['text']}; --text2: {THEME['text2']}; --muted: {THEME['muted']};
  --up: {THEME['up']}; --down: {THEME['down']}; --accent: {THEME['accent']};
  --gold: {THEME['gold']}; --purple: {THEME['purple']}; --cyan: {THEME['cyan']};
}}
html {{ zoom: 1.25; }}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif; min-height: 100vh; }}
.sidebar {{ position: fixed; left: 0; top: 0; width: 220px; height: 100vh; background: var(--bg2); border-right: 1px solid var(--border); padding: 0; z-index: 100; overflow-y: auto; }}
.sidebar-header {{ padding: 20px 16px 16px; border-bottom: 1px solid var(--border); }}
.sidebar-header h2 {{ font-size: 16px; font-weight: 600; color: var(--text); margin-bottom: 4px; }}
.sidebar-header p {{ font-size: 11px; color: var(--muted); }}
.sidebar-nav {{ padding: 8px 0; }}
.nav-item {{ display: flex; align-items: center; gap: 12px; padding: 12px 20px; color: var(--text2); text-decoration: none; font-size: 14px; cursor: pointer; transition: all 0.2s; border-left: 3px solid transparent; }}
.nav-item:hover {{ background: var(--bg3); color: var(--text); }}
.nav-item.active {{ background: var(--bg3); color: var(--accent); border-left-color: var(--accent); }}
.main-content {{ margin-left: 220px; min-height: 100vh; }}
.topbar {{ position: sticky; top: 0; z-index: 50; background: var(--bg2); border-bottom: 1px solid var(--border); padding: 12px 24px; display: flex; align-items: center; justify-content: space-between; }}
.topbar-title {{ font-size: 18px; font-weight: 600; }}
.page {{ display: none; padding: 24px; }}
.page.active {{ display: block; }}
.card {{ background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 20px; margin-bottom: 16px; }}
.card-header {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }}
.card-title {{ font-size: 12px; font-weight: 600; color: var(--text2); text-transform: uppercase; letter-spacing: 0.5px; }}
.stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }}
.stat-card {{ background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 20px; transition: transform 0.2s; }}
.stat-card:hover {{ transform: translateY(-2px); box-shadow: 0 4px 20px rgba(0,0,0,0.3); }}
.stat-label {{ font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; }}
.stat-value {{ font-size: 26px; font-weight: 700; line-height: 1; }}
.up {{ color: var(--up); }} .down {{ color: var(--down); }}
.ratio-high {{ color: var(--gold); }} .ratio-low {{ color: var(--purple); }}
.btn {{ display: inline-flex; align-items: center; gap: 6px; padding: 8px 16px; border-radius: 6px; border: 1px solid var(--border); background: var(--bg3); color: var(--text); font-size: 13px; cursor: pointer; transition: all 0.2s; text-decoration: none; }}
.btn:hover {{ background: var(--accent); border-color: var(--accent); color: white; }}
.btn-primary {{ background: var(--accent); border-color: var(--accent); color: white; }}
.btn-danger {{ background: var(--down); border-color: var(--down); color: white; }}
.btn-sm {{ padding: 4px 10px; font-size: 12px; }}
.form-group {{ margin-bottom: 16px; }}
.form-label {{ display: block; font-size: 11px; color: var(--text2); margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.5px; }}
.form-input {{ width: 100%; padding: 10px 12px; background: var(--bg3); border: 1px solid var(--border); border-radius: 6px; color: var(--text); font-size: 14px; outline: none; }}
.form-input:focus {{ border-color: var(--accent); }}
.form-row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }}
.table-container {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th {{ text-align: left; padding: 10px 12px; background: var(--bg3); color: var(--muted); font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid var(--border); }}
td {{ padding: 10px 12px; border-bottom: 1px solid var(--border); }}
tr:hover td {{ background: var(--bg3); }}
.text-right {{ text-align: right; }} .text-center {{ text-align: center; }}
.tag {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 500; }}
.tag-stock {{ background: rgba(59,130,246,0.2); color: var(--accent); }}
.tag-etf {{ background: rgba(167,139,250,0.2); color: var(--purple); }}
.tag-index {{ background: rgba(34,211,238,0.2); color: var(--cyan); }}
.tag-commodity {{ background: rgba(251,191,36,0.2); color: var(--gold); }}
.modal-overlay {{ display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.7); z-index: 300; align-items: center; justify-content: center; padding: 24px; box-sizing: border-box; }}
.modal-overlay.show {{ display: flex; }}
.modal {{ background: var(--card); border: 1px solid var(--border); border-radius: 12px; width: 90%; max-width: 600px; max-height: 100%; display: flex; flex-direction: column; overflow: hidden; }}
.modal-header {{ flex-shrink: 0; display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 20px 24px; border-bottom: 1px solid var(--border); }}
.modal-title {{ font-size: 18px; font-weight: 600; }}
.modal-close {{ background: var(--bg3); border: 1px solid var(--border); color: var(--text); font-size: 18px; width: 36px; height: 36px; line-height: 1; border-radius: 6px; cursor: pointer; flex-shrink: 0; }}
.modal-close:hover {{ background: var(--accent); border-color: var(--accent); color: #fff; }}
.modal-body {{ flex: 1; overflow-y: auto; padding: 24px; }}
.modal-footer {{ flex-shrink: 0; display: flex; justify-content: flex-end; gap: 12px; padding: 16px 24px; border-top: 1px solid var(--border); background: var(--card); }}
.dropdown-content {{ display: none; position: absolute; background: var(--card); border: 1px solid var(--border); border-radius: 8px; min-width: 280px; max-height: 400px; overflow-y: auto; z-index: 200; box-shadow: 0 8px 32px rgba(0,0,0,0.4); }}
.dropdown-content.show {{ display: block; }}
.dropdown-item {{ padding: 10px 16px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; }}
.dropdown-item:hover {{ background: var(--bg3); }}
.dropdown-item .sym {{ color: var(--accent); font-weight: 600; font-size: 13px; }}
.dropdown-item .name {{ color: var(--text2); font-size: 12px; }}
.dropdown-item .meta {{ color: var(--muted); font-size: 11px; }}
.search-box {{ position: relative; display: inline-block; width: 100%; }}
.search-box::before {{ content: "\\1F50D"; position: absolute; left: 10px; top: 50%; transform: translateY(-50%); font-size: 14px; z-index: 1; }}
.search-box .form-input {{ padding-left: 36px; }}
.empty-state {{ text-align: center; padding: 60px 20px; color: var(--muted); }}
.empty-state .icon {{ font-size: 48px; margin-bottom: 16px; }}
.info-cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; }}
.info-card {{ background: var(--bg3); border: 1px solid var(--border); border-radius: 8px; padding: 14px; }}
.info-card h4 {{ font-size: 12px; color: var(--accent); margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.5px; }}
.info-row {{ display: flex; justify-content: space-between; gap: 12px; padding: 6px 0; font-size: 13px; border-bottom: 1px solid rgba(255,255,255,0.05); }}
.info-row .lbl {{ color: var(--text2); }}
.info-row .val {{ color: var(--text); font-weight: 500; text-align: right; }}
.news-item {{ background: var(--bg3); border: 1px solid var(--border); border-radius: 8px; padding: 12px 14px; margin-bottom: 10px; }}
.news-item h4 {{ font-size: 14px; margin-bottom: 4px; }}
.news-item h4 a {{ color: var(--text); text-decoration: none; }}
.news-item h4 a:hover {{ color: var(--accent); }}
.news-meta {{ font-size: 11px; color: var(--muted); margin-bottom: 6px; }}
.news-summary {{ font-size: 12px; color: var(--text2); line-height: 1.5; }}
.tab-btn.active {{ background: var(--accent) !important; border-color: var(--accent) !important; color: #fff !important; }}
@keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: translateY(0); }} }}
.fade-in {{ animation: fadeIn 0.3s ease; }}
</style>
"""

    sidebar = """
    <div class="sidebar">
      <div class="sidebar-header">
        <h2>📊 投資績效分析軟體</h2>
        <p>v1.0.0 | Desktop Edition</p>
      </div>
      <div class="sidebar-nav">
        <a class="nav-item active" onclick="switchPage('overview')"><span class="nav-icon">📊</span><span>資產總覽</span></a>
        <a class="nav-item" onclick="switchPage('market')"><span class="nav-icon">📈</span><span>市場行情</span></a>
        <a class="nav-item" onclick="switchPage('portfolio')"><span class="nav-icon">💼</span><span>持倉管理</span></a>
        <a class="nav-item" onclick="switchPage('performance')"><span class="nav-icon">📉</span><span>績效分析</span></a>
        <a class="nav-item" onclick="switchPage('analysis')"><span class="nav-icon">🔍</span><span>歷史分析</span></a>
        <a class="nav-item" onclick="switchPage('symbols')"><span class="nav-icon">⭐</span><span>標的管理</span></a>
        <a class="nav-item" onclick="switchPage('reports')"><span class="nav-icon">📄</span><span>報告匯出</span></a>
        <a class="nav-item" onclick="switchPage('settings')"><span class="nav-icon">⚙️</span><span>系統設置</span></a>
      </div>
    </div>
    """

    main = f"""
    <div class="main-content">
      <div class="topbar">
        <div class="topbar-title" id="page-title">資產總覽</div>
        <div style="display:flex;gap:8px;align-items:center">
          <span id="conn-status" style="font-size:12px;color:var(--muted)">● 就緒</span>
          <button class="btn btn-sm" onclick="location.reload()">🔄 刷新</button>
        </div>
      </div>

      <div class="page active" id="page-overview">
        <div class="stats-grid fade-in" id="overview-stats">
          <div class="stat-card"><div class="stat-label">總資產價值</div><div class="stat-value" id="ov-total-value">--</div></div>
          <div class="stat-card"><div class="stat-label">總投入資金</div><div class="stat-value" id="ov-total-cost">--</div></div>
          <div class="stat-card"><div class="stat-label">總損益</div><div class="stat-value" id="ov-total-pnl">--</div><div class="stat-change" id="ov-pnl-pct"></div></div>
          <div class="stat-card"><div class="stat-label">持倉數</div><div class="stat-value" id="ov-count">--</div></div>
          <div class="stat-card"><div class="stat-label">現金餘額</div><div class="stat-value" id="ov-cash">--</div></div>
        </div>
        <div class="card fade-in">
          <div class="card-header"><span class="card-title">持倉明細 <span id="ov-currency" style="color:var(--accent);font-size:11px"></span></span><button class="btn btn-sm" onclick="switchPage('portfolio')">管理持倉 →</button></div>
          <div class="table-container">
            <table>
              <thead><tr><th>標的</th><th>數量</th><th>成本價</th><th>現價</th><th class="text-right">市值</th><th class="text-right">損益</th><th class="text-right">損益率</th><th class="text-right">權重</th></tr></thead>
              <tbody id="ov-positions"></tbody>
            </table>
          </div>
        </div>
        <div class="card fade-in" id="dashboard-card">
          <div class="card-header"><span class="card-title">📊 投資組合可視圖</span></div>
          <div id="dash-body"></div>
        </div>
      </div>

      <div class="page" id="page-market">
        <div class="card fade-in">
          <div class="card-header"><span class="card-title">市場行情</span><button class="btn btn-sm" onclick="loadMarket()">🔄 刷新</button></div>
          <div style="display:flex;align-items:center;gap:8px;margin:-4px 0 14px;padding:8px 12px;background:rgba(245,158,11,0.12);border:1px solid rgba(245,158,11,0.45);border-radius:6px;color:#f59e0b;font-size:12px;font-weight:600">⚠️ <span>報價資訊延遲至少15~20分鐘。所有資訊僅供參考，實際交易價格請以券商或交易所為準。</span></div>
          <div style="display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap">
            <button class="btn btn-sm" onclick="filterMarket('ALL')">全部</button>
            <button class="btn btn-sm" onclick="filterMarket('STOCK')">股票</button>
            <button class="btn btn-sm" onclick="filterMarket('ETF')">ETF</button>
            <button class="btn btn-sm" onclick="filterMarket('INDEX')">指數</button>
            <button class="btn btn-sm" onclick="filterMarket('COMMODITY')">商品</button>
            <button class="btn btn-sm" onclick="filterMarket('FX')">匯率</button>
          </div>
          <div class="table-container">
            <table>
              <thead><tr><th>代碼</th><th>名稱</th><th>類別</th><th>現價</th><th class="text-right">漲跌</th><th class="text-right">漲跌幅</th><th class="text-right">3年貝塔</th><th class="text-right">3年夏普</th><th class="text-right">3年索提諾</th></tr></thead>
              <tbody id="market-tbody"></tbody>
            </table>
          </div>
        </div>
      </div>

      <div class="page" id="page-portfolio">
        <div class="card fade-in">
          <div class="card-header"><span class="card-title">投資組合 <span id="pf-currency" style="color:var(--accent);font-size:11px"></span></span>
            <div style="display:flex;gap:8px;align-items:center">
              <select class="form-input" style="width:200px" id="pf-select" onchange="selectPortfolio(this.value)"></select>
              <button class="btn btn-sm" onclick="showModal('add-pf-modal')">+ 新增組合</button>
              <button class="btn btn-sm btn-danger" onclick="deletePortfolio()">🗑 刪除組合</button>
              <button class="btn btn-primary btn-sm" onclick="showModal('add-pos-modal')">+ 新增標的</button>
            </div>
          </div>
          <div id="pf-stats" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:20px"></div>
          <div class="table-container">
            <table>
              <thead><tr><th>標的</th><th>成本</th><th>數量</th><th>現價</th><th class="text-right">總成本</th><th class="text-right">淨市值</th><th class="text-right">損益</th><th class="text-right">損益率</th><th class="text-center">操作</th></tr></thead>
              <tbody id="pf-positions"></tbody>
            </table>
          </div>
        </div>
      </div>

      <div class="page" id="page-performance">
        <div class="card fade-in">
          <div class="card-header"><span class="card-title">績效指標</span>
            <div style="display:flex;gap:8px;align-items:center">
              <select class="form-input" style="width:150px" id="perf-period" onchange="onPerfPeriodChange()">
                <option value="6m" selected>半年前至今</option>
                <option value="1y">一年前至今</option>
                <option value="custom">特定日期至今</option>
              </select>
              <input type="date" class="form-input" id="perf-date" style="width:150px;display:none" onchange="loadPerfRange()">
              <span class="form-label" style="color:var(--muted);font-size:11px" id="perf-bench-label"></span>
            </div>
          </div>
          <div class="stats-grid" id="perf-stats"></div>
          <div id="perf-chart" style="min-height:300px;background:var(--bg);border:1px solid var(--border);border-radius:8px;margin-top:16px;display:flex;align-items:center;justify-content:center;color:var(--muted)">
            <div class="empty-state"><div class="icon">📉</div><p>選擇區間以顯示績效與 Benchmark 對比曲線</p></div>
          </div>
          <div id="perf-legend" style="display:flex;gap:16px;margin-top:8px;font-size:12px;color:var(--muted)"></div>
          <div class="stats-grid" id="perf-risk" style="margin-top:16px"></div>
        </div>
      </div>

      <div class="page" id="page-analysis">
        <div class="card fade-in">
          <div class="card-header"><span class="card-title">歷史行情分析</span></div>
          <div style="display:flex;gap:12px;margin-bottom:16px;flex-wrap:wrap;align-items:flex-end">
            <div class="form-group" style="flex:1;min-width:200px;margin:0">
              <label class="form-label">標的代碼</label>
              <div class="search-box"><input class="form-input" id="analysis-symbol" placeholder="輸入代碼..."></div>
            </div>
            <div class="form-group" style="margin:0">
              <label class="form-label">期間</label>
              <select class="form-input" id="analysis-period" style="width:120px">
                <option value="1d">1日</option><option value="5d">5日</option><option value="1mo">1月</option>
                <option value="3mo">3月</option><option value="6mo" selected>6月</option>
                <option value="1y">1年</option><option value="2y">2年</option><option value="max">全部</option>
              </select>
            </div>
            <button class="btn btn-primary" onclick="loadAnalysis()">🔍 分析</button>
          </div>
          <div id="analysis-chart" style="min-height:350px;background:var(--bg);border:1px solid var(--border);border-radius:8px;display:flex;align-items:center;justify-content:center;color:var(--muted)">
            <div class="empty-state"><div class="icon">📈</div><p>選擇標的並點擊分析</p></div>
          </div>
          <div id="analysis-stats" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-top:16px"></div>
        </div>
      </div>

      <div class="page" id="page-symbols">
        <div class="card fade-in">
          <div class="card-header"><span class="card-title">標的庫管理</span>
            <button class="btn btn-sm" onclick="showAddSymbol()">+ 新增標的</button>
          </div>
          <div style="display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap">
            <button class="btn btn-sm" onclick="filterSymbols('ALL')">全部</button>
            <button class="btn btn-sm" onclick="filterSymbols('STOCK')">股票</button>
            <button class="btn btn-sm" onclick="filterSymbols('ETF')">ETF</button>
            <button class="btn btn-sm" onclick="filterSymbols('INDEX')">指數</button>
            <button class="btn btn-sm" onclick="filterSymbols('COMMODITY')">商品</button>
          </div>
          <div class="table-container">
            <table>
              <thead><tr><th>代碼</th><th>名稱</th><th>類別</th><th>貨幣</th><th>操作</th></tr></thead>
              <tbody id="sym-tbody"></tbody>
            </table>
          </div>
        </div>
      </div>

      <div class="page" id="page-reports">
        <div class="card fade-in">
          <div class="card-header"><span class="card-title">報告匯出</span></div>
          <div style="display:flex;gap:16px;flex-wrap:wrap">
            <div style="flex:1;min-width:200px">
              <div class="form-group"><label class="form-label">投資組合</label><select class="form-input" id="report-pf"></select></div>
              <div class="form-group"><label class="form-label">格式</label>
                <div style="display:flex;gap:8px">
                  <button class="btn" onclick="exportReport('csv')">📊 CSV</button>
                  <button class="btn" onclick="exportReport('json')">📋 JSON</button>
                  <button class="btn" onclick="exportReport('html')">🌐 HTML</button>
                </div>
              </div>
            </div>
            <div style="flex:2;min-width:300px">
              <div id="report-preview" style="min-height:200px;background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:16px;color:var(--muted);display:flex;align-items:center;justify-content:center">
                <div class="empty-state"><div class="icon">📋</div><p>選擇組合與格式後匯出</p></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="page" id="page-settings">
        <div class="card fade-in">
          <div class="card-header"><span class="card-title">系統設置</span></div>
          <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:20px">
            <div>
              <h3 style="font-size:14px;margin-bottom:12px;color:var(--text2)">語言</h3>
              <div class="form-group"><label class="form-label">介面語言</label>
                <select class="form-input" id="lang-select" onchange="changeLang(this.value)">
                  <option value="zh-TW"{lang_selected_zh_TW}>繁體中文</option>
                  <option value="zh-CN"{lang_selected_zh_CN}>简体中文</option>
                  <option value="en"{lang_selected_en}>English</option>
                </select>
              </div>
            </div>
            <div>
              <h3 style="font-size:14px;margin-bottom:12px;color:var(--text2)">數據緩存</h3>
              <div style="display:flex;gap:8px;margin-bottom:12px">
                <button class="btn btn-sm" onclick="clearCache()">清除緩存</button>
                <button class="btn btn-sm" onclick="showCacheStatus()">查看狀態</button>
              </div>
              <div id="cache-status" style="font-size:13px;color:var(--text2)"></div>
            </div>
            <div>
              <h3 style="font-size:14px;margin-bottom:12px;color:var(--text2)">手續費設定</h3>
              <div class="form-group"><label class="form-label">買入手續費率 (%)</label><input class="form-input" type="number" step="0.0001" value="0.1425" id="buy-fee"></div>
              <div class="form-group"><label class="form-label">賣出手續費率 (%)</label><input class="form-input" type="number" step="0.0001" value="0.1425" id="sell-fee"></div>
              <div class="form-group"><label class="form-label">交易稅率 (%)</label><input class="form-input" type="number" step="0.001" value="0.3" id="tax-rate"></div>
            </div>
            <div>
              <h3 style="font-size:14px;margin-bottom:12px;color:var(--text2)">關於</h3>
              <div style="font-size:13px;color:var(--text2);line-height:2">
                <p><strong>投資績效分析軟體</strong> v1.0.0</p>
                <p>技術棧: Python + pywebview + yfinance</p>
                <p>數據來源: Yahoo Finance</p>
                <p>所有數據存儲於本地</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 新增標的模態框 -->
    <div class="modal-overlay" id="add-pos-modal">
      <div class="modal">
        <div class="modal-header"><div class="modal-title">新增標的</div><button class="modal-close" onclick="hideModal('add-pos-modal')">&times;</button></div>
        <div class="modal-body">
        <div class="form-group">
          <label class="form-label">類型</label>
          <select class="form-input" id="pos-type" onchange="togglePosType(this.value)">
            <option value="stock">股票 / ETF / 指數</option>
            <option value="cash">現金</option>
          </select>
        </div>
        <div id="pos-stock-section">
          <div class="form-group">
            <label class="form-label">標的搜尋</label>
            <div class="search-box"><input class="form-input" id="pos-search" placeholder="輸入代碼或名稱..." oninput="searchSymbols(this.value)"></div>
            <div id="pos-dropdown" class="dropdown-content" style="position:relative;width:100%;border-radius:6px;margin-top:4px"></div>
          </div>
          <div class="form-group"><label class="form-label">標的名稱</label><input class="form-input" id="pos-name"></div>
          <div class="form-row">
            <div class="form-group"><label class="form-label">成本價</label><input class="form-input" type="number" step="0.01" id="pos-cost" placeholder="0.00"></div>
            <div class="form-group"><label class="form-label">持有數量</label><input class="form-input" type="number" step="1" id="pos-qty" placeholder="0"></div>
          </div>
          <div class="form-row">
            <div class="form-group"><label class="form-label">買入手續費率 (%)</label><input class="form-input" type="number" step="0.0001" value="0.1425" id="pos-buy-fee"></div>
            <div class="form-group"><label class="form-label">賣出手續費率 (%)</label><input class="form-input" type="number" step="0.0001" value="0.1425" id="pos-sell-fee"></div>
            <div class="form-group"><label class="form-label">交易稅率 (%)</label><input class="form-input" type="number" step="0.001" value="0.3" id="pos-tax"></div>
          </div>
        </div>
        <div id="pos-cash-section" style="display:none">
          <div class="form-group"><label class="form-label">現金金額</label><input class="form-input" type="number" step="0.01" id="pos-cash-amount" placeholder="輸入現金金額"></div>
          <p style="font-size:12px;color:var(--muted)">現金將作為一項標的加入投資組合（無手續費、無損益）。</p>
        </div>
        </div>
        <div class="modal-footer">
          <button class="btn" onclick="hideModal('add-pos-modal')">取消</button>
          <button class="btn btn-primary" onclick="submitPosition()">確認新增</button>
        </div>
      </div>
    </div>

    <!-- 新增組合模態框 -->
    <div class="modal-overlay" id="add-pf-modal">
      <div class="modal">
        <div class="modal-header"><div class="modal-title">新增投資組合</div><button class="modal-close" onclick="hideModal('add-pf-modal')">&times;</button></div>
        <div class="modal-body">
        <div class="form-group"><label class="form-label">組合名稱</label><input class="form-input" id="new-pf-name"></div>
        <div class="form-row">
          <div class="form-group"><label class="form-label">計價貨幣</label>
            <select class="form-input" id="new-pf-currency">
              <option value="TWD">台幣 (TWD)</option><option value="USD">美元 (USD)</option>
              <option value="CNY">人民幣 (CNY)</option><option value="HKD">港幣 (HKD)</option>
              <option value="JPY">日圓 (JPY)</option>
            </select>
          </div>
          <div class="form-group"><label class="form-label">基準指標</label>
            <select class="form-input" id="new-pf-benchmark">
              <option value="^TWII">台股加權指數</option><option value="^GSPC">標普500</option>
              <option value="^IXIC">納斯達克</option><option value="^HSI">恆生指數</option>
              <option value="000001.SS">上證指數</option><option value="SPY">SPY ETF</option>
            </select>
          </div>
        </div>
        </div>
        <div class="modal-footer">
          <button class="btn" onclick="hideModal('add-pf-modal')">取消</button>
          <button class="btn btn-primary" onclick="submitPortfolio()">建立組合</button>
        </div>
      </div>
    </div>

    <!-- 相關資訊模態框 -->
    <div class="modal-overlay" id="info-modal">
      <div class="modal" style="max-width:1100px;width:96%">
        <div class="modal-header">
          <div class="modal-title" id="info-title">相關資訊</div>
          <button class="modal-close" onclick="hideModal('info-modal')">&times;</button>
        </div>
        <div class="modal-body">
        <div style="display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap">
          <button class="btn btn-sm tab-btn" id="info-tab-fund" onclick="infoTab('fund')">📊 基本面</button>
          <button class="btn btn-sm tab-btn" id="info-tab-tech" onclick="infoTab('tech')">📈 技術圖</button>
          <button class="btn btn-sm tab-btn" id="info-tab-news" onclick="infoTab('news')">📰 相關新聞</button>
        </div>
        <div id="info-fund"></div>
        <div id="info-tech" style="display:none"></div>
        <div id="info-news" style="display:none"></div>
        </div>
        <div class="modal-footer">
          <button class="btn" onclick="hideModal('info-modal')">關閉</button>
        </div>
      </div>
    </div>

    <!-- 新增標的庫模態框 -->
    <div class="modal-overlay" id="add-sym-modal">
      <div class="modal">
        <div class="modal-header"><div class="modal-title">新增標的</div><button class="modal-close" onclick="hideModal('add-sym-modal')">&times;</button></div>
        <div class="modal-body">
          <div class="form-group">
            <label class="form-label">標的搜尋</label>
            <div class="search-box"><input class="form-input" id="sym-search" placeholder="輸入代碼或名稱搜尋..." oninput="searchSymIndex(this.value)"></div>
            <div id="sym-dropdown" class="dropdown-content" style="position:relative;width:100%;border-radius:6px;margin-top:4px"></div>
          </div>
          <div class="form-group"><label class="form-label">代碼</label><input class="form-input" id="sym-code" placeholder="例：AAPL、2330.TW"></div>
          <div class="form-group"><label class="form-label">名稱</label><input class="form-input" id="sym-name" placeholder="例：蘋果"></div>
          <div class="form-row">
            <div class="form-group"><label class="form-label">類別</label>
              <select class="form-input" id="sym-category">
                <option value="STOCK">股票</option>
                <option value="ETF">ETF</option>
                <option value="INDEX">指數</option>
                <option value="COMMODITY">商品</option>
                <option value="FX">匯率</option>
              </select>
            </div>
            <div class="form-group"><label class="form-label">貨幣</label>
              <select class="form-input" id="sym-currency">
                <option value="TWD">台幣 (TWD)</option><option value="USD">美元 (USD)</option>
                <option value="CNY">人民幣 (CNY)</option><option value="HKD">港幣 (HKD)</option>
                <option value="JPY">日圓 (JPY)</option>
              </select>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn" onclick="hideModal('add-sym-modal')">取消</button>
          <button class="btn btn-primary" onclick="submitSymbol()">確認新增</button>
        </div>
      </div>
    </div>
    """

    js = f"""
    <script>
    let activePF = localStorage.getItem('yfi_activePF') || '{active_id}';
    const symbols_db = {symbols_json};

    function switchPage(page) {{
      document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
      document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
      document.getElementById('page-' + page).classList.add('active');
      event.target.closest('.nav-item').classList.add('active');
      const titles = {{overview:'資產總覽',market:'市場行情',portfolio:'持倉管理',performance:'績效分析',analysis:'歷史分析',symbols:'標的管理',reports:'報告匯出',settings:'系統設置'}};
      document.getElementById('page-title').textContent = titles[page] || page;
      if (page === 'market') loadMarket();
      if (page === 'portfolio') loadPortfolio();
      if (page === 'performance') loadPerfRange();
      if (page === 'symbols') loadSymbols();
      if (page === 'reports') loadReportPFs();
    }}

    async function loadMarket(filter = 'ALL') {{
      const tbody = document.getElementById('market-tbody');
      tbody.innerHTML = '<tr><td colspan="10" class="text-center">載入中...</td></tr>';
      const allSymbols = Object.values(symbols_db);
      let symbols = filter === 'ALL' ? allSymbols : allSymbols.filter(s => s.category === filter);
      const symList = symbols.map(s => s.symbol).join(',');
      let quotes = {{}};
      let ratios = {{}};
      try {{
        const [qData, rData] = await Promise.all([
          fetch('/api/quotes?symbols=' + encodeURIComponent(symList)).then(r => r.json()).catch(() => ({{}})),
          fetch('/api/risk_ratios?symbols=' + encodeURIComponent(symList)).then(r => r.json()).catch(() => ({{}}))
        ]);
        quotes = (qData && qData.quotes) || {{}};
        ratios = (rData && rData.ratios) || {{}};
      }} catch(e) {{}}
      tbody.innerHTML = '';
      const fmtRatio = (v) => (v === null || v === undefined || isNaN(v)) ? '--' : Number(v).toFixed(2);
      const ratioClass = (v) => (v === null || v === undefined || isNaN(v)) ? '' : (Number(v) >= 1 ? 'up' : 'down');
      symbols.forEach(sym => {{
        const q = quotes[sym.symbol] || {{}};
        const rt = ratios[sym.symbol] || {{}};
        const tr = document.createElement('tr');
        const changeClass = (q.change_pct || 0) >= 0 ? 'up' : 'down';
        const sign = (q.change_pct || 0) >= 0 ? '+' : '';
        tr.innerHTML = `<td><strong>${{sym.symbol}}</strong></td><td>${{sym.name}}</td><td><span class="tag tag-${{sym.category.toLowerCase()}}">${{sym.category}}</span></td><td>${{q.price?.toLocaleString() || '--'}}</td><td class="text-right ${{changeClass}}">${{sign}}${{q.change?.toFixed(2) || '--'}}</td><td class="text-right ${{changeClass}}">${{sign}}${{q.change_pct?.toFixed(2) || '--'}}%</td><td class="text-right ${{ratioClass(rt.beta_3y)}}">${{fmtRatio(rt.beta_3y)}}</td><td class="text-right ${{ratioClass(rt.sharpe_3y)}}">${{fmtRatio(rt.sharpe_3y)}}</td><td class="text-right ${{ratioClass(rt.sortino_3y)}}">${{fmtRatio(rt.sortino_3y)}}</td>`;
        tbody.appendChild(tr);
      }});
    }}
    function filterMarket(cat) {{ loadMarket(cat); }}

    function loadPortfolioList() {{
      fetch('/api/portfolios').then(r => r.json()).then(data => {{
        const select = document.getElementById('pf-select');
        const list = data.portfolios || [];
        if (!list.length) {{
          select.innerHTML = '<option value="">尚無投資組合</option>';
          return;
        }}
        if (!list.find(p => p.id === activePF)) {{
          activePF = list[0].id;
          localStorage.setItem('yfi_activePF', activePF);
          loadPortfolio(activePF); loadOverview();
        }}
        select.innerHTML = list.map(p => `<option value="${{p.id}}" ${{p.id === activePF ? 'selected' : ''}}>${{p.name}}</option>`).join('');
        select.value = activePF;
      }});
    }}

    async function loadPortfolio(pid) {{
      if (!pid) pid = activePF;
      if (!pid) return;
      activePF = pid;
      localStorage.setItem('yfi_activePF', pid);
      const sel = document.getElementById('pf-select');
      if (sel && sel.value !== pid) sel.value = pid;
      const res = await fetch('/api/performance/' + pid);
      const perf = await res.json();
      if (!perf.name) {{
        document.getElementById('pf-stats').innerHTML = '<div class="empty-state"><div class="icon">💼</div><p>此組合尚無持倉</p></div>';
        document.getElementById('pf-positions').innerHTML = '<tr><td colspan="9" class="text-center" style="padding:40px;color:var(--muted)">尚無持倉，請點擊「新增標的」</td></tr>';
        return;
      }}
      const pfCurEl = document.getElementById('pf-currency');
      if (pfCurEl) pfCurEl.textContent = perf.base_currency ? '(' + perf.base_currency + ')' : '';
      document.getElementById('pf-stats').innerHTML = `
        <div class="stat-card"><div class="stat-label">總資產</div><div class="stat-value">${{Math.round(perf.total_value || 0).toLocaleString()}}</div></div>
        <div class="stat-card"><div class="stat-label">總投入</div><div class="stat-value">${{Math.round(perf.total_invested || 0).toLocaleString()}}</div></div>
        <div class="stat-card"><div class="stat-label">總損益</div><div class="stat-value" style="color:${{(perf.total_pnl||0)>=0?'var(--up)':'var(--down)'}}">${{(perf.total_pnl||0)>=0?'+':''}}${{Math.round(perf.total_pnl || 0).toLocaleString()}}</div></div>
        <div class="stat-card"><div class="stat-label">損益率</div><div class="stat-value" style="color:${{(perf.total_pnl_pct||0)>=0?'var(--up)':'var(--down)'}}">${{(perf.total_pnl_pct||0).toFixed(2)}}%</div></div>
      `;
      const tbody = document.getElementById('pf-positions');
      tbody.innerHTML = '';
      (perf.positions || []).forEach(pos => {{
        const pnlClass = pos.pnl >= 0 ? 'up' : 'down';
        const sign = pos.pnl >= 0 ? '+' : '';
        const symEsc = String(pos.symbol || '').replace(/'/g, "\\'");
        const nmEsc = String(pos.name || '').replace(/'/g, "\\'");
        const tr = document.createElement('tr');
        tr.innerHTML = `<td><strong>${{pos.name}}</strong><br><span style="color:var(--muted);font-size:11px">${{pos.symbol}}${{pos.currency && pos.currency !== pos.base_currency ? ' · ' + pos.currency : ''}}</span></td><td>${{pos.cost_price?.toFixed(2) || '--'}}</td><td>${{pos.quantity?.toLocaleString() || 0}}</td><td>${{(pos.current_price || 0).toFixed(2)}}${{pos.fx && pos.fx !== 1 ? `<br><span style="color:var(--muted);font-size:10px">${{(pos.base_price || 0).toFixed(2)}} ${{pos.currency}}</span>` : ''}}</td><td class="text-right">${{Math.round(pos.total_cost || 0).toLocaleString()}}</td><td class="text-right">${{Math.round(pos.net_market_value || 0).toLocaleString()}}</td><td class="text-right ${{pnlClass}}">${{sign}}${{Math.round(pos.pnl || 0).toLocaleString()}}</td><td class="text-right ${{pnlClass}}">${{sign}}${{pos.pnl_pct?.toFixed(2) || 0}}%</td><td class="text-center">${{pos.symbol !== 'CASH' ? `<button class="btn btn-sm" title="相關資訊" onclick="showInfoModal('${{symEsc}}','${{nmEsc}}')">ℹ</button>` : ''}}<button class="btn btn-sm btn-danger" onclick="removePosition('${{pos.id}}')">刪除</button></td>`;
        tbody.appendChild(tr);
      }});
    }}

    function selectPortfolio(pid) {{ loadPortfolio(pid); loadOverview(); }}

    async function deletePortfolio() {{
      if (!activePF) {{ alert('尚無投資組合可刪除'); return; }}
      if (!confirm('確定刪除此投資組合？此操作無法復原。')) return;
      const res = await fetch('/api/portfolios/' + activePF, {{ method: 'DELETE' }});
      const data = await res.json();
      if (!data.success) {{ alert('刪除失敗: ' + (data.error || '未知錯誤')); return; }}
      localStorage.removeItem('yfi_activePF');
      activePF = null;
      await loadPortfolioList();
      if (activePF) {{ loadPortfolio(activePF); loadOverview(); }}
      else {{
        document.getElementById('pf-stats').innerHTML = '<div class="empty-state"><div class="icon">💼</div><p>尚無投資組合</p></div>';
        document.getElementById('pf-positions').innerHTML = '<tr><td colspan="9" class="text-center" style="padding:40px;color:var(--muted)">請先建立投資組合</td></tr>';
        document.getElementById('ov-positions').innerHTML = '<tr><td colspan="8" class="text-center" style="padding:40px;color:var(--muted)">尚無投資組合</td></tr>';
        document.getElementById('ov-total-value').textContent = '--';
        document.getElementById('ov-total-cost').textContent = '--';
        document.getElementById('ov-total-pnl').textContent = '--';
        document.getElementById('ov-total-pnl').style.color = '';
        document.getElementById('ov-pnl-pct').textContent = '';
        document.getElementById('ov-count').textContent = '--';
        document.getElementById('ov-cash').textContent = '--';
      }}
    }}

    async function removePosition(posId) {{
      if (!confirm('確定刪除此持倉？')) return;
      await fetch('/api/portfolio/' + activePF + '/positions/' + posId, {{ method: 'DELETE' }});
      loadPortfolio(activePF); loadOverview();
    }}

    let infoSymbol = null;
    let techChartsInit = false;
    let techCycleCur = 'day';
    let techIndCur = 'kd';
    let tMain, tVol, tOsc, tCandle, tVolS, tK, tD, tMa5, tMa20, tDif, tDea, tMacd;
    let tVolByTime = {{}}, tKByTime = {{}}, tDByTime = {{}}, tMa5ByTime = {{}}, tMa20ByTime = {{}}, tDifByTime = {{}}, tDeaByTime = {{}}, tMacdByTime = {{}}, tDataByTime = {{}};
    let tSyncingCrosshair = false, tSyncingRange = false;
    let techReqId = 0;
    let tResizeObs = null;

    function loadLightweightCharts() {{
      return new Promise((resolve) => {{
        if (window.LightweightCharts) {{ resolve(true); return; }}
        const s = document.createElement('script');
        s.src = 'https://cdn.jsdelivr.net/npm/lightweight-charts@4.1.0/dist/lightweight-charts.standalone.production.js';
        s.onload = () => resolve(true);
        s.onerror = () => resolve(false);
        document.head.appendChild(s);
      }});
    }}

    async function showInfoModal(symbol, name) {{
      infoSymbol = symbol;
      document.getElementById('info-title').textContent = name + ' (' + symbol + ') 相關資訊';
      document.getElementById('info-fund').innerHTML = '<div class="empty-state"><div class="icon">⏳</div><p>載入基本面資料...</p></div>';
      document.getElementById('info-news').innerHTML = '<div class="empty-state"><div class="icon">⏳</div><p>載入新聞...</p></div>';
      infoTab('fund');
      showModal('info-modal');
      loadFundamental();
      loadNews();
    }}

    function infoTab(tab) {{
      ['fund','tech','news'].forEach(t => {{
        document.getElementById('info-tab-' + t).classList.toggle('active', t === tab);
        document.getElementById('info-' + t).style.display = t === tab ? 'block' : 'none';
      }});
      if (tab === 'tech') loadTech();
    }}

    async function loadFundamental() {{
      const el = document.getElementById('info-fund');
      try {{
        const res = await fetch('/api/fundamental/' + encodeURIComponent(infoSymbol));
        const d = await res.json();
        if (!d.success) {{ el.innerHTML = '<div class="empty-state"><div class="icon">⚠️</div><p>' + (d.error || '無資料') + '</p></div>'; return; }}
        const f = d.data;
        const cls = f.change_pct >= 0 ? 'up' : 'down';
        const sign = f.change_pct >= 0 ? '+' : '';
        let html = '<div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:14px">'
          + `<div class="stat-card" style="flex:1;min-width:150px"><div class="stat-label">現價 (${{f.currency}})</div><div class="stat-value ${{cls}}">${{(f.price||0).toLocaleString()}}</div></div>`
          + `<div class="stat-card" style="flex:1;min-width:150px"><div class="stat-label">漲跌</div><div class="stat-value ${{cls}}">${{sign}}${{(f.change||0).toFixed(2)}} (${{sign}}${{(f.change_pct||0).toFixed(2)}}%)</div></div>`
          + `<div class="stat-card" style="flex:1;min-width:150px"><div class="stat-label">財報季度</div><div class="stat-value" style="font-size:18px">${{f.report_date || '無資料'}}</div></div>`
          + '</div><div class="info-cards">';
        (f.cards || []).forEach(card => {{
          html += `<div class="info-card"><h4>${{card.title}}</h4>` + card.items.map(i => `<div class="info-row"><span class="lbl">${{i.label}}</span><span class="val">${{i.value}}</span></div>`).join('') + '</div>';
        }});
        html += '</div>';
        el.innerHTML = html;
      }} catch(e) {{ el.innerHTML = '<div class="empty-state"><div class="icon">⚠️</div><p>載入失敗</p></div>'; }}
    }}

    async function loadNews() {{
      const el = document.getElementById('info-news');
      try {{
        const res = await fetch('/api/news/' + encodeURIComponent(infoSymbol));
        const d = await res.json();
        if (!d.success || !d.data || !d.data.length) {{ el.innerHTML = '<div class="empty-state"><div class="icon">📰</div><p>暫無相關新聞</p></div>'; return; }}
        el.innerHTML = d.data.map(n => `
          <div class="news-item">
            <div class="news-meta">${{n.publish_time}} · ${{n.publisher}}</div>
            <h4><a href="${{n.url}}" target="_blank">${{n.title}}</a></h4>
            <div class="news-summary">${{n.summary}}</div>
          </div>`).join('');
      }} catch(e) {{ el.innerHTML = '<div class="empty-state"><div class="icon">⚠️</div><p>載入失敗</p></div>'; }}
    }}

    async function loadTech() {{
      const el = document.getElementById('info-tech');
      if (!el) return;
      if (!await loadLightweightCharts()) {{ el.innerHTML = '<div class="empty-state"><div class="icon">⚠️</div><p>無法載入圖表庫（需網路）</p></div>'; return; }}
      if (!el.querySelector('#tech-html')) {{
        el.innerHTML = `
          <div id="tech-html">
            <div style="display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap;align-items:center">
              <button class="btn btn-sm" onclick="techCycle('day')">日線</button>
              <button class="btn btn-sm" onclick="techCycle('week')">週線</button>
              <button class="btn btn-sm" onclick="techCycle('month')">月線</button>
              <span style="flex:1"></span>
              <button class="btn btn-sm" onclick="techIndicator('kd')">KD</button>
              <button class="btn btn-sm" onclick="techIndicator('macd')">MACD</button>
            </div>
            <div id="tech-info" style="font-size:13px;font-weight:600;color:var(--text2);margin-bottom:8px;min-height:18px;display:flex;flex-wrap:wrap;gap:0 14px"></div>
            <div id="tech-charts" style="border:1px solid var(--border);border-radius:8px;overflow:hidden">
              <div id="tech-kline" style="height:300px"></div>
              <div id="tech-volume" style="height:90px"></div>
              <div id="tech-osc" style="height:140px"></div>
            </div>
          </div>`;
        techChartsInit = false;
      }}
      techCycle(techCycleCur);
    }}

    async function techCycle(cycle) {{
      techCycleCur = cycle;
      const info = document.getElementById('tech-info');
      if (info) info.textContent = '載入 ' + (cycle === 'day' ? '日' : cycle === 'week' ? '週' : '月') + '線資料...';
      const rid = ++techReqId;
      try {{
        const res = await fetch('/api/techdata/' + encodeURIComponent(infoSymbol) + '?cycle=' + cycle);
        const d = await res.json();
        if (rid !== techReqId) return;
        if (!d.success) {{ if (info) info.textContent = '無技術數據'; return; }}
        if (!techChartsInit) initTechCharts();
        tBuildLookup(d.data);
        tSafeSet(function() {{ tCandle.setData(d.data.kline); }});
        tSafeSet(function() {{ tVolS.setData(d.data.volume); }});
        tSafeSet(function() {{ tK.setData(d.data.K); }});
        tSafeSet(function() {{ tD.setData(d.data.D); }});
        tSafeSet(function() {{ tMa5.setData(d.data.MA5); }});
        tSafeSet(function() {{ tMa20.setData(d.data.MA20); }});
        tSafeSet(function() {{ tDif.setData(d.data.DIF); }});
        tSafeSet(function() {{ tDea.setData(d.data.DEA); }});
        tSafeSet(function() {{ tMacd.setData(d.data.MACD); }});
        tVol.priceScale('right').applyOptions({{ scaleMargins: {{ top: 0.15, bottom: 0.15 }} }});
        tMain.timeScale().fitContent();
        tVol.timeScale().fitContent();
        tOsc.timeScale().fitContent();
        tVol.timeScale().fitContent();
        tOsc.timeScale().fitContent();
        techIndicator(techIndCur);
        if (info) info.textContent = '滑鼠移至圖表查看 開高低收、成交量、KD/MACD、MA5/MA20';
      }} catch(e) {{ if (rid === techReqId && info) info.textContent = '載入失敗'; }}
    }}

    function initTechCharts() {{
      const L = LightweightCharts;
      const theme = {{
        layout: {{ background: {{ type: 'solid', color: '#161923' }}, textColor: '#c0c8d8' }},
        grid: {{ vertLines: {{ color: '#282c38' }}, horzLines: {{ color: '#282c38' }} }},
        timeScale: {{ timeVisible: true, borderColor: '#353b48', visible: false }},
        rightPriceScale: {{ borderColor: '#353b48', visible: true, minimumWidth: 70 }},
        crosshair: {{ mode: 1, vertLine: {{ width: 1, color: '#788191', style: 0 }}, horzLine: {{ width: 1, color: '#788191', style: 0 }} }}
      }};
      const oscTheme = Object.assign({{}}, theme, {{ timeScale: Object.assign({{}}, theme.timeScale, {{ visible: true }}) }});
      tMain = L.createChart(document.getElementById('tech-kline'), Object.assign({{}}, theme));
      tCandle = tMain.addCandlestickSeries({{ upColor:'#4cd964', downColor:'#ff5e57', borderUpColor:'#4cd964', borderDownColor:'#ff5e57', wickUpColor:'#4cd964', wickDownColor:'#ff5e57' }});
      tMa5 = tMain.addLineSeries({{ color:'#2196F3', lineWidth:1 }});
      tMa20 = tMain.addLineSeries({{ color:'#FF9800', lineWidth:1 }});
      tVol = L.createChart(document.getElementById('tech-volume'), Object.assign({{}}, theme));
      tVolS = tVol.addHistogramSeries({{ priceFormat:{{ type:'custom', minMove:1, formatter:function(v){{ return (v/1000000).toFixed(2); }} }}, priceScaleId:'right' }});
      tOsc = L.createChart(document.getElementById('tech-osc'), oscTheme);
      tK = tOsc.addLineSeries({{ color:'#ffcc00', lineWidth:2 }});
      tD = tOsc.addLineSeries({{ color:'#a855f7', lineWidth:2 }});
      tDif = tOsc.addLineSeries({{ color:'#2196F3', lineWidth:2, visible:false }});
      tDea = tOsc.addLineSeries({{ color:'#FF9800', lineWidth:2, visible:false }});
      tMacd = tOsc.addHistogramSeries({{ visible:false }});
      [tMain, tVol, tOsc].forEach(function(ch) {{
        ch.timeScale().subscribeVisibleTimeRangeChange(function() {{ tSyncRange(ch); }});
        ch.subscribeCrosshairMove(function(param) {{ tSyncCrosshair(ch, param); }});
      }});
      if (window.ResizeObserver) {{
        const ro = new ResizeObserver(function(entries) {{
          entries.forEach(function(en) {{
            const w = en.contentRect.width, h = en.contentRect.height;
            if (w <= 0 || h <= 0) return;
            const cmap = {{ 'tech-kline': tMain, 'tech-volume': tVol, 'tech-osc': tOsc }};
            const ch = cmap[en.target.id];
            if (ch) ch.applyOptions({{ width: w, height: h }});
          }});
        }});
        ['tech-kline', 'tech-volume', 'tech-osc'].forEach(function(id) {{
          const elx = document.getElementById(id);
          if (elx) ro.observe(elx);
        }});
        tResizeObs = ro;
      }}
      techChartsInit = true;
    }}

    function tSafeSet(fn) {{ try {{ fn(); }} catch(e) {{}} }}

    function tBuildLookup(d) {{
      tVolByTime = {{}}; tKByTime = {{}}; tDByTime = {{}}; tMa5ByTime = {{}}; tMa20ByTime = {{}}; tDifByTime = {{}}; tDeaByTime = {{}}; tMacdByTime = {{}}; tDataByTime = {{}};
      d.volume.forEach(function(x) {{ tVolByTime[x.time] = x.value; }});
      d.K.forEach(function(x) {{ tKByTime[x.time] = x.value; }});
      d.D.forEach(function(x) {{ tDByTime[x.time] = x.value; }});
      d.MA5.forEach(function(x) {{ tMa5ByTime[x.time] = x.value; }});
      d.MA20.forEach(function(x) {{ tMa20ByTime[x.time] = x.value; }});
      d.DIF.forEach(function(x) {{ tDifByTime[x.time] = x.value; }});
      d.DEA.forEach(function(x) {{ tDeaByTime[x.time] = x.value; }});
      d.MACD.forEach(function(x) {{ tMacdByTime[x.time] = x.value; }});
      d.kline.forEach(function(x, i) {{ tDataByTime[x.time] = d.source[i]; }});
    }}

    function tNum(v) {{
      if (typeof v !== 'number' || isNaN(v)) return '--';
      return v.toFixed(2);
    }}

    function tDate(tm) {{
      const d = new Date(tm * 1000);
      return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
    }}

    function tUpdateInfo(tm) {{
      const info = document.getElementById('tech-info');
      if (!info || !tDataByTime[tm]) return;
      const item = tDataByTime[tm];
      const closeColor = item.close >= item.open ? 'var(--up)' : 'var(--down)';
      let indHtml = '';
      if (techIndCur === 'kd') {{
        indHtml = '<span>K:<span style="color:#ffcc00">' + tNum(item.K) + '</span></span> <span>D:<span style="color:#a855f7">' + tNum(item.D) + '</span></span>';
      }} else {{
        const macdColor = item.MACD >= 0 ? 'var(--up)' : 'var(--down)';
        indHtml = '<span style="color:#2196F3">DIF:' + tNum(item.DIF) + '</span> <span style="color:#FF9800">DEA:' + tNum(item.DEA) + '</span> <span style="color:' + macdColor + '">MACD:' + tNum(item.MACD) + '</span>';
      }}
      info.innerHTML = '<span>日期:' + item.date + '</span> <span>開:<span style="color:var(--up)">' + tNum(item.open) + '</span></span> <span>高:<span style="color:var(--up)">' + tNum(item.high) + '</span></span> <span>低:<span style="color:var(--down)">' + tNum(item.low) + '</span></span> <span>收:<span style="color:' + closeColor + '">' + tNum(item.close) + '</span></span> <span>量:' + (item.volume / 1000000).toFixed(2) + 'M</span> <span style="color:#2196F3">MA5:' + tNum(item.MA5) + '</span> <span style="color:#FF9800">MA20:' + tNum(item.MA20) + '</span> ' + indHtml;
    }}

    function tSyncCrosshair(source, param) {{
      if (tSyncingCrosshair) return;
      tSyncingCrosshair = true;
      try {{
        if (!param || param.time === undefined) {{
          [tMain, tVol, tOsc].forEach(function(ch) {{ if (ch !== source) ch.clearCrosshairPosition(); }});
          return;
        }}
        const tm = param.time;
        if (source !== tMain) {{
          const it = tDataByTime[tm];
          if (it) tMain.setCrosshairPosition(it.close, tm, tCandle);
        }}
        if (source !== tVol) {{
          const v = tVolByTime[tm];
          if (v !== undefined) tVol.setCrosshairPosition(v, tm, tVolS);
        }}
        if (source !== tOsc) {{
          const kv = tKByTime[tm];
          if (kv !== undefined) tOsc.setCrosshairPosition(kv, tm, tK);
        }}
        tUpdateInfo(tm);
      }} finally {{
        tSyncingCrosshair = false;
      }}
    }}

    function tSyncRange(source) {{
      if (tSyncingRange) return;
      tSyncingRange = true;
      try {{
        const range = source.timeScale().getVisibleRange();
        if (range) {{
          [tMain, tVol, tOsc].forEach(function(ch) {{
            if (ch !== source) ch.timeScale().setVisibleRange(range);
          }});
        }}
      }} finally {{
        tSyncingRange = false;
      }}
    }}

    function techIndicator(ind) {{
      techIndCur = ind;
      if (!techChartsInit) return;
      if (ind === 'kd') {{
        tK.applyOptions({{ visible:true }}); tD.applyOptions({{ visible:true }});
        tDif.applyOptions({{ visible:false }}); tDea.applyOptions({{ visible:false }}); tMacd.applyOptions({{ visible:false }});
      }} else {{
        tK.applyOptions({{ visible:false }}); tD.applyOptions({{ visible:false }});
        tDif.applyOptions({{ visible:true }}); tDea.applyOptions({{ visible:true }}); tMacd.applyOptions({{ visible:true }});
      }}
    }}

    function showModal(id) {{
      document.getElementById(id).classList.add('show');
      if (id === 'add-pos-modal') {{
        resetPosForm();
      }}
    }}
    function hideModal(id) {{ document.getElementById(id).classList.remove('show'); }}
    document.querySelectorAll('.modal-overlay').forEach(function (ov) {{
      ov.addEventListener('mousedown', function (e) {{ if (e.target === ov) ov.classList.remove('show'); }});
    }});
    document.addEventListener('keydown', function (e) {{
      if (e.key === 'Escape') document.querySelectorAll('.modal-overlay.show').forEach(function (ov) {{ ov.classList.remove('show'); }});
    }});
    function togglePosType(t) {{
      document.getElementById('pos-stock-section').style.display = t === 'cash' ? 'none' : 'block';
      document.getElementById('pos-cash-section').style.display = t === 'cash' ? 'block' : 'none';
    }}

    function searchSymbols(keyword) {{
      if (keyword.length < 2) {{ document.getElementById('pos-dropdown').innerHTML = ''; return; }}
      fetch('/api/search?q=' + encodeURIComponent(keyword)).then(r => r.json()).then(data => {{
        const results = (data.results || []).slice(0, 20);
        document.getElementById('pos-dropdown').innerHTML = results.map(r => {{
          const sym = String(r.symbol || '').replace(/'/g, "\\'");
          const nm = String(r.name || '').replace(/'/g, "\\'");
          const srcTag = r.source === 'yahoo' ? 'Yahoo' : '在地';
          return `<div class="dropdown-item" onclick="selectSymbol('${{sym}}','${{nm}}')"><span><span class="sym">${{r.symbol}}</span> <span class="name">${{r.name}}</span></span><span class="meta">${{r.category || ''}} · ${{srcTag}}</span></div>`;
        }}).join('');
        document.getElementById('pos-dropdown').classList.add('show');
      }}).catch(() => {{}});
    }}
    function selectSymbol(sym, name) {{
      document.getElementById('pos-search').value = sym;
      document.getElementById('pos-name').value = name;
      document.getElementById('pos-dropdown').classList.remove('show');
    }}

    function resetPosForm() {{
      const ps = document.getElementById('pos-search');
      if (ps) ps.value = '';
      const pn = document.getElementById('pos-name');
      if (pn) pn.value = '';
      const pc = document.getElementById('pos-cost');
      if (pc) pc.value = '';
      const pq = document.getElementById('pos-qty');
      if (pq) pq.value = '';
      const pa = document.getElementById('pos-cash-amount');
      if (pa) pa.value = '';
      const pt = document.getElementById('pos-type');
      if (pt) {{ pt.value = 'stock'; togglePosType('stock'); }}
      const pd = document.getElementById('pos-dropdown');
      if (pd) {{ pd.innerHTML = ''; pd.classList.remove('show'); }}
      if (ps) setTimeout(function() {{ ps.focus(); }}, 50);
    }}

    async function submitPosition() {{
      let payload;
      const ptype = document.getElementById('pos-type').value;
      if (ptype === 'cash') {{
        const amount = parseFloat(document.getElementById('pos-cash-amount').value);
        if (isNaN(amount) || amount <= 0) {{ alert('請輸入現金金額'); return; }}
        payload = {{ symbol: 'CASH', name: '現金', cost_price: 1, quantity: amount, buy_fee_rate: 0, sell_fee_rate: 0, tax_rate: 0 }};
      }} else {{
        const symbol = document.getElementById('pos-search').value.trim();
        const name = document.getElementById('pos-name').value.trim();
        const cost = parseFloat(document.getElementById('pos-cost').value);
        const qty = parseFloat(document.getElementById('pos-qty').value);
        const buyFee = parseFloat(document.getElementById('pos-buy-fee').value) / 100;
        const sellFee = parseFloat(document.getElementById('pos-sell-fee').value) / 100;
        const tax = parseFloat(document.getElementById('pos-tax').value) / 100;
        if (!symbol || !name || isNaN(cost) || isNaN(qty)) {{ alert('請填寫完整資訊'); return; }}
        payload = {{ symbol, name, cost_price: cost, quantity: qty, buy_fee_rate: buyFee, sell_fee_rate: sellFee, tax_rate: tax }};
      }}
      const res = await fetch('/api/portfolio/' + activePF + '/positions', {{
        method: 'POST', headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify(payload)
      }});
      const data = await res.json();
      if (data.success) {{ resetPosForm(); loadPortfolio(activePF); loadOverview(); }}
      else alert('新增失敗: ' + (data.error || '未知錯誤'));
    }}

    async function submitPortfolio() {{
      const name = document.getElementById('new-pf-name').value.trim();
      const currency = document.getElementById('new-pf-currency').value;
      const benchmark = document.getElementById('new-pf-benchmark').value;
      const res = await fetch('/api/portfolios', {{
        method: 'POST', headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{ name, base_currency: currency, benchmark }})
      }});
      const data = await res.json();
      if (data.success) {{ activePF = data.id; hideModal('add-pf-modal'); loadPortfolioList(); loadPortfolio(data.id); loadOverview(); }}
      else alert('建立失敗: ' + (data.error || '未知錯誤'));
    }}

    async function loadOverview() {{
      if (!activePF) return;
      const res = await fetch('/api/performance/' + activePF);
      const perf = await res.json();
      if (!perf.name) return;
      const curEl = document.getElementById('ov-currency');
      if (curEl) curEl.textContent = perf.base_currency ? '(' + perf.base_currency + ')' : '';
      document.getElementById('ov-total-value').textContent = Math.round(perf.total_value || 0).toLocaleString() || '--';
      document.getElementById('ov-total-cost').textContent = Math.round(perf.total_invested || 0).toLocaleString() || '--';
      const pnlEl = document.getElementById('ov-total-pnl');
      const pnlPctEl = document.getElementById('ov-pnl-pct');
      pnlEl.textContent = (perf.total_pnl >= 0 ? '+' : '') + Math.round(perf.total_pnl || 0).toLocaleString();
      pnlEl.style.color = (perf.total_pnl >= 0 ? 'var(--up)' : 'var(--down)');
      pnlPctEl.textContent = (perf.total_pnl_pct >= 0 ? '+' : '') + perf.total_pnl_pct?.toFixed(2) + '%';
      pnlPctEl.style.color = (perf.total_pnl_pct >= 0 ? 'var(--up)' : 'var(--down)');
      document.getElementById('ov-count').textContent = perf.position_count || 0;
      document.getElementById('ov-cash').textContent = perf.cash_balance?.toLocaleString() || 0;
      const tbody = document.getElementById('ov-positions');
      tbody.innerHTML = '';
      (perf.positions || []).sort((a, b) => (b.net_market_value || 0) - (a.net_market_value || 0)).forEach(pos => {{
        const pnlClass = pos.pnl >= 0 ? 'up' : 'down';
        const sign = pos.pnl >= 0 ? '+' : '';
        const tr = document.createElement('tr');
        tr.innerHTML = `<td><strong>${{pos.name}}</strong><br><span style="color:var(--muted);font-size:11px">${{pos.symbol}}${{pos.currency && pos.currency !== pos.base_currency ? ' · ' + pos.currency : ''}}</span></td><td>${{pos.quantity?.toLocaleString() || 0}}</td><td>${{pos.cost_price?.toFixed(2) || '--'}}</td><td>${{(pos.current_price || 0).toFixed(2)}}${{pos.fx && pos.fx !== 1 ? `<br><span style="color:var(--muted);font-size:10px">${{(pos.base_price || 0).toFixed(2)}} ${{pos.currency}}</span>` : ''}}</td><td class="text-right">${{Math.round(pos.market_value || 0).toLocaleString()}}</td><td class="text-right ${{pnlClass}}">${{sign}}${{Math.round(pos.pnl || 0).toLocaleString()}}</td><td class="text-right ${{pnlClass}}">${{sign}}${{pos.pnl_pct?.toFixed(2) || 0}}%</td><td class="text-right">${{pos.weight?.toFixed(1) || 0}}%</td>`;
        tbody.appendChild(tr);
      }});
      if (typeof loadDashboard === 'function') loadDashboard();
    }}

    async function loadAnalysis() {{
      const symbol = document.getElementById('analysis-symbol').value.trim();
      const period = document.getElementById('analysis-period').value;
      if (!symbol) {{ alert('請輸入標的代碼'); return; }}
      const res = await fetch('/api/history/' + encodeURIComponent(symbol) + '?period=' + period);
      const data = await res.json();
      if (!data.success || !data.data?.length) {{
        document.getElementById('analysis-chart').innerHTML = '<div class="empty-state"><div class="icon">⚠️</div><p>無法獲取數據</p></div>'; return;
      }}
      let risk = null;
      const records = data.data;
      const prices = records.map(r => r.close);
      const chartW = 900, chartH = 300, pad = 50;
      const maxP = Math.max(...prices), minP = Math.min(...prices);
      const range = maxP - minP || 1;
      const step = (chartW - pad * 2) / (prices.length - 1);
      function ma(data, w) {{ const r = []; for (let i = 0; i < data.length; i++) {{ if (i < w - 1) {{ r.push(null); continue; }} let s = 0; for (let j = 0; j < w; j++) s += data[i - j]; r.push(s / w); }} return r; }}
      const ma5 = ma(prices, 5), ma20 = ma(prices, 20);
      function pt(i, v) {{ return `${{pad + i * step}},${{chartH - pad - ((v - minP) / range) * (chartH - pad * 2)}}`; }}
      let svg = `<svg width="${{chartW}}" height="${{chartH + 80}}" xmlns="http://www.w3.org/2000/svg" style="background:var(--bg);border-radius:8px">`;
      svg += `<polyline points="${{prices.map((p,i) => pt(i,p)).join(' ')}}" fill="none" stroke="var(--accent)" stroke-width="2"/>`;
      svg += `<polyline points="${{ma5.map((v,i) => v ? pt(i,v) : '').filter(Boolean).join(' ')}}" fill="none" stroke="var(--gold)" stroke-width="1" stroke-dasharray="4,2"/>`;
      svg += `<polyline points="${{ma20.map((v,i) => v ? pt(i,v) : '').filter(Boolean).join(' ')}}" fill="none" stroke="var(--purple)" stroke-width="1" stroke-dasharray="4,2"/>`;
      svg += `<text x="5" y="${{pad}}" fill="var(--muted)" font-size="10">${{maxP.toFixed(2)}}</text><text x="5" y="${{chartH}}" fill="var(--muted)" font-size="10">${{minP.toFixed(2)}}</text></svg>`;
      document.getElementById('analysis-chart').innerHTML = svg;
      const totalReturn = ((prices[prices.length-1] / prices[0]) - 1) * 100;
      document.getElementById('analysis-stats').innerHTML = `
        <div class="stat-card"><div class="stat-label">期間報酬</div><div class="stat-value ${{totalReturn>=0?'up':'down'}}">${{totalReturn>=0?'+':''}}${{totalReturn.toFixed(2)}}%</div></div>
        <div class="stat-card"><div class="stat-label">最高價</div><div class="stat-value">${{maxP.toFixed(2)}}</div></div>
        <div class="stat-card"><div class="stat-label">最低價</div><div class="stat-value">${{minP.toFixed(2)}}</div></div>
        <div class="stat-card"><div class="stat-label">最大回撤</div><div class="stat-value down">${{calcMaxDrawdown(prices).toFixed(2)}}%</div></div>
        <div class="stat-card"><div class="stat-label">波動率</div><div class="stat-value">${{calcVolatility(prices).toFixed(2)}}%</div></div>
        <div class="stat-card"><div class="stat-label">數據點</div><div class="stat-value">${{prices.length}}</div></div>
      `;
      loadRiskRatios(symbol);
    }}
    async function loadRiskRatios(symbol) {{
      for (let attempt = 0; attempt < 3; attempt++) {{
        try {{
          const rr = await fetch('/api/analysis/' + encodeURIComponent(symbol));
          const rd = await rr.json();
          if (rd.success) {{
            const risk = rd;
            function fmtRatio(v) {{ return (v == null || isNaN(v)) ? '--' : v.toFixed(2); }}
            function ratioCard(label, value) {{
              const cls = (value != null && !isNaN(value)) ? (value > 1 ? 'ratio-high' : value < 1 ? 'ratio-low' : '') : '';
              return `<div class="stat-card"><div class="stat-label">${{label}}</div><div class="stat-value ${{cls}}">${{fmtRatio(value)}}</div></div>`;
            }}
            const cards = ratioCard('1年貝塔(β)', risk.beta_1y) + ratioCard('3年貝塔(β)', risk.beta_3y)
              + ratioCard('1年夏普比率', risk.sharpe_1y) + ratioCard('3年夏普比率', risk.sharpe_3y)
              + ratioCard('1年索提諾比率', risk.sortino_1y) + ratioCard('3年索提諾比率', risk.sortino_3y)
              + (risk.benchmark ? `<div class="stat-card"><div class="stat-label">基準指數</div><div class="stat-value" style="font-size:13px">${{risk.benchmark}}</div></div>` : '');
            document.getElementById('analysis-stats').insertAdjacentHTML('beforeend', cards);
            return;
          }}
        }} catch (e) {{}}
        await new Promise(r => setTimeout(r, 800));
      }}
    }}
    function calcMaxDrawdown(prices) {{
      if (prices.length < 2) return 0; let peak = prices[0], mdd = 0;
      for (const p of prices) {{ if (p > peak) peak = p; const dd = (p - peak) / peak * 100; if (dd < mdd) mdd = dd; }} return mdd;
    }}
    function calcVolatility(prices) {{
      if (prices.length < 2) return 0;
      const ret = prices.slice(1).map((p, i) => (p - prices[i]) / prices[i]);
      const avg = ret.reduce((a, b) => a + b, 0) / ret.length;
      const var_ = ret.reduce((a, b) => a + (b - avg) ** 2, 0) / (ret.length - 1);
      return Math.sqrt(var_) * Math.sqrt(252) * 100;
    }}

    function onPerfPeriodChange() {{
      const sel = document.getElementById('perf-period').value;
      document.getElementById('perf-date').style.display = sel === 'custom' ? '' : 'none';
      loadPerfRange();
    }}

    async function loadPerfRange() {{
      if (!activePF) return;
      const sel = document.getElementById('perf-period').value;
      const chart = document.getElementById('perf-chart');
      const stats = document.getElementById('perf-stats');
      let query = 'period=' + sel;
      if (sel === 'custom') {{
        const d = document.getElementById('perf-date').value;
        if (!d) {{
          stats.innerHTML = '<div class="empty-state"><div class="icon">📅</div><p>請選擇統計起始日期</p></div>';
          chart.innerHTML = '<div class="empty-state"><div class="icon">📉</div><p>請選擇統計起始日期</p></div>';
          return;
        }}
        query = 'period=custom&start_date=' + d;
      }}
      stats.innerHTML = '<div class="empty-state"><div class="icon">⏳</div><p>載入中...</p></div>';
      let data;
      try {{
        const res = await fetch('/api/performance/' + activePF + '?' + query);
        data = await res.json();
      }} catch (e) {{
        stats.innerHTML = '<div class="empty-state"><div class="icon">⚠️</div><p>載入失敗</p></div>';
        return;
      }}
      if (!data.success) {{
        const msg = data.error || '無法取得數據';
        stats.innerHTML = `<div class="empty-state"><div class="icon">⚠️</div><p>${{msg}}</p></div>`;
        chart.innerHTML = `<div class="empty-state"><div class="icon">⚠️</div><p>${{msg}}</p></div>`;
        document.getElementById('perf-legend').innerHTML = '';
        return;
      }}
      const s = data.stats;
      const pCls = s.portfolio_return >= 0 ? 'up' : 'down';
      const bCls = s.benchmark_return >= 0 ? 'up' : 'down';
      stats.innerHTML = `
        <div class="stat-card"><div class="stat-label">組合期間報酬</div><div class="stat-value ${{pCls}}">${{s.portfolio_return >= 0 ? '+' : ''}}${{s.portfolio_return.toFixed(2)}}%</div></div>
        <div class="stat-card"><div class="stat-label">Benchmark 報酬</div><div class="stat-value ${{bCls}}">${{s.benchmark_return >= 0 ? '+' : ''}}${{s.benchmark_return.toFixed(2)}}%</div></div>
        <div class="stat-card"><div class="stat-label">超額報酬</div><div class="stat-value ${{s.excess_return >= 0 ? 'up' : 'down'}}">${{s.excess_return >= 0 ? '+' : ''}}${{s.excess_return.toFixed(2)}}%</div></div>
        <div class="stat-card"><div class="stat-label">期末總資產</div><div class="stat-value">${{Math.round(s.portfolio_end_value || 0).toLocaleString()}}</div></div>
        <div class="stat-card"><div class="stat-label">組合年化報酬</div><div class="stat-value ${{s.portfolio_annualized >= 0 ? 'up' : 'down'}}">${{s.portfolio_annualized >= 0 ? '+' : ''}}${{s.portfolio_annualized.toFixed(2)}}%</div></div>
        <div class="stat-card"><div class="stat-label">組合最大回撤</div><div class="stat-value down">${{s.portfolio_max_drawdown.toFixed(2)}}%</div></div>
        <div class="stat-card"><div class="stat-label">組合波動率</div><div class="stat-value">${{s.portfolio_volatility.toFixed(2)}}%</div></div>
        <div class="stat-card"><div class="stat-label">統計區間</div><div class="stat-value" style="font-size:14px">${{data.start_date}} ~ ${{data.end_date}}</div></div>
      `;
      renderPerfChart(data);
      const benchMap = {{'^TWII':'台股加權指數','^GSPC':'標普500','^IXIC':'納斯達克','^HSI':'恆生指數','000001.SS':'上證指數','SPY':'SPY ETF'}};
      const benchName = benchMap[data.benchmark] || data.benchmark;
      document.getElementById('perf-bench-label').textContent = '基準: ' + benchName;
      document.getElementById('perf-legend').innerHTML = `
        <span><span style="display:inline-block;width:14px;height:3px;background:var(--accent);vertical-align:middle;margin-right:4px"></span>投資組合</span>
        <span><span style="display:inline-block;width:14px;height:3px;background:var(--gold);vertical-align:middle;margin-right:4px"></span>${{benchName}}</span>`;
      const risk = data.risk_ratios;
      const riskEl = document.getElementById('perf-risk');
      if (risk) {{
        const riskCards = [
          {{label:'1年貝塔比率', key:'beta_1y'}},
          {{label:'3年貝塔比率', key:'beta_3y'}},
          {{label:'1年夏普比率', key:'sharpe_1y'}},
          {{label:'3年夏普比率', key:'sharpe_3y'}},
          {{label:'1年索提諾比率', key:'sortino_1y'}},
          {{label:'3年索提諾比率', key:'sortino_3y'}}
        ].map(c => {{
          const v = risk[c.key];
          const cls = (v != null && !isNaN(v)) ? (v > 1 ? 'ratio-high' : v < 1 ? 'ratio-low' : '') : '';
          return `<div class="stat-card"><div class="stat-label">${{c.label}}</div><div class="stat-value ${{cls}}">${{(v==null||isNaN(v))?'--':v.toFixed(2)}}</div></div>`;
        }}).join('');
        riskEl.innerHTML = `<div class="card-header" style="grid-column:1/-1;padding:0 0 8px 0"><span class="card-title">投資組合期間風險指標</span></div>` + riskCards;
      }} else {{
        riskEl.innerHTML = '';
      }}
    }}

    function renderPerfChart(data) {{
      const dates = data.series.dates;
      const pf = data.series.portfolio;
      const bm = data.series.benchmark;
      const el = document.getElementById('perf-chart');
      if (!dates || dates.length < 2) {{
        el.innerHTML = '<div class="empty-state"><div class="icon">⚠️</div><p>數據不足</p></div>';
        return;
      }}
      const chartW = 900, chartH = 280, padL = 55, padR = 15, padT = 15, padB = 30;
      const all = pf.concat(bm);
      let maxV = Math.max(...all), minV = Math.min(...all, 0);
      if (maxV === minV) maxV = minV + 1;
      const range = maxV - minV;
      const n = dates.length;
      const stepX = (chartW - padL - padR) / (n - 1);
      const y = v => padT + (maxV - v) / range * (chartH - padT - padB);
      const x = i => padL + i * stepX;
      function path(series) {{
        return series.map((v, i) => `${{i === 0 ? 'M' : 'L'}}${{x(i).toFixed(1)}},${{y(v).toFixed(1)}}`).join(' ');
      }}
      let svg = `<svg width="${{chartW}}" height="${{chartH}}" xmlns="http://www.w3.org/2000/svg" style="background:var(--bg);border-radius:8px;width:100%;height:auto">`;
      const y0 = y(0);
      svg += `<line x1="${{padL}}" y1="${{y0}}" x2="${{chartW - padR}}" y2="${{y0}}" stroke="var(--border)" stroke-width="1" stroke-dasharray="4,2"/>`;
      for (let g = 0; g <= 4; g++) {{
        const v = maxV - g / 4 * range;
        const yy = y(v);
        svg += `<line x1="${{padL}}" y1="${{yy}}" x2="${{chartW - padR}}" y2="${{yy}}" stroke="var(--bg3)" stroke-width="0.5"/>`;
        svg += `<text x="${{padL - 4}}" y="${{yy + 3}}" fill="var(--muted)" font-size="10" text-anchor="end">${{v >= 0 ? '+' : ''}}${{v.toFixed(1)}}%</text>`;
      }}
      svg += `<text x="${{padL - 4}}" y="${{y0 - 4}}" fill="var(--muted)" font-size="10" text-anchor="end">0%</text>`;
      svg += `<path d="${{path(pf)}}" fill="none" stroke="var(--accent)" stroke-width="2"/>`;
      svg += `<path d="${{path(bm)}}" fill="none" stroke="var(--gold)" stroke-width="2"/>`;
      const tickIdx = [0, Math.floor((n - 1) / 2), n - 1];
      tickIdx.forEach(i => {{
        svg += `<text x="${{x(i)}}" y="${{chartH - 8}}" fill="var(--muted)" font-size="10" text-anchor="middle">${{dates[i]}}</text>`;
      }});
      svg += '</svg>';
      el.innerHTML = svg;
    }}

    async function loadSymbols(filter = 'ALL') {{
      const tbody = document.getElementById('sym-tbody');
      tbody.innerHTML = '<tr><td colspan="5" class="text-center">載入中...</td></tr>';
      let syms = Object.values(symbols_db);
      try {{
        const res = await fetch('/api/symbols');
        const data = await res.json();
        if (data.symbols && data.symbols.length) syms = data.symbols;
      }} catch(e) {{}}
      syms = filter === 'ALL' ? syms : syms.filter(s => s.category === filter);
      tbody.innerHTML = '';
      syms.forEach(s => {{
        const tr = document.createElement('tr');
        const escSym = String(s.symbol || '').replace(/'/g, "\\\\'").replace(/"/g, '&quot;');
        tr.innerHTML = `<td><strong>${{s.symbol}}</strong></td><td>${{s.name}}</td><td><span class="tag tag-${{String(s.category).toLowerCase()}}">${{s.category}}</span></td><td>${{s.currency}}</td><td><button class="btn btn-sm" onclick="quickAdd('${{escSym}}','${{s.name}}')">加入持倉</button> <button class="btn btn-sm btn-danger" onclick="deleteSymbol('${{escSym}}')">刪除</button></td>`;
        tbody.appendChild(tr);
      }});
    }}
    function filterSymbols(cat) {{ loadSymbols(cat); }}
    function quickAdd(sym, name) {{ showModal('add-pos-modal'); document.getElementById('pos-search').value = sym; document.getElementById('pos-name').value = name; }}

    function showAddSymbol() {{
      document.getElementById('sym-search').value = '';
      document.getElementById('sym-dropdown').innerHTML = '';
      document.getElementById('sym-dropdown').classList.remove('show');
      document.getElementById('sym-code').value = '';
      document.getElementById('sym-name').value = '';
      document.getElementById('sym-category').value = 'STOCK';
      document.getElementById('sym-currency').value = 'TWD';
      showModal('add-sym-modal');
    }}
    function searchSymIndex(keyword) {{
      if (keyword.length < 1) {{ document.getElementById('sym-dropdown').innerHTML = ''; return; }}
      fetch('/api/search?q=' + encodeURIComponent(keyword)).then(r => r.json()).then(data => {{
        const results = (data.results || []).slice(0, 20);
        document.getElementById('sym-dropdown').innerHTML = results.map(r => {{
          const sym = String(r.symbol || '').replace(/'/g, "\\\\'");
          const nm = String(r.name || '').replace(/'/g, "\\\\'");
          const cat = String(r.category || '');
          const cur = String(r.currency || 'USD');
          const srcTag = r.source === 'yahoo' ? 'Yahoo' : '在地';
          return `<div class="dropdown-item" onclick="selectSymIndex('${{sym}}','${{nm}}','${{cat}}','${{cur}}')"><span><span class="sym">${{r.symbol}}</span> <span class="name">${{r.name}}</span></span><span class="meta">${{cat}} · ${{srcTag}}</span></div>`;
        }}).join('');
        document.getElementById('sym-dropdown').classList.add('show');
      }}).catch(() => {{}});
    }}
    function selectSymIndex(sym, name, category, currency) {{
      document.getElementById('sym-code').value = sym;
      document.getElementById('sym-name').value = name;
      if (category) document.getElementById('sym-category').value = category;
      if (currency) document.getElementById('sym-currency').value = currency;
      document.getElementById('sym-search').value = sym + ' - ' + name;
      document.getElementById('sym-dropdown').classList.remove('show');
    }}
    async function submitSymbol() {{
      const symbol = document.getElementById('sym-code').value.trim().toUpperCase();
      const name = document.getElementById('sym-name').value.trim();
      const category = document.getElementById('sym-category').value;
      const currency = document.getElementById('sym-currency').value;
      if (!symbol || !name) {{ alert('請填寫代碼與名稱'); return; }}
      const res = await fetch('/api/symbols', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ symbol, name, category, currency }})
      }});
      const data = await res.json();
      if (!data.success) {{ alert(data.error || '新增失敗'); return; }}
      symbols_db[symbol] = {{ symbol, name, category, currency }};
      hideModal('add-sym-modal');
      loadSymbols();
    }}
    async function deleteSymbol(symbol) {{
      if (!confirm(`確定刪除標的 ${{symbol}}？`)) return;
      const res = await fetch('/api/symbols/' + encodeURIComponent(symbol), {{ method: 'DELETE' }});
      const data = await res.json();
      if (!data.success) {{ alert(data.error || '刪除失敗'); return; }}
      delete symbols_db[symbol];
      loadSymbols();
    }}

    async function loadReportPFs() {{
      const res = await fetch('/api/portfolios');
      const data = await res.json();
      document.getElementById('report-pf').innerHTML = data.portfolios.map(p => `<option value="${{p.id}}">${{p.name}}</option>`).join('');
    }}

    async function exportReport(format) {{
      const pid = document.getElementById('report-pf').value;
      if (!pid) {{ alert('請選擇投資組合'); return; }}
      if (window.pywebview && window.pywebview.api) {{
        const result = await window.pywebview.api.save_report(pid, format);
        if (result && result.success) {{
          alert('已匯出: ' + result.path);
        }} else if (result && result.cancelled) {{
          // 使用者取消，不提示
        }} else {{
          alert('匯出失敗: ' + (result?.error || '未知錯誤'));
        }}
      }} else {{
        // 備用：直接呼叫 API endpoint
        window.location.href = '/api/export/' + pid + '?format=' + format;
      }}
    }}

    async function clearCache() {{
      if (!confirm('確定清除緩存？')) return;
      await fetch('/api/cache/clear', {{ method: 'POST' }});
      alert('緩存已清除');
    }}
    async function showCacheStatus() {{
      const res = await fetch('/api/cache/status');
      const data = await res.json();
      document.getElementById('cache-status').innerHTML = `投資組合: ${{data.portfolio_count}} 個<br>緩存檔案: ${{data.cache_count}} 個`;
    }}
    async function changeLang(code) {{
      const res = await fetch('/api/settings/lang/' + encodeURIComponent(code), {{ method: 'POST' }});
      const data = await res.json();
      if (data && data.success) {{ location.reload(); }}
      else {{ alert('切換語言失敗'); }}
    }}

    document.addEventListener('click', e => {{
      if (!e.target.closest('.dropdown')) document.querySelectorAll('.dropdown-content').forEach(d => d.classList.remove('show'));
    }});

    window.addEventListener('load', () => {{
      loadPortfolioList();
      if (activePF) {{ loadPortfolio(activePF); loadOverview(); }}
    }});
    </script>
    {DASHBOARD_JS}
    """

    html = f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>投資績效分析軟體</title>
  {css}
</head>
<body>
{sidebar}
{main}
{js}
</body>
</html>"""

    return apply_lang(html, lang)


def run_server():
    """啟動 Flask 伺服器"""
    import threading

    def start_flask():
        app.run(host='127.0.0.1', port=PORT, debug=False, use_reloader=False)

    # 在背景執行 Flask
    thread = threading.Thread(target=start_flask, daemon=True)
    thread.start()
    time.sleep(1)  # 等待伺服器啟動

    return thread


def main():
    """主函數"""
    print("=" * 60)
    print("  投資績效分析軟體 v1.0.0")
    print("  Python + pywebview + yfinance")
    print("  數據來源: Yahoo Finance")
    print("=" * 60)

    # 啟動 Flask 伺服器
    print("\n啟動本地伺服器...")
    server_thread = run_server()

    # 等待伺服器就緒
    time.sleep(1)

    # 建立視窗
    print("開啟視窗...")
    api = Api()
    window = pywebview.create_window(
        title="投資績效分析軟體 v1.0.0",
        url=f"http://127.0.0.1:{PORT}/",
        js_api=api,
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
        min_size=(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT),
        resizable=True,
        fullscreen=False,
        background_color=THEME["bg"],
        frameless=False,
        text_select=True,
        zoomable=True,
        on_top=False,
    )
    Api._window = window

    print("\n應用程式已啟動，請在視窗中操作")
    print("按 Ctrl+C 或關閉視窗離開\n")

    # 運行視窗
    pywebview.start()

    # 關閉伺服器
    print("關閉伺服器...")
    # Flask 伺服器會在 daemon 模式中自動關閉


if __name__ == "__main__":
    main()