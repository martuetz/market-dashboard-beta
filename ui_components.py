
# ui_components.py
from __future__ import annotations
from typing import Dict, Optional, List

import numpy as np
import pandas as pd
import altair as alt
import streamlit as st

from settings import THRESHOLDS
from indicators import guidance_label

COLOR_MAP = {
    "green": "#10B981",
    "yellow": "#FBBF24",
    "red": "#EF4444",
    "grey": "#9CA3AF",
}

def gradient_card(title: str, value_str: str, spark_df: Optional[pd.DataFrame], color: str, footer: str, key: str):
    # Build a simple Altair sparkline if provided
    with st.container(border=True):
        st.markdown(f"#### {title}")
        st.markdown(f"**{value_str}**")
        if spark_df is not None and not spark_df.empty:
            line = alt.Chart(spark_df.reset_index()).mark_line().encode(
                x=alt.X("date:T", axis=None),
                y=alt.Y(spark_df.columns[0], axis=None)
            ).properties(height=60)
            st.altair_chart(line, use_container_width=True)
        # traffic light badge
        st.markdown(
            f"<div style='display:inline-block;padding:6px 10px;border-radius:999px;background:{COLOR_MAP.get(color, '#9CA3AF')};color:white;font-weight:600;'>"
            f"{color.upper()}</div>",
            unsafe_allow_html=True
        )
        st.caption(footer)


def series_tile(title: str, metric: Dict, fmt: str, spark_from_series: bool = True):
    value = metric.get("value")
    series = metric.get("series")
    color = metric.get("color", "grey")
    last = metric.get("last_updated")
    source = metric.get("source", "")
    v = "—" if value is None else fmt.format(value)
    spark_df = None
    if series is not None and hasattr(series, "to_frame"):
        tail = series.tail(260).to_frame(name="value")
        spark_df = tail
    footer = f"Updated: {last} · Source: {source}"
    gradient_card(title, v, spark_df, color, footer, key=title)


def price_panel(title: str, trend: Dict):
    import altair as alt
    import pandas as pd
    import streamlit as st

    if trend.get("error"):
        st.warning(trend["error"])
        return
    close = trend["close"]; sma50 = trend["sma50"]; sma200 = trend["sma200"]
    df = pd.DataFrame({"close": close, "sma50": sma50, "sma200": sma200}).reset_index().dropna()
    chart = alt.Chart(df).mark_line().encode(
        x="date:T",
        y=alt.Y("close:Q", title=title),
    )
    c50 = alt.Chart(df).mark_line().encode(x="date:T", y="sma50:Q")
    c200 = alt.Chart(df).mark_line().encode(x="date:T", y="sma200:Q")
    st.altair_chart(chart + c50 + c200, use_container_width=True)

    cols = st.columns(3)
    with cols[0]:
        st.metric("Trend", trend["trend_color"].title())
    with cols[1]:
        st.metric("RSI(14)", f"{trend['rsi'].iloc[-1]:.1f}")
    with cols[2]:
        st.metric("Drawdown", f"{trend['drawdown'].iloc[-1]*100:.1f}%")


def overall_strip(valuation_color: str, trend_color: str):
    label = guidance_label(valuation_color, trend_color)
    st.markdown(f"""
<div style="padding:14px 18px;border-radius:12px;background:linear-gradient(90deg, rgba(99,102,241,0.15), rgba(34,211,238,0.15));border:1px solid rgba(0,0,0,0.05)">
<strong>What this means:</strong> <span style="font-weight:600">{label}</span>
</div>
""", unsafe_allow_html=True)


def data_health(items: List[Dict]):
    rows = []
    for m in items:
        rows.append({
            "Metric": m.get("name",""),
            "Updated (UTC)": str(m.get("last")),
            "Source": m.get("source",""),
            "Status": m.get("status","OK" if m.get("value") is not None else "Missing"),
        })
    st.subheader("Data Health")
    st.dataframe(pd.DataFrame(rows))
