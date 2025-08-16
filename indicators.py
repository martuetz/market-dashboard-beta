
# indicators.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Tuple, List

import numpy as np
import pandas as pd

from settings import THRESHOLDS
from data_sources import stooq_history, yahoo_history, fred_series, cboe_vix, cboe_putcall, finra_margin_debt, spy_holdings, shiller_dataset

# ---------- Utility functions ----------

def pct_rank(series: pd.Series) -> pd.Series:
    return series.rank(pct=True)


def rolling_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    up = delta.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
    down = -delta.clip(upper=0).ewm(alpha=1/period, adjust=False).mean()
    rs = up / down.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def drawdown(series: pd.Series) -> pd.Series:
    roll_max = series.cummax()
    dd = series / roll_max - 0.999999999  # tiny epsilon to avoid zero division illusions
    return dd - 1.0  # negative values


def traffic_light(value: Optional[float], ranges: Dict[str, Tuple[Optional[float], Optional[float]]], higher_is_richer: bool = True) -> str:
    """
    Given a value and threshold ranges, return 'green' / 'yellow' / 'red' / 'grey'.
    For metrics where higher implies 'richer' (more overvalued), pass higher_is_richer=True.
    """
    if value is None or np.isnan(value):
        return "grey"
    # Ranges are absolute; we interpret inclusively on lower bound for yellow/red
    for color in ("green", "yellow", "red"):
        lo, hi = ranges[color]
        if lo is None and hi is None:
            return color
        if lo is None and value < hi:
            return color
        if hi is None and value >= lo:
            return color
        if lo is not None and hi is not None and (value >= lo) and (value < hi):
            return color
    return "grey"


def guidance_label(valuation_color: str, trend_color: str) -> str:
    # Simple matrix
    lookup = {
        ("green", "green"): "Accumulate",
        ("green", "yellow"): "Accumulate (scale in)",
        ("green", "red"): "Neutral / DCA",
        ("yellow", "green"): "Neutral / DCA",
        ("yellow", "yellow"): "Neutral",
        ("yellow", "red"): "Neutral / Trim",
        ("red", "green"): "Neutral",
        ("red", "yellow"): "Trim (raise cash)",
        ("red", "red"): "Trim / Wait",
    }
    return lookup.get((valuation_color, trend_color), "Neutral")


# ---------- Valuation metrics ----------

def get_price_series(preferred: str, fallback: str) -> Optional[pd.DataFrame]:
    df = stooq_history(preferred)
    if df is None:
        df = yahoo_history(fallback)
    return df


def compute_ttm_pe(spx_symbol_stooq: str = "^spx", spx_symbol_yahoo: str = "^GSPC") -> Dict:
    price_df = get_price_series(spx_symbol_stooq, spx_symbol_yahoo)
    shiller_df = shiller_dataset()
    value = None
    series = None
    last_ts = None
    if price_df is not None and shiller_df is not None and "earnings" in shiller_df.columns:
        # TTM EPS from last 12 months of monthly earnings
        shiller_df = shiller_df.dropna(subset=["earnings", "date"]).copy()
        shiller_df = shiller_df.sort_values("date")
        shiller_df["year"] = shiller_df["date"].dt.year
        shiller_df["month"] = shiller_df["date"].dt.month
        # Compute trailing 12-month EPS by summing last 12 monthly 'earnings'
        shiller_df["ttm_eps"] = shiller_df["earnings"].rolling(window=12).sum()
        # Map monthly TTM EPS to daily price dates by forward fill
        s = shiller_df.set_index("date")["ttm_eps"].asfreq("MS").ffill()
        price_df = price_df.set_index("date").sort_index()
        price_df["ttm_eps"] = s.reindex(price_df.index, method="ffill")
        price_df["pe_ttm"] = price_df["close"] / price_df["ttm_eps"]
        series = price_df["pe_ttm"].dropna()
        if not series.empty:
            value = float(series.iloc[-1])
            last_ts = series.index[-1]
    color = traffic_light(value, THRESHOLDS["pe_ttm"], higher_is_richer=True)
    return {"value": value, "series": series, "color": color, "last_updated": last_ts, "source": "Price: Stooq/Yahoo; Earnings: Yale/Shiller"}


def compute_cape() -> Dict:
    df = shiller_dataset()
    value = None
    series = None
    last_ts = None
    if df is not None and "cape" in df.columns:
        series = df.set_index("date")["cape"].dropna()
        if not series.empty:
            value = float(series.iloc[-1])
            last_ts = series.index[-1]
    color = traffic_light(value, THRESHOLDS["cape"], higher_is_richer=True)
    return {"value": value, "series": series, "color": color, "last_updated": last_ts, "source": "Yale/Shiller"}


def compute_margin_debt_yoy() -> Dict:
    df = finra_margin_debt()
    value = None
    series = None
    last_ts = None
    if df is not None:
        df = df.dropna().sort_values("date")
        df["yoy"] = df["margin_debt"].pct_change(periods=12)
        series = df.set_index("date")["yoy"].dropna()
        if not series.empty:
            value = float(series.iloc[-1])
            last_ts = series.index[-1]
    color = traffic_light(value, THRESHOLDS["margin_yoy"], higher_is_richer=True)
    return {"value": value, "series": series, "color": color, "last_updated": last_ts, "source": "FINRA"}


def compute_concentration_top10() -> Dict:
    df = spy_holdings()
    value = None
    last_ts = None
    series = None
    if df is not None and "weight" in df.columns:
        df = df.sort_values("weight", ascending=False)
        top10 = df.head(10)
        value = float(top10["weight"].sum())
        # This CSV sometimes has a "fund_as_of_date" column or similar
        date_col = None
        for c in df.columns:
            if "as_of" in c:
                date_col = c
                break
        if date_col:
            try:
                last_ts = pd.to_datetime(df[date_col].iloc[0], errors="coerce")
            except Exception:
                last_ts = None
    color = traffic_light(value, THRESHOLDS["concentration_top10"], higher_is_richer=True)
    return {"value": value, "series": series, "color": color, "last_updated": last_ts, "source": "State Street (SPY holdings)"}


def compute_sentiment_proxy() -> Dict:
    vix = cboe_vix()
    pcr = cboe_putcall()
    hy = fred_series("BAMLH0A0HYM2")

    value = None
    last_ts = None
    series = None

    if vix is not None and pcr is not None and hy is not None:
        # Build percentiles on recent 5 years (~1260 trading days). Use daily alignment
        vix = vix.rename(columns={"vix_close": "vix"})
        vix = vix.set_index("date")["vix"].astype(float).dropna()
        pcr = pcr.set_index("date")  # columns like "total_pcr"
        # Use total put/call ratio if present, else equity only
        pcr_col = None
        for c in pcr.columns:
            if "total" in c:
                pcr_col = c; break
        if pcr_col is None:
            for c in pcr.columns:
                if "equity" in c:
                    pcr_col = c; break
        pcr_series = pcr[pcr_col].astype(float).dropna() if pcr_col else None

        hy = hy.set_index("date")["value"].astype(float).dropna()

        # Align index
        df = pd.DataFrame(index=vix.index.union(pcr_series.index).union(hy.index))
        df["vix"] = vix.reindex(df.index).ffill()
        df["pcr"] = pcr_series.reindex(df.index).ffill()
        df["hy_oas"] = hy.reindex(df.index).ffill()

        # Recent window
        recent = df.last("1825D")
        if recent.empty:
            recent = df.dropna()

        # Percentiles: higher VIX/pcr/hy_oas = more fear => map to low "sentiment score"
        vix_pct = recent["vix"].rank(pct=True)
        pcr_pct = recent["pcr"].rank(pct=True)
        hy_pct = recent["hy_oas"].rank(pct=True)

        # Momentum proxy via RSP/SPY ratio is not here; keep it to 3 subcomponents (equal weights)
        fear_quantile = (vix_pct + pcr_pct + hy_pct) / 3.0  # 0 (calm/greed) .. 1 (fear)
        # Turn into "greed score" 0..100 (like CNN, high=greed)
        greed_score = (1.0 - fear_quantile) * 100.0

        series = greed_score
        if not series.empty:
            value = float(series.iloc[-1])
            last_ts = series.index[-1]

    color = traffic_light(value, THRESHOLDS["sentiment"], higher_is_richer=True)  # higher greed = 'richer' (red)
    return {"value": value, "series": series, "color": color, "last_updated": last_ts, "source": "CBOE (VIX, Put/Call), FRED (HY OAS) — proxy"}


def compute_buffett_indicator() -> Dict:
    # As FRED dropped Wilshire series, we attempt to build with optional local CSV
    # Expect CSV with columns: date, wilshire_index_level, nominal_gdp (quarterly)
    value = None; series = None; last_ts = None; src = "Local proxy (Wilshire+GDP)"
    try:
        df = pd.read_csv(LOCAL_WILSHIRE_CSV)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"]).sort_values("date")
        # Compute ratio scaled to ~1.x (market cap / GDP)
        # Assume columns: market_cap and gdp
        col_map = {c.lower(): c for c in df.columns}
        cap_col = col_map.get("market_cap") or col_map.get("wilshire") or col_map.get("total_market_cap")
        gdp_col = col_map.get("gdp") or col_map.get("nominal_gdp")
        if cap_col and gdp_col:
            df["ratio"] = df[cap_col].astype(float) / df[gdp_col].astype(float)
            series = df.set_index("date")["ratio"]
            value = float(series.iloc[-1])
            last_ts = series.index[-1]
    except Exception:
        pass
    color = traffic_light(value, THRESHOLDS["buffett"], higher_is_richer=True)
    return {"value": value, "series": series, "color": color, "last_updated": last_ts, "source": src}


# ---------- Trend lens (per asset) ----------

def compute_asset_trend(preferred: str, fallback: str) -> Dict:
    price_df = stooq_history(preferred)
    if price_df is None:
        price_df = yahoo_history(fallback)
    if price_df is None or price_df.empty:
        return {"error": "No price data", "series": None}
    df = price_df.set_index("date").sort_index()
    close = df["close"].dropna()
    sma50 = close.rolling(50).mean()
    sma200 = close.rolling(200).mean()
    rsi = rolling_rsi(close, 14)
    dd = (close / close.cummax()) - 1.0
    cross = (sma50.iloc[-1] > sma200.iloc[-1]) if len(sma200.dropna()) else False
    dist_200 = (close.iloc[-1] / sma200.iloc[-1] - 1.0) if not np.isnan(sma200.iloc[-1]) else np.nan

    # Trend color via distance to 200-DMA
    trend_color = "green" if dist_200 > 0.0 and cross else ("yellow" if dist_200 > -0.02 else "red")

    return {
        "close": close,
        "sma50": sma50,
        "sma200": sma200,
        "rsi": rsi,
        "drawdown": dd,
        "trend_color": trend_color,
        "last_updated": close.index[-1] if not close.empty else None,
        "source": "Stooq/Yahoo",
    }
