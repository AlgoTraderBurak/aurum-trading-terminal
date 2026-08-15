from __future__ import annotations

from hashlib import sha1

import numpy as np
import pandas as pd

from aurum.analysis.indicators import compute_indicator_frame
from aurum.analysis.structure import analyze_structure
from aurum.domain.models import (
    AnalysisSnapshot,
    Direction,
    MarketDataBundle,
    Signal,
    SignalAction,
    SignalStage,
    Timeframe,
    Zone,
)


class AnalysisEngine:
    def __init__(self, *, min_signal_score: int = 68, watch_score: int = 52) -> None:
        self.min_signal_score = min_signal_score
        self.watch_score = watch_score

    @staticmethod
    def _uid(
        symbol: str,
        timeframe: Timeframe,
        ts: pd.Timestamp,
        action: SignalAction,
        direction: Direction,
        setup: str,
    ) -> str:
        raw = (
            f"{symbol}|{timeframe.label}|{ts.isoformat()}|"
            f"{action.value}|{direction.value}|{setup}"
        )
        return sha1(raw.encode("utf-8")).hexdigest()[:20]

    @staticmethod
    def _regime(row: pd.Series) -> str:
        if bool(row.get("in_range", False)) and float(row.get("adx", 0) or 0) < 22:
            return "Sıkışma / Yatay"
        if float(row.get("atr_pct", 0) or 0) >= 0.85:
            return "Volatilite Genişlemesi"
        if float(row.get("adx", 0) or 0) >= 25:
            return "Trend"
        return "Geçiş / Belirsiz"

    def _derived_mtf_context(
        self, frame: pd.DataFrame, timeframe: Timeframe
    ) -> dict[str, dict[str, object]]:
        rules = {
            Timeframe.M5: "5min", Timeframe.M15: "15min", Timeframe.H1: "1h",
            Timeframe.H4: "4h", Timeframe.D1: "1D",
        }
        source_close = frame.index[-1] + pd.Timedelta(seconds=timeframe.seconds)
        context: dict[str, dict[str, object]] = {}
        for target in Timeframe:
            if target.seconds <= timeframe.seconds or target not in rules:
                continue
            resampled = frame.resample(rules[target], label="left", closed="left").agg(
                {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
            ).dropna()
            resampled = resampled[
                resampled.index + pd.Timedelta(seconds=target.seconds) <= source_close
            ]
            if len(resampled) < 50:
                continue
            indicators = compute_indicator_frame(resampled)
            structured = analyze_structure(indicators).frame
            row = structured.iloc[-1]
            long_score, _ = self._context_score(row, Direction.LONG)
            short_score, _ = self._context_score(row, Direction.SHORT)
            direction = (
                Direction.LONG if long_score > short_score + 6
                else Direction.SHORT if short_score > long_score + 6
                else Direction.NEUTRAL
            )
            context[target.label] = {
                "direction": direction.tr,
                "direction_value": direction.value,
                "score": int(min(100, max(long_score, short_score))),
                "regime": self._regime(row),
                "asof": structured.index[-1].isoformat(),
                "bars": len(structured),
                "derived": True,
            }
        return context

    @staticmethod
    def _context_score(row: pd.Series, direction: Direction) -> tuple[int, list[str]]:
        d = direction.value
        score = 0
        reasons: list[str] = []
        if int(row.get("structure_bias", 0)) == d:
            score += 22
            reasons.append("Piyasa yapısı yön ile uyumlu")
        ema20, ema50, ema200 = (row.get(x, np.nan) for x in ("ema20", "ema50", "ema200"))
        if np.isfinite(ema20) and np.isfinite(ema50) and (ema20 - ema50) * d > 0:
            score += 12
            reasons.append("EMA20/EMA50 eğilimi uyumlu")
        if np.isfinite(ema200) and (row["close"] - ema200) * d > 0:
            score += 8
            reasons.append("Fiyat EMA200'ün doğru tarafında")
        vwap = row.get("vwap", np.nan)
        if np.isfinite(vwap) and (row["close"] - vwap) * d > 0:
            score += 10
            reasons.append("Günlük VWAP konumu uyumlu")
        rsi_value = float(row.get("rsi", np.nan))
        if np.isfinite(rsi_value) and ((d > 0 and 42 <= rsi_value <= 72) or (d < 0 and 28 <= rsi_value <= 58)):
            score += 8
            reasons.append("RSI momentum aralığı uygun")
        adx_value = float(row.get("adx", np.nan))
        if np.isfinite(adx_value) and adx_value >= 20:
            score += 7
            reasons.append("ADX hareket gücünü teyit ediyor")
        rv = float(row.get("relative_volume", np.nan))
        if np.isfinite(rv) and rv >= 1.0:
            score += 6
            reasons.append("Göreli hacim ortalamanın üzerinde")
        return score, reasons

    @staticmethod
    def _risk_plan(
        frame: pd.DataFrame,
        i: int,
        direction: Direction,
        trigger_zone: Zone | None,
    ) -> tuple[float | None, float | None, float | None, float | None, list[str]]:
        row = frame.iloc[i]
        entry = float(row["close"])
        atr = float(row["atr"])
        warnings: list[str] = []
        if not np.isfinite(atr) or atr <= 0:
            return None, None, None, None, ["ATR hesaplanamadı"]
        recent = frame.iloc[max(0, i - 20) : i + 1]
        buffer = 0.12 * atr
        if direction is Direction.LONG:
            structural = float(recent["low"].min()) - buffer
            if trigger_zone is not None:
                structural = min(structural, trigger_zone.lower - buffer)
            stop = structural
            distance = entry - stop
        else:
            structural = float(recent["high"].max()) + buffer
            if trigger_zone is not None:
                structural = max(structural, trigger_zone.upper + buffer)
            stop = structural
            distance = stop - entry
        if distance < 0.45 * atr:
            distance = 0.45 * atr
            stop = entry - distance if direction is Direction.LONG else entry + distance
        if distance > 3.0 * atr:
            warnings.append(f"Yapısal stop çok geniş ({distance / atr:.1f} ATR)")
            return entry, stop, None, None, warnings

        rr = 2.0
        target = entry + direction.value * rr * distance
        level = row.get("resistance" if direction is Direction.LONG else "support", np.nan)
        if np.isfinite(level) and (float(level) - entry) * direction.value > 0:
            candidate_rr = abs(float(level) - entry) / distance
            if candidate_rr >= 1.5:
                target, rr = float(level), candidate_rr
        return entry, stop, target, rr, warnings

    def _signals(
        self,
        symbol: str,
        timeframe: Timeframe,
        frame: pd.DataFrame,
        zones: list[Zone],
    ) -> list[Signal]:
        signals: list[Signal] = []
        last_sweep = {1: -10_000, -1: -10_000}
        last_break = {1: -10_000, -1: -10_000}
        last_signal = {1: -10_000, -1: -10_000}
        zones_by_touch: dict[tuple[int, int], Zone] = {}
        for zone in zones:
            if zone.touched_at is not None:
                try:
                    pos = int(frame.index.get_loc(zone.touched_at))
                except KeyError:
                    continue
                zones_by_touch[(pos, zone.direction.value)] = zone

        for i in range(len(frame)):
            row = frame.iloc[i]
            if bool(row["sweep_low"]):
                last_sweep[1] = i
            if bool(row["sweep_high"]):
                last_sweep[-1] = i
            if bool(row["bull_break"]):
                last_break[1] = i
            if bool(row["bear_break"]):
                last_break[-1] = i
            if i < 200:
                continue

            for direction in (Direction.LONG, Direction.SHORT):
                d = direction.value
                trigger_flags = (
                    ("FVG geri çekilmesi", bool(row["fvg_touch_long"] if d > 0 else row["fvg_touch_short"])),
                    ("IFVG yeniden testi", bool(row["ifvg_touch_long"] if d > 0 else row["ifvg_touch_short"])),
                    ("Order block yeniden testi", bool(row["ob_touch_long"] if d > 0 else row["ob_touch_short"])),
                    ("Üç mum dönüş teyidi", bool(row["three_bull"] if d > 0 else row["three_bear"])),
                )
                active_triggers = [name for name, active in trigger_flags if active]
                if not active_triggers or i - last_signal[d] < 8:
                    continue
                ordered_chain = last_sweep[d] <= last_break[d] <= i
                recent_chain = i - last_sweep[d] <= 60 and i - last_break[d] <= 35
                score, reasons = self._context_score(row, direction)
                if ordered_chain and recent_chain:
                    score += 25
                    reasons.insert(0, "Likidite sweep → yapı kırılımı sırası doğrulandı")
                elif last_break[d] >= i - 20:
                    score += 10
                    reasons.insert(0, "Yakın zamanda yönlü yapı kırılımı oluştu")
                else:
                    continue
                score += min(15, 9 + 3 * (len(active_triggers) - 1))
                reasons.extend(active_triggers)
                trigger_zone = zones_by_touch.get((i, d))
                entry, stop, target, rr, warnings = self._risk_plan(frame, i, direction, trigger_zone)
                confirmed = score >= self.min_signal_score and rr is not None and rr >= 1.5
                if not confirmed and score < self.watch_score:
                    continue
                action = (
                    SignalAction.BUY if confirmed and d > 0 else
                    SignalAction.SELL if confirmed else
                    SignalAction.WATCH
                )
                setup = active_triggers[0]
                invalidation = (
                    f"{stop:.5f} altında kapanış" if d > 0 and stop is not None else
                    f"{stop:.5f} üzerinde kapanış" if stop is not None else
                    "Yapı yönünün bozulması"
                )
                signal = Signal(
                    uid=self._uid(symbol, timeframe, frame.index[i], action, direction, setup),
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=frame.index[i],
                    bar=i,
                    action=action,
                    stage=SignalStage.CONFIRMED if confirmed else SignalStage.WATCHING,
                    direction=direction,
                    score=int(min(100, score)),
                    setup=setup,
                    entry=entry,
                    stop=stop,
                    target=target,
                    rr=rr,
                    reasons=tuple(reasons),
                    warnings=tuple(warnings),
                    invalidation=invalidation,
                )
                signals.append(signal)
                last_signal[d] = i
        return signals

    def analyze(self, bundle: MarketDataBundle) -> AnalysisSnapshot:
        if not bundle.quality.valid_for_signals:
            details = "; ".join(x.message for x in bundle.quality.issues) or "Veri yetersiz."
            raise ValueError(f"Sinyal analizi durduruldu: {details}")
        indicators = compute_indicator_frame(bundle.closed_bars)
        structure = analyze_structure(indicators)
        frame = structure.frame
        signals = self._signals(bundle.symbol, bundle.timeframe, frame, structure.zones)
        row = frame.iloc[-1]
        long_score, long_reasons = self._context_score(row, Direction.LONG)
        short_score, short_reasons = self._context_score(row, Direction.SHORT)
        direction = Direction.LONG if long_score > short_score + 6 else Direction.SHORT if short_score > long_score + 6 else Direction.NEUTRAL
        score = max(long_score, short_score)
        regime = self._regime(row)
        reasons = long_reasons if direction is Direction.LONG else short_reasons if direction is Direction.SHORT else []
        narrative = (
            f"{bundle.symbol} {bundle.timeframe.label} görünümü {direction.tr.lower()}; "
            f"rejim {regime.lower()}. "
            + ("; ".join(reasons[:3]) + "." if reasons else "Yön için yeterli birleşik teyit yok.")
        )
        active_zones = [z for z in structure.zones if z.state in ("ACTIVE", "TOUCHED")]
        latest = signals[-1] if signals else None
        mtf_context = self._derived_mtf_context(bundle.closed_bars, bundle.timeframe)
        aligned_higher = [
            label for label, item in mtf_context.items()
            if int(item["direction_value"]) == direction.value and direction is not Direction.NEUTRAL
        ]
        session_label = (
            "Günlük" if bundle.timeframe is Timeframe.D1
            else "Çoklu seans" if bundle.timeframe is Timeframe.H4
            else str(row["session"])
        )
        metrics = {
            "EMA20": float(row["ema20"]) if np.isfinite(row["ema20"]) else None,
            "EMA50": float(row["ema50"]) if np.isfinite(row["ema50"]) else None,
            "EMA200": float(row["ema200"]) if np.isfinite(row["ema200"]) else None,
            "VWAP": float(row["vwap"]) if np.isfinite(row["vwap"]) else None,
            "ATR": float(row["atr"]) if np.isfinite(row["atr"]) else None,
            "ATR Yüzdesi": float(row["atr_pct"] * 100) if np.isfinite(row["atr_pct"]) else None,
            "RSI": float(row["rsi"]) if np.isfinite(row["rsi"]) else None,
            "ADX": float(row["adx"]) if np.isfinite(row["adx"]) else None,
            "Göreli Hacim": float(row["relative_volume"]) if np.isfinite(row["relative_volume"]) else None,
            "Seans": session_label,
            "Destek": float(row["support"]) if np.isfinite(row["support"]) else None,
            "Direnç": float(row["resistance"]) if np.isfinite(row["resistance"]) else None,
            "Aktif Bölge": len(active_zones),
            "Üst TF Hizası": ", ".join(aligned_higher) if aligned_higher else "Hizalı üst TF yok",
        }
        return AnalysisSnapshot(
            symbol=bundle.symbol,
            timeframe=bundle.timeframe,
            asof=frame.index[-1],
            price=float(row["close"]),
            direction=direction,
            regime=regime,
            score=int(min(100, score)),
            narrative=narrative,
            metrics=metrics,
            latest_signal=latest,
            signals=signals,
            zones=active_zones,
            structure_events=structure.events,
            frame=frame,
            quality=bundle.quality,
            source=bundle.source,
            mtf_context=mtf_context,
        )
