# Bundled NSE Symbol Lists (optional, but recommended for cloud hosting)

By default this app tries to fetch the current constituent list for
whichever universe you pick (Nifty 50 / Nifty 200 / Nifty 500 / Full NSE
Cash Segment) live from NSE. This usually works fine when you run the app
on your own laptop, but **NSE blocks requests from cloud server IPs**
(Streamlit Community Cloud, AWS, Render, etc.), so on a deployed app this
live fetch will often fail — the app then falls back to a small built-in
list (~294 stocks) that isn't a complete/accurate match for any of these
universes.

To get full, accurate coverage even when deployed, download each list
**once from your own browser** (browsers aren't blocked, only bots/cloud
IPs are) and commit the files to this repo. The app automatically picks
these up as a fallback whenever the live fetch fails — no code changes
needed.

## Files to add (add as many as you want — each is independent)

| Universe | Save as | Where to download |
|---|---|---|
| Nifty 50 | `stock_lists/nifty50.csv` | https://www.niftyindices.com/IndexConstituent/ind_nifty50list.csv |
| Nifty 200 | `stock_lists/nifty200.csv` | https://www.niftyindices.com/IndexConstituent/ind_nifty200list.csv |
| Nifty 500 | `stock_lists/nifty500.csv` | https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv |
| Full NSE Cash Segment (2500+ stocks) | `stock_lists/all_nse_symbols.csv` | See note below — different page |

For Nifty 50 / 200 / 500: just open the link in your browser — it downloads
the CSV directly. Rename it to the filename in the table above and drop it
in this `stock_lists/` folder.

### Full NSE Cash Segment (2500+ stocks) — different page, watch out for a mix-up

1. Go to: https://www.nseindia.com/market-data/securities-available-for-trading
2. This page has **two similarly-named CSV files** — pick the right one:
   - ❌ "Securities available for trading in **SME** (.csv)" (~33 KB) — small
     SME segment only (~500 stocks). **Not this one.**
   - ✅ **"Securities available for Equity segment (.csv)"** (~147 KB) — main
     board, **2500+ stocks**. **This is the one you want.**
   - Direct link: `https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv`
3. Rename it to `all_nse_symbols.csv` and place it in this folder.

## After adding files

Commit and push to GitHub along with the rest of the app. On the next scan,
whenever NSE's live fetch is blocked for that universe, the app will
automatically pick up the matching bundled file instead of the small
built-in list, and you'll see a caption like:

> 📄 Using bundled Nifty 500 list from `stock_lists/nifty500.csv` (500 symbols).

Any universe without a bundled file just falls back to the small built-in
list as before — nothing breaks if you only add some of these.

## Keeping it up to date

NSE rebalances these indices every few months (adds/removes constituents).
Repeat the download-and-commit steps periodically, or whenever you notice a
stock that should be in an index (or shouldn't be) is off.

## Notes

- None of these files are required — the app works without them, just with
  the smaller built-in fallback list when NSE blocks live fetch.
- These files are meant to be committed to git (unlike `price_cache/` and
  `data.json`, which `.gitignore` excludes since those are runtime-only).
