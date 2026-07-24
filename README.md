# Swing Trade Screener — Auto Scan

⚠️ Research/screening tool hai, financial advice nahi.

## Setup
```bash
pip install -r requirements.txt
```

## Use karo
```bash
streamlit run app.py
```

Browser khulega:
1. Top pe "🔍 Auto scan" mode already selected hoga
2. Universe choose karo — Nifty 50 (fast) / Nifty 200 / Nifty 500 / Full NSE Cash Segment (slowest)
3. "Scan Shuru Karo" dabao
4. Top 5 candidates result me dikhenge — technical reasons, risk-reward, fundamentals, red flags sab ke saath

## Kaise kaam karta hai (2-stage scan)
1. **Stage 1 (fast):** Chose universe ke saare stocks pe batch me technical scan — trend (daily+weekly),
   EMA, RSI, MACD crossover, Bollinger Bands, volume confirmation, resistance breakout.
2. **Stage 2 (targeted):** Sirf top technically-strong 20-30 stocks ka fundamentals + red-flag check
   (poore universe ka karna bahut slow hota, isliye ye funnel approach hai).

## Time lagega kitna
- Nifty 50: ~1-2 min
- Nifty 200: ~3-5 min
- Nifty 500: ~8-12 min
- Full NSE Cash Segment (1500+ stocks): ~25-40 min (patience rakhna)

## Notes
- NSE ki site kabhi-kabhi automated requests block kar deti hai — agar universe list load na ho to
  thodi der baad try karo.
- Upcoming results/corporate action jaisi news ye tool automatically nahi check karta — khud verify kar lena.
- Chart pattern/technical signals heuristic hain, guarantee nahi.
