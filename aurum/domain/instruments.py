from __future__ import annotations

from .models import InstrumentSpec


DEFAULT_INSTRUMENTS: dict[str, InstrumentSpec] = {
    "BTCUSD": InstrumentSpec(
        "BTCUSD", ("BTCUSD", "BTCUSDm", "BTCUSD.a", "BTCUSDT", "BTC/USD"), "Kripto", True
    ),
    "ETHUSD": InstrumentSpec(
        "ETHUSD", ("ETHUSD", "ETHUSDm", "ETHUSD.a", "ETHUSDT", "ETH/USD"), "Kripto", True
    ),
    "XAUUSD": InstrumentSpec(
        "XAUUSD", ("XAUUSD", "XAUUSD.m", "XAUUSDm", "GOLD", "XAU/USD"), "Metal"
    ),
    "XAGUSD": InstrumentSpec(
        "XAGUSD", ("XAGUSD", "XAGUSD.m", "XAGUSDm", "SILVER", "XAG/USD"), "Metal"
    ),
}


def aliases_for(symbol: str) -> tuple[str, ...]:
    clean = symbol.strip().upper()
    spec = DEFAULT_INSTRUMENTS.get(clean)
    return spec.aliases if spec else (symbol.strip(),)


def is_continuous(symbol: str) -> bool:
    spec = DEFAULT_INSTRUMENTS.get(symbol.strip().upper())
    return bool(spec and spec.continuous)


def is_crypto(symbol: str) -> bool:
    spec = DEFAULT_INSTRUMENTS.get(symbol.strip().upper())
    return bool(spec and spec.asset_class == "Kripto")
