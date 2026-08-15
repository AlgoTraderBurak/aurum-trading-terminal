from __future__ import annotations

import numpy as np
import pandas as pd


def true_range(df: pd.DataFrame) -> pd.Series:
    prev = df["close"].shift(1)
    return pd.concat(
        [df["high"] - df["low"], (df["high"] - prev).abs(), (df["low"] - prev).abs()],
        axis=1,
    ).max(axis=1)


def wilder(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(alpha=1.0 / length, adjust=False, min_periods=length).mean()


def atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    return wilder(true_range(df), length)


def rsi(close: pd.Series, length: int = 14) -> pd.Series:
    delta = close.diff()
    gain = wilder(delta.clip(lower=0.0), length)
    loss = wilder(-delta.clip(upper=0.0), length)
    rs = gain / loss.replace(0.0, np.nan)
    out = 100.0 - 100.0 / (1.0 + rs)
    out[(gain > 0) & (loss == 0)] = 100.0
    out[(gain == 0) & (loss == 0)] = 50.0
    return out


def adx(df: pd.DataFrame, length: int = 14) -> tuple[pd.Series, pd.Series, pd.Series]:
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)
    tr_s = wilder(true_range(df), length).replace(0.0, np.nan)
    plus_di = 100.0 * wilder(plus_dm, length) / tr_s
    minus_di = 100.0 * wilder(minus_dm, length) / tr_s
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)
    return wilder(dx, length), plus_di, minus_di


def daily_vwap(df: pd.DataFrame) -> pd.Series:
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    volume = df["volume"].clip(lower=0.0)
    groups = pd.Series(df.index.date, index=df.index)
    pv = (typical * volume).groupby(groups).cumsum()
    vv = volume.groupby(groups).cumsum().replace(0.0, np.nan)
    return pv / vv


def relative_volume(volume: pd.Series, length: int = 20) -> pd.Series:
    baseline = volume.shift(1).rolling(length, min_periods=length).mean()
    return volume / baseline.replace(0.0, np.nan)


def percentile_rank(series: pd.Series, length: int = 100) -> pd.Series:
    return series.rolling(length, min_periods=length).rank(pct=True)


def causal_kernel_mean(series: pd.Series, window: int = 40, bandwidth: float = 8.0) -> pd.Series:
    """Non-repainting Nadaraya-style smoother; each point uses only current/past values."""
    values = series.to_numpy(dtype=float)
    out = np.full(len(values), np.nan)
    distances = np.arange(window, dtype=float)
    weights = np.exp(-(distances**2) / (2.0 * bandwidth**2))
    for i in range(len(values)):
        start = max(0, i - window + 1)
        sample = values[start : i + 1][::-1]
        valid = np.isfinite(sample)
        if valid.sum() < min(10, window):
            continue
        w = weights[: len(sample)][valid]
        out[i] = np.dot(sample[valid], w) / w.sum()
    return pd.Series(out, index=series.index)


def session_name(index: pd.DatetimeIndex) -> pd.Series:
    minutes = index.hour * 60 + index.minute
    labels = np.full(len(index), "Kapalı/Geçiş", dtype=object)
    labels[(minutes >= 0) & (minutes < 8 * 60)] = "Asya"
    labels[(minutes >= 7 * 60) & (minutes < 16 * 60)] = "Londra"
    labels[(minutes >= 13 * 60 + 30) & (minutes < 21 * 60)] = "New York"
    return pd.Series(labels, index=index)


def compute_indicator_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["ema20"] = out["close"].ewm(span=20, adjust=False, min_periods=20).mean()
    out["ema50"] = out["close"].ewm(span=50, adjust=False, min_periods=50).mean()
    out["ema200"] = out["close"].ewm(span=200, adjust=False, min_periods=200).mean()
    out["atr"] = atr(out, 14)
    out["atr_pct"] = percentile_rank(out["atr"], 100)
    out["rsi"] = rsi(out["close"], 14)
    out["adx"], out["plus_di"], out["minus_di"] = adx(out, 14)
    out["vwap"] = daily_vwap(out)
    out["relative_volume"] = relative_volume(out["volume"], 20)
    out["kernel"] = causal_kernel_mean(out["close"], 40, 8.0)
    out["kernel_upper"] = out["kernel"] + 1.5 * out["atr"]
    out["kernel_lower"] = out["kernel"] - 1.5 * out["atr"]
    mid = out["close"].rolling(20, min_periods=20).mean()
    width = out["close"].rolling(20, min_periods=20).std(ddof=0)
    out["range_width_atr"] = (4.0 * width) / out["atr"].replace(0.0, np.nan)
    out["in_range"] = out["range_width_atr"] <= 3.0
    out["session"] = session_name(out.index)
    return out
