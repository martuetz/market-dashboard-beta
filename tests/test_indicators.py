
import pandas as pd
import numpy as np

from indicators import rolling_rsi, traffic_light, guidance_label
from settings import THRESHOLDS

def test_rsi_monotonic_on_trend():
    # Rising series -> RSI > 50 at end
    s = pd.Series(np.arange(1, 101, dtype=float))
    rsi = rolling_rsi(s, 14)
    assert rsi.iloc[-1] > 50

def test_traffic_light_basic():
    ranges = {"green": (None, 10), "yellow": (10, 20), "red": (20, None)}
    assert traffic_light(9.9, ranges) == "green"
    assert traffic_light(15, ranges) == "yellow"
    assert traffic_light(21, ranges) == "red"
    assert traffic_light(None, ranges) == "grey"

def test_guidance_matrix():
    assert guidance_label("green","green").startswith("Accumulate")
    assert "Trim" in guidance_label("red","red")
