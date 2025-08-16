
# app.py
from __future__ import annotations
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import streamlit as st

from settings import APP_TITLE, APP_TAGLINE, ASSETS, THRESHOLDS, TTL
from indicators import (
    compute_ttm_pe, compute_cape, compute_buffett_indicator, compute_margin_debt_yoy,
    compute_concentration_top10, compute_sentiment_proxy, compute_asset_trend, guidance_label
)
from ui_components import series_tile, price_panel, overall_strip, data_health


st.set_page_config(page_title=APP_TITLE, page_icon="📊", layout="wide")

# --- Styles ---
st.markdown("""
<style>
/* Rounded charts */
.css-1kyxreq { border-radius: 12px!important; }
/* Gradient headers */
h1, h2, h3, h4 { letter-spacing: 0.2px; }
</style>
""", unsafe_allow_html=True)

st.title(APP_TITLE)
st.caption(APP_TAGLINE)

# Sidebar navigation
page = st.sidebar.radio("Navigate", ["Market Overview", "Asset Browser", "Valuation Detail", "Signals", "Sources"])

# Cache wrappers
@st.cache_data(ttl=int(TTL["stooq_daily"].total_seconds()))
def _ttm_pe_cached():
    return compute_ttm_pe()

@st.cache_data(ttl=int(TTL["shiller_monthly"].total_seconds()))
def _cape_cached():
    return compute_cape()

@st.cache_data(ttl=int(TTL["finra_monthly"].total_seconds()))
def _margin_cached():
    return compute_margin_debt_yoy()

@st.cache_data(ttl=int(TTL["holdings_daily"].total_seconds()))
def _concentration_cached():
    return compute_concentration_top10()

@st.cache_data(ttl=int(TTL["cboe_daily"].total_seconds()))
def _sentiment_cached():
    return compute_sentiment_proxy()

@st.cache_data(ttl=int(TTL["fred_quarterly"].total_seconds()))
def _buffett_cached():
    return compute_buffett_indicator()

@st.cache_data(ttl=int(TTL["stooq_daily"].total_seconds()))
def _trend_cached(pref, fallback):
    return compute_asset_trend(pref, fallback)


def color_to_score(color: str) -> int:
    return {"green": 0, "yellow": 1, "red": 2, "grey": 1}.get(color, 1)


if page == "Market Overview":
    st.subheader("Top Tiles")
    col1, col2, col3 = st.columns(3)
    col4, col5, col6 = st.columns(3)

    pe = _ttm_pe_cached()
    cape = _cape_cached()
    buffett = _buffett_cached()
    margin = _margin_cached()
    conc = _concentration_cached()
    sent = _sentiment_cached()

    with col1:
        series_tile("S&P 500 TTM P/E", pe, "{:.1f}")
    with col2:
        series_tile("Shiller CAPE", cape, "{:.1f}")
    with col3:
        v = buffett.copy()
        if v.get("value") is not None:
            v["value"] = v["value"] * 100.0
        series_tile("Buffett Indicator", v, "{:.0f}%")
    with col4:
        v = margin.copy()
        if v.get("value") is not None:
            v["value"] = v["value"] * 100.0
        series_tile("Margin Debt (YoY)", v, "{:.1f}%")
    with col5:
        v = conc.copy()
        if v.get("value") is not None:
            v["value"] = v["value"] * 100.0
        series_tile("Concentration: SPY Top-10 Weight", v, "{:.1f}%")
    with col6:
        series_tile("Sentiment (Greed proxy 0–100)", sent, "{:.0f}")

    # Overall strip
    valuation_colors = [pe["color"], cape["color"], buffett["color"], margin["color"], conc["color"], sent["color"]]
    # Valuation lens uses the first five; sentiment is kept but lower weight
    val_score = np.mean([color_to_score(c) for c in [pe["color"], cape["color"], buffett["color"], margin["color"], conc["color"]]])
    valuation_color = "green" if val_score < 0.67 else ("yellow" if val_score < 1.34 else "red")

    # Trend lens = S&P 500 default
    trend = _trend_cached("^spx", "^GSPC")
    trend_color = trend.get("trend_color", "yellow")

    overall_strip(valuation_color, trend_color)

    st.divider()
    st.subheader("Data Health")
    data_health([
        {"name":"TTM P/E","last":pe.get("last_updated"),"source":pe.get("source"),"value":pe.get("value")},
        {"name":"CAPE","last":cape.get("last_updated"),"source":cape.get("source"),"value":cape.get("value")},
        {"name":"Buffett","last":buffett.get("last_updated"),"source":buffett.get("source"),"value":buffett.get("value")},
        {"name":"Margin debt YoY","last":margin.get("last_updated"),"source":margin.get("source"),"value":margin.get("value")},
        {"name":"SPY Top-10","last":conc.get("last_updated"),"source":conc.get("source"),"value":conc.get("value")},
        {"name":"Sentiment proxy","last":sent.get("last_updated"),"source":sent.get("source"),"value":sent.get("value")},
    ])


elif page == "Asset Browser":
    st.sidebar.markdown("### Filters")
    region = st.sidebar.selectbox("Region / Asset Class", list(ASSETS.keys()), index=0)
    instrument = st.sidebar.selectbox("Instrument", list(ASSETS[region].keys()), index=0)

    st.subheader(f"{region} · {instrument}")
    meta = ASSETS[region][instrument]
    pref = meta.get("stooq") or meta.get("fred") or meta.get("coingecko")
    fallback = meta.get("yahoo") or pref

    if "fred" in meta:
        # Simple plot from FRED series
        import altair as alt
        from data_sources import fred_series
        df = fred_series(meta["fred"])
        if df is None:
            st.warning("No data available from FRED.")
        else:
            st.altair_chart(alt.Chart(df).mark_line().encode(x="date:T", y="value:Q"), use_container_width=True)
    elif "coingecko" in meta:
        from data_sources import coingecko_markets
        df = coingecko_markets([meta["coingecko"]])
        if df is None or df.empty:
            st.warning("No data from CoinGecko.")
        else:
            item = df.iloc[0]
            cols = st.columns(3)
            with cols[0]: st.metric("Price (USD)", f"{item['current_price']:,}")
            with cols[1]: st.metric("24h %", f"{item['price_change_percentage_24h']:.2f}%")
            with cols[2]: st.metric("7d %", f"{item['price_change_percentage_7d_in_currency']:.2f}%")
    else:
        trend = _trend_cached(pref, fallback)
        price_panel(instrument, trend)

elif page == "Valuation Detail":
    st.subheader("Valuation Metrics")
    pe = compute_ttm_pe()
    cape = compute_cape()
    buffett = compute_buffett_indicator()
    margin = compute_margin_debt_yoy()
    conc = compute_concentration_top10()
    sent = compute_sentiment_proxy()

    def plot_series(title, dct, fmt):
        series = dct.get("series")
        value = dct.get("value")
        source = dct.get("source","")
        if series is None or series.empty:
            st.warning(f"{title}: no data")
            return
        import altair as alt
        df = series.to_frame(name="value").reset_index()
        st.markdown(f"**{title}** — current: {fmt.format(value) if value is not None else '—'}  \n*Source: {source}*")
        st.altair_chart(alt.Chart(df).mark_line().encode(x="date:T", y="value:Q"), use_container_width=True)

    plot_series("S&P 500 TTM P/E", pe, "{:.1f}")
    plot_series("Shiller CAPE", cape, "{:.1f}")
    # Buffett ratio plotted only if present
    if buffett.get("series") is not None:
        plot_series("Buffett Indicator (Market Cap / GDP)", buffett, "{:.2f}")
    else:
        st.info("Buffett Indicator: add a local CSV at `data/wilshire_5000_proxy.csv` with columns `date, market_cap, gdp` to enable chart.")
    plot_series("Margin Debt YoY", {"series": margin.get("series"), "value": margin.get("value"), "source": margin.get("source")}, "{:.2%}")
    st.markdown("---")
    # Concentration is a point estimate today; show only current value
    v = conc.get("value")
    st.markdown(f"**Concentration (SPY Top-10 weight):** {v*100:.1f}% — *Source: {conc.get('source')}*" if v is not None else "Concentration: data missing.")
    st.markdown("---")
    plot_series("Sentiment (Greed proxy 0–100)", sent, "{:.0f}")

elif page == "Signals":
    st.subheader("Signals")
    pe = compute_ttm_pe()
    cape = compute_cape()
    buffett = compute_buffett_indicator()
    margin = compute_margin_debt_yoy()
    conc = compute_concentration_top10()
    sent = compute_sentiment_proxy()
    trend = compute_asset_trend("^spx", "^GSPC")

    # Valuation and trend composite
    def color_to_score(color: str) -> int:
        return {"green": 0, "yellow": 1, "red": 2, "grey": 1}.get(color, 1)

    val_score = np.mean([color_to_score(c) for c in [pe["color"], cape["color"], buffett["color"], margin["color"], conc["color"]]])
    valuation_color = "green" if val_score < 0.67 else ("yellow" if val_score < 1.34 else "red")
    trend_color = trend.get("trend_color", "yellow")

    st.metric("Valuation lens", valuation_color.title())
    st.metric("Trend lens", trend_color.title())
    st.markdown(f"**Guidance (matrix-based):** {guidance_label(valuation_color, trend_color)}")
    st.caption("This is a rules-based, educational illustration — not investment advice.")

elif page == "Sources":
    st.subheader("Sources")
    st.markdown("""
- **Prices:** Stooq (CSV) with Yahoo as fallback  
- **Shiller CAPE & earnings:** Yale/Shiller (monthly XLS)  
- **US GDP (Nominal):** FRED (CSV)  
- **Wilshire 5000 proxy:** local CSV (optional)  
- **Margin debt:** FINRA (monthly XLS)  
- **SPY holdings (Top-10):** State Street daily holdings CSV  
- **VIX & Put/Call:** CBOE public CSV  
- **HY OAS:** FRED CSV  
- **Treasury yields:** FRED CSV (2Y/10Y)  
- **Crypto:** CoinGecko public API  
""")

st.markdown("---")
st.caption("© 2025 · Built with Streamlit. """)
