from __future__ import annotations

from aurum.data.crypto_client import BinancePublicClient
from aurum.domain.models import Timeframe


class FakeBinance(BinancePublicClient):
    def _request_page(self, symbol, interval, limit, end_time):
        base = 1_786_560_000_000
        return [
            [base + i * 900_000, "4400.10", "4402.20", "4398.00", "4401.50", "12.5"]
            for i in range(limit)
        ]


def test_crypto_client_normalizes_public_klines():
    result = FakeBinance().fetch_bars("BTCUSD", Timeframe.M15, 60)

    assert result.source == "Binance Public"
    assert result.symbol == "BTCUSD"
    assert len(result.frame) == 60
    assert list(result.frame.columns) == ["open", "high", "low", "close", "volume"]
    assert result.frame.index.tz is not None
