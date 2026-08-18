# Swing Trade Screener Pro (Streamlit)

Yeh ek Streamlit app hai jo NSE-listed stocks (Nifty 50 / 100 / 200 / 500) ko
swing-trade setups ke liye scan karta hai. Isme ek unified **technical score**
(0-100) aur **fundamental score** (ROE, growth, margins, debt, liquidity) diya
jaata hai, saath hi watchlist, notes, position-sizing calculator aur PDF report
export jaisi features bhi hain.

> ⚠️ Yeh app sirf educational/research purpose ke liye hai. **Investment advice
> nahi hai.** Trade lene se pehle apni khud ki research karein ya SEBI-registered
> advisor se consult karein.

## Features

- **Scanner**: Nifty 50/100/200/500 (ya NSE se live ticker list) scan karke
  swing-trade setups dhoondta hai (breakout, momentum, RSI divergence,
  candlestick patterns, etc.)
- **Technical Engine (0-100)**: EMA/SMA trend, RSI, MACD, Stochastic, ATR,
  Bollinger Bands + squeeze, ADX/DI, volume confirmation, VWAP, breakout state
  machine, candlestick patterns, weekly/monthly confluence
- **Fundamental Score**: ROE, growth, margins, debt, liquidity (Yahoo Finance
  data ke basis par)
- **Stock Detail View**: Interactive candlestick chart (Plotly) with indicators
- **Watchlist & Notes**: Session me aur `data.json` file me locally persist
  hota hai
- **Position Sizing Calculator**: Risk % ke hisaab se kitne shares kharidne hai
- **PDF Report Export**: ReportLab se professional PDF report banata hai
- **CSV Export**: Scan results ko CSV me download karein

## Requirements

- Python 3.9+
- Internet connection (Yahoo Finance se live data fetch karne ke liye)

## Installation

```bash
# 1) (Optional but recommended) Virtual environment banayein
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 2) Dependencies install karein
pip install -r requirements.txt
```

## Run kaise karein

```bash
streamlit run swing_trade_screener_streamlit.py
```

Browser automatically `http://localhost:8501` par khul jaayega. Agar nahi
khulta, to manually us URL ko open kar lein.

## File Structure

```
.
├── swing_trade_screener_streamlit.py   # Main app
├── requirements.txt                     # Python dependencies
├── README.md                            # Yeh file
└── data.json                            # Auto-generated — watchlist/notes/history
                                          # save karne ke liye (pehli run ke baad banta hai)
```

## Notes

- **Data Source**: Saara price/fundamental data [`yfinance`](https://pypi.org/project/yfinance/)
  library se aata hai, jo Yahoo Finance ko query karta hai. Prices delayed ho
  sakte hain.
- **Live NSE List**: Agar app me "live NSE list" fetch karne ka option select
  karte hain, to `nseindia.com` ko directly query kiya jaata hai — yeh site
  automated requests ko block kar sakti hai, aisi situation me app automatically
  built-in ticker list use kar leta hai.
- **Persistence**: Watchlist, notes aur scan history `data.json` (script ke
  same folder me) me save hote hain, taaki app restart karne par bhi data safe
  rahe.
- **Large Universe Scans**: "Full NSE" (1500+ stocks) scan karne me kaafi time
  lag sakta hai kyunki har stock ke liye Yahoo Finance se data fetch hota hai
  (multi-threaded hai, par phir bhi slow ho sakta hai on free/rate-limited
  connections).

## Troubleshooting

| Problem | Solution |
|---|---|
| `ModuleNotFoundError` | `pip install -r requirements.txt` dobara chalayein |
| Scan bahut slow hai | Chhoti universe select karein (Nifty 50 ya 100) |
| Live NSE fetch fail ho raha hai | Normal hai — NSE bots ko block karta hai; app fallback list use kar lega |
| PDF export me error | `reportlab` aur `matplotlib` sahi se installed hain, verify karein |
