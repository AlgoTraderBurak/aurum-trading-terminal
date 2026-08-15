from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import pandas as pd

from aurum.data.quality import normalize_bars
from aurum.domain.models import Timeframe


class BarCache:
    """Thread-safe-by-connection SQLite cache for closed OHLCV bars."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=15)
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=NORMAL")
        return con

    def _initialize(self) -> None:
        with closing(self._connect()) as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS bars (
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    PRIMARY KEY(symbol, timeframe, timestamp)
                );
                CREATE INDEX IF NOT EXISTS idx_bars_lookup
                    ON bars(symbol, timeframe, timestamp DESC);
                """
            )
            con.commit()

    def store(self, symbol: str, timeframe: Timeframe, frame: pd.DataFrame) -> int:
        df = normalize_bars(frame).dropna()
        if df.empty:
            return 0
        rows = [
            (
                symbol,
                timeframe.label,
                int(ts.timestamp()),
                float(row.open),
                float(row.high),
                float(row.low),
                float(row.close),
                float(row.volume),
            )
            for ts, row in df.iterrows()
        ]
        with closing(self._connect()) as con:
            con.executemany(
                """
                INSERT INTO bars(symbol,timeframe,timestamp,open,high,low,close,volume)
                VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(symbol,timeframe,timestamp) DO UPDATE SET
                    open=excluded.open, high=excluded.high, low=excluded.low,
                    close=excluded.close, volume=excluded.volume
                """,
                rows,
            )
            con.commit()
        return len(rows)

    def load(self, symbol: str, timeframe: Timeframe, limit: int = 5000) -> pd.DataFrame:
        with closing(self._connect()) as con:
            rows = con.execute(
                """
                SELECT timestamp,open,high,low,close,volume FROM (
                    SELECT timestamp,open,high,low,close,volume
                    FROM bars WHERE symbol=? AND timeframe=?
                    ORDER BY timestamp DESC LIMIT ?
                ) ORDER BY timestamp ASC
                """,
                (symbol, timeframe.label, int(limit)),
            ).fetchall()
        if not rows:
            return pd.DataFrame(columns=("open", "high", "low", "close", "volume"))
        df = pd.DataFrame(rows, columns=("timestamp", "open", "high", "low", "close", "volume"))
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
        return df.set_index("timestamp")
