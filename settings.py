
# settings.py
from datetime import timedelta

APP_TITLE = "Macro Market Dashboard (v1)"
APP_TAGLINE = "Educational use only · Not investment advice"

# Cache TTLs
TTL = {
    "stooq_intraday": timedelta(minutes=10),
    "stooq_daily": timedelta(minutes=30),
    "cboe_daily": timedelta(hours=24),
    "fred_quarterly": timedelta(days=7),
    "finra_monthly": timedelta(days=30),
    "shiller_monthly": timedelta(days=7),
    "treasury_daily": timedelta(days=1),
    "coingecko_live": timedelta(minutes=5),
    "holdings_daily": timedelta(hours=12),
}

# Metric thresholds (initial policy)
THRESHOLDS = {
    "pe_ttm": {"green": (None, 18), "yellow": (18, 24), "red": (24, None)},
    "cape": {"green": (None, 20), "yellow": (20, 30), "red": (30, None)},
    "buffett": {"green": (None, 1.20), "yellow": (1.20, 1.50), "red": (1.50, None)},
    "margin_yoy": {"green": (None, 0.0), "yellow": (0.0, 0.10), "red": (0.10, None)},
    "concentration_top10": {"green": (None, 0.25), "yellow": (0.25, 0.35), "red": (0.35, None)},
    "sentiment": {"green": (None, 25), "yellow": (25, 75), "red": (75, None)},  # note: sentiment=greed; low (fear) is green for future returns
}

# Region / asset definitions
ASSETS = {
    "US": {
        "S&P 500": {"stooq": "^spx", "yahoo": "^GSPC"},
        "Nasdaq-100": {"stooq": "^ndx", "yahoo": "^NDX"},
        "Russell 2000": {"stooq": "^rut", "yahoo": "^RUT"},
    },
    "Europe": {
        "STOXX 600": {"stooq": "stoxx600", "yahoo": "^STOXX"},
        "DAX": {"stooq": "^dax", "yahoo": "^GDAXI"},
        "FTSE 100": {"stooq": "^ukx", "yahoo": "^FTSE"},
    },
    "Asia": {
        "Nikkei 225": {"stooq": "^nkx", "yahoo": "^N225"},
        "TOPIX": {"stooq": "topix", "yahoo": "^TOPX"},
        "Hang Seng": {"stooq": "^hsi", "yahoo": "^HSI"},
    },
    "Commodities": {
        "WTI Crude": {"stooq": "cl.f", "yahoo": "CL=F"},
        "Brent Crude": {"stooq": "br.f", "yahoo": "BZ=F"},
        "Gold": {"stooq": "xauusd", "yahoo": "GC=F"},
        "Copper": {"stooq": "hg.f", "yahoo": "HG=F"},
    },
    "Bonds": {
        "US 10Y Yield": {"fred": "DGS10"},
        "US 2Y Yield": {"fred": "DGS2"},
        "HY OAS": {"fred": "BAMLH0A0HYM2"},
    },
    "Crypto": {
        "Bitcoin": {"coingecko": "bitcoin"},
        "Ethereum": {"coingecko": "ethereum"},
    },
}

# Misc constants
SPY_HOLDINGS_CSV = "https://www.ssga.com/us/en/institutional/etfs/library-content/products/fund-data/etfs/us/holdings-daily-us-en-spy.csv"
CBOE_VIX_CSV = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
CBOE_PUTCALL_CSV = "https://cdn.cboe.com/api/global/us_indices/put_call_ratio/historical_put_call_ratios.csv"
FRED_SERIES_CSV = "https://fred.stlouisfed.org/series/{sid}/downloaddata/{sid}.csv"

# Attempted FINRA margin debt URL candidates (the app tries in order until success)
FINRA_MARGIN_CANDIDATES = [
    # Often updated path; we try several likely candidates
    "https://www.finra.org/sites/default/files/2024-07/industry-margin-statistics.xlsx",
    "https://www.finra.org/sites/default/files/2023-07/industry-margin-statistics.xlsx",
    "https://www.finra.org/sites/default/files/industry-margin-statistics.xlsx",
]

# Yale/Shiller dataset
SHILLER_XLS = "http://www.econ.yale.edu/~shiller/data/ie_data.xls"

# Optional local fallback for Wilshire 5000 proxy (Buffett indicator)
LOCAL_WILSHIRE_CSV = "data/wilshire_5000_proxy.csv"  # If present, app will use it
