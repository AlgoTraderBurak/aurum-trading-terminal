from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import pandas as pd


class Timeframe(Enum):
    M1 = ("M1", 60)
    M5 = ("M5", 300)
    M15 = ("M15", 900)
    H1 = ("H1", 3600)
    H4 = ("H4", 14400)
    D1 = ("D1", 86400)

    def __init__(self, label: str, seconds: int) -> None:
        self.label = label
        self.seconds = seconds

    @classmethod
    def parse(cls, value: str | Timeframe) -> Timeframe:
        if isinstance(value, cls):
            return value
        key = value.upper().strip()
        return next(x for x in cls if x.label == key)


class Direction(Enum):
    SHORT = -1
    NEUTRAL = 0
    LONG = 1

    @property
    def tr(self) -> str:
        return {self.LONG: "Yükseliş", self.SHORT: "Düşüş", self.NEUTRAL: "Nötr"}[self]


class SignalAction(Enum):
    BUY = "BUY"
    SELL = "SELL"
    WATCH = "WATCH"
    NO_TRADE = "NO_TRADE"

    @property
    def tr(self) -> str:
        return {
            self.BUY: "AL",
            self.SELL: "SAT",
            self.WATCH: "İZLE",
            self.NO_TRADE: "İŞLEM YOK",
        }[self]


class SignalStage(Enum):
    WATCHING = "WATCHING"
    CONFIRMED = "CONFIRMED"
    INVALIDATED = "INVALIDATED"


class ZoneKind(Enum):
    FVG = "FVG"
    IFVG = "IFVG"
    ORDER_BLOCK = "ORDER_BLOCK"
    BREAKER = "BREAKER"
    LIQUIDITY = "LIQUIDITY"
    RANGE = "RANGE"


@dataclass(frozen=True)
class InstrumentSpec:
    logical_symbol: str
    aliases: tuple[str, ...]
    asset_class: str
    continuous: bool = False


@dataclass(frozen=True)
class SymbolMetadata:
    requested: str
    resolved: str
    description: str = ""
    digits: int = 5
    point: float = 0.00001
    tick_size: float = 0.00001
    tick_value: float = 0.0
    contract_size: float = 0.0
    volume_min: float = 0.01
    volume_max: float = 100.0
    volume_step: float = 0.01
    currency_profit: str = ""


@dataclass(frozen=True)
class QualityIssue:
    severity: str
    code: str
    message: str


@dataclass
class QualityReport:
    row_count: int
    start: pd.Timestamp | None
    end: pd.Timestamp | None
    duplicate_bars: int = 0
    missing_intervals: int = 0
    ohlc_violations: int = 0
    nan_rows: int = 0
    monotonic: bool = True
    stale: bool = False
    issues: list[QualityIssue] = field(default_factory=list)

    @property
    def valid_for_signals(self) -> bool:
        return not any(x.severity == "critical" for x in self.issues) and self.row_count >= 50

    @property
    def status_tr(self) -> str:
        if any(x.severity == "critical" for x in self.issues):
            return "KRİTİK"
        if self.issues:
            return "UYARI"
        return "SAĞLIKLI"


@dataclass
class MarketDataBundle:
    requested_symbol: str
    symbol: str
    timeframe: Timeframe
    bars: pd.DataFrame
    closed_bars: pd.DataFrame
    current_bar: pd.Series | None
    source: str
    metadata: SymbolMetadata
    quality: QualityReport
    fetched_at: pd.Timestamp


@dataclass(frozen=True)
class Zone:
    uid: str
    kind: ZoneKind
    direction: Direction
    lower: float
    upper: float
    born_at: pd.Timestamp
    born_bar: int
    state: str = "ACTIVE"
    touched_at: pd.Timestamp | None = None
    invalidated_at: pd.Timestamp | None = None
    source_event: str = ""


@dataclass(frozen=True)
class StructureEvent:
    kind: str
    direction: Direction
    bar: int
    timestamp: pd.Timestamp
    level: float
    source_bar: int


@dataclass(frozen=True)
class Signal:
    uid: str
    symbol: str
    timeframe: Timeframe
    timestamp: pd.Timestamp
    bar: int
    action: SignalAction
    stage: SignalStage
    direction: Direction
    score: int
    setup: str
    entry: float | None
    stop: float | None
    target: float | None
    rr: float | None
    reasons: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    invalidation: str = ""

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out.update(
            timeframe=self.timeframe.label,
            action=self.action.value,
            stage=self.stage.value,
            direction=self.direction.value,
            timestamp=self.timestamp.isoformat(),
        )
        return out


@dataclass
class AnalysisSnapshot:
    symbol: str
    timeframe: Timeframe
    asof: pd.Timestamp
    price: float
    direction: Direction
    regime: str
    score: int
    narrative: str
    metrics: dict[str, float | str | bool | None]
    latest_signal: Signal | None
    signals: list[Signal]
    zones: list[Zone]
    structure_events: list[StructureEvent]
    frame: pd.DataFrame
    quality: QualityReport
    source: str
    mtf_context: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass(frozen=True)
class BacktestConfig:
    initial_balance: float = 10_000.0
    risk_percent: float = 1.0
    spread_points: float = 0.0
    slippage_points: float = 0.0
    commission_per_lot: float = 0.0
    max_hold_bars: int = 200
    allow_overlapping: bool = False
    currency: str = "USD"


@dataclass(frozen=True)
class BacktestTrade:
    signal_uid: str
    direction: Direction
    signal_time: pd.Timestamp
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry: float
    exit: float
    stop: float
    target: float
    quantity: float
    gross_r: float
    net_r: float
    pnl: float
    exit_reason: str
    mfe_r: float = 0.0
    mae_r: float = 0.0


@dataclass
class BacktestResult:
    config: BacktestConfig
    trades: list[BacktestTrade]
    equity: pd.Series
    metrics: dict[str, float]
    warnings: list[str] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
