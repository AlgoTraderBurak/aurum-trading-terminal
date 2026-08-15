from __future__ import annotations

import numpy as np
import pandas as pd

from aurum.domain.models import QualityIssue, QualityReport, Timeframe


REQUIRED = ("open", "high", "low", "close", "volume")


def normalize_bars(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None:
        return pd.DataFrame(columns=REQUIRED)
    df = frame.copy()
    df.columns = [str(x).lower() for x in df.columns]
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        df = df.set_index("timestamp")
    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError("Bar verisinin indeksi DatetimeIndex olmalı.")
    df.index = pd.to_datetime(df.index, utc=True, errors="coerce")
    missing = [x for x in REQUIRED if x not in df.columns]
    if missing:
        raise ValueError(f"Eksik OHLCV kolonları: {', '.join(missing)}")
    for col in REQUIRED:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    # Do not sort or deduplicate here: integrity problems must remain visible
    # so the signal gate can stop instead of silently repairing input data.
    return df.loc[:, REQUIRED]


def split_closed_bars(
    frame: pd.DataFrame,
    timeframe: Timeframe,
    now: pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, pd.Series | None]:
    df = normalize_bars(frame)
    if df.empty:
        return df, None
    if not df.index.is_monotonic_increasing or df.index.has_duplicates:
        return df.copy(), None
    current_time = now or pd.Timestamp.now(tz="UTC")
    if current_time.tzinfo is None:
        current_time = current_time.tz_localize("UTC")
    last_open = df.index[-1]
    still_open = current_time < last_open + pd.Timedelta(seconds=timeframe.seconds)
    if still_open:
        return df.iloc[:-1].copy(), df.iloc[-1].copy()
    return df.copy(), None


def validate_bars(
    frame: pd.DataFrame,
    timeframe: Timeframe,
    *,
    continuous: bool = False,
    now: pd.Timestamp | None = None,
) -> QualityReport:
    issues: list[QualityIssue] = []
    try:
        df = normalize_bars(frame)
    except (TypeError, ValueError) as exc:
        issues.append(QualityIssue("critical", "schema", str(exc)))
        return QualityReport(0, None, None, issues=issues)

    duplicates = int(df.index.duplicated().sum())
    monotonic = bool(df.index.is_monotonic_increasing)
    nan_rows = int(df.loc[:, REQUIRED].isna().any(axis=1).sum())
    h, l, o, c = (df[x].to_numpy(dtype=float) for x in ("high", "low", "open", "close"))
    finite = np.isfinite(np.column_stack([h, l, o, c])).all(axis=1) if len(df) else np.array([])
    violations = int(((h < l) | (h < o) | (h < c) | (l > o) | (l > c))[finite].sum())

    if duplicates:
        issues.append(QualityIssue("critical", "duplicates", f"{duplicates} kopya zaman damgası var."))
    if not monotonic:
        issues.append(QualityIssue("critical", "order", "Zaman damgaları artan sırada değil."))
    if nan_rows:
        issues.append(QualityIssue("critical", "nan", f"{nan_rows} satırda eksik/sayısal olmayan değer var."))
    if violations:
        issues.append(QualityIssue("critical", "ohlc", f"{violations} mumda OHLC tutarsızlığı var."))
    if len(df) < 50:
        issues.append(QualityIssue("critical", "short_history", "Analiz için en az 50 kapanmış mum gerekir."))

    missing_intervals = 0
    if len(df) > 1:
        diffs = df.index.to_series().diff().dt.total_seconds().dropna()
        expected = timeframe.seconds
        if continuous:
            missing_intervals = int(np.maximum(np.rint(diffs / expected).astype(int) - 1, 0).sum())
        else:
            weekday = df.index.to_series().dt.dayofweek
            active_gap = (weekday.iloc[1:].to_numpy() < 5) & (diffs.to_numpy() > expected * 1.5)
            missing_intervals = int(active_gap.sum())
        if missing_intervals:
            issues.append(
                QualityIssue(
                    "warning",
                    "gaps",
                    f"{missing_intervals} olağandışı bar aralığı bulundu; seans/tatil olabilir.",
                )
            )

    stale = False
    current_time = now or pd.Timestamp.now(tz="UTC")
    if current_time.tzinfo is None:
        current_time = current_time.tz_localize("UTC")
    if len(df):
        tolerance = timeframe.seconds * (4 if continuous else 16)
        stale = (current_time - df.index[-1]).total_seconds() > tolerance
        if stale:
            issues.append(QualityIssue("warning", "stale", "Son kapanmış mum güncel görünmüyor."))

    return QualityReport(
        row_count=len(df),
        start=df.index[0] if len(df) else None,
        end=df.index[-1] if len(df) else None,
        duplicate_bars=duplicates,
        missing_intervals=missing_intervals,
        ohlc_violations=violations,
        nan_rows=nan_rows,
        monotonic=monotonic,
        stale=stale,
        issues=issues,
    )
