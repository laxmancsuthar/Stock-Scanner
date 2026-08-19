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
import calendar
import tempfile
import threading
import time as _time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta, date
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup
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
ALL_KNOWN_SYMBOLS = sorted(set(t.replace(".NS", "") for t in NIFTY_500_NS))


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

# Alternate source (different domain — NSE Indices' own site, not nseindia.com)
# tried if the primary URL above fails. Cloud hosts that get blocked by
# nseindia.com sometimes aren't blocked here, so this can rescue a live fetch
# without needing a bundled CSV at all.
NSE_INDEX_URLS_ALT = {
    "Nifty 50": "https://www.niftyindices.com/IndexConstituent/ind_nifty50list.csv",
    "Nifty 200": "https://www.niftyindices.com/IndexConstituent/ind_nifty200list.csv",
    "Nifty 500": "https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv",
}


@st.cache_data(show_spinner=False, ttl=60 * 60 * 6)
def get_universe_live(choice: str) -> Optional[List[str]]:
    """Fetch the current constituent list directly from NSE. Tries the
    primary nseindia.com URL first, then an alternate domain (niftyindices.com)
    if that fails. Returns None (instead of raising) if both are blocked, so
    the caller can fall back to a bundled/hardcoded list."""
    session = requests.Session()
    session.headers.update(NSE_HEADERS)

    urls_to_try = [u for u in [NSE_INDEX_URLS.get(choice), NSE_INDEX_URLS_ALT.get(choice)] if u]
    for url in urls_to_try:
        try:
            if "nseindia.com" in url and "niftyindices" not in url:
                session.get("https://www.nseindia.com", timeout=8)  # warms up cookies, NSE requires this
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
            df = pd.read_csv(io.StringIO(resp.text))
            col = "Symbol" if "Symbol" in df.columns else "SYMBOL"
            if "SERIES" in df.columns:
                symbols = df.loc[df["SERIES"].astype(str).str.strip() == "EQ", col].astype(str).str.strip().tolist()
            else:
                symbols = df[col].astype(str).str.strip().tolist()
            symbols = [s for s in symbols if s]
            if symbols:
                return _add_suffix(symbols)
        except Exception:
            continue
    return None


# ----------------------------------------------------------------------------
# Bundled index lists — static CSVs committed to the repo, used as a middle
# fallback when live NSE fetch is blocked (very common on cloud hosting like
# Streamlit Community Cloud, since NSE blocks datacenter IPs) but the small
# built-in hardcoded lists aren't enough / accurate coverage.
#
# To enable for any universe: download the matching CSV from NSE (works fine
# from a normal browser, only bots/cloud IPs get blocked) and save it under
# stock_lists/ using the filenames below. See stock_lists/README.md for the
# exact download links. Any file that isn't present is skipped silently and
# that universe falls back to the small built-in list as before.
# ----------------------------------------------------------------------------
BUNDLED_LIST_DIR = Path(__file__).resolve().parent / "stock_lists"

BUNDLED_LIST_FILES = {
    "Nifty 50": "nifty50.csv",
    "Nifty 200": "nifty200.csv",
    "Nifty 500": "nifty500.csv",
    "Full NSE Cash Segment (slow, 1500+ stocks)": "all_nse_symbols.csv",
}


@st.cache_data(show_spinner=False)
def load_bundled_list(universe_label: str) -> Optional[List[str]]:
    fname = BUNDLED_LIST_FILES.get(universe_label)
    if not fname:
        return None
    path = BUNDLED_LIST_DIR / fname
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path)
        col = "SYMBOL" if "SYMBOL" in df.columns else ("Symbol" if "Symbol" in df.columns else df.columns[0])
        if "SERIES" in df.columns:
            symbols = df.loc[df["SERIES"].astype(str).str.strip() == "EQ", col].astype(str).str.strip().tolist()
        elif " SERIES" in df.columns:  # NSE's CSV sometimes has a leading space in this header
            symbols = df.loc[df[" SERIES"].astype(str).str.strip() == "EQ", col].astype(str).str.strip().tolist()
        else:
            symbols = df[col].astype(str).str.strip().tolist()
        symbols = sorted(set(s for s in symbols if s and s.lower() != "nan"))
        return _add_suffix(symbols) if symbols else None
    except Exception:
        return None


# Backward-compatible alias (full-segment specific) used by get_lookup_symbols
def load_bundled_full_list() -> Optional[List[str]]:
    return load_bundled_list("Full NSE Cash Segment (slow, 1500+ stocks)")




# ============================================================================
# SECTION 1B: SEASONAL DATE-RANGE SCAN  (ported from seasonal_stock_scanner.py)
# ----------------------------------------------------------------------------
# Diya gaya date-range (sirf din-mahina, saal ignore) pichhle N saal me
# scan karta hai aur batata hai ki us range me har saal kitni baar profit
# mila (Accuracy % / win-rate) — Position Sizing page ki jagah naya button.
#
# Historical data daily change nahi hota, isliye ye disk par persist hota
# hai (price_cache/ folder) — ek baar fetch hone ke baad dobara scan karne
# par yfinance ko call nahi karna padta. Cache 30 din se purana ho jaye to
# khud-b-khud refresh ho jata hai; ya "🔄 Refresh All Cached Data" button se
# manually kabhi bhi poora cache force-refresh kiya ja sakta hai.
# ============================================================================

SEASONAL_CACHE_DIR = Path(__file__).resolve().parent / "price_cache"
SEASONAL_CACHE_DIR.mkdir(exist_ok=True)
SEASONAL_CACHE_MAX_AGE_DAYS = 30


def _seasonal_cache_path(ticker: str) -> Path:
    return SEASONAL_CACHE_DIR / f"{ticker.replace('.', '_')}.csv"


def _seasonal_load_cache(ticker: str) -> Optional[pd.DataFrame]:
    p = _seasonal_cache_path(ticker)
    if not p.exists():
        return None
    try:
        df = pd.read_csv(p, index_col=0, parse_dates=True)
        if "Close" not in df.columns or df.empty:
            return None
        return df
    except Exception:
        return None


def _seasonal_save_cache(ticker: str, df: pd.DataFrame) -> None:
    try:
        df[["Close"]].to_csv(_seasonal_cache_path(ticker))
    except Exception:
        pass


def _seasonal_cache_age_days(ticker: str) -> float:
    p = _seasonal_cache_path(ticker)
    if not p.exists():
        return float("inf")
    return (_time.time() - p.stat().st_mtime) / 86400.0


def _seasonal_download_fresh(ticker: str, years_back: int) -> Optional[pd.DataFrame]:
    """Yfinance se fresh data download karta hai (network call)."""
    try:
        df = yf.download(
            ticker, period=f"{years_back + 1}y",
            auto_adjust=True, progress=False, threads=False,
        )
        if df is None or df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        if "Close" not in df.columns:
            return None
        df = df.dropna(subset=["Close"])
        return df[["Close"]] if not df.empty else None
    except Exception:
        return None


def seasonal_fetch_history(ticker: str, years_back: int, force_refresh: bool = False) -> Optional[pd.DataFrame]:
    """Ek ticker ka (years_back+1) saal ka daily Close data laata hai.
    Priority: disk cache (agar 30 din se fresh hai aur force_refresh nahi hai)
    -> yfinance download (aur cache update) -> stale cache (fallback agar
    download fail ho jaye)."""
    if not force_refresh:
        cached = _seasonal_load_cache(ticker)
        if cached is not None and _seasonal_cache_age_days(ticker) < SEASONAL_CACHE_MAX_AGE_DAYS:
            return cached

    fresh = _seasonal_download_fresh(ticker, years_back)
    if fresh is not None:
        _seasonal_save_cache(ticker, fresh)
        return fresh

    # download fail hua (internet issue / rate-limit) -> jo bhi purana cache mile wahi use karo
    return _seasonal_load_cache(ticker)


def seasonal_refresh_all_cached(years_back: int, progress_cb=None) -> int:
    """price_cache/ me jitne bhi tickers ka data pehle se saved hai, sabko
    yfinance se force re-download karke overwrite karta hai. Returns count
    of tickers successfully refreshed."""
    cached_files = list(SEASONAL_CACHE_DIR.glob("*.csv"))
    tickers = []
    for f in cached_files:
        stem = f.stem
        if stem.endswith("_NS"):
            tickers.append(stem[:-3] + ".NS")
        elif stem.endswith("_BO"):
            tickers.append(stem[:-3] + ".BO")
        else:
            tickers.append(stem)

    refreshed = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(_seasonal_download_fresh, tkr, years_back): tkr for tkr in tickers}
        done = 0
        for fut in as_completed(futures):
            tkr = futures[fut]
            done += 1
            if progress_cb:
                progress_cb(done / len(tickers) if tickers else 1.0)
            try:
                df = fut.result()
            except Exception:
                df = None
            if df is not None:
                _seasonal_save_cache(tkr, df)
                refreshed += 1
    return refreshed


def seasonal_cache_status() -> Dict[str, Any]:
    """Cache ka summary — kitne symbols cached hain aur sabse purana/naya kab update hua."""
    cached_files = list(SEASONAL_CACHE_DIR.glob("*.csv"))
    if not cached_files:
        return {"count": 0, "oldest": None, "newest": None}
    mtimes = [f.stat().st_mtime for f in cached_files]
    return {
        "count": len(cached_files),
        "oldest": datetime.fromtimestamp(min(mtimes)),
        "newest": datetime.fromtimestamp(max(mtimes)),
    }


def seasonal_nearest_trading_price(df: pd.DataFrame, target: date, direction: str):
    """target date ke aas-paas nearest trading-day Close price dhoondhta hai.
    direction='forward' -> target ya usse baad ka pehla trading din
    direction='backward' -> target ya usse pehle ka aakhri trading din
    """
    idx = df.index
    ts = pd.Timestamp(target)
    if direction == "forward":
        cand = idx[idx >= ts]
        if len(cand) == 0:
            return None, None
        d = cand[0]
    else:
        cand = idx[idx <= ts]
        if len(cand) == 0:
            return None, None
        d = cand[-1]
    return d, float(df.loc[d, "Close"])


def _safe_date(year: int, month: int, day: int) -> date:
    """Builds a date, clamping day to the last valid day of that month
    (e.g. day=31 for April becomes 30). Used so the day/month-only picker
    never errors out on invalid combinations."""
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, last_day))


def seasonal_scan_one_stock(df: pd.DataFrame, start_md: tuple, end_md: tuple,
                             years_back: int, max_gap_days: int = 10) -> pd.DataFrame:
    """Ek stock ke liye, pichhle 'years_back' saalon me diye gaye (month, day)
    date-range ke andar har saal ka return nikalta hai."""
    today = date.today()
    current_year = today.year
    wraps = (end_md[0], end_md[1]) < (start_md[0], start_md[1])  # e.g. 20-Dec se 15-Jan

    records = []
    for y in range(current_year - years_back, current_year + 1):
        try:
            start_date = date(y, start_md[0], start_md[1])
        except ValueError:
            continue  # e.g. 29 Feb non-leap year
        end_year = y + 1 if wraps else y
        try:
            end_date = date(end_year, end_md[0], end_md[1])
        except ValueError:
            continue
        if end_date > today:
            continue  # future range abhi complete nahi hui

        sd, sp = seasonal_nearest_trading_price(df, start_date, "forward")
        ed, ep = seasonal_nearest_trading_price(df, end_date, "backward")
        if sd is None or ed is None or ed <= sd:
            continue
        if (sd.date() - start_date).days > max_gap_days:
            continue
        if (end_date - ed.date()).days > max_gap_days:
            continue

        ret = (ep - sp) / sp * 100
        records.append({
            "Year": y,
            "Start Date": sd.date(),
            "End Date": ed.date(),
            "Start Price": round(sp, 2),
            "End Price": round(ep, 2),
            "Return %": round(ret, 2),
            "Profit": ret > 0,
        })
    return pd.DataFrame(records)


def seasonal_summarize_symbol(sym: str, yearly_df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    if yearly_df.empty:
        return None
    total_years = len(yearly_df)
    profit_years = int(yearly_df["Profit"].sum())
    accuracy = profit_years / total_years * 100
    return {
        "Symbol": sym,
        "Years Analyzed": total_years,
        "Profitable Years": profit_years,
        "Loss Years": total_years - profit_years,
        "Accuracy %": round(accuracy, 1),
        "Avg Return %": round(yearly_df["Return %"].mean(), 2),
        "Best Year Return %": round(yearly_df["Return %"].max(), 2),
        "Worst Year Return %": round(yearly_df["Return %"].min(), 2),
    }


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
# SECTION 3B: nse_extra.py — Promoter/FII/DII/Public holding + Bulk/Block deals
# ----------------------------------------------------------------------------
# Uses the `nse` PyPI package (BennyThadikaran/NseIndiaApi) instead of hand-
# rolled requests calls. It handles NSE's cookie warm-up and correct endpoint
# paths for us, and — importantly — NSE's edge/WAF blocks plain `requests`
# (HTTP/1.1) traffic from datacenter/cloud IPs with 503s; the library works
# around this with an httpx HTTP/2 client when `server=True` is passed.
#
# Install:  pip install nse
# If deploying on a server/cloud host (Streamlit Cloud, AWS, Docker, etc.),
# also:     pip install "httpx[http2]"   and set NSE_RUN_ON_SERVER = True below.
# Running locally on your own machine/laptop, leave it False.
# ============================================================================

NSE_RUN_ON_SERVER = True  # True if this app is deployed on a cloud/server host

try:
    from nse import NSE as _NSEClient
    _NSE_LIB_AVAILABLE = True
except ImportError:
    _NSE_LIB_AVAILABLE = False


@st.cache_resource(show_spinner=False)
def _get_nse_client():
    """One shared NSE client for the app's lifetime (reuses cookies/session)."""
    if not _NSE_LIB_AVAILABLE:
        return None
    cookie_dir = Path(tempfile.gettempdir()) / "nse_cookies"
    cookie_dir.mkdir(parents=True, exist_ok=True)
    try:
        return _NSEClient(download_folder=str(cookie_dir), server=NSE_RUN_ON_SERVER, timeout=15)
    except Exception:
        return None


def fetch_nse_debug(symbol: str) -> Dict[str, Any]:
    """No-cache diagnostic call against each data source — returns status/error
    text for each, so a broken call can be identified from the UI directly."""
    base = symbol.replace(".NS", "")
    results: Dict[str, Any] = {}

    # Shareholding now comes from screener.in (see fetch_shareholding_filings) —
    # test that path here too so debug mode covers the real code path.
    try:
        sh = fetch_shareholding_filings(symbol)
        results["shareholding (screener.in)"] = {"status": "OK" if sh else "EMPTY", "body": str(sh)[:800]}
    except Exception as e:
        results["shareholding (screener.in)"] = {"status": type(e).__name__, "body": str(e)[:800]}

    try:
        dv = fetch_delivery_history(symbol, lookback_days=20, want_rows=10)
        results["delivery % (nse bhavcopy)"] = {"status": "OK" if dv else "EMPTY", "body": str(dv)[:800]}
    except Exception as e:
        results["delivery % (nse bhavcopy)"] = {"status": type(e).__name__, "body": str(e)[:800]}

    if not _NSE_LIB_AVAILABLE:
        results["nse package (bulk/block deals)"] = {"status": "NOT INSTALLED", "body": "Run: pip install nse"}
        return results

    for label, deal_type in (("bulk_deals", "bulk"), ("block_deals", "block")):
        try:
            data = fetch_all_deals_raw(deal_type, 90)  # same cached call the rest of the app uses
            matches = [r for r in data if str(r.get("BD_SYMBOL", "")).strip().upper() == base.upper()]
            fuzzy = [r for r in data if base.upper() in str(r.get("BD_SYMBOL", "")).strip().upper()]
            all_symbols_repr = sorted({repr(str(r.get("BD_SYMBOL", ""))) for r in data})
            body = (
                f"Total records (all symbols, 90d): {len(data)} | Exact match '{base}': {len(matches)} | "
                f"Fuzzy (contains) match: {len(fuzzy)}\n"
                f"Sample exact matches: {str(matches[:3])[:400]}\n"
                f"Sample fuzzy matches: {str(fuzzy[:3])[:400]}\n"
                f"First 15 raw symbol values (repr, to spot hidden whitespace): {all_symbols_repr[:15]}"
            )
            results[label] = {"status": "OK", "body": body}
        except Exception as e:
            results[label] = {"status": type(e).__name__, "body": str(e)[:800]}

    return results


@st.cache_data(show_spinner=False, ttl=60 * 60 * 6)
def _fetch_screener_soup(symbol: str) -> Optional[str]:
    """Fetch screener.in's company page HTML once per symbol (cached), reused
    by shareholding, quarterly/annual financials, etc. — avoids re-downloading
    the same page for every feature that needs it. Returns raw HTML text
    (BeautifulSoup objects aren't cache-friendly/picklable) — callers should
    parse it with BeautifulSoup themselves."""
    base = symbol.replace(".NS", "")
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.screener.in/",
    })
    for url in (f"https://www.screener.in/company/{base}/consolidated/",
                f"https://www.screener.in/company/{base}/"):
        try:
            resp = session.get(url, timeout=12)
            if resp.status_code == 200:
                return resp.text
        except Exception:
            continue
    return None


def _parse_screener_table(html: str, section_id: str) -> Dict[str, List[Optional[float]]]:
    """Parse one screener.in table section (by section id, e.g. 'quarters',
    'profit-loss', 'cash-flow', 'shareholding') into {row_label: [values...]},
    left-to-right = oldest to most recent period, matching screener's layout."""
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")
    section = soup.find("section", {"id": section_id})
    if not section:
        return {}
    table = section.find("table")
    if not table:
        return {}
    rows = table.find_all("tr")
    data: Dict[str, List[Optional[float]]] = {}
    for i, row in enumerate(rows):
        cols = row.find_all(["th", "td"])
        texts = [c.get_text(strip=True).replace("%", "").replace(",", "") for c in cols]
        if i == 0 or not texts or not texts[0]:
            continue
        label = texts[0].strip()
        try:
            vals = [float(v) if v not in ("", "-", "--") else None for v in texts[1:]]
        except Exception:
            vals = [None] * len(texts[1:])
        data[label] = vals
    return data


def _get_table_row(table_data: Dict[str, List[Optional[float]]], keys: List[str]) -> Optional[List[Optional[float]]]:
    for k in keys:
        for label, vals in table_data.items():
            if k.lower() in label.lower():
                return vals
    return None


@st.cache_data(show_spinner=False, ttl=60 * 60 * 6)
def fetch_shareholding_filings(symbol: str) -> List[Dict[str, Any]]:
    """Promoter / FII / DII / Public shareholding (current, previous quarter,
    QoQ change) scraped from screener.in's company page. This is a different,
    more reliable source than NSE's JSON API — no cookie/bot-protection dance,
    single HTML request, and screener already lines up quarter-over-quarter
    columns so the change % can be computed directly.
    Returns a single-row list (easiest to render as a table) with keys like
    promoter_cur/promoter_prev/promoter_chg, fii_*, dii_*, public_*."""
    html = _fetch_screener_soup(symbol)
    if html is None:
        return []
    sh_data = _parse_screener_table(html, "shareholding")
    if not sh_data:
        return []

    result: Dict[str, Any] = {}

    def fill(prefix: str, keys: List[str]):
        vals = _get_table_row(sh_data, keys)
        if vals and len(vals) >= 1 and vals[-1] is not None:
            result[f"{prefix}_cur"] = round(vals[-1], 2)
            if len(vals) >= 2 and vals[-2] is not None:
                result[f"{prefix}_prev"] = round(vals[-2], 2)
                result[f"{prefix}_chg"] = round(vals[-1] - vals[-2], 2)

    fill("promoter", ["Promoters", "Promoter"])
    fill("fii", ["FII", "Foreign", "FPI"])
    fill("dii", ["DII", "Domestic Institution"])
    fill("public", ["Public"])

    return [result] if result else []


# Row label -> keys used to find it on screener.in's quarterly/annual/cash-flow
# tables. "Net Profit" and "PAT" are the same screener row (Indian filings use
# the terms interchangeably) — both are shown since the user wants both
# labels, but they'll always carry identical values.
_FIN_METRIC_KEYS: Dict[str, List[str]] = {
    "EPS": ["EPS in Rs", "EPS"],
    "OPM": ["OPM"],
    "Sales Growth": ["Sales", "Revenue"],
    "PAT": ["Net Profit", "Profit after tax"],
    "PBT": ["Profit before tax"],
    "EBITDA": ["Operating Profit"],
    "NET PROFIT": ["Net Profit", "Profit after tax"],
    "CASH FLOW": ["Cash from Operating Activity", "Net Cash Flow"],
}
# OPM is already a percentage/ratio — QoQ/YoY "growth" for it is shown as a
# percentage-POINT delta (e.g. "+2.1 pts"), not a relative % change, since
# relative-% of a percentage is misleading. Everything else is a relative %.
_FIN_METRIC_IS_MARGIN = {"OPM"}


@st.cache_data(show_spinner=False, ttl=60 * 60 * 6)
def fetch_quarterly_yearly_financials(symbol: str) -> Dict[str, Dict[str, Optional[float]]]:
    """EPS / OPM / Sales Growth / PAT / PBT / EBITDA / Net Profit / Cash Flow —
    QoQ (from screener's 'quarters' table) and YoY (from the annual
    'profit-loss' + 'cash-flow' tables) change, for one symbol.
    Cash Flow only exists as an annual figure on screener.in, so its QoQ is
    always None (shown as '—' in the UI).
    Returns {metric_label: {"qoq": float|None, "yoy": float|None}}."""
    html = _fetch_screener_soup(symbol)
    if html is None:
        return {}

    q_data = _parse_screener_table(html, "quarters")
    a_data = _parse_screener_table(html, "profit-loss")
    cf_data = _parse_screener_table(html, "cash-flow")

    def pct_change(vals: Optional[List[Optional[float]]], is_margin: bool) -> Optional[float]:
        if not vals or len(vals) < 2:
            return None
        last, prev = vals[-1], vals[-2]
        if last is None or prev is None:
            return None
        if is_margin:
            return round(last - prev, 2)  # percentage-point delta
        if prev == 0:
            return None
        return round(((last - prev) / abs(prev)) * 100, 1)

    out: Dict[str, Dict[str, Optional[float]]] = {}
    for label, keys in _FIN_METRIC_KEYS.items():
        is_margin = label in _FIN_METRIC_IS_MARGIN
        if label == "CASH FLOW":
            qoq = None  # not published quarterly on screener.in
            yoy = pct_change(_get_table_row(cf_data, keys), is_margin)
        else:
            qoq = pct_change(_get_table_row(q_data, keys), is_margin)
            yoy = pct_change(_get_table_row(a_data, keys), is_margin)
        out[label] = {"qoq": qoq, "yoy": yoy}
    return out


@st.cache_data(show_spinner=False, ttl=60 * 30)
def fetch_all_deals_raw(deal_type: str = "bulk", days: int = 90) -> List[Dict[str, Any]]:
    """Raw bulk/block deal records for ALL symbols over the trailing `days`
    (unfiltered). Cached once and reused both by the per-stock detail view
    and the all-stocks 'Bulk/Block Deals' scanner page.

    NSE's historicalOR endpoint appears to silently cap/paginate results for
    wide date ranges (observed: a 90-day query and a much shorter query both
    returning suspiciously similar totals, with some genuinely recent deals
    missing). To work around this without relying on undocumented pagination
    params, the requested window is split into ~15-day chunks, each fetched
    separately and merged — a much smaller range per request is far less
    likely to hit whatever cap NSE applies."""
    if not _NSE_LIB_AVAILABLE:
        return []
    client = _get_nse_client()
    if client is None:
        return []
    option_type = "bulk_deals" if deal_type == "bulk" else "block_deals"

    chunk_days = 15 if days <= 90 else 30
    to_dt = datetime.now()
    start_dt = to_dt - timedelta(days=days)

    all_rows: List[Dict[str, Any]] = []
    seen_keys = set()
    chunk_end = to_dt
    while chunk_end > start_dt:
        chunk_start = max(start_dt, chunk_end - timedelta(days=chunk_days))
        try:
            rows = client.bulkdeals(option_type, chunk_start, chunk_end)
        except RuntimeError:
            rows = []  # no deals in this particular chunk — not an error
        except Exception:
            rows = []
        for r in rows:
            key = (
                r.get("BD_DT_DATE"), r.get("BD_SYMBOL"), r.get("BD_CLIENT_NAME"),
                r.get("BD_BUY_SELL"), r.get("BD_QTY_TRD"), r.get("BD_TP_WATP"),
            )
            if key not in seen_keys:
                seen_keys.add(key)
                all_rows.append(r)
        chunk_end = chunk_start

    return all_rows


def _normalize_deal_row(r: Dict[str, Any]) -> Dict[str, Any]:
    sym = r.get("BD_SYMBOL") or r.get("symbol")
    sec = r.get("BD_SCRIP_NAME") or r.get("scripName")
    cli = r.get("BD_CLIENT_NAME") or r.get("clientName")
    return {
        "Date": r.get("BD_DT_DATE") or r.get("date"),
        "Symbol": sym.strip() if isinstance(sym, str) else sym,
        "Security": sec.strip() if isinstance(sec, str) else sec,
        "Client": cli.strip() if isinstance(cli, str) else cli,
        "Buy/Sell": r.get("BD_BUY_SELL") or r.get("buySell"),
        "Qty": r.get("BD_QTY_TRD") or r.get("qty"),
        "Price": r.get("BD_TP_WATP") or r.get("price"),
    }


def fetch_deals(symbol: str, deal_type: str = "bulk", days: int = 90) -> List[Dict[str, Any]]:
    """Bulk or block deals for a single symbol over the trailing `days`.
    deal_type: 'bulk' or 'block'."""
    base = symbol.replace(".NS", "")
    rows = fetch_all_deals_raw(deal_type, days)
    out = []
    for r in rows:
        if str(r.get("BD_SYMBOL") or r.get("symbol") or "").strip().upper() != base.upper():
            continue
        row = _normalize_deal_row(r)
        row.pop("Symbol", None)
        row.pop("Security", None)
        out.append(row)
    return out


def fetch_all_deals(deal_type: str = "bulk", days: int = 90) -> pd.DataFrame:
    """All symbols' bulk/block deals over the trailing `days` as a DataFrame —
    powers the 'Bulk/Block Deals' scanner page."""
    rows = fetch_all_deals_raw(deal_type, days)
    if not rows:
        return pd.DataFrame(columns=["Date", "Symbol", "Security", "Client", "Buy/Sell", "Qty", "Price"])
    return pd.DataFrame([_normalize_deal_row(r) for r in rows])


# ----------------------------------------------------------------------------
# Delivery % — NSE's daily full-market "bhavcopy with delivery" CSV
# ----------------------------------------------------------------------------

@st.cache_data(show_spinner=False, ttl=60 * 60 * 6)
def _fetch_bhavcopy_day(date_str: str) -> Optional[pd.DataFrame]:
    """Full-market delivery bhavcopy (ALL symbols, one trading day) as a
    DataFrame. Cached per calendar day so every stock's detail view reuses
    the same download instead of re-fetching per symbol."""
    if not _NSE_LIB_AVAILABLE:
        return None
    client = _get_nse_client()
    if client is None:
        return None
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    try:
        path = client.deliveryBhavcopy(date_obj)
        df = pd.read_csv(path)
        df.columns = [c.strip() for c in df.columns]
        return df
    except Exception:
        return None  # weekend/holiday/report not yet published — not an error


@st.cache_data(show_spinner=False, ttl=60 * 60 * 6)
def fetch_delivery_history(symbol: str, lookback_days: int = 20, want_rows: int = 10) -> List[Dict[str, Any]]:
    """Trailing delivery qty/% for a symbol, most recent trading day first.
    Walks backward day-by-day — skipping weekends and any day the report
    isn't available (holiday, or same-day before EOD publish) — until
    `want_rows` valid records are collected or `lookback_days` calendar
    days have been checked."""
    base = symbol.replace(".NS", "").strip().upper()
    out: List[Dict[str, Any]] = []
    d = datetime.now()
    checked = 0
    while checked < lookback_days and len(out) < want_rows:
        if d.weekday() < 5:  # Mon-Fri only; weekends never have a report
            df = _fetch_bhavcopy_day(d.strftime("%Y-%m-%d"))
            if df is not None and not df.empty and "SYMBOL" in df.columns:
                mask = df["SYMBOL"].astype(str).str.strip().str.upper() == base
                if "SERIES" in df.columns:
                    mask &= df["SERIES"].astype(str).str.strip().str.upper() == "EQ"
                match = df[mask]
                if not match.empty:
                    r = match.iloc[0]

                    def g(*names):
                        for n in names:
                            if n in match.columns:
                                val = r[n]
                                try:
                                    return float(val)
                                except (TypeError, ValueError):
                                    return None
                        return None

                    out.append({
                        "Date": d.strftime("%d-%b-%Y"),
                        "Close": g("CLOSE_PRICE", "CLOSE"),
                        "Traded Qty": g("TTL_TRD_QNTY", "TTL_TRD_QTY"),
                        "Delivery Qty": g("DELIV_QTY"),
                        "Delivery %": g("DELIV_PER"),
                    })
        d -= timedelta(days=1)
        checked += 1
    return out


@st.cache_data(show_spinner=False, ttl=60 * 60 * 6)
def fetch_delivery_avg_all_symbols(trading_days_needed: int = 10, lookback_days: int = 20) -> pd.DataFrame:
    """Average Delivery % per symbol (EQ series) over the last
    `trading_days_needed` valid trading days — walks back up to
    `lookback_days` calendar days to collect enough data points, skipping
    weekends/holidays where no report exists. Reuses the same per-day
    bhavcopy cache as the single-day leaderboard, so days already fetched
    for one average aren't re-downloaded for the other."""
    d = datetime.now()
    checked = 0
    collected = 0
    frames = []
    while checked < lookback_days and collected < trading_days_needed:
        if d.weekday() < 5:
            df = _fetch_bhavcopy_day(d.strftime("%Y-%m-%d"))
            if df is not None and not df.empty and "SYMBOL" in df.columns and "DELIV_PER" in df.columns:
                work = df.copy()
                if "SERIES" in work.columns:
                    work = work[work["SERIES"].astype(str).str.strip().str.upper() == "EQ"]
                sub = work[["SYMBOL", "DELIV_PER"]].copy()
                sub["SYMBOL"] = sub["SYMBOL"].astype(str).str.strip()
                sub["DELIV_PER"] = pd.to_numeric(sub["DELIV_PER"], errors="coerce")
                frames.append(sub)
                collected += 1
        d -= timedelta(days=1)
        checked += 1
    if not frames:
        return pd.DataFrame(columns=["Symbol", "Avg Delivery %"])
    allrows = pd.concat(frames, ignore_index=True)
    grouped = allrows.groupby("SYMBOL")["DELIV_PER"].mean().reset_index()
    grouped.columns = ["Symbol", "Avg Delivery %"]
    return grouped


@st.cache_data(show_spinner=False, ttl=60 * 60 * 6)
def fetch_market_delivery_leaderboard(lookback_days: int = 5) -> pd.DataFrame:
    """Full-market Delivery % for every EQ-series stock on the most recent
    available trading day (walks backward up to `lookback_days` calendar
    days to find a published report — handles weekends/holidays and the
    same-day-before-EOD-publish case), plus 10-day and ~monthly (22 trading
    day) average Delivery % per symbol. Sorted by (latest-day) Delivery %
    descending, so 'best delivery' stocks are simply the top rows."""
    d = datetime.now()
    checked = 0
    while checked < lookback_days:
        if d.weekday() < 5:
            df = _fetch_bhavcopy_day(d.strftime("%Y-%m-%d"))
            if df is not None and not df.empty and "SYMBOL" in df.columns:
                work = df.copy()
                if "SERIES" in work.columns:
                    work = work[work["SERIES"].astype(str).str.strip().str.upper() == "EQ"]

                def col(*names):
                    for n in names:
                        if n in work.columns:
                            return work[n]
                    return None

                result = pd.DataFrame({
                    "Symbol": work["SYMBOL"].astype(str).str.strip(),
                    "Close": pd.to_numeric(col("CLOSE_PRICE", "CLOSE"), errors="coerce"),
                    "Traded Qty": pd.to_numeric(col("TTL_TRD_QNTY", "TTL_TRD_QTY"), errors="coerce"),
                    "Delivery Qty": pd.to_numeric(col("DELIV_QTY"), errors="coerce"),
                    "Delivery %": pd.to_numeric(col("DELIV_PER"), errors="coerce"),
                })
                result.insert(0, "Date", d.strftime("%d-%b-%Y"))
                result = result.dropna(subset=["Delivery %"])

                avg10 = fetch_delivery_avg_all_symbols(trading_days_needed=10, lookback_days=20)
                avg10 = avg10.rename(columns={"Avg Delivery %": "10D Avg Delivery %"})
                avgm = fetch_delivery_avg_all_symbols(trading_days_needed=22, lookback_days=40)
                avgm = avgm.rename(columns={"Avg Delivery %": "Monthly Avg Delivery %"})

                result = result.merge(avg10, on="Symbol", how="left")
                result = result.merge(avgm, on="Symbol", how="left")
                result["10D Avg Delivery %"] = result["10D Avg Delivery %"].round(2)
                result["Monthly Avg Delivery %"] = result["Monthly Avg Delivery %"].round(2)

                return result.sort_values("Delivery %", ascending=False).reset_index(drop=True)
        d -= timedelta(days=1)
        checked += 1
    return pd.DataFrame(columns=["Date", "Symbol", "Close", "Traded Qty", "Delivery Qty", "Delivery %",
                                  "10D Avg Delivery %", "Monthly Avg Delivery %"])



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


def _data_table(headers, rows, col_widths):
    """Header row + data rows table, styled consistently with the rest of the
    PDF (used for the QoQ/YoY financials table and the shareholding table)."""
    styles = getSampleStyleSheet()
    hdr_style = ParagraphStyle("TblHdr", parent=styles["BodyText"], fontSize=8, leading=11,
                                textColor=colors.HexColor(PDF_MUTED), fontName="Helvetica-Bold")
    cell_style = ParagraphStyle("TblCell", parent=styles["BodyText"], fontSize=8.5, leading=12,
                                 textColor=colors.HexColor(PDF_TEXT))
    data = [[Paragraph(h, hdr_style) for h in headers]]
    for row in rows:
        data.append([Paragraph(str(v), cell_style) for v in row])
    tbl = Table(data, colWidths=col_widths)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(PDF_CARD)),
        ("LINEBELOW", (0, 0), (-1, 0), 0.75, colors.HexColor(PDF_BORDER)),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, colors.HexColor(PDF_BORDER)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
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
    # Fundamental snapshot — QoQ/YoY financials (mirrors the on-screen
    # "Fundamental snapshot" expander)
    # ---------------------------------------------------------------
    story.append(Paragraph("Fundamental Snapshot — QoQ / YoY", h2))
    fin_data = fetch_quarterly_yearly_financials(candidate.get("symbol", ""))
    if fin_data:
        fin_rows = []
        for label in ["EPS", "OPM", "Sales Growth", "PAT", "PBT", "EBITDA", "NET PROFIT", "CASH FLOW"]:
            m = fin_data.get(label, {})
            qoq, yoy = m.get("qoq"), m.get("yoy")
            unit = " pts" if label in _FIN_METRIC_IS_MARGIN else "%"
            fin_rows.append([
                label,
                f"{qoq:+.1f}{unit}" if qoq is not None else "—",
                f"{yoy:+.1f}{unit}" if yoy is not None else "—",
            ])
        story.append(_data_table(["Metric", "QoQ", "YoY"], fin_rows, [content_w * 0.5, content_w * 0.25, content_w * 0.25]))
    else:
        story.append(Paragraph("No financial data available from screener.in for this stock.", muted_italic))
    story.append(Spacer(1, 14))

    # ---------------------------------------------------------------
    # Shareholding Pattern + Delivery % (mirrors the on-screen
    # "Shareholding & Delivery %" expander)
    # ---------------------------------------------------------------
    story.append(Paragraph("Shareholding Pattern (QoQ) — Promoter / FII / DII / Public", h2))
    filings = fetch_shareholding_filings(candidate.get("symbol", ""))
    if filings:
        srow = filings[0]

        def _sh_row(prefix, label):
            cur = srow.get(f"{prefix}_cur")
            prev = srow.get(f"{prefix}_prev")
            chg = srow.get(f"{prefix}_chg")
            if cur is None:
                return None
            arrow = "→"
            if chg is not None:
                arrow = "↑" if chg > 0 else ("↓" if chg < 0 else "→")
            return [label, f"{cur:.2f}%", f"{prev:.2f}%" if prev is not None else "—",
                    f"{chg:+.2f}%" if chg is not None else "—", arrow]

        sh_table_rows = [r for r in (
            _sh_row("promoter", "Promoter"), _sh_row("fii", "FII / FPI"),
            _sh_row("dii", "DII"), _sh_row("public", "Public"),
        ) if r is not None]
        if sh_table_rows:
            story.append(_data_table(
                ["Category", "Current %", "Previous Qtr %", "Change", "Trend"], sh_table_rows,
                [content_w * 0.25, content_w * 0.2, content_w * 0.22, content_w * 0.18, content_w * 0.15],
            ))
        else:
            story.append(Paragraph("Shareholding section found but no recognizable rows.", muted_italic))
    else:
        story.append(Paragraph("No shareholding data available from screener.in for this stock.", muted_italic))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Delivery %", h2))
    delivery_rows = fetch_delivery_history(candidate.get("symbol", ""), lookback_days=20, want_rows=10)
    if delivery_rows:
        latest_pct = delivery_rows[0].get("Delivery %")
        try:
            latest_pct = float(latest_pct) if latest_pct is not None else None
        except (TypeError, ValueError):
            latest_pct = None
        base_sym = candidate.get("symbol", "").replace(".NS", "").strip().upper()
        avg10_df = fetch_delivery_avg_all_symbols(trading_days_needed=10, lookback_days=20)
        avg10_row = avg10_df[avg10_df["Symbol"].astype(str).str.strip().str.upper() == base_sym]
        avg10_pct = float(avg10_row["Avg Delivery %"].iloc[0]) if not avg10_row.empty else None
        avgm_df = fetch_delivery_avg_all_symbols(trading_days_needed=22, lookback_days=40)
        avgm_row = avgm_df[avgm_df["Symbol"].astype(str).str.strip().str.upper() == base_sym]
        avgm_pct = float(avgm_row["Avg Delivery %"].iloc[0]) if not avgm_row.empty else None

        def _delta_suffix(base, ref):
            if base is None or ref is None:
                return ""
            d = base - ref
            sign = "+" if d >= 0 else ""
            return f"  ({sign}{d:.1f}%)"

        value_colors = {}
        pairs = [("Latest Delivery %", _fmt(latest_pct, "", "%", 1))]

        if avg10_pct is not None:
            pairs.append(("Last 10-Day Avg", _fmt(avg10_pct, "", "%", 1) + _delta_suffix(latest_pct, avg10_pct)))
            if latest_pct is not None:
                value_colors[1] = PDF_GREEN if latest_pct >= avg10_pct else PDF_RED
        else:
            pairs.append(("Last 10-Day Avg", "—"))

        if avgm_pct is not None:
            pairs.append(("Last Month Avg", _fmt(avgm_pct, "", "%", 1) + _delta_suffix(latest_pct, avgm_pct)))
            if latest_pct is not None:
                value_colors[2] = PDF_GREEN if latest_pct >= avgm_pct else PDF_RED
        else:
            pairs.append(("Last Month Avg", "—"))

        story.append(_metric_row(pairs, content_w / 3, value_colors=value_colors, value_size=11))
    else:
        story.append(Paragraph("No delivery data available for this stock.", muted_italic))
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
        if st.button("📄 Prepare PDF Report", key=f"pdfgen_{symbol}", use_container_width=True):
            with st.spinner("Building PDF (includes shareholding/financials/delivery — first time per stock takes a moment)..."):
                st.session_state[f"pdf_bytes_{symbol}"] = build_stock_report(c)
        pdf_bytes = st.session_state.get(f"pdf_bytes_{symbol}")
        if pdf_bytes:
            st.download_button(
                "⬇️ Download PDF Report", data=pdf_bytes,
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
        fin_col1, fin_col2 = st.columns([5, 1])
        fin_col1.caption("Auto-loads from screener.in (cached ~6 hours — repeat views are instant).")
        if fin_col2.button("🔄", key=f"fin_refresh_{symbol}", help="Force refresh (clears cached data for all stocks, not just this one)"):
            fetch_quarterly_yearly_financials.clear()

        with st.spinner("Fetching quarterly/annual financials from screener.in..."):
            fin_data = fetch_quarterly_yearly_financials(c["symbol"])

        if fin_data:
            fin_rows = []
            for label in ["EPS", "OPM", "Sales Growth", "PAT", "PBT", "EBITDA", "NET PROFIT", "CASH FLOW"]:
                m = fin_data.get(label, {})
                qoq, yoy = m.get("qoq"), m.get("yoy")
                unit = " pts" if label in _FIN_METRIC_IS_MARGIN else "%"
                fin_rows.append({
                    "Metric": label,
                    "QoQ": f"{qoq:+.1f}{unit}" if qoq is not None else "—",
                    "YoY": f"{yoy:+.1f}{unit}" if yoy is not None else "—",
                })
            st.dataframe(pd.DataFrame(fin_rows), use_container_width=True, hide_index=True)
            st.caption(
                "PAT and Net Profit are the same screener.in line item (shown as separate "
                "rows since both were requested). Cash Flow is only published annually on "
                "screener.in, so its QoQ is always '—'."
            )
        else:
            st.caption("No financial data returned from screener.in for this stock.")

    with st.expander("🏦 Shareholding & Delivery % (Screener.in + NSE — unofficial, best-effort)"):
        st.caption(
            "Promoter/FII/DII/Public holding is scraped from screener.in (simple "
            "HTML fetch, no bot-protection dance). Delivery % comes from "
            "nseindia.com via the `nse` package, which can be blocked/rate-limited "
            "on some hosts — retry if empty."
        )
        if not _NSE_LIB_AVAILABLE:
            st.warning("`nse` package not installed (needed for delivery % only). Run: `pip install nse` (and `pip install \"httpx[http2]\"` if deployed on a server/cloud host).")

        nse_col1, nse_col2 = st.columns([5, 1])
        nse_col1.caption("Auto-loads (cached ~6 hours — repeat views are instant; delivery % first-load can take a moment).")
        if nse_col2.button("🔄", key=f"nse_refresh_{symbol}", help="Force refresh (clears cached data for all stocks, not just this one)"):
            fetch_shareholding_filings.clear()
            fetch_delivery_history.clear()

        with st.spinner("Fetching from screener.in and nseindia.com (delivery % needs a few daily reports, may take a moment)..."):
            nse_cached = {
                "filings": fetch_shareholding_filings(c["symbol"]),
                "delivery": fetch_delivery_history(c["symbol"], lookback_days=20, want_rows=10),
            }

        if nse_cached:
            st.markdown("**Shareholding Pattern (QoQ) — Promoter / FII / DII / Public**")
            filings = nse_cached["filings"]
            if filings:
                row = filings[0]

                def _trend_row(prefix: str, label: str):
                    cur = row.get(f"{prefix}_cur")
                    prev = row.get(f"{prefix}_prev")
                    chg = row.get(f"{prefix}_chg")
                    if cur is None:
                        return None
                    arrow = "→"
                    if chg is not None:
                        arrow = "↑" if chg > 0 else ("↓" if chg < 0 else "→")
                    return {
                        "Category": label,
                        "Current %": cur,
                        "Previous Qtr %": prev if prev is not None else "—",
                        "Change": f"{chg:+.2f}%" if chg is not None else "—",
                        "Trend": arrow,
                    }

                sh_rows = [r for r in (
                    _trend_row("promoter", "Promoter"),
                    _trend_row("fii", "FII / FPI"),
                    _trend_row("dii", "DII"),
                    _trend_row("public", "Public"),
                ) if r is not None]

                if sh_rows:
                    st.dataframe(pd.DataFrame(sh_rows), use_container_width=True, hide_index=True)
                else:
                    st.caption("Shareholding section found but no recognizable Promoter/FII/DII/Public rows.")
            else:
                st.caption("No shareholding data returned.")

            st.markdown("**Delivery % (last 10 trading days)**")
            delivery_rows = nse_cached.get("delivery") or []
            if delivery_rows:
                dd = pd.DataFrame(delivery_rows)
                st.dataframe(dd, use_container_width=True, hide_index=True)
                try:
                    latest_pct = float(dd.iloc[0]["Delivery %"])
                    base_sym = c["symbol"].replace(".NS", "").strip().upper()

                    avg10_df = fetch_delivery_avg_all_symbols(trading_days_needed=10, lookback_days=20)
                    avg10_row = avg10_df[avg10_df["Symbol"].astype(str).str.strip().str.upper() == base_sym]
                    avg10_pct = float(avg10_row["Avg Delivery %"].iloc[0]) if not avg10_row.empty else None

                    avgm_df = fetch_delivery_avg_all_symbols(trading_days_needed=22, lookback_days=40)
                    avgm_row = avgm_df[avgm_df["Symbol"].astype(str).str.strip().str.upper() == base_sym]
                    avgm_pct = float(avgm_row["Avg Delivery %"].iloc[0]) if not avgm_row.empty else None

                    dcol1, dcol2, dcol3 = st.columns(3)
                    dcol1.metric("Latest Delivery %", f"{latest_pct:.1f}%")
                    if avg10_pct is not None:
                        dcol2.metric("Last 10-Day Avg", f"{avg10_pct:.1f}%", delta=f"{latest_pct - avg10_pct:+.1f}%")
                    else:
                        dcol2.metric("Last 10-Day Avg", "—")
                    if avgm_pct is not None:
                        dcol3.metric("Last Month Avg", f"{avgm_pct:.1f}%", delta=f"{latest_pct - avgm_pct:+.1f}%")
                    else:
                        dcol3.metric("Last Month Avg", "—")
                except Exception:
                    pass
                st.caption("Higher delivery % generally means more genuine (non-intraday) buying/selling interest, not just trading churn.")
            else:
                st.caption("No delivery data returned (report may not be published yet for recent sessions, or symbol/series mismatch).")

    st.markdown("#### 📝 Your Notes")
    note_val = st.text_area("Notes", value=get_note(symbol), key=f"note_{symbol}", label_visibility="collapsed")
    if st.button("Save note", key=f"savenote_{symbol}"):
        save_note(symbol, note_val)
        st.success("Note saved")


# ---------------------------- Sidebar navigation -----------------------
st.sidebar.title("📈 Stocks With Laxman")
st.sidebar.caption("Unified Engine — merged from both scanners")

# Apply any programmatic "jump to page X" request queued by a button elsewhere
# in the app. This MUST run before the radio widget below is instantiated —
# Streamlit forbids writing to a widget-bound session_state key afterward.
if "_pending_nav" in st.session_state:
    st.session_state["nav_page"] = st.session_state.pop("_pending_nav")

page = st.sidebar.radio("Navigate", ["🔍 Scanner", "⭐ Watchlist", "📢 Bulk/Block Deals", "📅 Seasonal Scanner", "ℹ️ About"], label_visibility="collapsed", key="nav_page")

st.sidebar.markdown("---")

@st.cache_data(show_spinner=False, ttl=60 * 60 * 6)
def get_lookup_symbols() -> List[str]:
    """Full pool of symbols used for the Quick lookup autocomplete.
    Tries to pull the complete NSE cash-segment list (1500+ stocks, so
    recently listed names like WAAREEENER / WAAREERTL are included too);
    falls back to the bundled full-NSE CSV (if present), then the built-in
    Nifty 500 list, if NSE blocks the live request."""
    live = get_universe_live("Full NSE Cash Segment (slow, 1500+ stocks)")
    if live:
        return sorted(set(t.replace(".NS", "") for t in live))
    bundled = load_bundled_full_list()
    if bundled:
        return sorted(set(t.replace(".NS", "") for t in bundled))
    return ALL_KNOWN_SYMBOLS


lookup = st.sidebar.text_input("Quick lookup (NSE symbol)", placeholder="e.g. RELIANCE")
if lookup.strip():
    query = lookup.strip().upper()
    lookup_pool = get_lookup_symbols()
    starts = sorted(s for s in lookup_pool if s.startswith(query))
    contains = sorted(s for s in lookup_pool if query in s and not s.startswith(query))
    suggestions = (starts + contains)[:8]
    if suggestions:
        st.sidebar.caption("Matching symbols — click to view:")
        for s in suggestions:
            if st.sidebar.button(s, key=f"suggest_{s}", use_container_width=True):
                st.session_state.selected_symbol = f"{s}.NS"
                st.session_state["_pending_nav"] = "🔍 Scanner"
                st.rerun()
    else:
        st.sidebar.caption("No matching symbols found.")
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
        "Universe", ["Nifty 50", "Nifty 200", "Nifty 500", "Full NSE Cash Segment (slow, 1500+ stocks)"], index=2,
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
    min_tech = st.sidebar.slider("Min technical score", 0, 100, 70)
    min_fund = st.sidebar.slider("Min fundamental score", 0, 100, 60)

    st.sidebar.markdown("**Market Cap range (₹ Crore)**")
    mc1, mc2 = st.sidebar.columns(2)
    min_mcap_input = mc1.number_input("Min", min_value=0, value=0, step=100, key="min_mcap_input", label_visibility="collapsed", placeholder="Min")
    max_mcap_input = mc2.number_input("Max (0 = no limit)", min_value=0, value=0, step=100, key="max_mcap_input", label_visibility="collapsed", placeholder="Max (0 = no limit)")
    st.sidebar.caption("e.g. Small cap < 5,000 Cr · Mid cap 5,000–20,000 Cr · Large cap > 20,000 Cr")

    top_n = st.sidebar.slider(
        "Show top N stocks", 1, 15, 5,
        help="Only the top N matches (by combined technical + fundamental score) will be shown. CSV export always includes every scanned match.",
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
                    "Could not fetch the live list from NSE (it often blocks automated requests, "
                    "especially from cloud hosting)."
                )
        if not tickers:
            bundled = load_bundled_list(universe_label)
            if bundled:
                tickers = bundled
                st.caption(f"📄 Using bundled {universe_label} list from `stock_lists/{BUNDLED_LIST_FILES[universe_label]}` ({len(bundled)} symbols).")
        if not tickers:
            tickers = get_universe(fallback_key)
            st.caption(
                f"⚠️ Falling back to the small built-in list ({len(tickers)} symbols) — "
                f"add `stock_lists/{BUNDLED_LIST_FILES.get(universe_label, 'all_nse_symbols.csv')}` to the repo for full coverage "
                "even when NSE blocks live fetch (see stock_lists/README.md)."
            )

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

        # CSV export always contains every scanned match, not just the top-N shown above
        df_all = pd.DataFrame([{
            "Symbol": r["base_symbol"], "Name": r["name"], "Sector": r["sector"],
            "Price (₹)": round(r["price"], 2), "Change %": round(r["change_pct"], 2),
            "Market Cap (₹ Cr)": round(r["market_cap"] / 1e7, 0) if r.get("market_cap") else None,
            "Tech Score": r["technical_score"], "Fund Score": r["fundamental_score"],
            "Setups": ", ".join(SETUP_LABELS.get(s, s) for s in (r.get("setups") or [r["setup_type"]])),
        } for r in all_results])
        csv_bytes = df_all.to_csv(index=False).encode("utf-8")
        st.download_button(
            f"⬇️ Export results to CSV ({len(all_results)} stock{'s' if len(all_results) != 1 else ''})",
            csv_bytes, "scan_results.csv", "text/csv",
        )

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

# ============================== BULK/BLOCK DEALS PAGE =====================
elif page == "📢 Bulk/Block Deals":
    st.title("Bulk & Block Deals / Delivery % — Last N Days")
    st.caption(
        "All bulk/block deals reported on NSE across every stock (not just your "
        "scan universe), via the `nse` package. Large trades here can hint at "
        "institutional accumulation or exit — cross-check before acting. Switch "
        "'Deal type' to Best Delivery % for a market-wide delivery leaderboard."
    )

    if not _NSE_LIB_AVAILABLE:
        st.warning("`nse` package not installed. Run: `pip install nse` (and `pip install \"httpx[http2]\"` if deployed on a server/cloud host).")
    else:
        fc1, fc2, fc3 = st.columns([1, 1, 2])
        days_back = fc1.selectbox("Period", [7, 15, 30, 60, 90, 180, 365], index=4, key="deals_days")
        deal_kind = fc2.selectbox("Deal type", ["Both", "Bulk only", "Block only", "Best Delivery %"], key="deals_kind")
        search_symbol = fc3.text_input("Filter by symbol (optional)", placeholder="e.g. RELIANCE", key="deals_search")

        min_qty = 0
        min_delivery_pct = 0
        if deal_kind == "Best Delivery %":
            dq1, dq2 = st.columns(2)
            min_qty = dq1.number_input(
                "Min traded qty (filters out illiquid stocks with misleading 100% delivery)",
                min_value=0, value=10000, step=5000, key="deals_min_qty",
            )
            min_delivery_pct = dq2.number_input(
                "Min Delivery % (e.g. 55 = only show stocks with 55%+ delivery)",
                min_value=0.0, max_value=100.0, value=55.0, step=5.0, key="deals_min_delivery_pct",
            )

        if st.button("🔄 Fetch deals", type="primary", key="fetch_all_deals_btn"):
            if deal_kind == "Best Delivery %":
                with st.spinner("Fetching latest NSE delivery report + 10-day/monthly averages (downloads up to ~40 daily reports the first time — later reruns reuse the cache and are much faster)..."):
                    st.session_state["all_deals_df"] = fetch_market_delivery_leaderboard(lookback_days=days_back)
                    st.session_state["all_deals_mode"] = "delivery"
            else:
                with st.spinner(f"Fetching bulk/block deals for the last {days_back} days (in date chunks to avoid NSE truncation — may take a bit longer)..."):
                    frames = []
                    if deal_kind in ("Both", "Bulk only"):
                        bdf = fetch_all_deals("bulk", days_back)
                        if not bdf.empty:
                            bdf.insert(1, "Type", "Bulk")
                            frames.append(bdf)
                    if deal_kind in ("Both", "Block only"):
                        kdf = fetch_all_deals("block", days_back)
                        if not kdf.empty:
                            kdf.insert(1, "Type", "Block")
                            frames.append(kdf)
                    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
                        columns=["Date", "Type", "Symbol", "Security", "Client", "Buy/Sell", "Qty", "Price"]
                    )
                    st.session_state["all_deals_df"] = combined
                    st.session_state["all_deals_mode"] = "deals"

        all_deals_df = st.session_state.get("all_deals_df")
        all_deals_mode = st.session_state.get("all_deals_mode", "deals")

        if all_deals_df is not None:
            display_df = all_deals_df.copy()
            if search_symbol.strip():
                q = search_symbol.strip().upper()
                display_df = display_df[display_df["Symbol"].astype(str).str.upper().str.contains(q, na=False)]

            if all_deals_mode == "delivery" and min_qty:
                display_df = display_df[display_df["Traded Qty"].fillna(0) >= min_qty]

            if all_deals_mode == "delivery" and min_delivery_pct:
                display_df = display_df[display_df["Delivery %"].fillna(0) >= min_delivery_pct]

            if display_df.empty:
                st.info("No data found for this period/filter.")
            elif all_deals_mode == "delivery":
                m1, m2, m3 = st.columns(3)
                m1.metric("Stocks with data", len(display_df))
                m2.metric("Avg Delivery %", f"{display_df['Delivery %'].mean():.1f}%")
                m3.metric("Max Delivery %", f"{display_df['Delivery %'].max():.1f}%")

                st.markdown("#### 🏆 Best delivery stocks (highest Delivery %)")
                top_counts = display_df.head(15)
                st.dataframe(top_counts, use_container_width=True, hide_index=True)

                st.markdown("#### All stocks (sorted by Delivery %)")
                sort_df = display_df.sort_values("Delivery %", ascending=False)
                st.dataframe(sort_df, use_container_width=True, hide_index=True, height=420)

                csv_bytes = sort_df.to_csv(index=False).encode("utf-8")
                st.download_button("⬇️ Download as CSV", csv_bytes, file_name="best_delivery_stocks.csv", mime="text/csv")

                st.caption("Tap a symbol below to jump to its full scan/detail view (technical + fundamental + shareholding).")
                unique_syms = sort_df["Symbol"].dropna().unique().tolist()
                pick_cols = st.columns(6)
                for i, sym in enumerate(unique_syms[:24]):
                    if pick_cols[i % 6].button(sym, key=f"deal_view_{sym}", use_container_width=True):
                        st.session_state.selected_symbol = f"{sym}.NS"
                        st.session_state["_pending_nav"] = "🔍 Scanner"
                        st.rerun()
                if len(unique_syms) > 24:
                    st.caption(f"...and {len(unique_syms) - 24} more (use the symbol filter above to narrow down).")
            else:
                m1, m2, m3 = st.columns(3)
                m1.metric("Total deals", len(display_df))
                m2.metric("Unique stocks", display_df["Symbol"].nunique())
                m3.metric("Buy vs Sell", f"{(display_df['Buy/Sell'].astype(str).str.upper() == 'BUY').sum()} / {(display_df['Buy/Sell'].astype(str).str.upper() == 'SELL').sum()}")

                st.markdown("#### Most active stocks (by number of deals)")
                top_counts = (
                    display_df.groupby("Symbol")
                    .size()
                    .reset_index(name="Deal Count")
                    .sort_values("Deal Count", ascending=False)
                    .head(15)
                )
                st.dataframe(top_counts, use_container_width=True, hide_index=True)

                st.markdown("#### All deals")
                sort_df = display_df.sort_values("Date", ascending=False)
                st.dataframe(sort_df, use_container_width=True, hide_index=True, height=420)

                csv_bytes = sort_df.to_csv(index=False).encode("utf-8")
                st.download_button("⬇️ Download as CSV", csv_bytes, file_name=f"bulk_block_deals_{days_back}d.csv", mime="text/csv")

                st.caption("Tap a symbol below to jump to its full scan/detail view (technical + fundamental + shareholding).")
                unique_syms = sorted(display_df["Symbol"].dropna().unique().tolist())
                pick_cols = st.columns(6)
                for i, sym in enumerate(unique_syms[:24]):
                    if pick_cols[i % 6].button(sym, key=f"deal_view_{sym}", use_container_width=True):
                        st.session_state.selected_symbol = f"{sym}.NS"
                        st.session_state["_pending_nav"] = "🔍 Scanner"
                        st.rerun()
                if len(unique_syms) > 24:
                    st.caption(f"...and {len(unique_syms) - 24} more (use the symbol filter above to narrow down).")
        else:
            st.info("Click **Fetch deals** to load data for the selected period.")


elif page == "📅 Seasonal Scanner":
    st.title("📅 Seasonal Date-Range Scanner")
    st.caption(
        "Ek date-range (sirf din-mahina, saal matter nahi) daalo — app pichhle N saal "
        "ka data scan karke batayega kaunse stocks ne us range me consistently profit diya, "
        "Accuracy % (win-rate) ke saath."
    )

    with st.form("seasonal_scan"):
        c1, c2 = st.columns(2)
        universe_label = c1.selectbox(
            "Universe",
            ["Nifty 50", "Nifty 200", "Nifty 500", "Full NSE Cash Segment (slow, 1500+ stocks)", "Custom List"],
            index=2,
        )
        custom_syms = []
        if universe_label == "Custom List":
            custom_syms = c2.multiselect("Pick symbols", ALL_KNOWN_SYMBOLS)
            use_live_nse = False
        else:
            use_live_nse = c2.checkbox(
                "Fetch live list from NSE", value=True,
                help="Downloads the current constituent list directly from nseindia.com. "
                     "Falls back to the built-in list if NSE blocks the request.",
            )

        d1, d2, d3, d4 = st.columns(4)
        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                       "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        today_date = date.today()
        default_end = today_date + timedelta(days=30)
        DUMMY_YEAR = 2024  # leap year, so 29 Feb stays selectable; year itself is ignored everywhere

        from_month = d1.selectbox("From month", month_names, index=today_date.month - 1)
        from_day = d2.number_input("From day", min_value=1, max_value=31, value=today_date.day, step=1)
        to_month = d3.selectbox("To month", month_names, index=default_end.month - 1)
        to_day = d4.number_input("To day", min_value=1, max_value=31, value=default_end.day, step=1)

        start_input = _safe_date(DUMMY_YEAR, month_names.index(from_month) + 1, int(from_day))
        end_input = _safe_date(DUMMY_YEAR, month_names.index(to_month) + 1, int(to_day))

        s1, s2, s3 = st.columns(3)
        years_back = s1.slider("Pichhle kitne saal scan karein?", 3, 20, 15)
        min_years_required = s2.slider("Minimum saal ka data chahiye", 1, 20, 5)
        min_accuracy = s3.slider("Minimum Accuracy %", 0, 100, 80)

        submitted = st.form_submit_button("🔍 Scan Karo", type="primary", use_container_width=True)

    cache_status = seasonal_cache_status()
    cache_col1, cache_col2 = st.columns([3, 1])
    with cache_col1:
        if cache_status["count"] > 0:
            st.caption(
                f"📦 Local cache: **{cache_status['count']} symbol(s)** saved | "
                f"oldest: {cache_status['oldest'].strftime('%d-%b-%Y')} | "
                f"newest: {cache_status['newest'].strftime('%d-%b-%Y')} "
                f"(auto-refreshes after {SEASONAL_CACHE_MAX_AGE_DAYS} din)"
            )
        else:
            st.caption("📦 Local cache abhi khali hai — pehle scan ke baad yahan data save hoga.")
    with cache_col2:
        refresh_all_clicked = st.button(
            "🔄 Refresh All Cached Data", use_container_width=True,
            disabled=cache_status["count"] == 0,
            help="Cache me jitne bhi symbols saved hain, sabka latest data yfinance se dobara download karke overwrite karega.",
        )

    if refresh_all_clicked:
        refresh_progress = st.progress(0.0, text="Cached data refresh ho raha hai...")

        def _update_refresh_progress(frac):
            refresh_progress.progress(frac, text=f"Cached data refresh ho raha hai... {int(frac * 100)}%")

        refreshed_count = seasonal_refresh_all_cached(years_back, progress_cb=_update_refresh_progress)
        refresh_progress.empty()
        st.success(f"✅ {refreshed_count}/{cache_status['count']} symbol(s) ka data refresh ho gaya.")
        st.rerun()

    if submitted:
        fallback_key = {
            "Nifty 50": "nifty50", "Nifty 200": "nifty200",
            "Nifty 500": "nifty500", "Full NSE Cash Segment (slow, 1500+ stocks)": "nifty500",
        }
        if universe_label == "Custom List":
            if not custom_syms:
                st.error("Custom List me kam se kam ek symbol chuno.")
                st.stop()
            tickers = _add_suffix(custom_syms)
        else:
            tickers = None
            if use_live_nse:
                with st.spinner(f"Fetching latest {universe_label} list from nseindia.com..."):
                    tickers = get_universe_live(universe_label)
                if not tickers:
                    st.warning(
                        "Could not fetch the live list from NSE (it often blocks automated requests, "
                        "especially from cloud hosting)."
                    )
            if not tickers:
                bundled = load_bundled_list(universe_label)
                if bundled:
                    tickers = bundled
                    st.caption(f"📄 Using bundled {universe_label} list from `stock_lists/{BUNDLED_LIST_FILES[universe_label]}` ({len(bundled)} symbols).")
            if not tickers:
                tickers = get_universe(fallback_key[universe_label])
                st.caption(
                    f"⚠️ Falling back to the small built-in list ({len(tickers)} symbols) — "
                    f"add `stock_lists/{BUNDLED_LIST_FILES.get(universe_label, 'all_nse_symbols.csv')}` to the repo for full coverage "
                    "even when NSE blocks live fetch (see stock_lists/README.md)."
                )

        min_years_required = min(min_years_required, years_back)
        start_md = (start_input.month, start_input.day)
        end_md = (end_input.month, end_input.day)

        st.info(
            f"Scanning **{len(tickers)} stock(s)** ({universe_label}) | Date range: "
            f"**{start_input.strftime('%d %b')} → {end_input.strftime('%d %b')}** | "
            f"Last **{years_back} years** | Min accuracy: **{min_accuracy}%**"
        )

        progress_bar = st.progress(0.0, text="Price data load ho raha hai...")
        summary_rows, detail_store = [], {}

        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = {ex.submit(seasonal_fetch_history, tkr, years_back): tkr for tkr in tickers}
            done = 0
            for fut in as_completed(futures):
                tkr = futures[fut]
                sym = tkr.replace(".NS", "")
                done += 1
                progress_bar.progress(done / len(tickers), text=f"Price data load ho raha hai... {done}/{len(tickers)}")
                try:
                    df = fut.result()
                except Exception:
                    df = None
                if df is None or df.empty:
                    continue
                yearly_df = seasonal_scan_one_stock(df, start_md, end_md, years_back)
                detail_store[sym] = yearly_df
                summ = seasonal_summarize_symbol(sym, yearly_df)
                if summ and summ["Years Analyzed"] >= min_years_required:
                    summary_rows.append(summ)

        progress_bar.empty()

        if not summary_rows:
            st.warning(
                "Koi bhi stock minimum years/data requirement pura nahi kar paya. "
                "'Minimum years' ya scan depth kam karke try karo."
            )
            st.session_state["seasonal_scan_result"] = None
        else:
            result_df = pd.DataFrame(summary_rows)
            # Store everything needed to re-render the results in session_state so
            # it survives reruns triggered by the "jump to detail" buttons below
            # (a plain `if submitted:` block resets on every other widget click).
            st.session_state["seasonal_scan_result"] = {
                "result_df": result_df,
                "detail_store": detail_store,
                "min_accuracy": min_accuracy,
                "start_label": start_input.strftime("%d%b"),
                "end_label": end_input.strftime("%d%b"),
            }

    stored = st.session_state.get("seasonal_scan_result")
    if stored is None:
        st.info("⬆️ Universe, date-range, aur accuracy % set karke **'Scan Karo'** button dabao.")
    else:
        result_df = stored["result_df"]
        detail_store = stored["detail_store"]
        min_accuracy = stored["min_accuracy"]
        filtered_df = result_df[result_df["Accuracy %"] >= min_accuracy].sort_values(
            ["Accuracy %", "Avg Return %"], ascending=[False, False]
        ).reset_index(drop=True)

        st.subheader(
            f"📊 Results — {len(filtered_df)} stock(s) with Accuracy ≥ {min_accuracy}% "
            f"(out of {len(result_df)} analyzed)"
        )

        if filtered_df.empty:
            st.warning(f"Is accuracy threshold ({min_accuracy}%) par koi stock match nahi hua. Slider se threshold kam karke dekho.")
        else:
            st.dataframe(
                filtered_df, use_container_width=True, hide_index=True,
                column_config={
                    "Accuracy %": st.column_config.ProgressColumn("Accuracy %", min_value=0, max_value=100, format="%.1f%%"),
                },
            )

            csv_bytes = filtered_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Download CSV", data=csv_bytes,
                file_name=f"seasonal_scan_{stored['start_label']}_{stored['end_label']}.csv",
                mime="text/csv",
            )

            st.caption("Tap a symbol below to jump to its full scan/detail view (technical + fundamental + shareholding).")
            unique_syms = filtered_df["Symbol"].dropna().unique().tolist()
            pick_cols = st.columns(6)
            for i, sym in enumerate(unique_syms[:24]):
                if pick_cols[i % 6].button(sym, key=f"seasonal_view_{sym}", use_container_width=True):
                    st.session_state.selected_symbol = f"{sym}.NS"
                    st.session_state["_pending_nav"] = "🔍 Scanner"
                    st.rerun()
            if len(unique_syms) > 24:
                st.caption(f"...and {len(unique_syms) - 24} more (use the accuracy/date filters above to narrow down).")

            st.divider()
            st.subheader("🔎 Year-by-Year Detail")
            pick = st.selectbox("Stock chuno detail dekhne ke liye:", filtered_df["Symbol"].tolist())
            if pick:
                yd = detail_store[pick].sort_values("Year", ascending=False)

                def _color_profit(v):
                    return "color: green" if v is True else ("color: red" if v is False else "")

                try:
                    styled = yd.style.map(_color_profit, subset=["Profit"])
                except AttributeError:
                    styled = yd.style.applymap(_color_profit, subset=["Profit"])
                st.dataframe(styled, use_container_width=True, hide_index=True)

        with st.expander("📋 Full analysis (sabhi stocks, accuracy filter ke bina)"):
            st.dataframe(result_df.sort_values("Accuracy %", ascending=False), use_container_width=True, hide_index=True)

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
