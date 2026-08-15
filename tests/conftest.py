from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def bars() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    n = 420
    close = 100.0 + np.cumsum(rng.normal(0, 0.55, n))
    open_ = np.r_[close[0], close[:-1]]
    spread = rng.uniform(0.15, 0.8, n)
    high = np.maximum(open_, close) + spread
    low = np.minimum(open_, close) - spread
    volume = rng.integers(100, 2000, n).astype(float)
    index = pd.date_range("2025-01-06", periods=n, freq="15min", tz="UTC")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=index,
    )
