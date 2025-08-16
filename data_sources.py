
# data_sources.py
import io
import time
import zipfile
import warnings
from datetime import datetime, timezone
from typing import Optional, Tuple, Dict

import numpy as np
import pandas as pd
import requests

from settings import TTL, CBOE_VIX_CSV, CBOE_PUTCALL_CSV, FRED_SERIES_CSV, FINRA_MARGIN_CANDIDATES, SHILLER_XLS, SPY_HOLDINGS_CSV, LOCAL_WILSHIRE_CSV

USER_AGENT = {"User-Agent": "Mozilla/5.0 (compatible; MacroDashboardBot/1.0)"}


def _utc_now_ts() -> pd.Timestamp:
    # Robust, tz-aware
    return pd.Timestamp.now(tz="UTC")


def fetch_csv(url: str, timeout: int = 20) -> Optional[pd.DataFrame]:
    try:
        r = requests.get(url, headers=USER_AGENT, timeout=timeout)
        r.raise_for_status()
        buf = io.StringIO(r.text)
        df = pd.read_csv(buf)
        return df
    except Exception as e:
        return None


def fetch_binary(url: str, timeout: int = 30) -> Optional[bytes]:
    try:
        r = requests.get(url, headers=USER_AGENT, timeout=timeout)
        r.raise_for_status()
        return r.content
    except Exception:
        return None


def stooq_history(symbol: str, interval: str = "d") -> Optional[pd.DataFrame]:
    """
    Fetch historical data from Stooq. interval in {'d','w','m'}
    Returns DataFrame with columns: Date, Open, High, Low, Close, Volume
    """
    base = f"https://stooq.com/q/d/l/?s={symbol}&i={interval}"
    df = fetch_csv(base)
    if df is None or "Date" not in df.columns:
        return None
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date")
    return df.rename(columns=str.lower)


def yahoo_history(symbol: str, period: str = "max", interval: str = "1d") -> Optional[pd.DataFrame]:
    """
    Fallback via Yahoo's 'query1.finance.yahoo.com' CSV style endpoint (no yfinance dependency).
    """
    try:
        # period1=0 (1970), period2=now
        period1 = 0
        period2 = int(time.time())
        url = f"https://query1.finance.yahoo.com/v7/finance/download/{symbol}?period1={period1}&period2={period2}&interval={interval}&events=history&includeAdjustedClose=true"
        df = fetch_csv(url)
        if df is None or "Date" not in df.columns:
            return None
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Date"]).sort_values("Date")
        df = df.rename(columns={"Adj Close": "AdjClose"})
        return df.rename(columns=str.lower)
    except Exception:
        return None


def fred_series(series_id: str) -> Optional[pd.DataFrame]:
    url = FRED_SERIES_CSV.format(sid=series_id)
    df = fetch_csv(url)
    if df is None:
        return None
    # Standardize
    df["DATE"] = pd.to_datetime(df["DATE"], errors="coerce")
    df = df.dropna(subset=["DATE"]).rename(columns={"DATE": "date", series_id: "value"})
    # Some FRED series have '.' missing values
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"]).sort_values("date")
    return df


def cboe_vix() -> Optional[pd.DataFrame]:
    df = fetch_csv(CBOE_VIX_CSV)
    if df is None:
        return None
    # The CBOE file typically has columns: DATE, VIX Close, etc.
    cols = {c: c.strip().lower().replace(" ", "_") for c in df.columns}
    df = df.rename(columns=cols)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"]).sort_values("date")
    return df


def cboe_putcall() -> Optional[pd.DataFrame]:
    df = fetch_csv(CBOE_PUTCALL_CSV)
    if df is None:
        return None
    cols = {c: c.strip().lower().replace(" ", "_") for c in df.columns}
    df = df.rename(columns=cols)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"]).sort_values("date")
    return df


def finra_margin_debt() -> Optional[pd.DataFrame]:
    for url in FINRA_MARGIN_CANDIDATES:
        content = fetch_binary(url)
        if content:
            try:
                df = pd.read_excel(io.BytesIO(content))
                # Try to infer the columns (FINRA sheet is usually wide; we search for "Customer debit balances"
                df.columns = [str(c).strip() for c in df.columns]
                # Melt if necessary
                if "Date" not in df.columns and "Month" in df.columns:
                    df.rename(columns={"Month": "Date"}, inplace=True)
                if "Date" in df.columns:
                    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
                    # Choose the column that contains "Customer debit balances"
                    target = None
                    for c in df.columns:
                        if "debit" in c.lower() and "balances" in c.lower():
                            target = c
                            break
                    if target:
                        out = df[["Date", target]].dropna()
                        out.columns = ["date", "margin_debt"]
                        out = out.sort_values("date")
                        return out
            except Exception:
                continue
    return None


def spy_holdings() -> Optional[pd.DataFrame]:
    df = fetch_csv(SPY_HOLDINGS_CSV)
    if df is None:
        return None
    # Normalize columns
    cols = {c: c.strip().lower().replace(" ", "_") for c in df.columns}
    df = df.rename(columns=cols)
    # Expect columns like: ticker, name, weight, shares, etc.
    # SPY uses "weight" as percentage; ensure numeric
    if "weight" in df.columns:
        df["weight"] = pd.to_numeric(df["weight"], errors="coerce") / 100.0
    return df


def shiller_dataset() -> Optional[pd.DataFrame]:
    content = fetch_binary(SHILLER_XLS)
    if not content:
        return None
    try:
        df = pd.read_excel(io.BytesIO(content), sheet_name="Data", skiprows=7)
        # The sheet usually has columns: Date, P, D, E, CPI, etc.
        # Try to standardize
        df.columns = [str(c).strip() for c in df.columns]
        if "Date" in df.columns:
            # Dates are monthly decimals like 1871.01; use pd.to_datetime with format if possible
            # Convert fractional year to month
            def yearfrac_to_ts(x):
                try:
                    year = int(x)
                    month = int(round((x - year) * 12)) + 1
                    month = min(max(month, 1), 12)
                    return pd.Timestamp(year=year, month=month, day=1, tz="UTC")
                except Exception:
                    return pd.NaT
            df["date"] = df["Date"].apply(yearfrac_to_ts)
        else:
            # Fallback: use index as date if possible
            df["date"] = pd.to_datetime(df.iloc[:, 0], errors="coerce")
        # Standardize key columns
        colmap = {}
        for c in df.columns:
            lc = c.lower()
            if lc in ("p", "price"):
                colmap[c] = "price"
            elif lc in ("e", "earnings"):
                colmap[c] = "earnings"
            elif "cape" in lc:
                colmap[c] = "cape"
        df = df.rename(columns=colmap)
        df = df.dropna(subset=["date"]).sort_values("date")
        return df
    except Exception:
        return None


def coingecko_markets(ids, vs_currency="usd") -> Optional[pd.DataFrame]:
    try:
        ids_param = ",".join(ids)
        url = f"https://api.coingecko.com/api/v3/coins/markets?vs_currency={vs_currency}&ids={ids_param}&price_change_percentage=1h,24h,7d"
        r = requests.get(url, headers=USER_AGENT, timeout=20)
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, list):
            return None
        df = pd.DataFrame(data)
        return df
    except Exception:
        return None


def last_updated(df: Optional[pd.DataFrame], date_col: str = "date") -> Optional[pd.Timestamp]:
    if df is None or date_col not in df.columns or df.empty:
        return None
    ts = pd.to_datetime(df[date_col]).max()
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts

