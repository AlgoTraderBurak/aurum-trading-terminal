"""Internal MT5 subprocess entrypoint. It never exposes order operations."""

from __future__ import annotations

import pickle
import sys

import pandas as pd

from aurum.domain.instruments import aliases_for


def _resolve(mt5, requested: str) -> str:
    for candidate in aliases_for(requested):
        info = mt5.symbol_info(candidate)
        if info is not None:
            if not info.visible and not mt5.symbol_select(candidate, True):
                continue
            return candidate
    key = requested.upper().replace("/", "")
    matches = [
        x.name for x in (mt5.symbols_get() or ())
        if key in x.name.upper().replace("/", "")
    ]
    if matches:
        matches.sort(key=lambda x: (len(x), x))
        if mt5.symbol_select(matches[0], True):
            return matches[0]
    raise RuntimeError(f"MT5 içinde '{requested}' için uygun sembol bulunamadı.")


def fetch_payload(requested: str, timeframe_label: str, count: int) -> dict:
    try:
        import MetaTrader5 as mt5
    except ImportError as exc:
        return {"ok": False, "error": f"MetaTrader5 Python paketi kurulu değil: {exc}"}
    try:
        if not mt5.initialize(timeout=3000):
            return {"ok": False, "error": f"MT5 bağlantısı kurulamadı: {mt5.last_error()}"}
        symbol = _resolve(mt5, requested)
        timeframe = getattr(mt5, f"TIMEFRAME_{timeframe_label}", None)
        if timeframe is None:
            return {"ok": False, "error": f"MT5 zaman dilimi desteklenmiyor: {timeframe_label}"}
        rates = mt5.copy_rates_from_pos(symbol, int(timeframe), 0, int(count))
        if rates is None or len(rates) == 0:
            return {
                "ok": False,
                "error": f"{symbol} {timeframe_label} verisi alınamadı: {mt5.last_error()}",
            }
        raw = pd.DataFrame(rates)
        raw["timestamp"] = pd.to_datetime(raw["time"], unit="s", utc=True)
        volume_col = "real_volume"
        if volume_col not in raw or float(raw[volume_col].sum()) <= 0:
            volume_col = "tick_volume"
        frame = raw.set_index("timestamp")[["open", "high", "low", "close", volume_col]]
        frame = frame.rename(columns={volume_col: "volume"})
        info = mt5.symbol_info(symbol)
        metadata = {
            "requested": requested,
            "resolved": symbol,
            "description": str(getattr(info, "description", "") or ""),
            "digits": int(getattr(info, "digits", 5) or 5),
            "point": float(getattr(info, "point", 0.00001) or 0.00001),
            "tick_size": float(getattr(info, "trade_tick_size", 0.0) or getattr(info, "point", 0.00001)),
            "tick_value": float(getattr(info, "trade_tick_value", 0.0) or 0.0),
            "contract_size": float(getattr(info, "trade_contract_size", 0.0) or 0.0),
            "volume_min": float(getattr(info, "volume_min", 0.01) or 0.01),
            "volume_max": float(getattr(info, "volume_max", 100.0) or 100.0),
            "volume_step": float(getattr(info, "volume_step", 0.01) or 0.01),
            "currency_profit": str(getattr(info, "currency_profit", "") or ""),
        }
        return {"ok": True, "symbol": symbol, "frame": frame, "metadata": metadata}
    except Exception as exc:
        return {"ok": False, "error": f"MT5 veri işlemi başarısız: {type(exc).__name__}: {exc}"}
    finally:
        mt5.shutdown()


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 3:
        payload = {"ok": False, "error": "MT5 yardımcı süreç argümanları geçersiz."}
    else:
        payload = fetch_payload(args[0], args[1], int(args[2]))
    sys.stdout.buffer.write(pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL))
    sys.stdout.buffer.flush()
    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
