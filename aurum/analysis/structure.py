from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1

import numpy as np
import pandas as pd

from aurum.domain.models import Direction, StructureEvent, Zone, ZoneKind


@dataclass
class StructureResult:
    frame: pd.DataFrame
    events: list[StructureEvent]
    zones: list[Zone]


def _uid(*parts: object) -> str:
    return sha1("|".join(map(str, parts)).encode("utf-8")).hexdigest()[:16]


def _pivot_masks(high: np.ndarray, low: np.ndarray, left: int, right: int) -> tuple[np.ndarray, np.ndarray]:
    n = len(high)
    ph = np.zeros(n, dtype=bool)
    pl = np.zeros(n, dtype=bool)
    for i in range(left, n - right):
        if high[i] >= np.max(high[i - left : i]) and high[i] > np.max(high[i + 1 : i + right + 1]):
            ph[i] = True
        if low[i] <= np.min(low[i - left : i]) and low[i] < np.min(low[i + 1 : i + right + 1]):
            pl[i] = True
    return ph, pl


def _inside(minutes: int, start: int, end: int) -> bool:
    return start <= minutes < end if start < end else minutes >= start or minutes < end


def analyze_structure(
    frame: pd.DataFrame,
    *,
    pivot_left: int = 3,
    pivot_right: int = 2,
    fvg_atr: float = 0.15,
    zone_max_age: int = 360,
) -> StructureResult:
    out = frame.copy()
    n = len(out)
    h = out["high"].to_numpy(dtype=float)
    l = out["low"].to_numpy(dtype=float)
    o = out["open"].to_numpy(dtype=float)
    c = out["close"].to_numpy(dtype=float)
    atr = out["atr"].to_numpy(dtype=float)
    ph, pl = _pivot_masks(h, l, pivot_left, pivot_right)

    structure_bias = np.zeros(n, dtype=int)
    support = np.full(n, np.nan)
    resistance = np.full(n, np.nan)
    sweep_high = np.zeros(n, dtype=bool)
    sweep_low = np.zeros(n, dtype=bool)
    bull_break = np.zeros(n, dtype=bool)
    bear_break = np.zeros(n, dtype=bool)
    fvg_touch_long = np.zeros(n, dtype=bool)
    fvg_touch_short = np.zeros(n, dtype=bool)
    ifvg_touch_long = np.zeros(n, dtype=bool)
    ifvg_touch_short = np.zeros(n, dtype=bool)
    ob_touch_long = np.zeros(n, dtype=bool)
    ob_touch_short = np.zeros(n, dtype=bool)
    three_bull = np.zeros(n, dtype=bool)
    three_bear = np.zeros(n, dtype=bool)

    pivot_schedule: dict[int, list[tuple[str, float, int]]] = {}
    for pos in np.flatnonzero(ph):
        pivot_schedule.setdefault(int(pos + pivot_right), []).append(("HIGH", float(h[pos]), int(pos)))
    for pos in np.flatnonzero(pl):
        pivot_schedule.setdefault(int(pos + pivot_right), []).append(("LOW", float(l[pos]), int(pos)))

    events: list[StructureEvent] = []
    raw_zones: list[dict] = []
    liquidity: list[dict] = []
    active_high: tuple[float, int] | None = None
    active_low: tuple[float, int] | None = None
    trend = 0
    previous_day = None
    day_high = day_low = None
    sessions = (("ASYA", 0, 480), ("LONDRA", 420, 960), ("NEW_YORK", 810, 1260))
    session_state = {name: {"inside": False, "high": None, "low": None} for name, _, _ in sessions}

    for i, ts in enumerate(out.index):
        day = ts.date()
        if previous_day is None:
            previous_day, day_high, day_low = day, h[i], l[i]
        elif day != previous_day:
            liquidity.append({"side": "HIGH", "price": float(day_high), "born": i, "swept": False, "source": "PDH"})
            liquidity.append({"side": "LOW", "price": float(day_low), "born": i, "swept": False, "source": "PDL"})
            previous_day, day_high, day_low = day, h[i], l[i]
        else:
            day_high, day_low = max(float(day_high), h[i]), min(float(day_low), l[i])

        minute = ts.hour * 60 + ts.minute
        for name, start, end in sessions:
            state = session_state[name]
            now_inside = _inside(minute, start, end)
            if now_inside:
                state["high"] = h[i] if state["high"] is None else max(state["high"], h[i])
                state["low"] = l[i] if state["low"] is None else min(state["low"], l[i])
            elif state["inside"] and state["high"] is not None:
                liquidity.append({"side": "HIGH", "price": float(state["high"]), "born": i, "swept": False, "source": name})
                liquidity.append({"side": "LOW", "price": float(state["low"]), "born": i, "swept": False, "source": name})
                state["high"] = state["low"] = None
            state["inside"] = now_inside

        # Existing liquidity is tested before newly confirmed pivots become active.
        for level in liquidity[-160:]:
            if level["swept"] or level["born"] >= i:
                continue
            if level["side"] == "HIGH" and h[i] > level["price"] and c[i] < level["price"]:
                level["swept"] = True
                sweep_high[i] = True
                events.append(StructureEvent("SWEEP_HIGH", Direction.SHORT, i, ts, level["price"], level["born"]))
            elif level["side"] == "LOW" and l[i] < level["price"] and c[i] > level["price"]:
                level["swept"] = True
                sweep_low[i] = True
                events.append(StructureEvent("SWEEP_LOW", Direction.LONG, i, ts, level["price"], level["born"]))

        for kind, price, source_bar in pivot_schedule.get(i, []):
            liquidity.append({"side": kind, "price": price, "born": i, "swept": False, "source": "SWING"})
            if kind == "HIGH":
                active_high = (price, source_bar)
            else:
                active_low = (price, source_bar)

        structure_event: StructureEvent | None = None
        if active_high and c[i] > active_high[0]:
            kind = "BOS_BULL" if trend == 1 else "CHOCH_BULL"
            structure_event = StructureEvent(kind, Direction.LONG, i, ts, active_high[0], active_high[1])
            trend = 1
            active_high = None
            bull_break[i] = True
        elif active_low and c[i] < active_low[0]:
            kind = "BOS_BEAR" if trend == -1 else "CHOCH_BEAR"
            structure_event = StructureEvent(kind, Direction.SHORT, i, ts, active_low[0], active_low[1])
            trend = -1
            active_low = None
            bear_break[i] = True
        if structure_event:
            events.append(structure_event)
            # Last opposite candle before a confirmed structure break becomes an OB candidate.
            for j in range(i - 1, max(-1, i - 13), -1):
                if structure_event.direction is Direction.LONG and c[j] < o[j]:
                    raw_zones.append({"kind": ZoneKind.ORDER_BLOCK, "dir": 1, "lower": l[j], "upper": o[j], "born": i, "origin": j, "state": "ACTIVE", "touched": None, "invalid": None})
                    break
                if structure_event.direction is Direction.SHORT and c[j] > o[j]:
                    raw_zones.append({"kind": ZoneKind.ORDER_BLOCK, "dir": -1, "lower": o[j], "upper": h[j], "born": i, "origin": j, "state": "ACTIVE", "touched": None, "invalid": None})
                    break

        structure_bias[i] = trend
        if active_low:
            support[i] = active_low[0]
        if active_high:
            resistance[i] = active_high[0]

        # Update zones born on prior bars only.
        inverse_to_add: list[dict] = []
        for zone in raw_zones:
            if zone["state"] not in ("ACTIVE", "TOUCHED") or zone["born"] >= i:
                continue
            if i - zone["born"] > zone_max_age:
                zone["state"] = "EXPIRED"
                continue
            overlap = l[i] <= zone["upper"] and h[i] >= zone["lower"]
            if zone["dir"] == 1 and c[i] < zone["lower"]:
                zone["state"] = "INVALID"
                zone["invalid"] = i
                if zone["kind"] is ZoneKind.FVG:
                    inverse_to_add.append({"kind": ZoneKind.IFVG, "dir": -1, "lower": zone["lower"], "upper": zone["upper"], "born": i, "origin": zone["origin"], "state": "ACTIVE", "touched": None, "invalid": None})
            elif zone["dir"] == -1 and c[i] > zone["upper"]:
                zone["state"] = "INVALID"
                zone["invalid"] = i
                if zone["kind"] is ZoneKind.FVG:
                    inverse_to_add.append({"kind": ZoneKind.IFVG, "dir": 1, "lower": zone["lower"], "upper": zone["upper"], "born": i, "origin": zone["origin"], "state": "ACTIVE", "touched": None, "invalid": None})
            elif overlap and zone["touched"] is None:
                zone["touched"] = i
                zone["state"] = "TOUCHED"
                if zone["kind"] is ZoneKind.FVG:
                    (fvg_touch_long if zone["dir"] == 1 else fvg_touch_short)[i] = True
                elif zone["kind"] is ZoneKind.IFVG:
                    (ifvg_touch_long if zone["dir"] == 1 else ifvg_touch_short)[i] = True
                elif zone["kind"] is ZoneKind.ORDER_BLOCK:
                    (ob_touch_long if zone["dir"] == 1 else ob_touch_short)[i] = True
        raw_zones.extend(inverse_to_add)

        if i >= 2 and np.isfinite(atr[i]) and atr[i] > 0:
            bull_gap = l[i] - h[i - 2]
            bear_gap = l[i - 2] - h[i]
            if bull_gap >= fvg_atr * atr[i]:
                raw_zones.append({"kind": ZoneKind.FVG, "dir": 1, "lower": h[i - 2], "upper": l[i], "born": i, "origin": i - 2, "state": "ACTIVE", "touched": None, "invalid": None})
            if bear_gap >= fvg_atr * atr[i]:
                raw_zones.append({"kind": ZoneKind.FVG, "dir": -1, "lower": h[i], "upper": l[i - 2], "born": i, "origin": i - 2, "state": "ACTIVE", "touched": None, "invalid": None})

        if i >= 2:
            three_bull[i] = c[i - 2] < o[i - 2] and l[i - 1] < l[i - 2] and c[i] > h[i - 1]
            three_bear[i] = c[i - 2] > o[i - 2] and h[i - 1] > h[i - 2] and c[i] < l[i - 1]

    out["structure_bias"] = structure_bias
    out["support"] = pd.Series(support, index=out.index).ffill()
    out["resistance"] = pd.Series(resistance, index=out.index).ffill()
    out["sweep_high"] = sweep_high
    out["sweep_low"] = sweep_low
    out["bull_break"] = bull_break
    out["bear_break"] = bear_break
    out["fvg_touch_long"] = fvg_touch_long
    out["fvg_touch_short"] = fvg_touch_short
    out["ifvg_touch_long"] = ifvg_touch_long
    out["ifvg_touch_short"] = ifvg_touch_short
    out["ob_touch_long"] = ob_touch_long
    out["ob_touch_short"] = ob_touch_short
    out["three_bull"] = three_bull
    out["three_bear"] = three_bear

    zones = [
        Zone(
            uid=_uid(z["kind"].value, z["dir"], out.index[z["born"]], z["lower"], z["upper"]),
            kind=z["kind"],
            direction=Direction.LONG if z["dir"] == 1 else Direction.SHORT,
            lower=float(z["lower"]),
            upper=float(z["upper"]),
            born_at=out.index[z["born"]],
            born_bar=int(z["born"]),
            state=z["state"],
            touched_at=out.index[z["touched"]] if z["touched"] is not None else None,
            invalidated_at=out.index[z["invalid"]] if z["invalid"] is not None else None,
            source_event=f"bar:{z['origin']}",
        )
        for z in raw_zones
    ]
    return StructureResult(out, events, zones)
