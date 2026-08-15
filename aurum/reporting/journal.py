from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

import numpy as np

from aurum import __version__
from aurum.domain.models import AnalysisSnapshot, BacktestResult, MarketDataBundle


@dataclass(frozen=True)
class JournalEntry:
    id: int
    kind: str
    created_at: str
    symbol: str
    timeframe: str
    asof: str
    title: str
    direction: str
    score: int
    action: str
    rr: float | None
    summary: str
    payload: dict[str, Any]
    note: str
    tags: str


class ReportJournal:
    """Analiz ve backtest anlık görüntülerini değişmez girdiler halinde saklar."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=15)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=NORMAL")
        con.execute("PRAGMA foreign_keys=ON")
        return con

    def _initialize(self) -> None:
        with closing(self._connect()) as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS journal_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL CHECK(kind IN ('ANALYSIS','BACKTEST')),
                    fingerprint TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    asof TEXT NOT NULL,
                    title TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    rr REAL,
                    summary TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    tags TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_journal_latest
                    ON journal_entries(created_at DESC, id DESC);
                CREATE INDEX IF NOT EXISTS idx_journal_market
                    ON journal_entries(symbol, timeframe, asof DESC);
                """
            )
            con.commit()

    @staticmethod
    def _fingerprint(*parts: object) -> str:
        return sha256("|".join(map(str, parts)).encode("utf-8")).hexdigest()

    @staticmethod
    def _json(value: object) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)

    def _insert(self, values: tuple[object, ...]) -> int:
        with closing(self._connect()) as con:
            con.execute(
                """
                INSERT INTO journal_entries(
                    kind,fingerprint,created_at,symbol,timeframe,asof,title,
                    direction,score,action,rr,summary,payload_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(fingerprint) DO NOTHING
                """,
                values,
            )
            row = con.execute(
                "SELECT id FROM journal_entries WHERE fingerprint=?", (values[1],)
            ).fetchone()
            con.commit()
        if row is None:
            raise RuntimeError("Rapor kaydı oluşturulamadı.")
        return int(row["id"])

    def record_analysis(self, snapshot: AnalysisSnapshot) -> int:
        signal = snapshot.latest_signal
        payload = {
            "engine_version": __version__,
            "metrics": snapshot.metrics,
            "mtf_context": snapshot.mtf_context,
            "quality": {
                "status": snapshot.quality.status_tr,
                "row_count": snapshot.quality.row_count,
                "issues": [asdict(x) for x in snapshot.quality.issues],
            },
            "latest_signal": signal.to_dict() if signal else None,
            "active_zones": [
                {
                    "kind": z.kind.value,
                    "direction": z.direction.tr,
                    "lower": z.lower,
                    "upper": z.upper,
                    "state": z.state,
                    "born_at": z.born_at.isoformat(),
                }
                for z in snapshot.zones
            ],
            "source": snapshot.source,
        }
        action = signal.action.tr if signal else "İŞLEM YOK"
        title = f"{snapshot.symbol} {snapshot.timeframe.label} piyasa analizi"
        fingerprint = self._fingerprint("ANALYSIS", __version__, snapshot.symbol, snapshot.timeframe.label, snapshot.asof.isoformat())
        return self._insert(
            (
                "ANALYSIS", fingerprint, datetime.now(timezone.utc).isoformat(), snapshot.symbol,
                snapshot.timeframe.label, snapshot.asof.isoformat(), title, snapshot.direction.tr,
                snapshot.score, action, signal.rr if signal else None, snapshot.narrative,
                self._json(payload),
            )
        )

    def record_backtest(
        self,
        bundle: MarketDataBundle,
        snapshot: AnalysisSnapshot,
        result: BacktestResult,
    ) -> int:
        config = asdict(result.config)
        signal_by_uid = {signal.uid: signal for signal in snapshot.signals}
        feature_names = (
            "rsi", "adx", "atr", "atr_pct", "relative_volume", "structure_bias", "session",
            "in_range", "sweep_high", "sweep_low", "bull_break", "bear_break",
            "fvg_touch_long", "fvg_touch_short", "ifvg_touch_long", "ifvg_touch_short",
            "ob_touch_long", "ob_touch_short",
        )
        trades = []
        for trade in result.trades:
            signal = signal_by_uid.get(trade.signal_uid)
            features: dict[str, object] = {}
            if signal is not None and signal.timestamp in snapshot.frame.index:
                row = snapshot.frame.loc[signal.timestamp]
                for name in feature_names:
                    value = row.get(name)
                    if isinstance(value, (np.bool_, bool)):
                        features[name] = bool(value)
                    elif isinstance(value, (np.integer, int)):
                        features[name] = int(value)
                    elif isinstance(value, (np.floating, float)):
                        features[name] = float(value) if np.isfinite(value) else None
                    elif value is not None:
                        features[name] = str(value)
            trades.append(
                {
                    **asdict(trade),
                    "direction": trade.direction.tr,
                    "signal_time": trade.signal_time.isoformat(),
                    "entry_time": trade.entry_time.isoformat(),
                    "exit_time": trade.exit_time.isoformat(),
                    "signal": signal.to_dict() if signal is not None else None,
                    "features": features,
                }
            )
        payload = {
            "engine_version": __version__,
            "config": config,
            "metrics": result.metrics,
            "warnings": result.warnings,
            "diagnostics": result.diagnostics,
            "trades": trades,
            "data": {
                "rows": len(bundle.closed_bars),
                "start": bundle.closed_bars.index[0].isoformat() if not bundle.closed_bars.empty else None,
                "end": bundle.closed_bars.index[-1].isoformat() if not bundle.closed_bars.empty else None,
                "source": bundle.source,
            },
        }
        fingerprint = self._fingerprint(
            "BACKTEST", __version__, bundle.symbol, bundle.timeframe.label, snapshot.asof.isoformat(), self._json(config)
        )
        final_balance = result.metrics.get("final_balance", result.config.initial_balance)
        summary = (
            f"{int(result.metrics.get('trade_count', 0))} işlem · "
            f"{result.metrics.get('net_r', 0.0):+.2f} R · "
            f"son bakiye {final_balance:,.2f} {result.config.currency}"
        )
        score = int(max(0, min(100, round(result.metrics.get("win_rate", 0.0)))))
        action = "KÂRLI" if result.metrics.get("net_profit", 0.0) > 0 else "ZARAR" if result.metrics.get("net_profit", 0.0) < 0 else "NÖTR"
        return self._insert(
            (
                "BACKTEST", fingerprint, result.generated_at.isoformat(), bundle.symbol,
                bundle.timeframe.label, snapshot.asof.isoformat(),
                f"{bundle.symbol} {bundle.timeframe.label} backtest", snapshot.direction.tr,
                score, action, result.metrics.get("net_r"), summary, self._json(payload),
            )
        )

    def list_entries(self, *, kind: str | None = None, limit: int = 500) -> list[JournalEntry]:
        sql = "SELECT * FROM journal_entries"
        params: list[object] = []
        if kind in ("ANALYSIS", "BACKTEST"):
            sql += " WHERE kind=?"
            params.append(kind)
        sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
        params.append(max(1, min(5000, int(limit))))
        with closing(self._connect()) as con:
            rows = con.execute(sql, params).fetchall()
        return [
            JournalEntry(
                id=int(row["id"]), kind=str(row["kind"]), created_at=str(row["created_at"]),
                symbol=str(row["symbol"]), timeframe=str(row["timeframe"]), asof=str(row["asof"]),
                title=str(row["title"]), direction=str(row["direction"]), score=int(row["score"]),
                action=str(row["action"]), rr=float(row["rr"]) if row["rr"] is not None else None,
                summary=str(row["summary"]), payload=json.loads(str(row["payload_json"])),
                note=str(row["note"]), tags=str(row["tags"]),
            )
            for row in rows
        ]

    def update_note(self, entry_id: int, note: str, tags: str = "") -> None:
        with closing(self._connect()) as con:
            cursor = con.execute(
                "UPDATE journal_entries SET note=?, tags=? WHERE id=?",
                (note.strip(), tags.strip(), int(entry_id)),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"Rapor bulunamadı: {entry_id}")
            con.commit()
