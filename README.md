
# Macro Market Dashboard (v1)

A Streamlit app that aggregates free, near-real-time macro-market indicators and renders a clean, modern dashboard.

## Features
- Market Overview tiles: S&P 500 TTM P/E, Shiller CAPE, Buffett Indicator (optional local proxy), Margin Debt YoY, SPY Top-10 concentration, Sentiment proxy (VIX, Put/Call, HY OAS)
- Asset Browser with trend lens: 50/200-DMA, RSI(14), drawdown
- Valuation Detail with long-run charts and thresholds
- Signals page with matrix-based guidance (educational only)
- Caching with sensible TTLs; graceful fail-soft if a source is down

## Data Sources (free)
- Stooq (CSV) with Yahoo CSV fallback for prices
- Yale/Shiller monthly XLS
- FRED CSV for GDP, HY OAS, 2Y/10Y
- FINRA monthly XLS (multiple candidate URLs tried)
- SPY holdings daily CSV (State Street)
- CBOE VIX historical CSV, Put/Call CSV
- CoinGecko public API (no key)

## Local Buffett proxy (optional)
Create `data/wilshire_5000_proxy.csv` with columns:
```
date,market_cap,gdp
2020-12-31,40000000000000,21000000000000
2021-12-31,47000000000000,23000000000000
...
```
The app will plot and tile the Buffett Indicator if present.

## Run locally
```
pip install -r requirements.txt
streamlit run app.py
```

## Tests
```
python -m pytest -q
```
Tests are minimal and offline (no network calls).

## Deployment
- Push this folder to GitHub
- Deploy on Streamlit Community Cloud (streamlit.io)
