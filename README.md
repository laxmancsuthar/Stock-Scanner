# Bundled Full NSE Symbol List (optional, but recommended for cloud hosting)

By default this app tries to fetch the live "Full NSE Cash Segment" list
(2500+ symbols) directly from nseindia.com. This usually works fine when
you run the app on your own laptop, but **NSE blocks requests from cloud
server IPs** (Streamlit Community Cloud, AWS, Render, etc.), so on a
deployed app this live fetch will often fail and the app falls back to a
small built-in list of ~294 stocks.

To get full 2500+ coverage even when deployed, download the official list
**once from your own browser** (browsers aren't blocked) and commit it to
this repo. The app will automatically use it as a fallback whenever the
live fetch fails — no code changes needed.

## Steps

1. Go to: https://www.nseindia.com/market-data/securities-available-for-trading
2. On that page there are **two similarly-named CSV files** — make sure you
   pick the right one:
   - ❌ "Securities available for trading in **SME** (.csv)" (~33 KB) — this
     is the small SME segment (~500 stocks). **Not this one.**
   - ✅ **"Securities available for **Equity segment** (.csv)"** (~147 KB) —
     this is the main board with **2500+ stocks**. **This is the one you want.**
   - Direct link (works in a normal browser, not from cloud/bots):
     `https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv`
3. Rename the downloaded file to exactly: `all_nse_symbols.csv`
4. Place it in this folder, so the final path is:
   ```
   stock_lists/all_nse_symbols.csv
   ```
5. Commit and push it to GitHub along with the rest of the app.

That's it. On the next scan, whenever NSE's live fetch is blocked, the app
will automatically pick up this bundled file instead of the small built-in
list, and you'll see a caption like:

> 📄 Using bundled full NSE list from `stock_lists/all_nse_symbols.csv` (2500+ symbols).

## Keeping it up to date

NSE adds/removes listings occasionally. Repeat the steps above (re-download
and overwrite `all_nse_symbols.csv`, then commit) every few months, or
whenever you notice a recently-listed stock is missing from scan results.

## Notes

- This file is **not required** — the app works fine without it, just with
  the smaller ~294-stock built-in fallback list when NSE blocks live fetch.
- The file is excluded from `.gitignore`'s runtime-data rules — it's meant
  to be committed, unlike `price_cache/` and `data.json`.
