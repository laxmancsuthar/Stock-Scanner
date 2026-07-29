"""
Swing Trade Screener Pro — Streamlit version.

This is a Streamlit rewrite of the original FastAPI backend
(swing_trade_screener.py). All analysis/scoring/PDF logic is unchanged;
the FastAPI + MongoDB(local-JSON) + REST-endpoint layer has been replaced
with a Streamlit UI. Watchlist / notes / alerts are kept in
st.session_state (in-memory) with optional persistence to a local
data.json file so they survive app restarts on your machine.

HOW TO RUN
----------
1) Install dependencies:
   pip install streamlit yfinance pandas numpy reportlab plotly

2) Run:
   streamlit run swing_trade_screener_streamlit.py

3) Browser will auto-open at http://localhost:8501
"""

from __future__ import annotations

import json
import io
import threading
import time as _time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests
import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import matplotlib
matplotlib.use("Agg")  # headless rendering — needed for the PDF report chart
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image as RLImage, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


# ============================================================================
# SECTION 1: universes.py — NSE ticker universes (unchanged)
# ============================================================================

NIFTY_50 = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR", "ITC",
    "SBIN", "BHARTIARTL", "KOTAKBANK", "LT", "HCLTECH", "AXISBANK", "ASIANPAINT",
    "MARUTI", "BAJFINANCE", "SUNPHARMA", "TITAN", "WIPRO", "ULTRACEMCO",
    "NESTLEIND", "ADANIENT", "M&M", "NTPC", "POWERGRID", "TATAMOTORS", "TATASTEEL",
    "ONGC", "JSWSTEEL", "COALINDIA", "GRASIM", "HINDALCO", "TECHM", "INDUSINDBK",
    "BAJAJFINSV", "CIPLA", "DIVISLAB", "DRREDDY", "EICHERMOT", "HDFCLIFE",
    "BRITANNIA", "BPCL", "APOLLOHOSP", "HEROMOTOCO", "SBILIFE", "TATACONSUM",
    "SHRIRAMFIN", "ADANIPORTS", "BAJAJ-AUTO", "LTIM"
]

NIFTY_NEXT_50 = [
    "ABB", "ADANIGREEN", "ADANIPOWER", "AMBUJACEM", "BAJAJHLDNG", "BANKBARODA",
    "BEL", "BOSCHLTD", "CANBK", "CHOLAFIN", "COLPAL", "DABUR", "DLF", "DMART",
    "GAIL", "GODREJCP", "HAVELLS", "ICICIGI", "ICICIPRULI", "IOC", "INDIGO",
    "IRCTC", "JINDALSTEL", "LICI", "MARICO", "NAUKRI", "PIDILITIND", "PIIND",
    "PNB", "SBICARD", "SIEMENS", "SRF", "TATAPOWER", "TVSMOTOR", "TORNTPHARM",
    "TRENT", "VBL", "VEDL", "ZOMATO", "ZYDUSLIFE", "IDEA", "MOTHERSON",
    "GODREJPROP", "MUTHOOTFIN", "TATACHEM", "BERGEPAINT", "PGHH", "AUROPHARMA",
    "MCDOWELL-N", "LUPIN"
]

MIDCAPS = [
    "MRF", "PAGEIND", "3MINDIA", "HAL", "IRFC", "BEML", "CONCOR", "COFORGE",
    "CROMPTON", "CUMMINSIND", "CUB", "DALBHARAT", "DELHIVERY", "DEEPAKNTR",
    "DEEPAKFERT", "DIXON", "EMAMILTD", "ESCORTS", "EXIDEIND", "FEDERALBNK",
    "GLENMARK", "GMRINFRA", "GNFC", "GRANULES", "GSPL", "GUJGASLTD", "HAVELLS",
    "HONAUT", "IDFCFIRSTB", "IEX", "IGL", "INDHOTEL", "INDUSTOWER", "IPCALAB",
    "JUBLFOOD", "KANSAINER", "L&TFH", "LAURUSLABS", "LICHSGFIN", "LINDEINDIA",
    "LTTS", "MAHABANK", "MANAPPURAM", "MFSL", "MPHASIS", "NAVINFLUOR",
    "NMDC", "NAM-INDIA", "OBEROIRLTY", "OFSS", "PERSISTENT", "PETRONET",
    "PFC", "POLYCAB", "POONAWALLA", "PVRINOX", "RAMCOCEM", "RECLTD", "SAIL",
    "SHREECEM", "SUNDARMFIN", "SUPREMEIND", "SYNGENE", "TATACOMM", "TATAELXSI",
    "TIINDIA", "TORNTPOWER", "UBL", "UPL", "VOLTAS", "YESBANK", "ZEEL",
    "ZFCVINDIA", "ABBOTINDIA", "ACC", "ALKEM", "APLAPOLLO", "ASHOKLEY",
    "AUBANK", "AWL", "BALKRISIND", "BANDHANBNK", "BATAINDIA", "BHARATFORG",
    "BIOCON", "CHAMBLFERT", "COROMANDEL", "ESSENTIA", "GILLETTE", "HFCL",
    "HINDPETRO", "HINDCOPPER", "HINDZINC", "IDBI", "INDIANB", "IOB",
    "JKCEMENT", "JSWENERGY", "JSWINFRA", "KAJARIACER", "KEC", "KPIL",
    "LODHA", "MRPL"
]

SMALLCAPS = [
    "ABFRL", "ATUL", "APOLLOTYRE", "ASTRAL", "ASTERDM", "BALRAMCHIN", "BASF",
    "BAYERCROP", "BLUEDART", "BLUESTARCO", "CANFINHOME", "CAPLIPOINT", "CARBORUNIV",
    "CENTRALBK", "CENTURYPLY", "CERA", "CGCL", "CHENNPETRO", "CDSL", "CENTURYTEX",
    "CIEINDIA", "COCHINSHIP", "CREDITACC", "CRISIL", "CYIENT", "DBREALTY",
    "DEEPAKNTR", "DHANI", "EIDPARRY", "ENDURANCE", "ENGINERSIN", "EQUITAS",
    "ERIS", "FINEORG", "FINCABLES", "FIVESTAR", "FLUOROCHEM", "FORTIS", "FSL",
    "GESHIP", "GILLANDERS", "GLAND", "GMDCLTD", "GODFRYPHLP", "GODREJIND",
    "GRAPHITE", "GRSE", "GUJALKALI", "HATSUN", "HEG", "HEIDELBERG", "HEMIPROP",
    "HGS", "IBULHSGFIN", "IIFL", "INDIACEM", "IOLCP", "IRCON", "ISEC",
    "JBCHEPHARM", "JCHAC", "JINDWORLD", "JKPAPER", "JMFINANCIL", "JYOTHYLAB",
    "KALPATPOWR", "KEI", "KIMS", "KIRLOSENG", "KPRMILL", "KRBL", "KSB",
    "LALPATHLAB", "LEMONTREE", "LTFOODS", "LUXIND", "MAHLIFE", "MASTEK",
    "MAXHEALTH", "MEDPLUS", "METROBRAND", "METROPOLIS", "MINDACORP", "MOIL",
    "MSUMI", "NATCOPHARM", "NCC", "NESCO", "NIACL", "NUVOCO"
]

SECTORS = {
    "IT": ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM", "LTIM", "PERSISTENT", "COFORGE", "MPHASIS", "LTTS", "OFSS", "CYIENT", "TATAELXSI"],
    "Banking": ["HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK", "INDUSINDBK", "BANKBARODA", "PNB", "CANBK", "IDFCFIRSTB", "AUBANK", "FEDERALBNK", "BANDHANBNK", "YESBANK", "MAHABANK", "IDBI", "INDIANB", "IOB", "CENTRALBK"],
    "FMCG": ["HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "DABUR", "MARICO", "GODREJCP", "COLPAL", "TATACONSUM", "EMAMILTD", "VBL", "UBL", "MCDOWELL-N", "PGHH", "GILLETTE"],
    "Auto": ["MARUTI", "TATAMOTORS", "M&M", "BAJAJ-AUTO", "HEROMOTOCO", "EICHERMOT", "TVSMOTOR", "ASHOKLEY", "MOTHERSON", "MRF", "BOSCHLTD", "BALKRISIND", "APOLLOTYRE", "ESCORTS", "ENDURANCE"],
    "Pharma": ["SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "TORNTPHARM", "APOLLOHOSP", "AUROPHARMA", "LUPIN", "ZYDUSLIFE", "GLENMARK", "IPCALAB", "LAURUSLABS", "BIOCON", "SYNGENE", "ALKEM", "GLAND", "JBCHEPHARM", "NATCOPHARM", "ABBOTINDIA"],
    "Energy": ["RELIANCE", "ONGC", "COALINDIA", "NTPC", "POWERGRID", "BPCL", "IOC", "GAIL", "TATAPOWER", "ADANIPOWER", "ADANIGREEN", "JSWENERGY", "HINDPETRO", "PETRONET", "TORNTPOWER", "MRPL", "GSPL", "GUJGASLTD", "IGL"],
    "Metals": ["TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL", "JINDALSTEL", "SAIL", "NMDC", "HINDCOPPER", "HINDZINC", "MOIL", "APLAPOLLO"],
    "Cement": ["ULTRACEMCO", "GRASIM", "SHREECEM", "AMBUJACEM", "ACC", "DALBHARAT", "RAMCOCEM", "JKCEMENT", "HEIDELBERG", "INDIACEM", "NUVOCO"],
    "Financial Services": ["BAJFINANCE", "BAJAJFINSV", "BAJAJHLDNG", "HDFCLIFE", "SBILIFE", "ICICIPRULI", "ICICIGI", "LICI", "SBICARD", "SHRIRAMFIN", "CHOLAFIN", "MUTHOOTFIN", "MFSL", "L&TFH", "LICHSGFIN", "MANAPPURAM", "POONAWALLA", "PFC", "RECLTD", "IIFL", "SUNDARMFIN", "CREDITACC", "IBULHSGFIN"],
    "Realty": ["DLF", "GODREJPROP", "OBEROIRLTY", "LODHA", "MAHLIFE", "DBREALTY"],
    "Consumer Durables": ["TITAN", "HAVELLS", "DIXON", "VOLTAS", "CROMPTON", "BLUESTARCO", "POLYCAB", "BATAINDIA", "KAJARIACER", "CERA", "METROBRAND", "KANSAINER"],
    "Chemicals": ["PIDILITIND", "SRF", "PIIND", "TATACHEM", "DEEPAKNTR", "DEEPAKFERT", "NAVINFLUOR", "GNFC", "COROMANDEL", "CHAMBLFERT", "ATUL", "FINEORG", "GRANULES", "AARTIIND", "FLUOROCHEM"],
    "Others": []
}


def _add_suffix(tickers):
    return [f"{t}.NS" for t in tickers]


NIFTY_50_NS = _add_suffix(NIFTY_50)
NIFTY_100_NS = _add_suffix(NIFTY_50 + NIFTY_NEXT_50)
NIFTY_200_NS = _add_suffix(list(dict.fromkeys(NIFTY_50 + NIFTY_NEXT_50 + MIDCAPS)))
NIFTY_500_NS = _add_suffix(list(dict.fromkeys(NIFTY_50 + NIFTY_NEXT_50 + MIDCAPS + SMALLCAPS)))


def get_universe(name: str):
    name = (name or "").lower().replace(" ", "")
    if name in ("nifty50", "n50"):
        return NIFTY_50_NS
    if name in ("nifty100", "n100"):
        return NIFTY_100_NS
    if name in ("nifty200", "n200"):
        return NIFTY_200_NS
    if name in ("nifty500", "n500", "fullnse", "full"):
        return NIFTY_500_NS
    return NIFTY_50_NS


def get_sector(symbol_ns: str) -> str:
    base = symbol_ns.replace(".NS", "")
    for sector, tickers in SECTORS.items():
        if base in tickers:
            return sector
    return "Others"


ALL_SECTORS = list(SECTORS.keys())


# ----------------------------------------------------------------------------
# Live universe fetch — pulls the current constituent list directly from
# nseindia.com instead of relying on the (potentially stale) hardcoded lists
# above. Falls back to the hardcoded list if NSE blocks/rate-limits the
# request (which it frequently does for non-browser clients).
# ----------------------------------------------------------------------------

NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

NSE_INDEX_URLS = {
    "Nifty 50": "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
    "Nifty 200": "https://archives.nseindia.com/content/indices/ind_nifty200list.csv",
    "Nifty 500": "https://archives.nseindia.com/content/indices/ind_nifty500list.csv",
    "Full NSE Cash Segment (slow, 1500+ stocks)": "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv",
}


@st.cache_data(show_spinner=False, ttl=60 * 60 * 6)
def get_universe_live(choice: str) -> Optional[List[str]]:
    """Fetch the current constituent list directly from nseindia.com.
    Returns None (instead of raising) if NSE blocks/rate-limits the request,
    so the caller can fall back to the built-in list."""
    session = requests.Session()
    session.headers.update(NSE_HEADERS)
    try:
        session.get("https://www.nseindia.com", timeout=8)  # warms up cookies, NSE requires this
        resp = session.get(NSE_INDEX_URLS[choice], timeout=15)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
        col = "Symbol" if "Symbol" in df.columns else "SYMBOL"
        if "SERIES" in df.columns:
            symbols = df.loc[df["SERIES"].astype(str).str.strip() == "EQ", col].astype(str).str.strip().tolist()
        else:
            symbols = df[col].astype(str).str.strip().tolist()
        return _add_suffix(symbols)
    except Exception:
        return None


# ============================================================================
# SECTION 2: UNIFIED TECHNICAL ENGINE
# ----------------------------------------------------------------------------
# Merges two scanners:
#   Engine A (original analysis.py): EMA/RSI/MACD/VWAP/ATR using Wilder's
#       smoothing, simple single-label setup classification.
#   Engine B (app.py "Upgraded Edition"): ADX, Stochastic, Bollinger Bands,
#       candlestick patterns, RSI divergence, gap analysis, weekly/monthly
#       multi-timeframe confluence, multi-label setup classification,
#       dedicated breakout-state machine.
#
# This engine keeps ALL indicators from both, standardises every smoothed
# indicator (RSI/ATR/ADX) on Wilder's method (ewm alpha=1/period) since that
# is the textbook-correct formula and Engine B's plain rolling-mean RSI/ATR
# were numerically nonstandard. Scoring is unified onto a single 0-100 scale
# combining every signal from both engines with de-duplicated weights.
# ============================================================================

def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return (100 - (100 / (1 + rs))).fillna(50)


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def bollinger(series: pd.Series, period: int = 20, std_mult: float = 2):
    ma = series.rolling(period).mean()
    std = series.rolling(period).std()
    upper = ma + std_mult * std
    lower = ma - std_mult * std
    width_pct = (upper - lower) / ma.replace(0, np.nan) * 100
    return upper, lower, width_pct


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def adx(df: pd.DataFrame, period: int = 14):
    high, low, close = df["high"], df["low"], df["close"]
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
    tr = pd.concat([
        (high - low), (high - close.shift(1)).abs(), (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    atr_val = tr.ewm(alpha=1 / period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr_val.replace(0, np.nan))
    minus_di = 100 * (minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr_val.replace(0, np.nan))
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan)) * 100
    adx_val = dx.ewm(alpha=1 / period, adjust=False).mean()
    return adx_val, plus_di, minus_di


def stochastic(df: pd.DataFrame, k_period: int = 14, d_period: int = 3):
    lowest_low = df["low"].rolling(k_period).min()
    highest_high = df["high"].rolling(k_period).max()
    k = 100 * (df["close"] - lowest_low) / (highest_high - lowest_low).replace(0, np.nan)
    d = k.rolling(d_period).mean()
    return k, d


def vwap(df: pd.DataFrame) -> pd.Series:
    typical = (df["high"] + df["low"] + df["close"]) / 3
    pv = typical * df["volume"]
    return pv.cumsum() / df["volume"].cumsum().replace(0, np.nan)


def find_support_resistance(df: pd.DataFrame, lookback: int = 30) -> Tuple[float, float]:
    if len(df) < lookback + 5:
        recent = df.tail(min(len(df), lookback))
        return float(recent["low"].min()), float(recent["high"].max())
    window = df.iloc[-(lookback + 5):-5]  # exclude last 5 days to avoid look-ahead bias
    return round(float(window["low"].min()), 2), round(float(window["high"].max()), 2)


def detect_candlestick_patterns(df: pd.DataFrame) -> List[str]:
    if len(df) < 3:
        return []
    c1, c2 = df.iloc[-1], df.iloc[-2]
    patterns = []
    o1, h1, l1, cl1 = c1["open"], c1["high"], c1["low"], c1["close"]
    o2, cl2 = c2["open"], c2["close"]
    body1 = abs(cl1 - o1)
    range1 = h1 - l1
    upper_shadow1 = h1 - max(o1, cl1)
    lower_shadow1 = min(o1, cl1) - l1
    if range1 > 0:
        if lower_shadow1 > 2 * body1 and upper_shadow1 < body1 and cl1 > o1:
            patterns.append("Hammer (bullish reversal)")
        if upper_shadow1 > 2 * body1 and lower_shadow1 < body1 and cl1 < o1:
            patterns.append("Shooting Star (bearish reversal)")
        if body1 < 0.1 * range1:
            patterns.append("Doji (indecision)")
    if cl2 < o2 and cl1 > o1 and o1 < cl2 and cl1 > o2:
        patterns.append("Bullish Engulfing")
    if cl2 > o2 and cl1 < o1 and o1 > cl2 and cl1 < o2:
        patterns.append("Bearish Engulfing")
    return patterns


def detect_divergence(df: pd.DataFrame, lookback: int = 20) -> Optional[str]:
    if len(df) < lookback + 5:
        return None
    price = df["close"].iloc[-lookback:]
    ind = df["rsi14"].iloc[-lookback:]
    price_lows = price.iloc[:-5].min(), price.iloc[-5:].min()
    ind_lows = ind.iloc[:-5].min(), ind.iloc[-5:].min()
    price_highs = price.iloc[:-5].max(), price.iloc[-5:].max()
    ind_highs = ind.iloc[:-5].max(), ind.iloc[-5:].max()
    if price_lows[1] < price_lows[0] and ind_lows[1] > ind_lows[0]:
        return "Bullish Divergence"
    if price_highs[1] > price_highs[0] and ind_highs[1] < ind_highs[0]:
        return "Bearish Divergence"
    return None


def gap_analysis(df: pd.DataFrame) -> Optional[str]:
    if len(df) < 2:
        return None
    prev_close = df["close"].iloc[-2]
    curr_open = df["open"].iloc[-1]
    if not prev_close:
        return None
    gap_pct = (curr_open - prev_close) / prev_close * 100
    if gap_pct > 2:
        return f"Gap Up +{gap_pct:.1f}%"
    if gap_pct < -2:
        return f"Gap Down {gap_pct:.1f}%"
    return None


def weekly_trend_ok(df: pd.DataFrame) -> Optional[bool]:
    try:
        weekly = df.set_index("date").resample("W").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
        ).dropna()
        if len(weekly) < 12:
            return None
        w_ema10 = ema(weekly["close"], 10)
        return bool(weekly["close"].iloc[-1] > w_ema10.iloc[-1])
    except Exception:
        return None


def monthly_trend_ok(df: pd.DataFrame) -> Optional[bool]:
    try:
        monthly = df.set_index("date").resample("ME").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
        ).dropna()
        if len(monthly) < 6:
            return None
        m_ema6 = ema(monthly["close"], 6)
        return bool(monthly["close"].iloc[-1] > m_ema6.iloc[-1])
    except Exception:
        return None


def breakout_analysis(df: pd.DataFrame, support: float, resistance: float,
                       volume_mult: float = 1.5, near_pct: float = 1.5) -> Dict[str, Any]:
    last = df.iloc[-1]
    vol_avg = df["vol_avg20"].iloc[-1]
    vol_confirmed = bool(vol_avg and not pd.isna(vol_avg) and last["volume"] > volume_mult * vol_avg)
    if resistance and last["close"] > resistance and vol_confirmed:
        status = "breakout_confirmed"
    elif resistance and last["close"] > resistance:
        status = "breakout_low_volume"
    elif resistance and (resistance - last["close"]) / resistance * 100 <= near_pct:
        status = "near_breakout"
    else:
        status = "no_breakout"
    return {"status": status, "support": support, "resistance": resistance, "volume_confirmed": vol_confirmed}


SETUP_PRIORITY = [
    "BREAKOUT", "NEAR_BREAKOUT", "BULLISH_DIVERGENCE", "VWAP_RECLAIM", "GAP_AND_GO",
    "PULLBACK_EMA20", "PULLBACK_EMA50", "STOCHASTIC_BOUNCE", "RSI_REVERSAL",
    "NEAR_SUPPORT", "TREND", "CONSOLIDATION",
]


def classify_setups(df: pd.DataFrame, breakout: Dict[str, Any], weekly_ok: Optional[bool],
                     patterns: List[str], divergence: Optional[str], gap: Optional[str]) -> List[str]:
    last = df.iloc[-1]
    setups = []
    if breakout["status"] in ("breakout_confirmed", "breakout_low_volume"):
        setups.append("BREAKOUT")
    elif breakout["status"] == "near_breakout":
        setups.append("NEAR_BREAKOUT")
    if last["close"] > last["ema20"] and last["low"] <= last["ema20"] * 1.02:
        setups.append("PULLBACK_EMA20")
    elif last["close"] > last["ema50"] and last["low"] <= last["ema50"] * 1.02:
        setups.append("PULLBACK_EMA50")
    if breakout["support"] and last["close"] <= breakout["support"] * 1.03:
        setups.append("NEAR_SUPPORT")
    if gap and "Gap Up" in gap:
        setups.append("GAP_AND_GO")
    if len(df) >= 3 and last["rsi14"] < 40 and last["rsi14"] > df["rsi14"].iloc[-3]:
        setups.append("RSI_REVERSAL")
    if last["stoch_k"] < 30 and last["stoch_k"] > last["stoch_d"]:
        setups.append("STOCHASTIC_BOUNCE")
    if divergence == "Bullish Divergence":
        setups.append("BULLISH_DIVERGENCE")
    if len(df) >= 2 and last["close"] > last["vwap"] and df["close"].iloc[-2] <= df["vwap"].iloc[-2]:
        setups.append("VWAP_RECLAIM")
    if price_uptrend := (last["close"] > last["ema20"] > last["ema50"]):
        setups.append("TREND")
    return setups if setups else ["CONSOLIDATION"]


def primary_setup(setups: List[str]) -> str:
    for s in SETUP_PRIORITY:
        if s in setups:
            return s
    return setups[0] if setups else "CONSOLIDATION"


def compute_technicals(df_raw: pd.DataFrame) -> Dict[str, Any]:
    """Takes a raw yfinance history() DataFrame (Capitalized OHLCV columns,
    DatetimeIndex) and returns the full merged indicator/pattern/setup bundle."""
    if df_raw is None or df_raw.empty or len(df_raw) < 30:
        return {}

    df = df_raw.reset_index()
    df.columns = [str(c).lower() for c in df.columns]
    if "date" not in df.columns:
        df = df.rename(columns={df.columns[0]: "date"})

    df["ema9"] = ema(df["close"], 9)
    df["ema20"] = ema(df["close"], 20)
    df["ema50"] = ema(df["close"], 50)
    df["ema200"] = ema(df["close"], 200) if len(df) >= 50 else pd.Series([np.nan] * len(df), index=df.index)
    df["sma20"] = sma(df["close"], 20)
    df["sma50"] = sma(df["close"], 50)
    df["rsi14"] = rsi(df["close"], 14)
    df["macd_line"], df["macd_signal"], df["macd_hist"] = macd(df["close"])
    df["bb_upper"], df["bb_lower"], df["bb_width_pct"] = bollinger(df["close"])
    df["atr14"] = atr(df, 14)
    df["vol_avg20"] = df["volume"].rolling(20).mean()
    df["adx14"], df["plus_di"], df["minus_di"] = adx(df, 14)
    df["stoch_k"], df["stoch_d"] = stochastic(df)
    df["vwap"] = vwap(df)

    support, resistance = find_support_resistance(df, lookback=30)
    patterns = detect_candlestick_patterns(df)
    divergence = detect_divergence(df)
    gap = gap_analysis(df)
    weekly_ok = weekly_trend_ok(df)
    monthly_ok = monthly_trend_ok(df)
    breakout = breakout_analysis(df, support, resistance)
    setups = classify_setups(df, breakout, weekly_ok, patterns, divergence, gap)

    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else last
    price = float(last["close"])
    prev_close = float(prev["close"])
    vol = float(last["volume"])
    avg_vol = float(df["volume"].tail(20).mean())
    hi_52w = float(df["high"].tail(252).max())
    lo_52w = float(df["low"].tail(252).min())
    macd_crossed_up = bool((
        (df["macd_line"] > df["macd_signal"]) & (df["macd_line"].shift(1) <= df["macd_signal"].shift(1))
    ).tail(5).any())
    bb_width_now = last["bb_width_pct"]
    bb_squeeze = bool(pd.notna(bb_width_now) and bb_width_now < df["bb_width_pct"].tail(60).quantile(0.25))

    return {
        "price": price,
        "prev_close": prev_close,
        "change_pct": ((price - prev_close) / prev_close * 100) if prev_close else 0.0,
        "ema9": float(last["ema9"]),
        "ema20": float(last["ema20"]),
        "ema50": float(last["ema50"]),
        "ema200": float(last["ema200"]) if pd.notna(last["ema200"]) else None,
        "sma20": float(last["sma20"]) if pd.notna(last["sma20"]) else None,
        "sma50": float(last["sma50"]) if pd.notna(last["sma50"]) else None,
        "rsi": float(last["rsi14"]),
        "macd": float(last["macd_line"]),
        "macd_signal": float(last["macd_signal"]),
        "macd_hist": float(last["macd_hist"]),
        "macd_hist_prev": float(prev["macd_hist"]) if len(df) >= 2 else 0.0,
        "macd_crossed_up": macd_crossed_up,
        "bb_upper": float(last["bb_upper"]) if pd.notna(last["bb_upper"]) else None,
        "bb_lower": float(last["bb_lower"]) if pd.notna(last["bb_lower"]) else None,
        "bb_width_pct": float(bb_width_now) if pd.notna(bb_width_now) else None,
        "bb_squeeze": bb_squeeze,
        "adx": float(last["adx14"]) if pd.notna(last["adx14"]) else None,
        "plus_di": float(last["plus_di"]) if pd.notna(last["plus_di"]) else None,
        "minus_di": float(last["minus_di"]) if pd.notna(last["minus_di"]) else None,
        "stoch_k": float(last["stoch_k"]) if pd.notna(last["stoch_k"]) else None,
        "stoch_d": float(last["stoch_d"]) if pd.notna(last["stoch_d"]) else None,
        "vwap": float(last["vwap"]) if pd.notna(last["vwap"]) else price,
        "atr": float(last["atr14"]) if pd.notna(last["atr14"]) else 0.0,
        "support": support,
        "resistance": resistance,
        "volume": vol,
        "avg_volume_20": avg_vol,
        "volume_ratio": (vol / avg_vol) if avg_vol else 1.0,
        "hi_52w": hi_52w,
        "lo_52w": lo_52w,
        "distance_from_52w_high_pct": ((hi_52w - price) / hi_52w * 100) if hi_52w else 0.0,
        "patterns": patterns,
        "divergence": divergence,
        "gap": gap,
        "weekly_trend_up": weekly_ok,
        "monthly_trend_up": monthly_ok,
        "breakout": breakout,
        "setups": setups,
        "chart": {
            "dates": [d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d) for d in df["date"].tail(150)],
            "open": df["open"].tail(150).round(2).tolist(),
            "high": df["high"].tail(150).round(2).tolist(),
            "low": df["low"].tail(150).round(2).tolist(),
            "close": df["close"].tail(150).round(2).tolist(),
            "volume": df["volume"].tail(150).astype(int).tolist(),
            "vol_avg20": df["vol_avg20"].tail(150).round(2).tolist(),
            "ema9": df["ema9"].tail(150).round(2).tolist(),
            "ema20": df["ema20"].tail(150).round(2).tolist(),
            "ema50": df["ema50"].tail(150).round(2).tolist(),
            "ema200": df["ema200"].tail(150).round(2).tolist() if df["ema200"].notna().any() else None,
            "vwap": df["vwap"].tail(150).round(2).tolist(),
            "bb_upper": df["bb_upper"].tail(150).round(2).tolist(),
            "bb_lower": df["bb_lower"].tail(150).round(2).tolist(),
            "rsi": df["rsi14"].tail(150).round(2).tolist(),
            "stoch_k": df["stoch_k"].tail(150).round(2).tolist(),
            "stoch_d": df["stoch_d"].tail(150).round(2).tolist(),
            "macd": df["macd_line"].tail(150).round(4).tolist(),
            "macd_signal": df["macd_signal"].tail(150).round(4).tolist(),
            "macd_hist": df["macd_hist"].tail(150).round(4).tolist(),
            "adx": df["adx14"].tail(150).round(2).tolist(),
            "plus_di": df["plus_di"].tail(150).round(2).tolist(),
            "minus_di": df["minus_di"].tail(150).round(2).tolist(),
        }
    }


def score_technical(t: Dict[str, Any]) -> Tuple[int, List[str], List[str], str]:
    """Unified 0-100 technical score combining both engines' signals."""
    if not t:
        return 0, [], ["Insufficient data"], "NA"
    reasons, flags = [], []
    score = 0
    price = t["price"]

    # 1) Trend structure (15)
    if t.get("ema200") and price > t["ema20"] > t["ema50"] > t["ema200"]:
        score += 15; reasons.append("Strong uptrend: Price > EMA20 > EMA50 > EMA200")
    elif price > t["ema20"] > t["ema50"]:
        score += 12; reasons.append("Uptrend: Price > EMA20 > EMA50")
    elif price > t["ema20"]:
        score += 6; reasons.append("Price above EMA20")
    else:
        flags.append("Price below EMA20 — no short-term uptrend")

    # 2) Multi-timeframe confluence (10)
    w, m = t.get("weekly_trend_up"), t.get("monthly_trend_up")
    if w and m:
        score += 10; reasons.append("Daily + Weekly + Monthly all aligned up")
    elif w:
        score += 7; reasons.append("Daily + Weekly aligned up")
    elif m:
        score += 5; reasons.append("Monthly aligned up")
    elif w is False and m is False:
        flags.append("Weekly & Monthly trend both down")

    # 3) ADX trend strength (10)
    adx_val = t.get("adx")
    if adx_val is not None:
        if adx_val > 25:
            score += 10; reasons.append(f"Strong trend (ADX {adx_val:.1f})")
        elif adx_val > 20:
            score += 5; reasons.append(f"Trend building (ADX {adx_val:.1f})")
        else:
            flags.append(f"Weak/no trend (ADX {adx_val:.1f})")

    # 4) RSI (8)
    r = t["rsi"]
    if 50 <= r <= 65:
        score += 8; reasons.append(f"RSI sweet spot ({r:.1f})")
    elif 40 <= r < 50:
        score += 6; reasons.append(f"RSI recovering ({r:.1f})")
    elif 65 < r <= 75:
        score += 4; reasons.append(f"RSI strong but watch overbought ({r:.1f})")
    elif r > 75:
        flags.append(f"RSI overbought ({r:.1f})")
    else:
        flags.append(f"RSI weak ({r:.1f})")

    # 5) MACD momentum (8)
    if t.get("macd_crossed_up"):
        score += 8; reasons.append("MACD bullish crossover recently")
    elif t["macd_hist"] > 0 and t["macd_hist"] > t["macd_hist_prev"]:
        score += 5; reasons.append("MACD bullish & histogram expanding")
    elif t["macd_hist"] <= 0:
        flags.append("MACD negative")

    # 6) Stochastic (5)
    sk, sd = t.get("stoch_k"), t.get("stoch_d")
    if sk is not None and sd is not None:
        if sk < 30 and sk > sd:
            score += 5; reasons.append("Stochastic oversold bounce")
        elif 30 <= sk <= 70 and sk > sd:
            score += 3; reasons.append("Stochastic bullish")

    # 7) Bollinger (5)
    if t.get("bb_upper") and price > t["bb_upper"] and t["breakout"]["volume_confirmed"]:
        score += 5; reasons.append("Bollinger upper-band breakout + volume")
    elif t.get("bb_squeeze"):
        score += 3; reasons.append("Bollinger squeeze — volatility contraction, breakout watch")

    # 8) Volume confirmation (10)
    vr = t["volume_ratio"]
    if vr > 2:
        score += 10; reasons.append(f"Volume 2x+ average — strong conviction ({vr:.1f}x)")
    elif vr > 1.5:
        score += 7; reasons.append(f"Volume spike {vr:.1f}x avg")
    elif vr > 1:
        score += 4; reasons.append(f"Volume above avg ({vr:.1f}x)")

    # 9) VWAP (7)
    if price > t["vwap"]:
        score += 7; reasons.append("Price above VWAP")
    else:
        flags.append("Price below VWAP")

    # 10) Breakout / support-resistance (10)
    bo = t["breakout"]["status"]
    if bo == "breakout_confirmed":
        score += 10; reasons.append("Breakout confirmed with volume")
    elif bo == "breakout_low_volume":
        score += 5; reasons.append("Breakout on price but volume unconfirmed")
    elif bo == "near_breakout":
        score += 6; reasons.append("Near breakout — watch closely")

    # 11) Patterns / divergence / gap (max 8, combined)
    extra = 0
    if t.get("patterns"):
        extra += 4; reasons.append(f"Candlestick: {', '.join(t['patterns'])}")
    if t.get("divergence") == "Bullish Divergence":
        extra += 4; reasons.append("Bullish divergence detected")
    elif t.get("divergence") == "Bearish Divergence":
        flags.append("Bearish divergence detected")
    if t.get("gap") and "Gap Up" in t["gap"]:
        extra += 3; reasons.append(t["gap"])
    elif t.get("gap"):
        flags.append(t["gap"])
    score += min(extra, 8)

    setup = primary_setup(t.get("setups", []))
    return min(round(score), 100), reasons, flags, setup


# ============================================================================
# Fundamental scoring — unchanged from the original engine (user only asked
# to merge the TECHNICAL scan; fundamentals were identical in spirit between
# both apps so left as-is here).
# ============================================================================

def score_fundamental(info: Dict[str, Any]) -> Tuple[int, List[str], List[str], Dict[str, Any]]:
    if not info:
        return 0, [], ["No fundamental data"], {}

    reasons, flags = [], []
    score = 0
    metrics = {}

    def g(*keys, default=None):
        for k in keys:
            v = info.get(k)
            if v is not None and not (isinstance(v, float) and np.isnan(v)):
                return v
        return default

    roe = g("returnOnEquity")
    metrics["roe"] = roe
    if roe is not None:
        roe_pct = roe * 100 if abs(roe) < 5 else roe
        metrics["roe_pct"] = roe_pct
        if roe_pct >= 18:
            score += 15; reasons.append(f"ROE strong ({roe_pct:.1f}%)")
        elif roe_pct >= 12:
            score += 10; reasons.append(f"ROE decent ({roe_pct:.1f}%)")
        elif roe_pct < 8:
            flags.append(f"ROE weak ({roe_pct:.1f}%)")

    eg = g("earningsGrowth", "earningsQuarterlyGrowth")
    metrics["earnings_growth"] = eg
    if eg is not None:
        eg_pct = eg * 100 if abs(eg) < 5 else eg
        metrics["earnings_growth_pct"] = eg_pct
        if eg_pct >= 20:
            score += 15; reasons.append(f"Strong earnings growth ({eg_pct:.1f}%)")
        elif eg_pct >= 10:
            score += 10; reasons.append(f"Solid earnings growth ({eg_pct:.1f}%)")
        elif eg_pct < 0:
            flags.append(f"Earnings declining ({eg_pct:.1f}%)")

    rg = g("revenueGrowth")
    metrics["revenue_growth"] = rg
    if rg is not None:
        rg_pct = rg * 100 if abs(rg) < 5 else rg
        metrics["revenue_growth_pct"] = rg_pct
        if rg_pct >= 15:
            score += 15; reasons.append(f"Strong sales growth ({rg_pct:.1f}%)")
        elif rg_pct >= 8:
            score += 10; reasons.append(f"Sales growth ({rg_pct:.1f}%)")
        elif rg_pct < 0:
            flags.append(f"Sales declining ({rg_pct:.1f}%)")

    pe = g("trailingPE", "forwardPE")
    metrics["pe"] = pe
    if pe is not None:
        if 8 < pe < 30:
            score += 10; reasons.append(f"PE reasonable ({pe:.1f})")
        elif 30 <= pe <= 50:
            score += 5
        elif pe > 60:
            flags.append(f"PE stretched ({pe:.1f})")
        elif pe < 0:
            flags.append("Negative PE (loss making)")

    pm = g("profitMargins")
    metrics["profit_margin"] = pm
    if pm is not None:
        pm_pct = pm * 100 if abs(pm) < 5 else pm
        metrics["profit_margin_pct"] = pm_pct
        if pm_pct >= 15:
            score += 10; reasons.append(f"Strong margins ({pm_pct:.1f}%)")
        elif pm_pct >= 8:
            score += 5
        elif pm_pct < 0:
            flags.append(f"Negative margins ({pm_pct:.1f}%)")

    om = g("operatingMargins")
    metrics["operating_margin"] = om
    if om is not None:
        om_pct = om * 100 if abs(om) < 5 else om
        metrics["operating_margin_pct"] = om_pct
        if om_pct >= 18:
            score += 10; reasons.append(f"Strong operating margin ({om_pct:.1f}%)")
        elif om_pct >= 10:
            score += 5

    de = g("debtToEquity")
    metrics["debt_to_equity"] = de
    if de is not None:
        de_val = de / 100 if de > 5 else de
        metrics["debt_to_equity_val"] = de_val
        if de_val < 0.5:
            score += 10; reasons.append(f"Low debt (D/E {de_val:.2f})")
        elif de_val < 1.0:
            score += 5
        elif de_val > 2.0:
            flags.append(f"High debt (D/E {de_val:.2f})")

    ocf = g("operatingCashflow", "freeCashflow")
    metrics["operating_cashflow"] = ocf
    if ocf is not None:
        if ocf > 0:
            score += 10; reasons.append("Positive operating cash flow")
        else:
            flags.append("Negative operating cash flow")

    cr = g("currentRatio")
    metrics["current_ratio"] = cr
    if cr is not None:
        if cr >= 1.5:
            score += 5; reasons.append(f"Healthy liquidity (CR {cr:.2f})")
        elif cr < 1.0:
            flags.append(f"Weak liquidity (CR {cr:.2f})")

    metrics.update({
        "market_cap": g("marketCap"),
        "sector": g("sector"),
        "industry": g("industry"),
        "book_value": g("bookValue"),
        "eps": g("trailingEps"),
        "dividend_yield": g("dividendYield"),
        "52w_high": g("fiftyTwoWeekHigh"),
        "52w_low": g("fiftyTwoWeekLow"),
        "beta": g("beta"),
    })

    return min(score, 100), reasons, flags, metrics


def compute_trade_plan(t: Dict[str, Any]) -> Dict[str, Any]:
    """ATR + swing-support based entry/stop/target (best of both engines:
    Engine A's clean output keys, Engine B's tighter stop-selection logic)."""
    if not t:
        return {}
    price = t["price"]
    a = t.get("atr") or 0
    if a <= 0:
        sl = price * 0.95
    else:
        swing_stop = t["support"] if t.get("support") and t["support"] < price else price * 0.95
        atr_stop = price - 1.5 * a
        sl = max(swing_stop, atr_stop) if swing_stop < price else atr_stop
    sl = round(sl, 2)
    risk = round(price - sl, 2)
    target = round(price + 2.5 * risk, 2) if risk > 0 else price
    rr = round((target - price) / risk, 2) if risk > 0 else 0
    return {
        "entry": round(price, 2),
        "stop_loss": sl,
        "target": target,
        "risk_per_share": risk,
        "reward_per_share": round(target - price, 2),
        "risk_reward": rr,
    }


# ============================================================================
# SECTION 3: scanner.py — fetch + scan engine
# ============================================================================

def _fetch_one(symbol: str, period: str = "1y") -> Optional[Dict[str, Any]]:
    try:
        tk = yf.Ticker(symbol)
        hist = tk.history(period=period, interval="1d", auto_adjust=False)
        if hist is None or hist.empty or len(hist) < 30:
            return None
        info = {}
        try:
            info = tk.info or {}
        except Exception:
            info = {}
        return {"symbol": symbol, "history": hist, "info": info}
    except Exception:
        return None


def _analyze_one(symbol: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    hist = data["history"]
    info = data.get("info", {})

    t = compute_technicals(hist)
    if not t:
        return None

    t_score, t_reasons, t_flags, primary = score_technical(t)
    f_score, f_reasons, f_flags, metrics = score_fundamental(info)
    plan = compute_trade_plan(t)

    base = symbol.replace(".NS", "")
    company_name = info.get("longName") or info.get("shortName") or base

    return {
        "symbol": symbol,
        "base_symbol": base,
        "name": company_name,
        "sector": info.get("sector") or get_sector(symbol),
        "industry": info.get("industry"),
        "market_cap": info.get("marketCap"),
        "price": t["price"],
        "change_pct": t["change_pct"],
        "technical_score": t_score,
        "fundamental_score": f_score,
        "setup_type": primary,
        "setups": t.get("setups", [primary]),
        "technical": t,
        "fundamentals": metrics,
        "reasons": t_reasons + f_reasons,
        "red_flags": t_flags + f_flags,
        "trade_plan": plan,
    }


def _passes_filters(c: Dict[str, Any], f: Dict[str, Any]) -> bool:
    if not f:
        return True
    min_t = f.get("min_technical_score", 0) or 0
    min_f = f.get("min_fundamental_score", 0) or 0
    if c["technical_score"] < min_t:
        return False
    if c["fundamental_score"] < min_f:
        return False
    sectors = f.get("sectors") or []
    if sectors and c.get("sector") and c["sector"] not in sectors:
        return False
    min_mcap_cr = f.get("min_mcap_cr")
    max_mcap_cr = f.get("max_mcap_cr")
    if min_mcap_cr is not None or max_mcap_cr is not None:
        mcap = c.get("market_cap")
        if mcap:  # only filter stocks where market cap data is actually available
            mcap_cr = mcap / 1e7
            if min_mcap_cr is not None and mcap_cr < min_mcap_cr:
                return False
            if max_mcap_cr is not None and mcap_cr > max_mcap_cr:
                return False
    setups = f.get("setup_types") or []
    if setups and not (set(c.get("setups", [c["setup_type"]])) & set(setups)):
        return False
    return True


def run_scan(
    tickers: List[str],
    filters: Dict[str, Any],
    progress_cb: Callable[[Dict[str, Any]], None],
    max_workers: int = 8,
    period: str = "1y",
) -> List[Dict[str, Any]]:
    total = len(tickers)
    results = []
    processed = 0
    started = _time.time()

    progress_cb({
        "type": "start", "total": total, "processed": 0,
        "message": f"Starting scan of {total} tickers...",
    })

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_fetch_one, sym, period): sym for sym in tickers}
        for fut in as_completed(futures):
            sym = futures[fut]
            processed += 1
            try:
                data = fut.result()
                if data:
                    candidate = _analyze_one(sym, data)
                    if candidate:
                        if _passes_filters(candidate, filters):
                            results.append(candidate)
                progress_cb({
                    "type": "progress", "total": total, "processed": processed,
                    "current_symbol": sym, "matches": len(results),
                    "elapsed": round(_time.time() - started, 1),
                })
            except Exception as e:
                progress_cb({
                    "type": "progress", "total": total, "processed": processed,
                    "current_symbol": sym, "matches": len(results), "error": str(e),
                    "elapsed": round(_time.time() - started, 1),
                })

    def combined(r):
        return r["technical_score"] / 100 * 0.5 + r["fundamental_score"] / 100 * 0.5

    results.sort(key=combined, reverse=True)
    return results


def fetch_stock_detail(symbol: str, period: str = "1y") -> Optional[Dict[str, Any]]:
    data = _fetch_one(symbol, period=period)
    if not data:
        return None
    return _analyze_one(symbol, data)


# ============================================================================
# SECTION 4: reports.py — PDF report generation (extended with new signals)
# ============================================================================

PDF_BG = "#FFFFFF"
PDF_CARD = "#F8FAFC"
PDF_BORDER = "#E2E8F0"
PDF_TEXT = "#0F172A"
PDF_MUTED = "#64748B"
PDF_GREEN = "#16A34A"
PDF_RED = "#DC2626"


def build_price_chart_image(t: Dict[str, Any], symbol: str, plan: Optional[Dict[str, Any]] = None) -> bytes:
    """Static PNG version of the app's chart — Price Action (candles + EMA20/50/200 +
    Bollinger + VWAP + Entry/SL/Target/Support/Resistance levels), Volume, RSI, MACD.
    Light-themed and high-resolution so it stays crisp when embedded in the PDF report."""
    c = t["chart"]
    n = len(c["dates"])
    dates = pd.to_datetime(c["dates"])
    x = mdates.date2num(dates)
    plan = plan or {}

    fig, axes = plt.subplots(
        4, 1, figsize=(10, 10.5), sharex=True,
        gridspec_kw={"height_ratios": [3.4, 1.0, 1.1, 1.1], "hspace": 0.3},
    )
    fig.patch.set_facecolor(PDF_BG)
    ax_price, ax_vol, ax_rsi, ax_macd = axes

    legend_kwargs = dict(fontsize=7.5, frameon=True, facecolor="white",
                          edgecolor=PDF_BORDER, framealpha=0.95, borderpad=0.6)

    for ax in axes:
        ax.set_facecolor(PDF_CARD)
        for spine in ax.spines.values():
            spine.set_color(PDF_BORDER)
        ax.tick_params(colors=PDF_TEXT, labelsize=8)
        ax.grid(color=PDF_BORDER, linewidth=0.6, alpha=0.8, linestyle="-")
        ax.margins(x=0.01)

    # Reserve a little extra room on the right for the Entry/SL/Target/etc. labels
    x_pad = (x[-1] - x[0]) * 0.07 if n > 1 else 1
    for ax in axes:
        ax.set_xlim(x[0], x[-1] + x_pad)

    # --- Price + EMA + Bollinger + VWAP (candlesticks) ---
    price_range = max(c["high"]) - min(c["low"]) or 1.0
    width = (x[-1] - x[0]) / max(n, 1) * 0.7 if n > 1 else 0.7
    for i in range(n):
        color = "#16A34A" if c["close"][i] >= c["open"][i] else "#DC2626"
        ax_price.plot([x[i], x[i]], [c["low"][i], c["high"][i]], color=color, linewidth=0.9, zorder=2, solid_capstyle="round")
        y0, y1 = sorted([c["open"][i], c["close"][i]])
        body_h = max(y1 - y0, price_range * 0.0025)
        ax_price.add_patch(plt.Rectangle((x[i] - width / 2, y0), width, body_h,
                                          facecolor=color, edgecolor=color, linewidth=0.4, zorder=3))
    ax_price.plot(x, c["ema20"], color="#2563EB", linewidth=1.3, label="EMA20")
    ax_price.plot(x, c["ema50"], color="#EA580C", linewidth=1.3, label="EMA50")
    if c.get("ema200"):
        ax_price.plot(x, c["ema200"], color="#9333EA", linewidth=1.3, label="EMA200")
    ax_price.plot(x, c["vwap"], color="#64748B", linewidth=1, linestyle=":", label="VWAP")
    ax_price.plot(x, c["bb_upper"], color="#16A34A", linewidth=0.7, alpha=0.7)
    ax_price.plot(x, c["bb_lower"], color="#16A34A", linewidth=0.7, alpha=0.7)
    ax_price.fill_between(x, c["bb_lower"], c["bb_upper"], color="#16A34A", alpha=0.06)

    # --- Trade-plan reference levels: Target / Resistance / Entry / Stop Loss / Support ---
    levels = [
        ("Target", plan.get("target"), "#16A34A", (0, (1, 1))),
        ("Resistance", t.get("resistance"), "#DC2626", (0, (5, 3))),
        ("Entry", plan.get("entry"), "#0F172A", (0, (1, 1.5))),
        ("Stop Loss", plan.get("stop_loss"), "#DC2626", (0, (1, 1))),
        ("Support", t.get("support"), "#16A34A", (0, (5, 3))),
    ]
    for label, val, color, dashes in levels:
        if val is None:
            continue
        ax_price.axhline(val, color=color, linewidth=1.1, linestyle=dashes, zorder=1)
        ax_price.text(x[-1] + x_pad * 0.12, val, f" {label}", fontsize=7, color=color,
                       fontweight="bold", va="center", ha="left", clip_on=False)

    ax_price.set_title(f"{symbol} — Price Action", fontsize=11, fontweight="bold", color=PDF_TEXT, pad=8)
    ax_price.legend(loc="upper left", ncol=4, **legend_kwargs)

    # --- Volume ---
    vol_colors = ["#16A34A" if c["close"][i] >= c["open"][i] else "#DC2626" for i in range(n)]
    ax_vol.bar(x, c["volume"], color=vol_colors, width=width, alpha=0.85)
    ax_vol.plot(x, c["vol_avg20"], color=PDF_TEXT, linewidth=1)
    ax_vol.set_title("Volume", fontsize=10, fontweight="bold", loc="left", color=PDF_TEXT, pad=6)

    # --- RSI ---
    ax_rsi.plot(x, c["rsi"], color="#2563EB", linewidth=1.3, label="RSI")
    ax_rsi.axhline(70, color="#DC2626", linewidth=0.9, linestyle="--")
    ax_rsi.axhline(30, color="#16A34A", linewidth=0.9, linestyle="--")
    ax_rsi.set_ylim(-2, 102)
    ax_rsi.set_title("RSI", fontsize=10, fontweight="bold", loc="left", color=PDF_TEXT, pad=6)

    # --- MACD ---
    hist_colors = ["#16A34A" if v >= 0 else "#DC2626" for v in c["macd_hist"]]
    ax_macd.bar(x, c["macd_hist"], color=hist_colors, width=width, alpha=0.85)
    ax_macd.plot(x, c["macd"], color="#2563EB", linewidth=1.3, label="MACD")
    ax_macd.plot(x, c["macd_signal"], color="#DC2626", linewidth=1.3, label="Signal")
    ax_macd.axhline(0, color=PDF_BORDER, linewidth=0.8)
    ax_macd.set_title("MACD", fontsize=10, fontweight="bold", loc="left", color=PDF_TEXT, pad=6)
    ax_macd.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax_macd.xaxis.set_major_locator(mdates.AutoDateLocator())
    fig.autofmt_xdate()

    buf = BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png", dpi=220, facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def _fmt(val, prefix="", suffix="", decimals=2):
    if val is None:
        return "—"
    try:
        return f"{prefix}{float(val):,.{decimals}f}{suffix}"
    except Exception:
        return str(val)


def _pdf_bg_painter(canvas, doc):
    """Paints the full page dark-navy so every page matches the on-screen theme."""
    canvas.saveState()
    canvas.setFillColor(colors.HexColor(PDF_BG))
    canvas.rect(0, 0, doc.pagesize[0], doc.pagesize[1], fill=1, stroke=0)
    canvas.restoreState()


def _metric_row(pairs, col_width, value_colors=None, label_size=7.5, value_size=13):
    """2-row Table: small muted labels on top, bold values below — mirrors the
    st.metric() blocks used in the on-screen detail view."""
    labels = [p[0] for p in pairs]
    values = [p[1] for p in pairs]
    tbl = Table([labels, values], colWidths=[col_width] * len(pairs))
    style = [
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(PDF_CARD)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor(PDF_MUTED)),
        ("TEXTCOLOR", (0, 1), (-1, 1), colors.HexColor(PDF_TEXT)),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica"),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), label_size),
        ("FONTSIZE", (0, 1), (-1, 1), value_size),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, 0), 8), ("BOTTOMPADDING", (0, 0), (-1, 0), 1),
        ("TOPPADDING", (0, 1), (-1, 1), 2), ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    if value_colors:
        for idx, col in value_colors.items():
            style.append(("TEXTCOLOR", (idx, 1), (idx, 1), colors.HexColor(col)))
    tbl.setStyle(TableStyle(style))
    return tbl


def _kv_grid(rows, col_width):
    """A grid of 'Label: value' cells (3 per row) — mirrors the Advanced
    Signals expander in the on-screen detail view."""
    styles = getSampleStyleSheet()
    kv_style = ParagraphStyle("KV", parent=styles["BodyText"], fontSize=9, leading=13,
                               textColor=colors.HexColor(PDF_TEXT))
    data = []
    for row in rows:
        data.append([Paragraph(f"<font color='{PDF_MUTED}'>{label}:</font> <b>{value}</b>", kv_style)
                     for label, value in row])
    ncols = max(len(r) for r in rows)
    tbl = Table(data, colWidths=[col_width] * ncols)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(PDF_CARD)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return tbl


def build_stock_report(candidate: dict) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=12 * mm, rightMargin=12 * mm, topMargin=12 * mm, bottomMargin=12 * mm,
        title=f"Swing Trade Report — {candidate.get('base_symbol', '')}",
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=18, textColor=colors.HexColor(PDF_TEXT), spaceAfter=0)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=12, textColor=colors.HexColor(PDF_TEXT), spaceAfter=4)
    body = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=8.5, leading=12, textColor=colors.HexColor(PDF_TEXT))
    small = ParagraphStyle("Small", parent=styles["BodyText"], fontSize=8, textColor=colors.HexColor(PDF_MUTED))
    muted_italic = ParagraphStyle("MutedItalic", parent=small, fontName="Helvetica-Oblique")

    content_w = doc.width
    story = []

    # ---------------------------------------------------------------
    # Header card: name/symbol + sector/industry + setup badges + metrics
    # ---------------------------------------------------------------
    setups = candidate.get("setups") or [candidate.get("setup_type", "—")]
    badge_cells = []
    for s in setups:
        label = SETUP_LABELS.get(s, s)
        color = SETUP_COLORS.get(s, "#64748B")
        chip = Table([[label]])
        chip.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(color)),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("ROUNDEDCORNERS", [6, 6, 6, 6]),
        ]))
        badge_cells.append(chip)
    badges_row = Table([badge_cells], hAlign="RIGHT")
    badges_row.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(PDF_CARD)),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    title_cell = Paragraph(
        f"{candidate.get('name','')} <font color='{PDF_MUTED}' size='13'>({candidate.get('base_symbol','')})</font>", h1,
    )
    header_top = Table([[title_cell, badges_row]], colWidths=[content_w * 0.62, content_w * 0.38])
    header_top.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(PDF_CARD)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 12), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(header_top)

    sub = Table([[Paragraph(
        f"{candidate.get('sector','—')} &middot; {candidate.get('industry','—')}", small,
    )]], colWidths=[content_w])
    sub.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(PDF_CARD)),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(sub)

    price = candidate.get("price", 0)
    change = candidate.get("change_pct", 0) or 0
    t = candidate.get("technical", {}) or {}
    t_score = candidate.get("technical_score", 0)
    f_score = candidate.get("fundamental_score", 0)
    change_sign = "+" if change >= 0 else ""
    change_color = PDF_GREEN if change >= 0 else PDF_RED

    story.append(_metric_row(
        [
            ("Price", _fmt(price, "₹")),
            ("Technical Score", f"{t_score}/100"),
            ("Fundamental Score", f"{f_score}/100"),
            ("RSI (14)", _fmt(t.get("rsi"), decimals=1)),
            ("ADX (14)", _fmt(t.get("adx"), decimals=1)),
        ],
        content_w / 5, value_colors={0: change_color},
    ))
    change_line = Table([[Paragraph(
        f"<font color='{change_color}'>{change_sign}{_fmt(change, '', '%')}</font>", small,
    )]], colWidths=[content_w])
    change_line.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(PDF_CARD)),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
    ]))
    story.append(change_line)
    story.append(Spacer(1, 8))

    # ---------------------------------------------------------------
    # Chart (mirrors the on-screen detail-view chart, with trade-plan levels)
    # ---------------------------------------------------------------
    plan = candidate.get("trade_plan", {}) or {}
    if t.get("chart"):
        try:
            chart_png = build_price_chart_image(t, candidate.get("base_symbol", ""), plan)
            img = RLImage(BytesIO(chart_png), width=content_w, height=content_w * (10.5 / 10))
            story.append(img)
            story.append(Spacer(1, 10))
        except Exception:
            pass  # if chart rendering fails for any reason, skip it rather than break the whole report

    # ---------------------------------------------------------------
    # Trade Plan
    # ---------------------------------------------------------------
    story.append(Paragraph("Trade Plan", h2))
    story.append(_metric_row(
        [
            ("Entry", _fmt(plan.get("entry"), "₹")),
            ("Stop Loss", _fmt(plan.get("stop_loss"), "₹")),
            ("Target", _fmt(plan.get("target"), "₹")),
            ("Risk : Reward", _fmt(plan.get("risk_reward"), "1 : ", "", 2)),
        ],
        content_w / 4, value_colors={1: PDF_RED, 2: PDF_GREEN},
    ))
    story.append(Spacer(1, 12))

    # ---------------------------------------------------------------
    # Reasons / Red Flags (two columns, like the on-screen layout)
    # ---------------------------------------------------------------
    reasons = candidate.get("reasons") or []
    flags = candidate.get("red_flags") or []

    def _bullet_list(items, empty_text):
        cell_style = ParagraphStyle("Bullet", parent=body, fontSize=8.5, leading=12)
        if not items:
            return [Paragraph(empty_text, muted_italic)]
        return [Paragraph(f"• {r}", cell_style) for r in items]

    reasons_col = [Paragraph(f"<font color='{PDF_GREEN}'><b>Reasons</b></font>", h2)] + _bullet_list(reasons, "No positive signals found.")
    flags_col = [Paragraph(f"<font color='{PDF_RED}'><b>Red Flags</b></font>", h2)] + _bullet_list(flags, "No red flags found.")

    rf_tbl = Table([[reasons_col, flags_col]], colWidths=[content_w / 2, content_w / 2])
    rf_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(PDF_CARD)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (0, 0), 10), ("LEFTPADDING", (1, 0), (1, 0), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LINEBEFORE", (1, 0), (1, 0), 0.5, colors.HexColor(PDF_BORDER)),
    ]))
    story.append(rf_tbl)
    story.append(Spacer(1, 12))

    # ---------------------------------------------------------------
    # Advanced Signals (mirrors the "Advanced Signals" expander)
    # ---------------------------------------------------------------
    story.append(Paragraph(
        f"Advanced Signals <font size='8' color='{PDF_MUTED}'>(patterns, divergence, gap, multi-timeframe)</font>", h2,
    ))
    stoch_k, stoch_d = t.get("stoch_k"), t.get("stoch_d")
    stoch_txt = f"{stoch_k:.1f} / {stoch_d:.1f}" if stoch_k is not None and stoch_d is not None else "—"
    breakout_status = "—"
    if (t.get("breakout") or {}).get("status"):
        breakout_status = t["breakout"]["status"].replace("_", " ").title()
    adv_rows = [
        [("Candlestick", ", ".join(t.get("patterns") or []) or "—"),
         ("Divergence", t.get("divergence") or "—"),
         ("Gap", t.get("gap") or "—")],
        [("Weekly trend up", t.get("weekly_trend_up")),
         ("Monthly trend up", t.get("monthly_trend_up")),
         ("Breakout status", breakout_status)],
        [("Stoch %K / %D", stoch_txt),
         ("BB width %", _fmt(t.get("bb_width_pct"), "", "%", 1)),
         ("Volume ratio", _fmt(t.get("volume_ratio"), "", "x"))],
    ]
    story.append(_kv_grid(adv_rows, content_w / 3))
    story.append(Spacer(1, 12))

    # ---------------------------------------------------------------
    # Fundamental snapshot (mirrors the "Fundamental snapshot" expander)
    # ---------------------------------------------------------------
    f = candidate.get("fundamentals", {}) or {}
    story.append(Paragraph("Fundamental Snapshot", h2))
    story.append(_metric_row(
        [
            ("ROE", _fmt(f.get("roe_pct"), "", "%", 1)),
            ("PE", _fmt(f.get("pe"), decimals=1)),
            ("Rev. Growth", _fmt(f.get("revenue_growth_pct"), "", "%", 1)),
            ("D/E", _fmt(f.get("debt_to_equity_val"), decimals=2)),
        ],
        content_w / 4,
    ))
    story.append(Spacer(1, 14))

    story.append(Paragraph(
        "Disclaimer: This report is generated for informational purposes only and does not constitute investment advice. "
        "Please do your own research and consult a SEBI-registered advisor before making any trades.", small,
    ))

    doc.build(story, onFirstPage=_pdf_bg_painter, onLaterPages=_pdf_bg_painter)
    buf.seek(0)
    return buf.getvalue()
# ============================================================================
# SECTION 5: lightweight local persistence (drop-in replacement for MongoDB)
# Watchlist / notes / alerts / past scans are saved to data.json next to this
# file, so they survive an app restart. Loaded once into session_state.
# ============================================================================

DATA_FILE = Path(__file__).parent / "data.json"
_store_lock = threading.Lock()


def _load_store() -> Dict[str, list]:
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            return {
                "watchlist": loaded.get("watchlist", []),
                "notes": loaded.get("notes", []),
                "alerts": loaded.get("alerts", []),
                "scan_history": loaded.get("scan_history", []),
            }
        except Exception:
            pass
    return {"watchlist": [], "notes": [], "alerts": [], "scan_history": []}


def _save_store():
    with _store_lock:
        tmp = DATA_FILE.with_suffix(".tmp")
        payload = {
            "watchlist": st.session_state.watchlist,
            "notes": st.session_state.notes,
            "alerts": st.session_state.alerts,
            "scan_history": st.session_state.scan_history[-20:],  # keep last 20
        }
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, default=str, ensure_ascii=False, indent=2)
        tmp.replace(DATA_FILE)


# ============================================================================
# SECTION 6: Streamlit app
# ============================================================================

st.set_page_config(
    page_title="Swing Trade Screener Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---- session state init -----------------------------------------------
if "_store_loaded" not in st.session_state:
    store = _load_store()
    st.session_state.watchlist = store["watchlist"]      # list of {symbol, name, added_at}
    st.session_state.notes = store["notes"]               # list of {symbol, content, created_at}
    st.session_state.alerts = store["alerts"]              # list of {id, symbol, kind, value, active, ...}
    st.session_state.scan_history = store["scan_history"]  # list of past scan summaries
    st.session_state._store_loaded = True

if "scan_results" not in st.session_state:
    st.session_state.scan_results = []
if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = None


@st.cache_data(ttl=300, show_spinner=False)
def cached_stock_detail(symbol: str, period: str = "1y"):
    return fetch_stock_detail(symbol, period=period)


def add_to_watchlist(symbol: str, name: str):
    if any(w["symbol"] == symbol for w in st.session_state.watchlist):
        return
    st.session_state.watchlist.append({
        "symbol": symbol, "name": name,
        "added_at": datetime.now(timezone.utc).isoformat(),
    })
    _save_store()


def remove_from_watchlist(symbol: str):
    st.session_state.watchlist = [w for w in st.session_state.watchlist if w["symbol"] != symbol]
    _save_store()


def save_note(symbol: str, content: str):
    st.session_state.notes = [n for n in st.session_state.notes if n["symbol"] != symbol]
    if content.strip():
        st.session_state.notes.append({
            "symbol": symbol, "content": content,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    _save_store()


def get_note(symbol: str) -> str:
    for n in st.session_state.notes:
        if n["symbol"] == symbol:
            return n["content"]
    return ""


SETUP_LABELS = {
    "BREAKOUT": "Breakout", "NEAR_BREAKOUT": "Near Breakout",
    "PULLBACK_EMA20": "Pullback to EMA20", "PULLBACK_EMA50": "Pullback to EMA50",
    "NEAR_SUPPORT": "Near Support", "GAP_AND_GO": "Gap & Go",
    "RSI_REVERSAL": "RSI Reversal", "STOCHASTIC_BOUNCE": "Stochastic Bounce",
    "BULLISH_DIVERGENCE": "Bullish Divergence", "VWAP_RECLAIM": "VWAP Reclaim",
    "TREND": "Trend", "CONSOLIDATION": "Consolidation", "NA": "N/A",
}

SETUP_COLORS = {
    "BREAKOUT": "#16A34A", "NEAR_BREAKOUT": "#22C55E", "PULLBACK_EMA20": "#2563EB",
    "PULLBACK_EMA50": "#3B82F6", "NEAR_SUPPORT": "#0EA5E9", "GAP_AND_GO": "#DB2777",
    "RSI_REVERSAL": "#EA580C", "STOCHASTIC_BOUNCE": "#F59E0B", "BULLISH_DIVERGENCE": "#9333EA",
    "VWAP_RECLAIM": "#0891B2", "TREND": "#7C3AED", "CONSOLIDATION": "#64748B", "NA": "#64748B",
}


def build_price_chart(t: Dict[str, Any], symbol: str):
    c = t["chart"]
    fig = make_subplots(
        rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.025,
        row_heights=[0.40, 0.14, 0.16, 0.16, 0.14],
        subplot_titles=(
            f"{symbol} — Price / EMA / Bollinger / VWAP", "Volume",
            "RSI (14) + Stochastic", "MACD", "ADX / DI",
        ),
    )

    fig.add_trace(go.Candlestick(
        x=c["dates"], open=c["open"], high=c["high"], low=c["low"], close=c["close"],
        name="Price", increasing_line_color="#16A34A", decreasing_line_color="#DC2626",
    ), row=1, col=1)
    fig.add_trace(go.Scatter(x=c["dates"], y=c["ema20"], name="EMA20", line=dict(color="#2563EB", width=1.2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=c["dates"], y=c["ema50"], name="EMA50", line=dict(color="#EA580C", width=1.2)), row=1, col=1)
    if c.get("ema200"):
        fig.add_trace(go.Scatter(x=c["dates"], y=c["ema200"], name="EMA200", line=dict(color="#7C3AED", width=1.2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=c["dates"], y=c["vwap"], name="VWAP", line=dict(color="#64748B", width=1, dash="dot")), row=1, col=1)
    fig.add_trace(go.Scatter(x=c["dates"], y=c["bb_upper"], name="BB Upper", line=dict(color="rgba(22,163,74,0.4)", width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=c["dates"], y=c["bb_lower"], name="BB Lower", line=dict(color="rgba(22,163,74,0.4)", width=1), fill="tonexty", fillcolor="rgba(22,163,74,0.05)"), row=1, col=1)

    vol_colors = ["#16A34A" if c["close"][i] >= c["open"][i] else "#DC2626" for i in range(len(c["close"]))]
    fig.add_trace(go.Bar(x=c["dates"], y=c["volume"], marker_color=vol_colors, name="Volume"), row=2, col=1)
    fig.add_trace(go.Scatter(x=c["dates"], y=c["vol_avg20"], name="Vol Avg20", line=dict(color="#0F172A", width=1)), row=2, col=1)

    fig.add_trace(go.Scatter(x=c["dates"], y=c["rsi"], name="RSI", line=dict(color="#0EA5E9", width=1.3)), row=3, col=1)
    fig.add_trace(go.Scatter(x=c["dates"], y=c["stoch_k"], name="Stoch %K", line=dict(color="#F59E0B", width=1)), row=3, col=1)
    fig.add_trace(go.Scatter(x=c["dates"], y=c["stoch_d"], name="Stoch %D", line=dict(color="#EA580C", width=1, dash="dot")), row=3, col=1)
    fig.add_hline(y=70, line_dash="dot", line_color="#DC2626", row=3, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="#16A34A", row=3, col=1)

    fig.add_trace(go.Bar(x=c["dates"], y=c["macd_hist"], name="MACD Hist", marker_color="#94A3B8"), row=4, col=1)
    fig.add_trace(go.Scatter(x=c["dates"], y=c["macd"], name="MACD", line=dict(color="#2563EB", width=1.2)), row=4, col=1)
    fig.add_trace(go.Scatter(x=c["dates"], y=c["macd_signal"], name="Signal", line=dict(color="#EA580C", width=1.2)), row=4, col=1)

    fig.add_trace(go.Scatter(x=c["dates"], y=c["adx"], name="ADX", line=dict(color="#0F172A", width=1.4)), row=5, col=1)
    fig.add_trace(go.Scatter(x=c["dates"], y=c["plus_di"], name="+DI", line=dict(color="#16A34A", width=1)), row=5, col=1)
    fig.add_trace(go.Scatter(x=c["dates"], y=c["minus_di"], name="-DI", line=dict(color="#DC2626", width=1)), row=5, col=1)
    fig.add_hline(y=25, line_dash="dot", line_color="#64748B", row=5, col=1)

    fig.update_layout(
        height=980, xaxis_rangeslider_visible=False, margin=dict(t=40, b=10, l=10, r=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def render_stock_detail(symbol: str):
    with st.spinner(f"Fetching {symbol}..."):
        c = cached_stock_detail(symbol)
    if not c:
        st.error(f"Could not fetch data for {symbol}. Check the symbol (NSE, e.g. RELIANCE.NS) and try again.")
        return

    t = c["technical"]
    plan = c["trade_plan"]
    setups = c.get("setups") or [c["setup_type"]]

    top_l, top_r = st.columns([3, 1.4])
    with top_l:
        st.subheader(f"{c['name']} ({c['base_symbol']})")
        st.caption(f"{c.get('sector','—')} · {c.get('industry','—')}")
    with top_r:
        badges = "".join(
            f"<span style='background:{SETUP_COLORS.get(s,'#64748B')};color:white;padding:3px 9px;"
            f"border-radius:6px;font-weight:600;font-size:12px;margin-left:4px'>{SETUP_LABELS.get(s,s)}</span>"
            for s in setups
        )
        st.markdown(f"<div style='text-align:right'>{badges}</div>", unsafe_allow_html=True)

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Price", f"₹{c['price']:.2f}", f"{c['change_pct']:.2f}%")
    m2.metric("Technical Score", f"{c['technical_score']}/100")
    m3.metric("Fundamental Score", f"{c['fundamental_score']}/100")
    m4.metric("RSI (14)", f"{t['rsi']:.1f}")
    m5.metric("ADX (14)", f"{t['adx']:.1f}" if t.get("adx") is not None else "—")

    b1, b2 = st.columns(2)
    with b1:
        if st.button("⭐ Add to Watchlist", key=f"wl_{symbol}", use_container_width=True):
            add_to_watchlist(c["symbol"], c["name"])
            st.success("Added to watchlist")
    with b2:
        pdf_bytes = build_stock_report(c)
        st.download_button(
            "📄 Download PDF Report", data=pdf_bytes,
            file_name=f"{c['base_symbol']}_swing_report.pdf", mime="application/pdf",
            key=f"pdf_{symbol}", use_container_width=True,
        )

    st.plotly_chart(build_price_chart(t, c["base_symbol"]), use_container_width=True)

    st.markdown("#### Trade Plan")
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Entry", f"₹{plan['entry']}")
    p2.metric("Stop Loss", f"₹{plan['stop_loss']}")
    p3.metric("Target", f"₹{plan['target']}")
    p4.metric("Risk : Reward", f"1 : {plan['risk_reward']}")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### ✅ Reasons")
        for r in c["reasons"]:
            st.markdown(f"- {r}")
        if not c["reasons"]:
            st.caption("No positive signals found.")
    with col_b:
        st.markdown("#### 🚩 Red Flags")
        for r in c["red_flags"]:
            st.markdown(f"- {r}")
        if not c["red_flags"]:
            st.caption("No red flags found.")

    with st.expander("📡 Advanced Signals (patterns, divergence, gap, multi-timeframe)"):
        a1, a2, a3 = st.columns(3)
        a1.write(f"**Candlestick:** {', '.join(t['patterns']) if t.get('patterns') else '—'}")
        a2.write(f"**Divergence:** {t.get('divergence') or '—'}")
        a3.write(f"**Gap:** {t.get('gap') or '—'}")
        b1c, b2c, b3c = st.columns(3)
        b1c.write(f"**Weekly trend up:** {t.get('weekly_trend_up')}")
        b2c.write(f"**Monthly trend up:** {t.get('monthly_trend_up')}")
        b3c.write(f"**Breakout status:** {t['breakout']['status'].replace('_',' ').title()}")
        c1c, c2c, c3c = st.columns(3)
        c1c.write(f"**Stoch %K / %D:** {t.get('stoch_k'):.1f} / {t.get('stoch_d'):.1f}" if t.get("stoch_k") is not None else "—")
        c2c.write(f"**BB width %:** {t.get('bb_width_pct'):.1f}%" if t.get("bb_width_pct") is not None else "—")
        c3c.write(f"**Volume ratio:** {t.get('volume_ratio'):.2f}x")

    with st.expander("Fundamental snapshot"):
        f = c["fundamentals"]
        fcols = st.columns(4)
        fcols[0].metric("ROE", f"{f.get('roe_pct'):.1f}%" if f.get("roe_pct") is not None else "—")
        fcols[1].metric("PE", f"{f.get('pe'):.1f}" if f.get("pe") is not None else "—")
        fcols[2].metric("Rev. Growth", f"{f.get('revenue_growth_pct'):.1f}%" if f.get("revenue_growth_pct") is not None else "—")
        fcols[3].metric("D/E", f"{f.get('debt_to_equity_val'):.2f}" if f.get("debt_to_equity_val") is not None else "—")

    st.markdown("#### 📝 Your Notes")
    note_val = st.text_area("Notes", value=get_note(symbol), key=f"note_{symbol}", label_visibility="collapsed")
    if st.button("Save note", key=f"savenote_{symbol}"):
        save_note(symbol, note_val)
        st.success("Note saved")


# ---------------------------- Sidebar navigation -----------------------
st.sidebar.title("📈 Swing Trade Screener Pro")
st.sidebar.caption("Unified Engine — merged from both scanners")
page = st.sidebar.radio("Navigate", ["🔍 Scanner", "⭐ Watchlist", "🧮 Position Sizing", "ℹ️ About"], label_visibility="collapsed")

st.sidebar.markdown("---")

lookup = st.sidebar.text_input("Quick lookup (NSE symbol)", placeholder="e.g. RELIANCE")
if st.sidebar.button("View stock", use_container_width=True) and lookup.strip():
    sym = lookup.strip().upper()
    if not sym.endswith(".NS"):
        sym += ".NS"
    st.session_state.selected_symbol = sym
    page = "🔍 Scanner"

# ============================== SCANNER PAGE ============================
if page == "🔍 Scanner":
    st.sidebar.markdown("### Scan Filters")
    universe_label = st.sidebar.selectbox(
        "Universe", ["Nifty 50", "Nifty 200", "Nifty 500", "Full NSE Cash Segment (slow, 1500+ stocks)"], index=0,
    )
    use_live_nse = st.sidebar.checkbox(
        "Fetch live list from NSE", value=True,
        help="Downloads the current constituent list directly from nseindia.com. "
             "Falls back to the built-in list if NSE blocks the request.",
    )

    setups_sel = st.sidebar.multiselect(
        "Setup types (optional)",
        list(SETUP_LABELS.keys())[:-1],
        format_func=lambda k: SETUP_LABELS.get(k, k),
    )
    min_tech = st.sidebar.slider("Min technical score", 0, 100, 0)
    min_fund = st.sidebar.slider("Min fundamental score", 0, 100, 0)

    st.sidebar.markdown("**Market Cap range (₹ Crore)**")
    mc1, mc2 = st.sidebar.columns(2)
    min_mcap_input = mc1.number_input("Min", min_value=0, value=0, step=100, key="min_mcap_input", label_visibility="collapsed", placeholder="Min")
    max_mcap_input = mc2.number_input("Max (0 = no limit)", min_value=0, value=0, step=100, key="max_mcap_input", label_visibility="collapsed", placeholder="Max (0 = no limit)")
    st.sidebar.caption("e.g. Small cap < 5,000 Cr · Mid cap 5,000–20,000 Cr · Large cap > 20,000 Cr")

    top_n = st.sidebar.slider(
        "Show top N stocks", 1, 15, 15,
        help="Only the top N matches (by combined technical + fundamental score) will be shown/exported.",
    )

    run_col, clear_col = st.sidebar.columns(2)
    run_clicked = run_col.button("🚀 Run Scan", type="primary", use_container_width=True)
    clear_clicked = clear_col.button(
        "🗑️ Clear", use_container_width=True,
        disabled=not st.session_state.scan_results,
    )

    if clear_clicked:
        st.session_state.scan_results = []
        st.session_state.selected_symbol = None
        st.rerun()

    st.title("Scanner")
    st.caption("Unified technical engine: EMA/RSI/MACD/VWAP/ATR + ADX/Stochastic/Bollinger + candlestick patterns, divergence, gap & multi-timeframe confluence.")

    if run_clicked:
        fallback_key = {
            "Nifty 50": "nifty50", "Nifty 200": "nifty200",
            "Nifty 500": "nifty500", "Full NSE Cash Segment (slow, 1500+ stocks)": "nifty500",
        }[universe_label]

        tickers = None
        if use_live_nse:
            with st.spinner(f"Fetching latest {universe_label} list from nseindia.com..."):
                tickers = get_universe_live(universe_label)
            if not tickers:
                st.warning(
                    "Could not fetch the live list from NSE (it often blocks automated requests). "
                    "Using the built-in list instead."
                )
        if not tickers:
            tickers = get_universe(fallback_key)

        filters = {
            "min_technical_score": min_tech, "min_fundamental_score": min_fund,
            "setup_types": setups_sel,
            "min_mcap_cr": min_mcap_input if min_mcap_input > 0 else None,
            "max_mcap_cr": max_mcap_input if max_mcap_input > 0 else None,
        }

        progress_bar = st.progress(0.0)
        status_text = st.empty()
        matches_text = st.empty()

        def progress_cb(evt: Dict[str, Any]):
            if evt["type"] == "start":
                status_text.info(evt["message"])
            elif evt["type"] == "progress":
                pct = evt["processed"] / max(evt["total"], 1)
                progress_bar.progress(min(pct, 1.0))
                status_text.text(f"Scanned {evt['processed']}/{evt['total']} — last: {evt.get('current_symbol','')}")
                matches_text.markdown(f"**Matches so far: {evt['matches']}**")

        with st.spinner("Scanning... this can take a couple of minutes for larger universes."):
            results = run_scan(tickers, filters, progress_cb, max_workers=8)

        progress_bar.progress(1.0)
        status_text.success(f"Done — {len(results)} match(es) out of {len(tickers)} scanned.")

        st.session_state.scan_results = results
        st.session_state.scan_history.append({
            "id": str(uuid.uuid4()), "universe": universe_label, "filters": filters,
            "total_scanned": len(tickers), "matches": len(results),
            "run_at": datetime.now(timezone.utc).isoformat(),
        })
        _save_store()

    all_results = st.session_state.scan_results
    if all_results:
        results = all_results[:top_n]
        st.markdown(f"### Results — showing top {len(results)} of {len(all_results)} match(es)")
        df = pd.DataFrame([{
            "Symbol": r["base_symbol"], "Name": r["name"], "Sector": r["sector"],
            "Price (₹)": round(r["price"], 2), "Change %": round(r["change_pct"], 2),
            "Market Cap (₹ Cr)": round(r["market_cap"] / 1e7, 0) if r.get("market_cap") else None,
            "Tech Score": r["technical_score"], "Fund Score": r["fundamental_score"],
            "Setups": ", ".join(SETUP_LABELS.get(s, s) for s in (r.get("setups") or [r["setup_type"]])),
        } for r in results])
        st.dataframe(df, use_container_width=True, hide_index=True)

        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Export results to CSV", csv_bytes, "scan_results.csv", "text/csv")

        symbol_options = {f"{r['base_symbol']} — {r['name']}": r["symbol"] for r in results}
        pick = st.selectbox("View detail for:", list(symbol_options.keys()))
        if st.button("Open detail view"):
            st.session_state.selected_symbol = symbol_options[pick]
    else:
        st.info("Set your filters in the sidebar and click **Run Scan** to find swing-trade candidates.")

    if st.session_state.selected_symbol:
        st.markdown("---")
        render_stock_detail(st.session_state.selected_symbol)

# ============================== WATCHLIST PAGE ===========================
elif page == "⭐ Watchlist":
    st.title("Watchlist")
    wl = st.session_state.watchlist
    if not wl:
        st.info("Your watchlist is empty. Add stocks from the Scanner page.")
    else:
        for w in list(wl):
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 1, 1])
                c1.markdown(f"**{w['name']}** ({w['symbol'].replace('.NS','')})")
                if c2.button("View", key=f"view_{w['symbol']}"):
                    st.session_state.selected_symbol = w["symbol"]
                if c3.button("Remove", key=f"rm_{w['symbol']}"):
                    remove_from_watchlist(w["symbol"])
                    st.rerun()

    if st.session_state.selected_symbol:
        st.markdown("---")
        render_stock_detail(st.session_state.selected_symbol)

# ============================== POSITION SIZING PAGE =====================
elif page == "🧮 Position Sizing":
    st.title("Position Sizing Calculator")
    st.caption("Work out how many shares to buy given your account size and risk tolerance.")

    with st.form("position_sizing"):
        c1, c2 = st.columns(2)
        portfolio_size = c1.number_input("Portfolio size (₹)", min_value=0.0, value=100000.0, step=1000.0)
        risk_pct = c2.number_input("Risk per trade (%)", min_value=0.1, max_value=100.0, value=1.0, step=0.1)
        c3, c4 = st.columns(2)
        entry = c3.number_input("Entry price (₹)", min_value=0.0, value=100.0, step=1.0)
        stop_loss = c4.number_input("Stop loss (₹)", min_value=0.0, value=95.0, step=1.0)
        submitted = st.form_submit_button("Calculate", type="primary")

    if submitted:
        risk_amount = portfolio_size * (risk_pct / 100)
        risk_per_share = entry - stop_loss
        if risk_per_share <= 0:
            st.error("Stop loss must be below entry price.")
        else:
            shares = int(risk_amount // risk_per_share)
            position_value = shares * entry
            r1, r2, r3 = st.columns(3)
            r1.metric("Max risk amount", f"₹{risk_amount:,.0f}")
            r2.metric("Shares to buy", f"{shares}")
            r3.metric("Position value", f"₹{position_value:,.0f}")
            if portfolio_size > 0:
                st.caption(f"This position uses {position_value / portfolio_size * 100:.1f}% of your portfolio.")

# ============================== ABOUT PAGE ================================
else:
    st.title("About")
    st.markdown(
        """
This app screens NSE-listed stocks (Nifty 50 / 100 / 200 / 500) for swing-trade
setups using a **unified technical engine** merged from two independent
scanners, plus a **fundamental** (ROE, growth, margins, debt, liquidity) score.

**Technical engine (0-100) combines:**
- Trend structure: EMA9/20/50/200, SMA20/50
- Momentum: RSI(14, Wilder), MACD(12,26,9), Stochastic(14,3)
- Volatility & bands: ATR(14, Wilder), Bollinger Bands(20,2) + squeeze detection
- Trend strength: ADX(14, Wilder) + DI+/DI-
- Volume confirmation vs 20-day average
- VWAP position
- Breakout state machine (confirmed / low-volume / near breakout) vs 30-day S/R
- Candlestick patterns (Hammer, Shooting Star, Engulfing, Doji)
- RSI divergence, gap analysis, weekly + monthly multi-timeframe confluence
- Multi-label setup classification (a stock can show several setups at once)

Data source: Yahoo Finance via `yfinance`. Prices can be delayed and
fundamentals are sourced as-is from Yahoo — always cross-check before trading.

**This is not investment advice.** Please do your own research and consult a
SEBI-registered advisor before making any trades.

Your watchlist, notes, and scan history are saved locally to `data.json`
next to this script, so they persist between app restarts on your machine.
        """
    )
