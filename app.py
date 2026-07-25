"""
Swing Trade Screener Pro — Upgraded Edition
============================================
Major upgrades over v1:
  • 15+ Technical indicators (ADX, Stochastic, VWAP, S/R, Candlesticks,
    Divergence, Gap Analysis, Relative Strength vs Nifty)
  • 20+ Fundamental metrics (P/B, PEG, Cash Flow, Beta, 52W range,
    Institutional holding, Quarterly earnings growth, Current ratio, etc.)
  • Interactive Plotly charts per candidate
  • Multi-timeframe confluence scoring + Swing Setup classification
  • Earnings proximity alert
  • Sector & Market Cap filters
  • Export to CSV
  • Position sizing calculator

Chalane ka tareeka:
    pip install -r requirements.txt
    streamlit run app.py
"""

import io
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import yfinance as yf
from datetime import datetime, timedelta
from plotly.subplots import make_subplots
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage,
    PageBreak, HRFlowable,
)

st.set_page_config(page_title="Swing Trade Screener Pro", layout="wide", page_icon="📈")

NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

INDEX_URLS = {
    "Nifty 50": "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
    "Nifty 200": "https://archives.nseindia.com/content/indices/ind_nifty200list.csv",
    "Nifty 500": "https://archives.nseindia.com/content/indices/ind_nifty500list.csv",
    "Full NSE Cash Segment (slow, 1500+ stocks)": "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv",
}


# =============================================================================
# NSE UNIVERSE FETCH
# =============================================================================
@st.cache_data(show_spinner=False, ttl=60 * 60 * 6)
def get_universe(choice):
    session = requests.Session()
    session.headers.update(NSE_HEADERS)
    try:
        session.get("https://www.nseindia.com", timeout=8)
        resp = session.get(INDEX_URLS[choice], timeout=15)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
        col = "Symbol" if "Symbol" in df.columns else "SYMBOL"
        symbols = df[col].astype(str).str.strip().tolist()
        if "SERIES" in df.columns:
            symbols = df.loc[df["SERIES"].str.strip() == "EQ", col].astype(str).str.strip().tolist()
        return symbols
    except Exception as e:
        st.error(f"NSE se list download nahi ho payi ({e}). Thodi der baad try karo.")
        return []


# =============================================================================
# TECHNICAL INDICATORS
# =============================================================================
def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


def sma(series, period):
    return series.rolling(period).mean()


def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(series, fast=12, slow=26, signal=9):
    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def bollinger(series, period=20, std_mult=2):
    ma = series.rolling(period).mean()
    std = series.rolling(period).std()
    upper = ma + std_mult * std
    lower = ma - std_mult * std
    width_pct = (upper - lower) / ma * 100
    return upper, lower, width_pct


def atr(df, period=14):
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def adx(df, period=14):
    high, low, close = df["high"], df["low"], df["close"]
    plus_dm = high.diff()
    minus_dm = low.diff().abs()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
    tr = pd.concat([(high - low), (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
    atr_val = tr.rolling(period).mean()
    plus_di = 100 * (plus_dm.rolling(period).mean() / atr_val.replace(0, np.nan))
    minus_di = 100 * (minus_dm.rolling(period).mean() / atr_val.replace(0, np.nan))
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan)) * 100
    adx_val = dx.rolling(period).mean()
    return adx_val, plus_di, minus_di


def stochastic(df, k_period=14, d_period=3):
    lowest_low = df["low"].rolling(k_period).min()
    highest_high = df["high"].rolling(k_period).max()
    k = 100 * (df["close"] - lowest_low) / (highest_high - lowest_low).replace(0, np.nan)
    d = k.rolling(d_period).mean()
    return k, d


def vwap(df):
    typical = (df["high"] + df["low"] + df["close"]) / 3
    vwap_val = (typical * df["volume"]).cumsum() / df["volume"].cumsum()
    return vwap_val


def compute_all_indicators(df):
    df = df.copy()
    df["ema9"] = ema(df["close"], 9)
    df["ema20"] = ema(df["close"], 20)
    df["ema50"] = ema(df["close"], 50)
    df["ema200"] = ema(df["close"], 200)
    df["rsi14"] = rsi(df["close"], 14)
    df["macd_line"], df["macd_signal"], df["macd_hist"] = macd(df["close"])
    df["bb_upper"], df["bb_lower"], df["bb_width_pct"] = bollinger(df["close"])
    df["atr14"] = atr(df, 14)
    df["vol_avg20"] = df["volume"].rolling(20).mean()
    df["adx14"], df["plus_di"], df["minus_di"] = adx(df)
    df["stoch_k"], df["stoch_d"] = stochastic(df)
    df["vwap"] = vwap(df)
    df["sma20"] = sma(df["close"], 20)
    df["sma50"] = sma(df["close"], 50)
    return df


# =============================================================================
# SUPPORT / RESISTANCE & PATTERNS
# =============================================================================
def find_support_resistance(df, lookback=30):
    if len(df) < lookback + 5:
        return None, None
    window = df.iloc[-(lookback + 5):-5]
    resistance = window["high"].max()
    support = window["low"].min()
    return round(float(support), 2), round(float(resistance), 2)


def detect_candlestick_patterns(df):
    if len(df) < 3:
        return []
    c1, c2, c3 = df.iloc[-1], df.iloc[-2], df.iloc[-3]
    patterns = []
    o1, h1, l1, cl1 = c1["open"], c1["high"], c1["low"], c1["close"]
    o2, h2, l2, cl2 = c2["open"], c2["high"], c2["low"], c2["close"]
    body1 = abs(cl1 - o1)
    range1 = h1 - l1
    upper_shadow1 = h1 - max(o1, cl1)
    lower_shadow1 = min(o1, cl1) - l1

    # Hammer
    if lower_shadow1 > 2 * body1 and upper_shadow1 < body1 and cl1 > o1:
        patterns.append("Hammer (bullish reversal)")
    # Shooting Star
    if upper_shadow1 > 2 * body1 and lower_shadow1 < body1 and cl1 < o1:
        patterns.append("Shooting Star (bearish reversal)")
    # Bullish Engulfing
    if cl2 < o2 and cl1 > o1 and o1 < cl2 and cl1 > o2:
        patterns.append("Bullish Engulfing")
    # Bearish Engulfing
    if cl2 > o2 and cl1 < o1 and o1 > cl2 and cl1 < o2:
        patterns.append("Bearish Engulfing")
    # Doji
    if body1 < 0.1 * range1:
        patterns.append("Doji (indecision)")
    return patterns


def detect_divergence(df, indicator="rsi", lookback=20):
    if len(df) < lookback + 5:
        return None
    price = df["close"].iloc[-lookback:]
    ind = df[f"{indicator}14" if indicator == "rsi" else "macd_line"].iloc[-lookback:]
    price_lows = price.iloc[-lookback:-5].min(), price.iloc[-5:].min()
    ind_lows = ind.iloc[-lookback:-5].min(), ind.iloc[-5:].min()
    price_highs = price.iloc[-lookback:-5].max(), price.iloc[-5:].max()
    ind_highs = ind.iloc[-lookback:-5].max(), ind.iloc[-5:].max()

    # Bullish divergence: lower price low, higher indicator low
    if price_lows[1] < price_lows[0] and ind_lows[1] > ind_lows[0]:
        return "Bullish Divergence"
    # Bearish divergence: higher price high, lower indicator high
    if price_highs[1] > price_highs[0] and ind_highs[1] < ind_highs[0]:
        return "Bearish Divergence"
    return None


def gap_analysis(df):
    if len(df) < 2:
        return None
    prev_close = df["close"].iloc[-2]
    curr_open = df["open"].iloc[-1]
    gap_pct = (curr_open - prev_close) / prev_close * 100
    if gap_pct > 2:
        return f"Gap Up +{gap_pct:.1f}%"
    elif gap_pct < -2:
        return f"Gap Down {gap_pct:.1f}%"
    return None


def weekly_trend_ok(df):
    weekly = df.set_index("date").resample("W").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna()
    if len(weekly) < 12:
        return None
    weekly["ema10"] = ema(weekly["close"], 10)
    return bool(weekly["close"].iloc[-1] > weekly["ema10"].iloc[-1])


def monthly_trend_ok(df):
    monthly = df.set_index("date").resample("ME").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna()
    if len(monthly) < 6:
        return None
    monthly["ema6"] = ema(monthly["close"], 6)
    return bool(monthly["close"].iloc[-1] > monthly["ema6"].iloc[-1])


# =============================================================================
# BREAKOUT & SETUP CLASSIFICATION
# =============================================================================
def breakout_analysis(df, lookback=40, near_pct=1.5, volume_mult=1.5):
    if len(df) < lookback + 5:
        return {"status": "insufficient_data"}
    window = df.iloc[-(lookback + 3):-3]
    resistance = window["high"].max()
    support = window["low"].min()
    last = df.iloc[-1]
    vol_avg = df["vol_avg20"].iloc[-1]
    vol_confirmed = vol_avg and last["volume"] > volume_mult * vol_avg

    if last["close"] > resistance and vol_confirmed:
        status = "breakout_confirmed"
    elif last["close"] > resistance:
        status = "breakout_low_volume"
    elif resistance > 0 and (resistance - last["close"]) / resistance * 100 <= near_pct:
        status = "near_breakout"
    else:
        status = "no_breakout"

    return {
        "status": status,
        "resistance": round(float(resistance), 2),
        "support": round(float(support), 2),
        "last_volume": int(last["volume"]),
        "avg_volume_20d": None if pd.isna(vol_avg) else int(vol_avg),
        "volume_confirmed": bool(vol_confirmed),
    }


def classify_setup(df, breakout, weekly_ok, patterns, divergence, gap):
    last = df.iloc[-1]
    setups = []

    # VCP / Breakout
    if breakout["status"] in ["breakout_confirmed", "breakout_low_volume"]:
        setups.append("Breakout")
    elif breakout["status"] == "near_breakout":
        setups.append("Near Breakout")

    # Pullback to EMA
    if last["close"] > last["ema20"] and last["low"] <= last["ema20"] * 1.02:
        setups.append("Pullback to EMA20")
    if last["close"] > last["ema50"] and last["low"] <= last["ema50"] * 1.02:
        setups.append("Pullback to EMA50")

    # Bounce from support
    if breakout["support"] and last["close"] <= breakout["support"] * 1.03:
        setups.append("Near Support")

    # Gap & Go
    if gap and "Gap Up" in gap:
        setups.append("Gap & Go")

    # RSI Reversal
    if last["rsi14"] < 40 and last["rsi14"] > df["rsi14"].iloc[-3]:
        setups.append("RSI Reversal")

    # Stochastic bounce
    if last["stoch_k"] < 30 and last["stoch_k"] > last["stoch_d"]:
        setups.append("Stochastic Bounce")

    # Divergence
    if divergence == "Bullish Divergence":
        setups.append("Bullish Divergence")

    # VWAP reclaim
    if last["close"] > last["vwap"] and df["close"].iloc[-2] <= df["vwap"].iloc[-2]:
        setups.append("VWAP Reclaim")

    return setups if setups else ["Consolidation"]


# =============================================================================
# SCORING SYSTEM
# =============================================================================
def technical_score(df, weekly_ok, monthly_ok, patterns, divergence, gap, breakout):
    last = df.iloc[-1]
    score, reasons = 0, []

    # 1) Trend structure (15)
    if last["close"] > last["ema20"] > last["ema50"] > last["ema200"]:
        score += 15
        reasons.append("Strong uptrend: Price > EMA20 > EMA50 > EMA200")
    elif last["close"] > last["ema20"] > last["ema50"]:
        score += 12
        reasons.append("Uptrend: Price > EMA20 > EMA50")
    elif last["close"] > last["ema20"]:
        score += 6
        reasons.append("Price > EMA20 only")

    # 2) Multi-timeframe alignment (10)
    if weekly_ok and monthly_ok:
        score += 10
        reasons.append("Daily + Weekly + Monthly all aligned UP")
    elif weekly_ok:
        score += 7
        reasons.append("Daily + Weekly aligned UP")
    elif monthly_ok:
        score += 5
        reasons.append("Monthly aligned UP")

    # 3) ADX Trend Strength (10)
    adx_val = last["adx14"]
    if not pd.isna(adx_val):
        if adx_val > 25:
            score += 10
            reasons.append(f"Strong trend (ADX {adx_val:.1f})")
        elif adx_val > 20:
            score += 5
            reasons.append(f"Trend building (ADX {adx_val:.1f})")

    # 4) RSI (8)
    r = last["rsi14"]
    if 50 <= r <= 65:
        score += 8
        reasons.append(f"RSI sweet spot ({r:.1f})")
    elif 40 <= r < 50:
        score += 6
        reasons.append(f"RSI recovering ({r:.1f})")
    elif 65 < r <= 75:
        score += 4
        reasons.append(f"RSI strong but watch ({r:.1f})")

    # 5) MACD (8)
    recent = df.tail(5)
    crossed = ((recent["macd_line"] > recent["macd_signal"]) &
               (recent["macd_line"].shift(1) <= recent["macd_signal"].shift(1))).any()
    if crossed:
        score += 8
        reasons.append("MACD bullish crossover recently")
    elif last["macd_line"] > last["macd_signal"] and last["macd_hist"] > df["macd_hist"].iloc[-2]:
        score += 5
        reasons.append("MACD bullish & histogram expanding")

    # 6) Stochastic (5)
    if last["stoch_k"] < 30 and last["stoch_k"] > last["stoch_d"]:
        score += 5
        reasons.append("Stochastic oversold bounce")
    elif 30 <= last["stoch_k"] <= 70 and last["stoch_k"] > last["stoch_d"]:
        score += 3
        reasons.append("Stochastic bullish")

    # 7) Bollinger (5)
    if last["close"] > last["bb_upper"] and breakout["volume_confirmed"]:
        score += 5
        reasons.append("Bollinger upper band breakout + volume")
    elif last["bb_width_pct"] < df["bb_width_pct"].tail(60).quantile(0.25):
        score += 3
        reasons.append("Bollinger squeeze setup")

    # 8) Volume (8)
    vol_avg = df["vol_avg20"].iloc[-1]
    if vol_avg and last["volume"] > 2 * vol_avg:
        score += 8
        reasons.append("Volume 2x average — strong conviction")
    elif vol_avg and last["volume"] > 1.5 * vol_avg:
        score += 5
        reasons.append("Volume 1.5x average")

    # 9) Breakout (8)
    if breakout["status"] == "breakout_confirmed":
        score += 8
        reasons.append("Breakout confirmed with volume")
    elif breakout["status"] == "near_breakout":
        score += 5
        reasons.append("Near breakout — watch closely")

    # 10) Candlestick / Divergence / Gap (8)
    if patterns:
        score += 4
        reasons.append(f"Candlestick: {', '.join(patterns)}")
    if divergence == "Bullish Divergence":
        score += 4
        reasons.append("Bullish divergence detected")
    if gap and "Gap Up" in gap:
        score += 3
        reasons.append(gap)

    return round(min(score, 70), 1), reasons


def risk_reward(df, breakout):
    last = df.iloc[-1]
    a = last["atr14"]
    if pd.isna(a) or a <= 0:
        return None
    entry = round(float(last["close"]), 2)
    # Stop below recent swing low or 1.5 ATR, whichever is closer (tighter)
    swing_stop = breakout.get("support", entry * 0.95) if breakout else entry * 0.95
    atr_stop = round(entry - 1.5 * a, 2)
    stop = max(swing_stop, atr_stop) if swing_stop < entry else atr_stop
    stop = round(stop, 2)
    risk = entry - stop
    target = round(entry + 2.5 * risk, 2)  # 1:2.5 R:R
    atr_pct = round(a / entry * 100, 2)
    return {
        "entry": entry,
        "stop_loss": stop,
        "target": target,
        "risk": round(risk, 2),
        "atr_pct": atr_pct,
        "r_r": round((target - entry) / risk, 1) if risk > 0 else 0,
    }


# =============================================================================
# FUNDAMENTALS (Enhanced)
# =============================================================================
def fetch_fundamentals(symbol):
    try:
        info = yf.Ticker(f"{symbol}.NS").info
    except Exception:
        return None
    if not info or info.get("regularMarketPrice") is None:
        return None

    def pct(val):
        return round(val * 100, 2) if val is not None else None

    return {
        # Valuation
        "pe_ratio": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "pb_ratio": info.get("priceToBook"),
        "peg_ratio": info.get("pegRatio"),
        "ev_ebitda": info.get("enterpriseToEbitda"),
        # Profitability
        "roe": pct(info.get("returnOnEquity")),
        "roa": pct(info.get("returnOnAssets")),
        "profit_margin": pct(info.get("profitMargins")),
        "operating_margin": pct(info.get("operatingMargins")),
        # Growth
        "revenue_growth": pct(info.get("revenueGrowth")),
        "earnings_growth": pct(info.get("earningsGrowth")),
        "revenue_qtr_growth": pct(info.get("revenueQuarterlyGrowth")),
        "earnings_qtr_growth": pct(info.get("earningsQuarterlyGrowth")),
        # Financial Health
        "debt_to_equity": info.get("debtToEquity"),
        "current_ratio": info.get("currentRatio"),
        "quick_ratio": info.get("quickRatio"),
        "interest_coverage": info.get("interestCoverage"),
        "total_cash": info.get("totalCash"),
        "total_debt": info.get("totalDebt"),
        "free_cashflow": info.get("freeCashflow"),
        "operating_cashflow": info.get("operatingCashflow"),
        # Market Data
        "beta": info.get("beta"),
        "dividend_yield": pct(info.get("dividendYield")),
        "market_cap": info.get("marketCap"),
        "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
        "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
        "avg_volume_3m": info.get("averageVolume3Month"),
        # Ownership
        "institutional_pct": pct(info.get("heldPercentInstitutions")),
        "insider_pct": pct(info.get("heldPercentInsiders")),
        "short_ratio": info.get("shortRatio"),
        # Analyst
        "analyst_rating": info.get("recommendationMean"),  # 1=strong buy, 5=strong sell
        "num_analysts": info.get("numberOfAnalystOpinions"),
        # Meta
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "website": info.get("website"),
    }


def check_red_flags(fund, last_close):
    flags = []
    if last_close < 20:
        flags.append("⚠️ Penny stock (< ₹20) — manipulation risk")
    if not fund:
        return flags + ["❓ Fundamental data nahi mila — manually verify karo"]

    de = fund.get("debt_to_equity")
    if de is not None and de > 150:
        flags.append(f"🔴 High debt-to-equity ({de:.0f}%)")

    margin = fund.get("profit_margin")
    if margin is not None and margin < 0:
        flags.append("🔴 Negative profit margin")

    roe = fund.get("roe")
    if roe is not None and roe < 5:
        flags.append(f"🟡 Low ROE ({roe:.1f}%)")

    rev = fund.get("revenue_growth")
    if rev is not None and rev < -5:
        flags.append(f"🔴 Revenue declining ({rev:.1f}%)")

    curr = fund.get("current_ratio")
    if curr is not None and curr < 1:
        flags.append("🟡 Current ratio < 1 — liquidity concern")

    fcf = fund.get("free_cashflow")
    if fcf is not None and fcf < 0:
        flags.append("🟡 Negative free cash flow")

    beta = fund.get("beta")
    if beta is not None and beta > 2:
        flags.append(f"🟡 Very high beta ({beta:.2f}) — volatile")

    insider = fund.get("insider_pct")
    if insider is not None and insider < 10:
        flags.append(f"🟡 Low insider holding ({insider:.1f}%)")

    return flags if flags else ["✅ Koi major red flag nahi mila"]


def fundamental_score(fund):
    if not fund:
        return 30, ["Data nahi mila"]
    score = 30
    reasons = []

    # Valuation (max 15)
    pe = fund.get("pe_ratio")
    pb = fund.get("pb_ratio")
    peg = fund.get("peg_ratio")
    if pe is not None and 10 <= pe <= 25:
        score += 8
        reasons.append(f"P/E healthy ({pe:.1f})")
    elif pe is not None and pe < 40:
        score += 4
        reasons.append(f"P/E acceptable ({pe:.1f})")
    if pb is not None and pb <= 3:
        score += 4
        reasons.append(f"P/B reasonable ({pb:.2f})")
    if peg is not None and peg < 1.5:
        score += 3
        reasons.append(f"PEG attractive ({peg:.2f})")

    # Profitability (max 12)
    roe = fund.get("roe")
    margin = fund.get("profit_margin")
    if roe is not None and roe > 15:
        score += 6
        reasons.append(f"ROE strong ({roe:.1f}%)")
    elif roe is not None and roe > 10:
        score += 3
        reasons.append(f"ROE decent ({roe:.1f}%)")
    if margin is not None and margin > 10:
        score += 6
        reasons.append(f"Profit margin healthy ({margin:.1f}%)")

    # Growth (max 10)
    rev = fund.get("revenue_growth")
    earn = fund.get("earnings_qtr_growth")
    if rev is not None and rev > 10:
        score += 5
        reasons.append(f"Revenue growing ({rev:.1f}%)")
    if earn is not None and earn > 10:
        score += 5
        reasons.append(f"Qtr earnings growing ({earn:.1f}%)")

    # Financial Health (max 8)
    de = fund.get("debt_to_equity")
    curr = fund.get("current_ratio")
    fcf = fund.get("free_cashflow")
    if de is not None and de < 60:
        score += 3
        reasons.append("Low debt")
    if curr is not None and curr > 1.5:
        score += 3
        reasons.append("Good liquidity")
    if fcf is not None and fcf > 0:
        score += 2
        reasons.append("Positive FCF")

    return max(0, min(100, round(score, 1))), reasons


# =============================================================================
# SHORT TERM FUNDAMENTALS (QoQ + YoY strict checklist) — Short Term tab only
# =============================================================================
# ⚠️ IMPORTANT LIMITATION (padh lo):
# Promoter holding / FII holding / DII holding ka TREND (intact ya badhta hua)
# yfinance ya kisi free NSE data source se reliably nahi milta — sirf current
# snapshot milta hai, history nahi. Isliye ye teeno checks "Manual Check
# Needed" ke roop me dikhaye jaate hain (score me count nahi hote) — inhe
# screener.in ya NSE shareholding pattern filing se khud verify karo.
# "Industry PE" ka bhi koi single official free API nahi hai — is tool me
# hum scan-universe ke same-sector stocks ka average P/E proxy ke roop me
# use karte hain (real "industry PE" se thoda different ho sakta hai).

def _series_val(df, *row_names):
    """Kisi financial statement (income stmt/balance sheet/cashflow) me se
    ek row Series nikaalta hai. yfinance me columns latest -> oldest order
    me hote hain (index 0 = sabse latest period)."""
    if df is None or df.empty:
        return None
    for n in row_names:
        if n in df.index:
            s = df.loc[n].dropna()
            if len(s):
                return s
    return None


def _latest(series, idx=0):
    if series is None or len(series) <= idx or pd.isna(series.iloc[idx]):
        return None
    return float(series.iloc[idx])


def _growth_pct(series, a=0, b=1):
    """series index 0 = sabse latest period. a period ki b period ke mukable growth (%)."""
    if series is None or len(series) <= max(a, b):
        return None
    va, vb = series.iloc[a], series.iloc[b]
    if pd.isna(va) or pd.isna(vb) or vb == 0:
        return None
    return round((va - vb) / abs(vb) * 100, 2)


def fetch_short_term_financials(symbol):
    """Quarterly + Annual financial statements yfinance se fetch karta hai
    taaki QoQ/YoY fundamental checklist compute ho sake."""
    try:
        tk = yf.Ticker(f"{symbol}.NS")
        data = {
            "qf": tk.quarterly_financials,
            "qcf": tk.quarterly_cashflow,
            "qbs": tk.quarterly_balance_sheet,
            "af": tk.financials,
            "acf": tk.cashflow,
            "abs": tk.balance_sheet,
            "info": tk.info,
        }
    except Exception:
        return None
    if data["qf"] is None or data["qf"].empty:
        return None
    return data


def _opm(op_income_series, sales_series, idx=0):
    oi, sl = _latest(op_income_series, idx), _latest(sales_series, idx)
    if oi is None or sl is None or sl == 0:
        return None
    return round(oi / sl * 100, 2)


def short_term_fundamental_checklist(symbol, fin, sector_avg_pe=None):
    """
    User ke diye gaye QoQ + YoY fundamental checklist evaluate karta hai.
    Returns: (score 0-100, reasons list, checks dict)

    NOTE: Promoter/FII/DII holding checks are NOT included here — free data
    sources don't reliably expose their historical trend, so rather than show
    an unscored "manual check" placeholder in the app, they're left out of
    the scan entirely. Verify those three manually on screener.in / NSE
    shareholding pattern filings if needed.
    """
    checks = {"qoq": {}, "yoy": {}}

    if not fin:
        return 20, ["❓ Financial statement data nahi mila — manually verify karo"], checks

    qf, qcf, qbs = fin["qf"], fin["qcf"], fin["qbs"]
    af, acf, abs_ = fin["af"], fin["acf"], fin["abs"]
    info = fin.get("info") or {}

    # ---- QoQ (quarterly) source rows ----
    sales_q = _series_val(qf, "Total Revenue", "Operating Revenue")
    ebitda_q = _series_val(qf, "EBITDA")
    pat_q = _series_val(qf, "Net Income", "Net Income Common Stockholders")
    pbt_q = _series_val(qf, "Pretax Income")
    eps_q = _series_val(qf, "Basic EPS", "Diluted EPS")
    ocf_q = _series_val(qcf, "Operating Cash Flow", "Cash Flow From Continuing Operating Activities")
    op_income_q = _series_val(qf, "Operating Income")
    debt_q = _series_val(qbs, "Total Debt")

    qoq_growth = _growth_pct(sales_q)
    checks["qoq"]["Sales growth positive (QoQ)"] = None if qoq_growth is None else qoq_growth > 0
    v = _latest(ebitda_q); checks["qoq"]["EBITDA positive"] = None if v is None else v > 0
    v = _latest(pat_q); checks["qoq"]["PAT positive"] = None if v is None else v > 0
    v = _latest(pbt_q); checks["qoq"]["PBT positive"] = None if v is None else v > 0
    v = _latest(eps_q); checks["qoq"]["EPS positive"] = None if v is None else v > 0
    v = _latest(ocf_q); checks["qoq"]["CASH (OCF) positive"] = None if v is None else v > 0
    opm_q0 = _opm(op_income_q, sales_q, 0)
    checks["qoq"]["OPM positive"] = None if opm_q0 is None else opm_q0 > 0
    debt_now, debt_prev = _latest(debt_q, 0), _latest(debt_q, 1)
    checks["qoq"]["Loan kam ya nahi badha"] = (
        None if (debt_now is None or debt_prev is None) else debt_now <= debt_prev
    )

    # ---- YoY (annual) source rows ----
    sales_a = _series_val(af, "Total Revenue", "Operating Revenue")
    ebitda_a = _series_val(af, "EBITDA")
    pat_a = _series_val(af, "Net Income", "Net Income Common Stockholders")
    pbt_a = _series_val(af, "Pretax Income")
    eps_a = _series_val(af, "Basic EPS", "Diluted EPS")
    ocf_a = _series_val(acf, "Operating Cash Flow", "Cash Flow From Continuing Operating Activities")
    op_income_a = _series_val(af, "Operating Income")
    debt_a = _series_val(abs_, "Total Debt")

    yoy_growth = _growth_pct(sales_a)
    checks["yoy"]["Sales growth positive (YoY)"] = None if yoy_growth is None else yoy_growth > 0
    v = _latest(ebitda_a); checks["yoy"]["EBITDA positive"] = None if v is None else v > 0
    v = _latest(pat_a); checks["yoy"]["PAT positive"] = None if v is None else v > 0
    v = _latest(pbt_a); checks["yoy"]["PBT positive"] = None if v is None else v > 0
    v = _latest(eps_a); checks["yoy"]["EPS positive"] = None if v is None else v > 0
    v = _latest(ocf_a); checks["yoy"]["CASH (OCF) positive"] = None if v is None else v > 0
    opm_a0 = _opm(op_income_a, sales_a, 0)
    checks["yoy"]["OPM positive"] = None if opm_a0 is None else opm_a0 > 0
    debt_a_now, debt_a_prev = _latest(debt_a, 0), _latest(debt_a, 1)
    checks["yoy"]["Loan kam ya nahi badha"] = (
        None if (debt_a_now is None or debt_a_prev is None) else debt_a_now <= debt_a_prev
    )

    roe = info.get("returnOnEquity")
    roe_pct = round(roe * 100, 1) if roe is not None else None
    checks["yoy"]["ROE > 20%"] = None if roe_pct is None else roe_pct > 20

    # ROCE approx = EBIT / (Total Assets - Current Liabilities)
    roce_pct = None
    try:
        ebit = _latest(_series_val(af, "EBIT", "Operating Income"))
        total_assets = _latest(_series_val(abs_, "Total Assets"))
        curr_liab = _latest(_series_val(abs_, "Current Liabilities", "Total Current Liabilities"))
        if ebit is not None and total_assets is not None and curr_liab is not None:
            cap_employed = total_assets - curr_liab
            if cap_employed:
                roce_pct = round(ebit / cap_employed * 100, 1)
    except Exception:
        roce_pct = None
    checks["yoy"]["ROCE > 20%"] = None if roce_pct is None else roce_pct > 20

    pe = info.get("trailingPE")
    pe_label = f"PE < Industry PE ({sector_avg_pe if sector_avg_pe else 'N/A'})"
    pe_check = None
    if pe is not None and sector_avg_pe:
        pe_check = pe < sector_avg_pe
    checks["yoy"][pe_label] = pe_check

    # ---- Scoring: % of checks passed among checks jinke liye data mila ----
    all_vals = list(checks["qoq"].values()) + list(checks["yoy"].values())
    scored_vals = [v for v in all_vals if v is not None]
    pass_pct = (sum(1 for v in scored_vals if v) / len(scored_vals) * 100) if scored_vals else 30

    reasons = []
    for k, v in checks["qoq"].items():
        reasons.append(f"{'✅' if v else ('❌' if v is False else '❓')} QoQ: {k}" + ("" if v is not None else " — data nahi mila"))
    for k, v in checks["yoy"].items():
        reasons.append(f"{'✅' if v else ('❌' if v is False else '❓')} YoY: {k}" + ("" if v is not None else " — data nahi mila"))

    return round(pass_pct, 1), reasons, checks


# =============================================================================
# MARKET CONTEXT & RELATIVE STRENGTH
# =============================================================================
@st.cache_data(show_spinner=False, ttl=60 * 30)
def get_market_context():
    try:
        nifty = yf.Ticker("^NSEI").history(period="6mo").reset_index()
        nifty.columns = [c.lower() for c in nifty.columns]
        nifty["ema20"] = ema(nifty["close"], 20)
        nifty["ema50"] = ema(nifty["close"], 50)
        last = nifty.iloc[-1]
        if last["close"] > last["ema20"] > last["ema50"]:
            trend = "Bullish 🟢"
            note = "Nifty uptrend me — swing longs ke liye supportive"
        elif last["close"] < last["ema20"] < last["ema50"]:
            trend = "Bearish 🔴"
            note = "Nifty downtrend me — caution, short side ya cash preferable"
        else:
            trend = "Neutral/Choppy 🟡"
            note = "Mixed market — stock-specific selection zyada important"
        return trend, note, nifty
    except Exception:
        return "Unknown", "Market context fetch nahi ho paya", None


def relative_strength(stock_close, benchmark_close, period=60):
    """Stock vs Nifty RS ratio — stock ne nifty se kitna out/under-perform kiya."""
    if len(stock_close) < period or len(benchmark_close) < period:
        return None
    stock_ret = (stock_close.iloc[-1] / stock_close.iloc[-period] - 1) * 100
    bench_ret = (benchmark_close.iloc[-1] / benchmark_close.iloc[-period] - 1) * 100
    rs = round(stock_ret - bench_ret, 2)
    return rs, stock_ret, bench_ret


# =============================================================================
# PLOTLY CHART
# =============================================================================
def generate_chart(df, symbol, breakout, rr):
    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.55, 0.15, 0.15, 0.15],
        subplot_titles=(f"{symbol} — Price Action", "Volume", "RSI", "MACD")
    )

    # Candlestick
    fig.add_trace(go.Candlestick(
        x=df["date"], open=df["open"], high=df["high"],
        low=df["low"], close=df["close"], name="Price"
    ), row=1, col=1)

    # EMAs
    fig.add_trace(go.Scatter(x=df["date"], y=df["ema9"], line=dict(color="orange", width=1), name="EMA9"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["date"], y=df["ema20"], line=dict(color="blue", width=1.5), name="EMA20"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["date"], y=df["ema50"], line=dict(color="purple", width=1.5), name="EMA50"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["date"], y=df["vwap"], line=dict(color="gray", width=1, dash="dot"), name="VWAP"), row=1, col=1)

    # Bollinger
    fig.add_trace(go.Scatter(x=df["date"], y=df["bb_upper"], line=dict(color="rgba(0,128,0,0.3)"), name="BB Upper"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["date"], y=df["bb_lower"], line=dict(color="rgba(0,128,0,0.3)"), name="BB Lower"), row=1, col=1)

    # Support/Resistance
    if breakout.get("resistance"):
        fig.add_hline(y=breakout["resistance"], line_dash="dash", line_color="red", annotation_text="Resistance", row=1, col=1)
    if breakout.get("support"):
        fig.add_hline(y=breakout["support"], line_dash="dash", line_color="green", annotation_text="Support", row=1, col=1)

    # RR levels
    if rr:
        fig.add_hline(y=rr["entry"], line_dash="dot", line_color="black", annotation_text="Entry", row=1, col=1)
        fig.add_hline(y=rr["stop_loss"], line_dash="dot", line_color="red", annotation_text="SL", row=1, col=1)
        fig.add_hline(y=rr["target"], line_dash="dot", line_color="green", annotation_text="Target", row=1, col=1)

    # Volume
    colors = ["green" if df["close"].iloc[i] >= df["open"].iloc[i] else "red" for i in range(len(df))]
    fig.add_trace(go.Bar(x=df["date"], y=df["volume"], marker_color=colors, name="Volume"), row=2, col=1)
    fig.add_trace(go.Scatter(x=df["date"], y=df["vol_avg20"], line=dict(color="black", width=1), name="Vol MA20"), row=2, col=1)

    # RSI
    fig.add_trace(go.Scatter(x=df["date"], y=df["rsi14"], line=dict(color="blue"), name="RSI"), row=3, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)

    # MACD
    fig.add_trace(go.Scatter(x=df["date"], y=df["macd_line"], line=dict(color="blue"), name="MACD"), row=4, col=1)
    fig.add_trace(go.Scatter(x=df["date"], y=df["macd_signal"], line=dict(color="red"), name="Signal"), row=4, col=1)
    macd_colors = ["green" if df["macd_hist"].iloc[i] >= 0 else "red" for i in range(len(df))]
    fig.add_trace(go.Bar(x=df["date"], y=df["macd_hist"], marker_color=macd_colors, name="Histogram"), row=4, col=1)

    fig.update_layout(
        height=900, template="plotly_white",
        xaxis_rangeslider_visible=False,
        showlegend=False,
        margin=dict(l=40, r=40, t=60, b=40)
    )
    return fig


# =============================================================================
# STAGE 1: BATCH TECHNICAL SCAN
# =============================================================================
def batch_technical_scan(symbols, progress_bar, min_price=20, min_avg_volume=50000, batch_size=50, nifty_df=None):
    passed = []
    total_batches = (len(symbols) + batch_size - 1) // batch_size

    for b in range(total_batches):
        chunk = symbols[b * batch_size:(b + 1) * batch_size]
        tickers_str = " ".join(f"{s}.NS" for s in chunk)
        try:
            data = yf.download(tickers_str, period="9mo", interval="1d",
                             group_by="ticker", threads=True, progress=False, auto_adjust=True)
        except Exception:
            progress_bar.progress((b + 1) / total_batches)
            continue

        for sym in chunk:
            try:
                col_key = f"{sym}.NS"
                sub = data[col_key] if len(chunk) > 1 else data
                sub = sub.dropna().reset_index()
                sub.columns = [str(c).lower() for c in sub.columns]
                if "close" not in sub.columns or len(sub) < 60:
                    continue

                last_close = sub["close"].iloc[-1]
                avg_vol = sub["volume"].tail(20).mean()
                if last_close < min_price or avg_vol < min_avg_volume:
                    continue

                sub = compute_all_indicators(sub)
                weekly_ok = weekly_trend_ok(sub)
                monthly_ok = monthly_trend_ok(sub)
                support, resistance = find_support_resistance(sub)
                patterns = detect_candlestick_patterns(sub)
                divergence = detect_divergence(sub, "rsi")
                gap = gap_analysis(sub)
                breakout = breakout_analysis(sub)
                breakout["support"] = support
                breakout["resistance"] = resistance

                tscore, treasons = technical_score(sub, weekly_ok, monthly_ok, patterns, divergence, gap, breakout)
                rr = risk_reward(sub, breakout)
                setups = classify_setup(sub, breakout, weekly_ok, patterns, divergence, gap)

                # Relative strength vs Nifty
                rs_data = None
                if nifty_df is not None and len(nifty_df) >= 60:
                    rs_data = relative_strength(sub["close"], nifty_df["close"])

                passed.append({
                    "symbol": sym,
                    "df_last_close": round(float(last_close), 2),
                    "technical_score": tscore,
                    "technical_reasons": treasons,
                    "breakout": breakout,
                    "risk_reward": rr,
                    "rsi14": round(float(sub["rsi14"].iloc[-1]), 1),
                    "adx14": round(float(sub["adx14"].iloc[-1]), 1) if not pd.isna(sub["adx14"].iloc[-1]) else None,
                    "weekly_ok": weekly_ok,
                    "monthly_ok": monthly_ok,
                    "patterns": patterns,
                    "divergence": divergence,
                    "gap": gap,
                    "setups": setups,
                    "relative_strength": rs_data,
                    "raw_df": sub,
                })
            except Exception:
                continue
        progress_bar.progress((b + 1) / total_batches)

    return passed


# =============================================================================
# PDF REPORT GENERATOR (mirrors the on-screen card layout, per stock)
# =============================================================================
STATUS_MAP = {
    "breakout_confirmed": "✅ Breakout CONFIRMED",
    "near_breakout": "🟡 Near Breakout",
    "breakout_low_volume": "🟠 Breakout (weak volume)",
    "no_breakout": "⚪ No breakout",
    "insufficient_data": "❓ Data kam",
}


def _pdf_styles():
    styles = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("TitleX", parent=styles["Title"], fontSize=18, spaceAfter=4),
        "meta": ParagraphStyle("Meta", parent=styles["Normal"], fontSize=9, textColor=colors.grey),
        "h2": ParagraphStyle("H2", parent=styles["Heading2"], fontSize=14,
                              textColor=colors.HexColor("#0d47a1"), spaceBefore=4, spaceAfter=4),
        "body": ParagraphStyle("BodyX", parent=styles["Normal"], fontSize=9.5, leading=13),
        "small": ParagraphStyle("SmallX", parent=styles["Normal"], fontSize=8.5, leading=12,
                                 textColor=colors.HexColor("#333333")),
        "warn": ParagraphStyle("WarnX", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#b00020")),
    }


def _pdf_check_line(label, value):
    """Ek checklist item ko reportlab-safe colored line banata hai.
    Emoji (✅/❌/❓) reportlab ke default font me black box ban jaate hain,
    isliye color + text label use karte hain: green=PASS, red=FAIL, grey=N/A."""
    if value is True:
        return f'<font color="#1b7a1b"><b>PASS</b></font> — {label}'
    elif value is False:
        return f'<font color="#c0392b"><b>FAIL</b></font> — {label}'
    else:
        return f'<font color="#888888"><b>N/A</b></font> — {label} (data nahi mila)'


def _score_table(r):
    data = [
        ["Composite", "Technical", "Fundamental", "Context"],
        [
            f"{r.get('composite_score', '-')}/100",
            r.get("technical_score", "-"),
            r.get("fundamental_score", "-"),
            r.get("context_score", "-"),
        ],
    ]
    t = Table(data, colWidths=[42 * mm, 42 * mm, 42 * mm, 42 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e3f2fd")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bbbbbb")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
    ]))
    return t


def _metrics_table(r):
    data = [
        ["Last Close", "RSI", "ADX", "Weekly", "Monthly"],
        [
            f"₹{r.get('df_last_close')}",
            r.get("rsi14"),
            r.get("adx14") or "N/A",
            "✅" if r.get("weekly_ok") else "❌",
            "✅" if r.get("monthly_ok") else "❌",
        ],
    ]
    t = Table(data, colWidths=[34 * mm, 34 * mm, 34 * mm, 34 * mm, 34 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bbbbbb")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    return t


def build_stock_pdf_elements(r, rank, styles, include_chart=True):
    """Same info as the on-screen card, in PDF flowable form."""
    els = []
    fund = r.get("fundamentals") or {}
    sector = fund.get("sector") or ""
    els.append(Paragraph(f"#{rank} · {r['symbol']}  <font size=9 color='grey'>{sector}</font>", styles["h2"]))

    els.append(_score_table(r))
    els.append(Spacer(1, 6))

    if r.get("setups"):
        els.append(Paragraph(f"<b>Setup:</b> {', '.join(r['setups'])}", styles["body"]))
        els.append(Spacer(1, 4))

    els.append(_metrics_table(r))
    els.append(Spacer(1, 6))

    bt = r.get("breakout", {}) or {}
    els.append(Paragraph(
        f"<b>Breakout:</b> {STATUS_MAP.get(bt.get('status'), bt.get('status'))} | "
        f"Resistance: ₹{bt.get('resistance')} | Support: ₹{bt.get('support')}", styles["body"]))

    rr = r.get("risk_reward")
    if rr:
        els.append(Paragraph(
            f"<b>Risk-Reward:</b> Entry ₹{rr['entry']} | SL ₹{rr['stop_loss']} | "
            f"Target ₹{rr['target']} | R:R 1:{rr['r_r']} | ATR: {rr['atr_pct']}%", styles["body"]))

    if r.get("relative_strength"):
        rs, sret, bret = r["relative_strength"]
        els.append(Paragraph(
            f"<b>vs Nifty (60d):</b> {rs:+.1f}% (Stock: {sret:+.1f}% | Nifty: {bret:+.1f}%)", styles["body"]))

    els.append(Spacer(1, 6))

    # Technical reasons
    els.append(Paragraph("<b>📊 Technical Reasons</b>", styles["body"]))
    for reason in r.get("technical_reasons", []):
        els.append(Paragraph(f"• {reason}", styles["small"]))
    if r.get("patterns"):
        els.append(Paragraph(f"• Patterns: {', '.join(r['patterns'])}", styles["small"]))
    if r.get("divergence"):
        els.append(Paragraph(f"• Divergence: {r['divergence']}", styles["small"]))
    if r.get("gap"):
        els.append(Paragraph(f"• Gap: {r['gap']}", styles["small"]))
    els.append(Spacer(1, 6))

    # Fundamentals
    els.append(Paragraph("<b>🏛️ Fundamentals</b>", styles["body"]))
    if fund:
        fund_lines = [
            f"P/E: {fund.get('pe_ratio')} | Forward P/E: {fund.get('forward_pe')} | "
            f"P/B: {fund.get('pb_ratio')} | PEG: {fund.get('peg_ratio')}",
            f"ROE: {fund.get('roe')}% | ROA: {fund.get('roa')}% | "
            f"Margin: {fund.get('profit_margin')}% | Op Margin: {fund.get('operating_margin')}%",
            f"D/E: {fund.get('debt_to_equity')} | Current Ratio: {fund.get('current_ratio')} | "
            f"Beta: {fund.get('beta')} | Div Yield: {fund.get('dividend_yield')}%",
            f"Growth: Revenue {fund.get('revenue_growth')}% | Qtr Earnings {fund.get('earnings_qtr_growth')}%",
            f"Ownership: Institutions {fund.get('institutional_pct')}% | Insiders {fund.get('insider_pct')}%",
            f"Analyst Rating: {fund.get('analyst_rating')}/5 ({fund.get('num_analysts')} analysts)",
            f"52W Range: ₹{fund.get('fifty_two_week_low')} - ₹{fund.get('fifty_two_week_high')}",
        ]
        for line in fund_lines:
            els.append(Paragraph(line, styles["small"]))

        stchecks = r.get("st_checks")
        has_st_data = stchecks and (stchecks.get("qoq") or stchecks.get("yoy"))
        if has_st_data:
            # Short Term tab result — render QoQ/YoY checklist with color, no emoji
            els.append(Spacer(1, 4))
            els.append(Paragraph("<b>Quarter on Quarter (QoQ)</b>", styles["small"]))
            for k, v in stchecks.get("qoq", {}).items():
                els.append(Paragraph(_pdf_check_line(k, v), styles["small"]))
            els.append(Paragraph("<b>Year on Year (YoY)</b>", styles["small"]))
            for k, v in stchecks.get("yoy", {}).items():
                els.append(Paragraph(_pdf_check_line(k, v), styles["small"]))
        elif r.get("fundamental_reasons"):
            els.append(Paragraph("Score reasons: " + "; ".join(r["fundamental_reasons"]), styles["small"]))
    else:
        els.append(Paragraph("Fundamental data nahi mila.", styles["small"]))
    els.append(Spacer(1, 6))

    # Red flags
    els.append(Paragraph("<b>🚩 Red Flags</b>", styles["body"]))
    for flag in r.get("red_flags", []):
        els.append(Paragraph(flag, styles["small"]))
    els.append(Spacer(1, 8))

    # Chart
    if include_chart and r.get("raw_df") is not None:
        try:
            fig = generate_chart(r["raw_df"], r["symbol"], bt, rr)
            img_bytes = fig.to_image(format="png", width=1000, height=750, scale=1.4)
            els.append(RLImage(io.BytesIO(img_bytes), width=170 * mm, height=127 * mm))
        except Exception:
            els.append(Paragraph("(Chart PDF me render nahi ho paya)", styles["small"]))

    return els


def generate_pdf_report(results, market_status, market_note, mode_label="Auto Scan", include_charts=True):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=14 * mm, bottomMargin=14 * mm, leftMargin=14 * mm, rightMargin=14 * mm,
    )
    styles = _pdf_styles()
    elements = []

    elements.append(Paragraph("📈 Swing Trade Screener Pro — Report", styles["title"]))
    elements.append(Paragraph(f"Generated: {datetime.now().strftime('%d %b %Y, %H:%M')} | Mode: {mode_label}",
                               styles["meta"]))
    elements.append(Paragraph(f"Market Context (Nifty): {market_status} — {market_note}", styles["meta"]))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph("📈 Stocks With Laxman 📈.",
                               styles["warn"]))
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", color=colors.HexColor("#cccccc")))
    elements.append(Spacer(1, 10))

    for rank, r in enumerate(results, start=1):
        elements.extend(build_stock_pdf_elements(r, rank, styles, include_chart=include_charts))
        if rank != len(results):
            elements.append(PageBreak())

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


# =============================================================================
# UI
# =============================================================================
st.title("📈 Swing Trade Screener Pro")
st.warning("📈 Stocks With Laxman 📈.")

market_status, market_note, nifty_df = get_market_context()
st.info(f"**Market Context (Nifty):** {market_status} — {market_note}")

# Session state init — results persist across reruns (e.g. when the position
# sizing widgets inside an expander are touched) until "Clear Results" is clicked.
if "auto_scan_result" not in st.session_state:
    st.session_state.auto_scan_result = None
if "custom_scan_result" not in st.session_state:
    st.session_state.custom_scan_result = None


tab1, tab2 = st.tabs(["📈 Swing Trade", "⚡ Short Term"])

with tab1:
    mode = st.radio("Mode choose karo", ["🔍 Auto scan (NSE se khud dhundo)", "📋 Apni list paste karo"], horizontal=True)

    if mode.startswith("🔍"):
        universe_choice = st.selectbox("Universe", list(INDEX_URLS.keys()), index=1)
        c1, c2, c3, c4 = st.columns(4)
        min_price = c1.number_input("Min price (₹)", value=20, min_value=1)
        min_volume = c2.number_input("Min avg volume", value=50000, min_value=0, step=10000)
        top_n = c3.slider("Top candidates", 1, 15, 5)
        min_tech_score = c4.slider("Min Technical Score", 0, 70, 25)

        sector_filter = st.multiselect("Sector filter (optional)", [
            "Technology", "Financial Services", "Consumer Cyclical", "Healthcare",
            "Industrials", "Consumer Defensive", "Energy", "Basic Materials",
            "Real Estate", "Communication Services", "Utilities"
        ])

        btn_col1, btn_col2 = st.columns([1, 1])
        scan_clicked = btn_col1.button("🚀 Scan Shuru Karo", type="primary")
        clear_clicked = btn_col2.button("🗑️ Clear Results", disabled=st.session_state.auto_scan_result is None)

        if clear_clicked:
            st.session_state.auto_scan_result = None
            st.rerun()

        if scan_clicked:
            symbols = get_universe(universe_choice)
            if not symbols:
                st.stop()

            st.write(f"**{len(symbols)} stocks** scan honge. Bade universe me time lagega ⏳")
            progress = st.progress(0.0, text="Stage 1: Technical scan chal raha hai...")
            stage1 = batch_technical_scan(symbols, progress, min_price=min_price, min_avg_volume=min_volume, nifty_df=nifty_df)
            progress.empty()

            # Filter by minimum technical score
            stage1 = [r for r in stage1 if r["technical_score"] >= min_tech_score]

            if not stage1:
                st.error("Koi stock minimum technical score pass nahi kar paya. Filters loosen karo.")
                st.stop()

            stage1_sorted = sorted(stage1, key=lambda r: r["technical_score"], reverse=True)
            shortlist = stage1_sorted[:max(25, top_n * 5)]

            st.write(f"Stage 1 se **{len(shortlist)}** technically strong stocks shortlist hue. Ab fundamentals check ho raha hai...")
            progress2 = st.progress(0.0, text="Stage 2: Fundamentals check...")
            final_results = []
            for i, r in enumerate(shortlist):
                fund = fetch_fundamentals(r["symbol"])
                fscore, freasons = fundamental_score(fund)
                red_flags = check_red_flags(fund, r["df_last_close"])

                # Context score
                cscore = 0
                if r["relative_strength"]:
                    rs, _, _ = r["relative_strength"]
                    if rs > 5:
                        cscore += 5
                    elif rs > 0:
                        cscore += 3

                composite = round(r["technical_score"] * 0.60 + fscore * 0.30 + cscore * 0.10, 1)

                r.update({
                    "fundamentals": fund,
                    "fundamental_score": fscore,
                    "fundamental_reasons": freasons,
                    "red_flags": red_flags,
                    "composite_score": composite,
                    "context_score": cscore,
                })
                final_results.append(r)
                progress2.progress((i + 1) / len(shortlist))
            progress2.empty()

            # Sector filter
            if sector_filter:
                final_results = [r for r in final_results if r["fundamentals"] and r["fundamentals"].get("sector") in sector_filter]

            top = sorted(final_results, key=lambda r: r["composite_score"], reverse=True)[:top_n]

            # Store in session_state so results survive reruns until Clear is clicked
            st.session_state.auto_scan_result = {
                "top": top,
                "market_status": market_status,
                "market_note": market_note,
            }

        # Render from session_state (persists across reruns e.g. position-sizing widget interactions)
        saved = st.session_state.auto_scan_result
        if saved:
            top = saved["top"]

            if top:
                pdf_bytes = generate_pdf_report(top, saved["market_status"], saved["market_note"], mode_label="Auto Scan")
                st.download_button("📥 PDF Report Download karo", pdf_bytes, "swing_screener_report.pdf", "application/pdf")

            st.subheader(f"🏆 Top {len(top)} Swing Trade Candidates")

            for rank, r in enumerate(top, start=1):
                with st.container(border=True):
                    fund = r["fundamentals"] or {}
                    col_main, col_score = st.columns([3, 1])
                    col_main.markdown(f"### #{rank} · {r['symbol']}  <span style='font-size:0.7em;color:gray'>{fund.get('sector','')}</span>", unsafe_allow_html=True)
                    col_score.metric("Composite Score", f"{r['composite_score']}/100")
                    col_score.caption(f"Tech: {r['technical_score']} | Fund: {r['fundamental_score']} | Ctx: {r['context_score']}")

                    # Setup tags
                    setup_html = " ".join([f"<span style='background:#e3f2fd;padding:3px 8px;border-radius:10px;margin-right:5px;font-size:0.8em'>{s}</span>" for s in r["setups"]])
                    st.markdown(f"**Setup:** {setup_html}", unsafe_allow_html=True)

                    c1, c2, c3, c4, c5 = st.columns(5)
                    c1.metric("Last Close", f"₹{r['df_last_close']}")
                    c2.metric("RSI", r["rsi14"])
                    c3.metric("ADX", r["adx14"] or "N/A")
                    c4.metric("Weekly", "✅" if r["weekly_ok"] else "❌")
                    c5.metric("Monthly", "✅" if r["monthly_ok"] else "❌")

                    bt = r["breakout"]
                    st.write(f"**Breakout:** {STATUS_MAP.get(bt['status'], bt['status'])} | Resistance: ₹{bt.get('resistance')} | Support: ₹{bt.get('support')}")

                    rr = r["risk_reward"]
                    if rr:
                        st.write(f"**Risk-Reward:** Entry ₹{rr['entry']} | SL ₹{rr['stop_loss']} | Target ₹{rr['target']} | R:R 1:{rr['r_r']} | ATR: {rr['atr_pct']}%")

                    if r["relative_strength"]:
                        rs, sret, bret = r["relative_strength"]
                        color = "green" if rs > 0 else "red"
                        st.write(f"**vs Nifty (60d):** <span style='color:{color};font-weight:bold'>{rs:+.1f}%</span> (Stock: {sret:+.1f}% | Nifty: {bret:+.1f}%)", unsafe_allow_html=True)

                    # Expanders
                    with st.expander("📊 Technical Reasons"):
                        for reason in r["technical_reasons"]:
                            st.write(f"- {reason}")
                        if r["patterns"]:
                            st.write(f"- **Patterns:** {', '.join(r['patterns'])}")
                        if r["divergence"]:
                            st.write(f"- **Divergence:** {r['divergence']}")
                        if r["gap"]:
                            st.write(f"- **Gap:** {r['gap']}")

                    with st.expander("🏛️ Fundamentals"):
                        if fund:
                            fcols = st.columns(3)
                            fcols[0].write(f"**P/E:** {fund.get('pe_ratio')} | **Forward P/E:** {fund.get('forward_pe')}")
                            fcols[0].write(f"**P/B:** {fund.get('pb_ratio')} | **PEG:** {fund.get('peg_ratio')}")
                            fcols[1].write(f"**ROE:** {fund.get('roe')}% | **ROA:** {fund.get('roa')}%")
                            fcols[1].write(f"**Margin:** {fund.get('profit_margin')}% | **Op Margin:** {fund.get('operating_margin')}%")
                            fcols[2].write(f"**D/E:** {fund.get('debt_to_equity')} | **Current Ratio:** {fund.get('current_ratio')}")
                            fcols[2].write(f"**Beta:** {fund.get('beta')} | **Div Yield:** {fund.get('dividend_yield')}%")
                            st.write(f"**Growth:** Revenue {fund.get('revenue_growth')}% | Qtr Earnings {fund.get('earnings_qtr_growth')}%")
                            st.write(f"**Cash Flow:** FCF ₹{fund.get('free_cashflow')} | OCF ₹{fund.get('operating_cashflow')}")
                            st.write(f"**Ownership:** Institutions {fund.get('institutional_pct')}% | Insiders {fund.get('insider_pct')}%")
                            st.write(f"**Analyst Rating:** {fund.get('analyst_rating')}/5 ({fund.get('num_analysts')} analysts)")
                            st.write(f"**52W Range:** ₹{fund.get('fifty_two_week_low')} - ₹{fund.get('fifty_two_week_high')}")
                            st.write("**Score reasons:**")
                            for freason in r["fundamental_reasons"]:
                                st.write(f"- {freason}")
                        else:
                            st.write("Fundamental data nahi mila.")

                    with st.expander("🚩 Red Flags"):
                        for flag in r["red_flags"]:
                            st.write(flag)

                    with st.expander("📈 Chart"):
                        fig = generate_chart(r["raw_df"], r["symbol"], bt, rr)
                        st.plotly_chart(fig, use_container_width=True, key=f"chart_{r['symbol']}_{rank}")

                    # Position sizing calculator
                    with st.expander("🧮 Position Sizing Calculator"):
                        portfolio = st.number_input(f"Portfolio Size (₹) — {r['symbol']}", min_value=10000, value=500000, step=50000, key=f"port_{r['symbol']}_{rank}")
                        risk_pct = st.slider(f"Risk % per trade — {r['symbol']}", 0.5, 5.0, 1.0, 0.5, key=f"risk_{r['symbol']}_{rank}")
                        if rr:
                            max_risk = portfolio * risk_pct / 100
                            qty = int(max_risk / rr["risk"]) if rr["risk"] > 0 else 0
                            investment = qty * rr["entry"]
                            st.success(f"**Qty:** {qty} shares | **Investment:** ₹{investment:,.0f} | **Max Risk:** ₹{max_risk:,.0f}")

            st.caption("📌 Upcoming results/corporate actions khud check kar lo — ye tool sudden news predict nahi karta.")

    else:
        st.info("Apni list paste karne ke liye niche symbols enter karo (comma separated):")
        custom_input = st.text_area("Symbols", "RELIANCE, TCS, INFY, HDFCBANK")

        btn_col1, btn_col2 = st.columns([1, 1])
        custom_scan_clicked = btn_col1.button("Custom List Scan Karo", type="primary")
        custom_clear_clicked = btn_col2.button("🗑️ Clear Results", key="clear_custom", disabled=st.session_state.custom_scan_result is None)

        if custom_clear_clicked:
            st.session_state.custom_scan_result = None
            st.rerun()

        if custom_scan_clicked:
            custom_symbols = [s.strip().upper() for s in custom_input.split(",") if s.strip()]
            progress = st.progress(0.0, text="Scanning custom list...")
            stage1 = batch_technical_scan(custom_symbols, progress, nifty_df=nifty_df)
            progress.empty()

            if not stage1:
                st.error("Koi stock criteria pass nahi kiya.")
                st.stop()

            shortlist = sorted(stage1, key=lambda r: r["technical_score"], reverse=True)
            for r in shortlist:
                fund = fetch_fundamentals(r["symbol"])
                fscore, freasons = fundamental_score(fund)
                red_flags = check_red_flags(fund, r["df_last_close"])
                composite = round(r["technical_score"] * 0.6 + fscore * 0.3, 1)
                r.update({
                    "fundamentals": fund,
                    "fundamental_score": fscore,
                    "fundamental_reasons": freasons,
                    "red_flags": red_flags,
                    "composite_score": composite,
                    "context_score": 0,
                })

            st.session_state.custom_scan_result = {
                "shortlist": shortlist,
                "market_status": market_status,
                "market_note": market_note,
            }

        saved_custom = st.session_state.custom_scan_result
        if saved_custom:
            shortlist = saved_custom["shortlist"]

            if shortlist:
                pdf_bytes = generate_pdf_report(shortlist, saved_custom["market_status"], saved_custom["market_note"], mode_label="Custom List Scan")
                st.download_button("📥 PDF Report Download karo", pdf_bytes, "swing_screener_report.pdf", "application/pdf", key="pdf_custom")

            for rank, r in enumerate(shortlist, start=1):
                with st.container(border=True):
                    fund = r["fundamentals"] or {}
                    col_main, col_score = st.columns([3, 1])
                    col_main.markdown(f"### #{rank} · {r['symbol']}  <span style='font-size:0.7em;color:gray'>{fund.get('sector','')}</span>", unsafe_allow_html=True)
                    col_score.metric("Composite Score", f"{r['composite_score']}/100")
                    col_score.caption(f"Tech: {r['technical_score']} | Fund: {r['fundamental_score']}")

                    setup_html = " ".join([f"<span style='background:#e3f2fd;padding:3px 8px;border-radius:10px;margin-right:5px;font-size:0.8em'>{s}</span>" for s in r["setups"]])
                    st.markdown(f"**Setup:** {setup_html}", unsafe_allow_html=True)

                    c1, c2, c3 = st.columns(3)
                    c1.metric("Last Close", f"₹{r['df_last_close']}")
                    c2.metric("RSI", r["rsi14"])
                    c3.metric("ADX", r["adx14"] or "N/A")

                    bt = r["breakout"]
                    st.write(f"**Breakout:** {STATUS_MAP.get(bt['status'], bt['status'])} | Resistance: ₹{bt.get('resistance')} | Support: ₹{bt.get('support')}")

                    rr = r["risk_reward"]
                    if rr:
                        st.write(f"**Risk-Reward:** Entry ₹{rr['entry']} | SL ₹{rr['stop_loss']} | Target ₹{rr['target']} | R:R 1:{rr['r_r']} | ATR: {rr['atr_pct']}%")

                    with st.expander("📊 Technical Reasons"):
                        for reason in r["technical_reasons"]:
                            st.write(f"- {reason}")
                        if r["patterns"]:
                            st.write(f"- **Patterns:** {', '.join(r['patterns'])}")
                        if r["divergence"]:
                            st.write(f"- **Divergence:** {r['divergence']}")
                        if r["gap"]:
                            st.write(f"- **Gap:** {r['gap']}")

                    with st.expander("🏛️ Fundamentals"):
                        if fund:
                            fcols = st.columns(3)
                            fcols[0].write(f"**P/E:** {fund.get('pe_ratio')} | **Forward P/E:** {fund.get('forward_pe')}")
                            fcols[0].write(f"**P/B:** {fund.get('pb_ratio')} | **PEG:** {fund.get('peg_ratio')}")
                            fcols[1].write(f"**ROE:** {fund.get('roe')}% | **ROA:** {fund.get('roa')}%")
                            fcols[1].write(f"**Margin:** {fund.get('profit_margin')}% | **Op Margin:** {fund.get('operating_margin')}%")
                            fcols[2].write(f"**D/E:** {fund.get('debt_to_equity')} | **Current Ratio:** {fund.get('current_ratio')}")
                            fcols[2].write(f"**Beta:** {fund.get('beta')} | **Div Yield:** {fund.get('dividend_yield')}%")
                            st.write("**Score reasons:**")
                            for freason in r["fundamental_reasons"]:
                                st.write(f"- {freason}")
                        else:
                            st.write("Fundamental data nahi mila.")

                    with st.expander("🚩 Red Flags"):
                        for flag in r["red_flags"]:
                            st.write(flag)

                    with st.expander("📈 Chart"):
                        fig = generate_chart(r["raw_df"], r["symbol"], bt, rr)
                        st.plotly_chart(fig, use_container_width=True, key=f"chart_custom_{r['symbol']}_{rank}")

                    with st.expander("🧮 Position Sizing Calculator"):
                        portfolio = st.number_input(f"Portfolio Size (₹) — {r['symbol']}", min_value=10000, value=500000, step=50000, key=f"cport_{r['symbol']}_{rank}")
                        risk_pct = st.slider(f"Risk % per trade — {r['symbol']}", 0.5, 5.0, 1.0, 0.5, key=f"crisk_{r['symbol']}_{rank}")
                        if rr:
                            max_risk = portfolio * risk_pct / 100
                            qty = int(max_risk / rr["risk"]) if rr["risk"] > 0 else 0
                            investment = qty * rr["entry"]
                            st.success(f"**Qty:** {qty} shares | **Investment:** ₹{investment:,.0f} | **Max Risk:** ₹{max_risk:,.0f}")

with tab2:
    st.title("⚡ Short Term Screener")
    st.warning("⚠️ Sirf research/screening tool hai — financial advice nahi. Apna risk management khud karo.")
    st.info(f"**Market Context (Nifty):** {market_status} — {market_note}")
    st.caption(
        "Technical scanner Swing Trade tab jaisa hi hai. Fundamentals me QoQ + YoY "
        "checklist add ki gayi hai (Sales/EBITDA/PAT/PBT/EPS/Cash/OPM growth, "
        "Loan trend, ROE, ROCE, PE vs Industry PE — Industry PE sector-avg proxy hai). "
        "⚠️ Promoter/FII/DII holding trend ka reliable free data source na hone ki "
        "wajah se ye 3 checks scan me include nahi kiye gaye hain — inhe screener.in "
        "ya NSE shareholding pattern filing se khud verify kar lena."
    )

    if "short_auto_scan_result" not in st.session_state:
        st.session_state.short_auto_scan_result = None
    if "short_custom_scan_result" not in st.session_state:
        st.session_state.short_custom_scan_result = None

    def _score_short_term_batch(shortlist):
        """Pass 1: fundamentals + financials fetch. Pass 2: sector-avg PE proxy
        ('Industry PE') compute karke final checklist score nikalna."""
        enriched = []
        prog = st.progress(0.0, text="Fundamentals + Financials fetch ho rahe hain...")
        for i, r in enumerate(shortlist):
            fund = fetch_fundamentals(r["symbol"])
            fin = fetch_short_term_financials(r["symbol"])
            enriched.append({"r": r, "fund": fund, "fin": fin})
            prog.progress((i + 1) / len(shortlist))
        prog.empty()

        sector_pes = {}
        for e in enriched:
            f = e["fund"]
            if f and f.get("sector") and f.get("pe_ratio"):
                sector_pes.setdefault(f["sector"], []).append(f["pe_ratio"])
        sector_avg_pe = {sec: round(sum(v) / len(v), 1) for sec, v in sector_pes.items() if len(v) >= 2}

        final_results = []
        for e in enriched:
            r, fund, fin = e["r"], e["fund"], e["fin"]
            sec = fund.get("sector") if fund else None
            avg_pe = sector_avg_pe.get(sec)
            stscore, streasons, stchecks = short_term_fundamental_checklist(r["symbol"], fin, avg_pe)
            red_flags = check_red_flags(fund, r["df_last_close"])
            composite = round(r["technical_score"] * 0.5 + stscore * 0.5, 1)
            r.update({
                "fundamentals": fund,
                "fundamental_score": stscore,
                "fundamental_reasons": streasons,
                "st_checks": stchecks,
                "red_flags": red_flags,
                "composite_score": composite,
                "context_score": 0,
            })
            final_results.append(r)
        return final_results

    def _render_short_term_card(r, rank, key_prefix):
        fund = r["fundamentals"] or {}
        with st.container(border=True):
            col_main, col_score = st.columns([3, 1])
            col_main.markdown(
                f"### #{rank} · {r['symbol']}  <span style='font-size:0.7em;color:gray'>{fund.get('sector','')}</span>",
                unsafe_allow_html=True,
            )
            col_score.metric("Composite Score", f"{r['composite_score']}/100")
            col_score.caption(f"Tech: {r['technical_score']} | Fund Checklist: {r['fundamental_score']}%")

            setup_html = " ".join(
                [f"<span style='background:#fff3e0;padding:3px 8px;border-radius:10px;margin-right:5px;font-size:0.8em'>{s}</span>" for s in r["setups"]]
            )
            st.markdown(f"**Setup:** {setup_html}", unsafe_allow_html=True)

            c1, c2, c3 = st.columns(3)
            c1.metric("Last Close", f"₹{r['df_last_close']}")
            c2.metric("RSI", r["rsi14"])
            c3.metric("ADX", r["adx14"] or "N/A")

            bt = r["breakout"]
            st.write(f"**Breakout:** {STATUS_MAP.get(bt['status'], bt['status'])} | Resistance: ₹{bt.get('resistance')} | Support: ₹{bt.get('support')}")

            rr = r["risk_reward"]
            if rr:
                st.write(f"**Risk-Reward:** Entry ₹{rr['entry']} | SL ₹{rr['stop_loss']} | Target ₹{rr['target']} | R:R 1:{rr['r_r']} | ATR: {rr['atr_pct']}%")

            with st.expander("📊 Technical Reasons"):
                for reason in r["technical_reasons"]:
                    st.write(f"- {reason}")
                if r["patterns"]:
                    st.write(f"- **Patterns:** {', '.join(r['patterns'])}")

            with st.expander("🏛️ Short-Term Fundamental Checklist (QoQ + YoY)", expanded=True):
                stchecks = r.get("st_checks", {"qoq": {}, "yoy": {}})
                colq, coly = st.columns(2)
                colq.markdown("**Quarter on Quarter (QoQ)**")
                for k, v in stchecks.get("qoq", {}).items():
                    icon = "✅" if v else ("❌" if v is False else "❓")
                    colq.write(f"{icon} {k}")
                coly.markdown("**Year on Year (YoY)**")
                for k, v in stchecks.get("yoy", {}).items():
                    icon = "✅" if v else ("❌" if v is False else "❓")
                    coly.write(f"{icon} {k}")

            with st.expander("🚩 Red Flags"):
                for flag in r["red_flags"]:
                    st.write(flag)

            with st.expander("📈 Chart"):
                fig = generate_chart(r["raw_df"], r["symbol"], bt, rr)
                st.plotly_chart(fig, use_container_width=True, key=f"chart_{key_prefix}_{r['symbol']}_{rank}")

            with st.expander("🧮 Position Sizing Calculator"):
                portfolio = st.number_input(f"Portfolio Size (₹) — {r['symbol']}", min_value=10000, value=500000, step=50000, key=f"port_{key_prefix}_{r['symbol']}_{rank}")
                risk_pct = st.slider(f"Risk % per trade — {r['symbol']}", 0.5, 5.0, 1.0, 0.5, key=f"risk_{key_prefix}_{r['symbol']}_{rank}")
                if rr:
                    max_risk = portfolio * risk_pct / 100
                    qty = int(max_risk / rr["risk"]) if rr["risk"] > 0 else 0
                    investment = qty * rr["entry"]
                    st.success(f"**Qty:** {qty} shares | **Investment:** ₹{investment:,.0f} | **Max Risk:** ₹{max_risk:,.0f}")

    short_mode = st.radio(
        "Mode choose karo", ["🔍 Auto scan (NSE se khud dhundo)", "📋 Apni list paste karo"],
        horizontal=True, key="short_mode_radio",
    )

    if short_mode.startswith("🔍"):
        st_universe_choice = st.selectbox("Universe", list(INDEX_URLS.keys()), index=1, key="short_universe")
        sc1, sc2, sc3, sc4 = st.columns(4)
        st_min_price = sc1.number_input("Min price (₹)", value=20, min_value=1, key="short_min_price")
        st_min_volume = sc2.number_input("Min avg volume", value=50000, min_value=0, step=10000, key="short_min_vol")
        st_top_n = sc3.slider("Top candidates", 1, 15, 5, key="short_top_n")
        st_min_tech_score = sc4.slider("Min Technical Score", 0, 70, 25, key="short_min_tech")

        st_min_fund_pct = st.slider(
            "Min Fundamental Checklist Pass %", 0, 100, 60, key="short_min_fund",
            help="QoQ + YoY checklist me kitne % criteria pass hone chahiye (jinke liye data available hai)"
        )

        st_sector_filter = st.multiselect("Sector filter (optional)", [
            "Technology", "Financial Services", "Consumer Cyclical", "Healthcare",
            "Industrials", "Consumer Defensive", "Energy", "Basic Materials",
            "Real Estate", "Communication Services", "Utilities"
        ], key="short_sector_filter")

        sbtn1, sbtn2 = st.columns([1, 1])
        short_scan_clicked = sbtn1.button("🚀 Scan Shuru Karo", type="primary", key="short_scan_btn")
        short_clear_clicked = sbtn2.button("🗑️ Clear Results", key="short_clear_btn", disabled=st.session_state.short_auto_scan_result is None)

        if short_clear_clicked:
            st.session_state.short_auto_scan_result = None
            st.rerun()

        if short_scan_clicked:
            symbols = get_universe(st_universe_choice)
            if not symbols:
                st.stop()

            st.write(f"**{len(symbols)} stocks** scan honge. Bade universe me time lagega ⏳")
            progress = st.progress(0.0, text="Stage 1: Technical scan chal raha hai...")
            stage1 = batch_technical_scan(symbols, progress, min_price=st_min_price, min_avg_volume=st_min_volume, nifty_df=nifty_df)
            progress.empty()

            stage1 = [r for r in stage1 if r["technical_score"] >= st_min_tech_score]
            if not stage1:
                st.error("Koi stock minimum technical score pass nahi kar paya. Filters loosen karo.")
                st.stop()

            stage1_sorted = sorted(stage1, key=lambda r: r["technical_score"], reverse=True)
            shortlist = stage1_sorted[:max(25, st_top_n * 5)]

            st.write(f"Stage 1 se **{len(shortlist)}** technically strong stocks shortlist hue. Ab short-term fundamental checklist check ho raha hai...")
            final_results = _score_short_term_batch(shortlist)

            if st_sector_filter:
                final_results = [r for r in final_results if r["fundamentals"] and r["fundamentals"].get("sector") in st_sector_filter]

            final_results = [r for r in final_results if r["fundamental_score"] >= st_min_fund_pct]

            top = sorted(final_results, key=lambda r: r["composite_score"], reverse=True)[:st_top_n]

            st.session_state.short_auto_scan_result = {
                "top": top,
                "market_status": market_status,
                "market_note": market_note,
            }

        saved = st.session_state.short_auto_scan_result
        if saved:
            top = saved["top"]
            if not top:
                st.error("Koi stock filters pass nahi kar paya. Min Fundamental % ya Min Technical Score kam karo.")
            else:
                pdf_bytes = generate_pdf_report(top, saved["market_status"], saved["market_note"], mode_label="Short Term Scan")
                st.download_button("📥 PDF Report Download karo", pdf_bytes, "short_term_screener_report.pdf", "application/pdf", key="pdf_short_auto")

                st.subheader(f"🏆 Top {len(top)} Short Term Candidates")
                for rank, r in enumerate(top, start=1):
                    _render_short_term_card(r, rank, key_prefix="short_auto")

        st.caption("📌 Upcoming results/corporate actions khud check kar lo — ye tool sudden news predict nahi karta.")

    else:
        st.info("Apni list paste karne ke liye niche symbols enter karo (comma separated):")
        st_custom_input = st.text_area("Symbols", "RELIANCE, TCS, INFY, HDFCBANK", key="short_custom_input")

        st_min_fund_pct_c = st.slider(
            "Min Fundamental Checklist Pass %", 0, 100, 0, key="short_min_fund_custom",
            help="Custom list me default 0 rakha hai taaki tumhare diye stocks filter na ho jaayein"
        )

        cbtn1, cbtn2 = st.columns([1, 1])
        short_custom_scan_clicked = cbtn1.button("Custom List Scan Karo", type="primary", key="short_custom_scan_btn")
        short_custom_clear_clicked = cbtn2.button("🗑️ Clear Results", key="short_clear_custom", disabled=st.session_state.short_custom_scan_result is None)

        if short_custom_clear_clicked:
            st.session_state.short_custom_scan_result = None
            st.rerun()

        if short_custom_scan_clicked:
            custom_symbols = [s.strip().upper() for s in st_custom_input.split(",") if s.strip()]
            progress = st.progress(0.0, text="Scanning custom list...")
            stage1 = batch_technical_scan(custom_symbols, progress, nifty_df=nifty_df)
            progress.empty()

            if not stage1:
                st.error("Koi stock criteria pass nahi kiya.")
                st.stop()

            shortlist = sorted(stage1, key=lambda r: r["technical_score"], reverse=True)
            final_results = _score_short_term_batch(shortlist)
            final_results = [r for r in final_results if r["fundamental_score"] >= st_min_fund_pct_c]

            st.session_state.short_custom_scan_result = {
                "shortlist": final_results,
                "market_status": market_status,
                "market_note": market_note,
            }

        saved_custom = st.session_state.short_custom_scan_result
        if saved_custom:
            shortlist = saved_custom["shortlist"]
            if not shortlist:
                st.error("Koi stock filters pass nahi kar paya.")
            else:
                pdf_bytes = generate_pdf_report(shortlist, saved_custom["market_status"], saved_custom["market_note"], mode_label="Short Term Custom Scan")
                st.download_button("📥 PDF Report Download karo", pdf_bytes, "short_term_screener_report.pdf", "application/pdf", key="pdf_short_custom")

                for rank, r in enumerate(shortlist, start=1):
                    _render_short_term_card(r, rank, key_prefix="short_custom")
