"""
Swing Trade Screener — Auto Scan (No List Needed)
====================================================
List paste karne ki zaroorat nahi. App khud NSE cash segment se stocks
fetch karke, sab criteria check karke top candidates deta hai.

Criteria covered:
  1. Trend & Price Action (daily + weekly alignment, EMA20/50)
  2. Volume confirmation
  3. RSI, MACD crossover, Bollinger Bands
  4. Risk-Reward suggestion (ATR-based stop-loss/target)
  5. Market context (Nifty trend)
  6. Basic fundamentals + red flags
  7. Volatility (ATR%)

Chalane ka tareeka:
    pip install -r requirements.txt
    streamlit run app.py
"""

import numpy as np
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="Swing Trade Screener", layout="wide", page_icon="📈")

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


@st.cache_data(show_spinner=False, ttl=60 * 60 * 6)
def get_universe(choice):
    """NSE se stock symbols ki list laata hai (cookies/session ke saath, NSE bot-protection ke liye)."""
    session = requests.Session()
    session.headers.update(NSE_HEADERS)
    try:
        session.get("https://www.nseindia.com", timeout=8)  # cookies warm-up
        resp = session.get(INDEX_URLS[choice], timeout=15)
        resp.raise_for_status()
        from io import StringIO
        df = pd.read_csv(StringIO(resp.text))
        col = "Symbol" if "Symbol" in df.columns else "SYMBOL"
        symbols = df[col].astype(str).str.strip().tolist()
        if "SERIES" in df.columns:  # full EQUITY_L.csv me sirf EQ series lo (cash segment)
            symbols = df.loc[df["SERIES"].str.strip() == "EQ", col].astype(str).str.strip().tolist()
        return symbols
    except Exception as e:
        st.error(
            f"NSE se list download nahi ho payi ({e}). "
            "NSE ki site kabhi-kabhi script requests block karti hai. "
            "Thodi der baad try karo, ya 'Apni list paste karo' mode use karo."
        )
        return []


# ---------------------------------------------------------------------------
# INDICATORS
# ---------------------------------------------------------------------------
def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


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
    return macd_line, signal_line


def bollinger(series, period=20, std_mult=2):
    sma = series.rolling(period).mean()
    std = series.rolling(period).std()
    upper = sma + std_mult * std
    lower = sma - std_mult * std
    width_pct = (upper - lower) / sma * 100
    return upper, lower, width_pct


def atr(df, period=14):
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def compute_all_indicators(df):
    df = df.copy()
    df["ema20"] = ema(df["close"], 20)
    df["ema50"] = ema(df["close"], 50)
    df["rsi14"] = rsi(df["close"], 14)
    df["macd_line"], df["macd_signal"] = macd(df["close"])
    df["bb_upper"], df["bb_lower"], df["bb_width_pct"] = bollinger(df["close"])
    df["atr14"] = atr(df, 14)
    df["vol_avg20"] = df["volume"].rolling(20).mean()
    return df


def weekly_trend_ok(df):
    """Weekly timeframe pe bhi uptrend confirm karo (daily + weekly alignment)."""
    weekly = df.set_index("date").resample("W").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna()
    if len(weekly) < 12:
        return None
    weekly["ema20"] = ema(weekly["close"], 10)  # ~10 weekly bars ≈ short trend filter
    return bool(weekly["close"].iloc[-1] > weekly["ema20"].iloc[-1])


def breakout_analysis(df, lookback=40, near_pct=1.5, volume_mult=1.5):
    if len(df) < lookback + 5:
        return {"status": "insufficient_data"}
    window = df.iloc[-(lookback + 3):-3]
    resistance = window["high"].max()
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
        "status": status, "resistance": round(float(resistance), 2),
        "last_volume": int(last["volume"]),
        "avg_volume_20d": None if pd.isna(vol_avg) else int(vol_avg),
        "volume_confirmed": bool(vol_confirmed),
    }


def technical_score(df, weekly_ok):
    last = df.iloc[-1]
    score, reasons = 0, []

    # 1) Daily trend structure (25)
    if last["close"] > last["ema20"] > last["ema50"]:
        score += 25
        reasons.append("Daily uptrend: Price > EMA20 > EMA50")
    elif last["close"] > last["ema20"]:
        score += 12
        reasons.append("Price > EMA20 (EMA50 se neeche)")

    # 2) Weekly alignment (15)
    if weekly_ok:
        score += 15
        reasons.append("Weekly timeframe bhi uptrend me hai (daily+weekly aligned)")
    elif weekly_ok is False:
        reasons.append("Weekly trend abhi weak/neutral hai")

    # 3) RSI zone (15)
    r = last["rsi14"]
    if 50 <= r <= 70:
        score += 15
        reasons.append(f"RSI healthy zone me ({r:.1f})")
    elif 70 < r <= 80:
        score += 7
        reasons.append(f"RSI overbought-ish ({r:.1f})")

    # 4) MACD bullish crossover (15) - last 3 din me crossover hua ho
    recent = df.tail(3)
    crossed = ((recent["macd_line"] > recent["macd_signal"]) &
               (recent["macd_line"].shift(1) <= recent["macd_signal"].shift(1))).any()
    if crossed:
        score += 15
        reasons.append("MACD bullish crossover recently hua")
    elif last["macd_line"] > last["macd_signal"]:
        score += 7
        reasons.append("MACD line signal ke upar hai")

    # 5) Bollinger — squeeze (setup) ya upper-band breakout (10)
    bb_width = df["bb_width_pct"]
    if last["close"] > last["bb_upper"]:
        score += 10
        reasons.append("Bollinger upper band breakout")
    elif bb_width.iloc[-1] < bb_width.tail(60).quantile(0.25):
        score += 6
        reasons.append("Bollinger squeeze - breakout ka setup ban raha hai")

    # 6) Volume confirmation (10)
    vol_avg = df["vol_avg20"].iloc[-1]
    if vol_avg and last["volume"] > 1.5 * vol_avg:
        score += 10
        reasons.append("Aaj ka volume 20-din average se 1.5x zyada")

    return round(min(score, 100), 1), reasons


def risk_reward(df):
    last = df.iloc[-1]
    a = last["atr14"]
    if pd.isna(a) or a <= 0:
        return None
    entry = round(float(last["close"]), 2)
    stop = round(entry - 1.5 * a, 2)
    target = round(entry + 2 * (entry - stop), 2)  # 1:2 R:R
    atr_pct = round(a / entry * 100, 2)
    return {"entry": entry, "stop_loss": stop, "target": target, "atr_pct": atr_pct}


# ---------------------------------------------------------------------------
# FUNDAMENTALS (stage 2 only — top candidates pe)
# ---------------------------------------------------------------------------
def fetch_fundamentals(symbol):
    try:
        info = yf.Ticker(f"{symbol}.NS").info
    except Exception:
        return None
    if not info or info.get("regularMarketPrice") is None:
        return None
    return {
        "pe_ratio": info.get("trailingPE"), "debt_to_equity": info.get("debtToEquity"),
        "roe": info.get("returnOnEquity"), "profit_margin": info.get("profitMargins"),
        "revenue_growth": info.get("revenueGrowth"), "sector": info.get("sector"),
    }


def check_red_flags(fund, last_close):
    flags = []
    if last_close < 20:
        flags.append("Penny stock (₹20 se kam) - junk/manipulation risk")
    if not fund:
        return flags + ["Fundamental data nahi mila - manually verify karo"]
    de = fund.get("debt_to_equity")
    if de is not None and de > 150:
        flags.append(f"High debt-to-equity ({de:.0f}%)")
    margin = fund.get("profit_margin")
    if margin is not None and margin < 0:
        flags.append("Negative profit margin (company loss me hai)")
    roe = fund.get("roe")
    if roe is not None and roe < 0.05:
        flags.append(f"Low ROE ({roe*100:.1f}%)")
    rev = fund.get("revenue_growth")
    if rev is not None and rev < 0:
        flags.append(f"Revenue declining ({rev*100:.1f}%)")
    return flags if flags else ["Koi major red flag nahi mila"]


def fundamental_score(fund):
    if not fund:
        return 50
    score = 50
    de, roe, margin, rev = (fund.get(k) for k in ["debt_to_equity", "roe", "profit_margin", "revenue_growth"])
    if de is not None:
        score += 15 if de < 60 else (-15 if de > 150 else 0)
    if roe is not None:
        score += 15 if roe > 0.15 else (-10 if roe < 0.05 else 0)
    if margin is not None:
        score += 10 if margin > 0.10 else (-15 if margin < 0 else 0)
    if rev is not None:
        score += 10 if rev > 0.10 else (-10 if rev < 0 else 0)
    return max(0, min(100, round(score, 1)))


# ---------------------------------------------------------------------------
# MARKET CONTEXT
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False, ttl=60 * 30)
def get_market_context():
    try:
        nifty = yf.Ticker("^NSEI").history(period="6mo").reset_index()
        nifty.columns = [c.lower() for c in nifty.columns]
        nifty["ema20"] = ema(nifty["close"], 20)
        nifty["ema50"] = ema(nifty["close"], 50)
        last = nifty.iloc[-1]
        if last["close"] > last["ema20"] > last["ema50"]:
            return "Bullish 🟢", "Nifty uptrend me hai - naye longs ke liye supportive environment"
        elif last["close"] < last["ema20"] < last["ema50"]:
            return "Bearish 🔴", "Nifty downtrend me hai - swing longs risky ho sakte hain, caution rakho"
        else:
            return "Neutral/Choppy 🟡", "Nifty sideways/mixed hai - stock-specific selection zyada important"
    except Exception:
        return "Unknown", "Market context fetch nahi ho paya"


# ---------------------------------------------------------------------------
# STAGE 1: batch technical scan (fast)
# ---------------------------------------------------------------------------
def batch_technical_scan(symbols, progress_bar, min_price=20, min_avg_volume=50000, batch_size=50):
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
                    continue  # liquidity/junk filter

                sub = compute_all_indicators(sub)
                weekly_ok = weekly_trend_ok(sub)
                tscore, reasons = technical_score(sub, weekly_ok)
                breakout = breakout_analysis(sub)
                rr = risk_reward(sub)

                passed.append({
                    "symbol": sym, "df_last_close": round(float(last_close), 2),
                    "technical_score": tscore, "reasons": reasons,
                    "breakout": breakout, "risk_reward": rr,
                    "rsi14": round(float(sub["rsi14"].iloc[-1]), 1),
                    "weekly_ok": weekly_ok,
                })
            except Exception:
                continue
        progress_bar.progress((b + 1) / total_batches)

    return passed


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
st.title("📈 Swing Trade Screener — Auto Scan")
st.warning("⚠️ Sirf research/screening tool hai — financial advice nahi. Apna risk management khud karo.")

market_status, market_note = get_market_context()
st.info(f"**Market Context (Nifty):** {market_status} — {market_note}")

mode = st.radio("Mode choose karo", ["🔍 Auto scan (NSE cash segment se khud dhundo)", "📋 Apni list paste karo"], horizontal=True)

if mode.startswith("🔍"):
    universe_choice = st.selectbox("Universe (kitna bada scan karna hai)", list(INDEX_URLS.keys()), index=1)
    col1, col2, col3 = st.columns(3)
    min_price = col1.number_input("Minimum price (₹)", value=20, min_value=1)
    min_volume = col2.number_input("Minimum avg daily volume", value=50000, min_value=0, step=10000)
    top_n = col3.slider("Top kitne stocks chahiye", 1, 10, 5)

    if st.button("🚀 Scan Shuru Karo", type="primary"):
        symbols = get_universe(universe_choice)
        if not symbols:
            st.stop()
        st.write(f"**{len(symbols)} stocks** scan honge. Bade universe (Nifty500/Full) me time lagega, patience rakho ⏳")

        progress = st.progress(0.0, text="Stage 1: Technical scan chal raha hai...")
        stage1 = batch_technical_scan(symbols, progress, min_price=min_price, min_avg_volume=min_volume)
        progress.empty()

        if not stage1:
            st.error("Koi stock filters pass nahi kar paya. Filters loosen karo ya universe badlo.")
            st.stop()

        stage1_sorted = sorted(stage1, key=lambda r: r["technical_score"], reverse=True)
        shortlist = stage1_sorted[:max(20, top_n * 4)]  # top candidates ka fundamentals check karenge

        st.write(f"Stage 1 se **{len(shortlist)}** technically strong stocks shortlist hue. Ab fundamentals check ho raha hai...")
        progress2 = st.progress(0.0, text="Stage 2: Fundamentals check ho raha hai...")
        final_results = []
        for i, r in enumerate(shortlist):
            fund = fetch_fundamentals(r["symbol"])
            fscore = fundamental_score(fund)
            red_flags = check_red_flags(fund, r["df_last_close"])
            composite = round(r["technical_score"] * 0.65 + fscore * 0.35, 1)
            r.update({"fundamentals": fund, "fundamental_score": fscore,
                       "red_flags": red_flags, "composite_score": composite})
            final_results.append(r)
            progress2.progress((i + 1) / len(shortlist))
        progress2.empty()

        top = sorted(final_results, key=lambda r: r["composite_score"], reverse=True)[:top_n]

        st.subheader(f"🏆 Top {len(top)} Swing Trade Candidates")
        status_map = {
            "breakout_confirmed": "✅ Breakout CONFIRMED (volume ke saath)",
            "near_breakout": "🟡 Near breakout", "breakout_low_volume": "🟠 Breakout hua lekin volume weak",
            "no_breakout": "⚪ Koi breakout nahi", "insufficient_data": "❓ Data kam hai",
        }
        for rank, r in enumerate(top, start=1):
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 1, 1])
                c1.markdown(f"### #{rank} · {r['symbol']}")
                c2.metric("Score", f"{r['composite_score']}/100")
                c3.metric("Last Close", f"₹{r['df_last_close']}")

                bt = r["breakout"]
                st.write(f"**Breakout:** {status_map.get(bt['status'], bt['status'])} (Resistance: ₹{bt.get('resistance')})")
                st.write(f"**Weekly trend aligned:** {'✅ Haan' if r['weekly_ok'] else '❌ Nahi/Unclear'} | **RSI:** {r['rsi14']}")

                rr = r["risk_reward"]
                if rr:
                    st.write(f"**Suggested Risk-Reward (1:2):** Entry ₹{rr['entry']} | Stop-loss ₹{rr['stop_loss']} | Target ₹{rr['target']} | ATR: {rr['atr_pct']}%")

                st.write("**Technical reasons:**")
                for reason in r["reasons"]:
                    st.write(f"- {reason}")

                fund = r["fundamentals"]
                if fund:
                    st.write(f"**Fundamentals:** P/E: {fund.get('pe_ratio')} | ROE: {fund.get('roe')} | D/E: {fund.get('debt_to_equity')} | Sector: {fund.get('sector')}")
                st.write("**Red flags:**")
                for flag in r["red_flags"]:
                    st.write(f"- {flag}")

        st.caption("📌 Reminder: upcoming results/corporate actions khud check kar lo — ye tool sudden news-based gaps predict nahi karta.")

else:
    st.info("Purane 'paste list' mode ke liye pehle wali app.py use karo, ya yahan bata do to isi file me dono modes merge kar dunga.")
