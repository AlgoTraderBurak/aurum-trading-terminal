from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from aurum.data.provider import MarketFetch
from aurum.data.quality import normalize_bars
from aurum.domain.models import SymbolMetadata, Timeframe


class CryptoDataError(RuntimeError):
    pass


class BinancePublicClient:
    """Anahtar gerektirmeyen Binance spot mum istemcisi; emir işlemi içermez."""

    BASE_URL = "https://api.binance.com/api/v3/klines"
    SYMBOLS = {"BTCUSD": "BTCUSDT", "ETHUSD": "ETHUSDT"}
    INTERVALS = {
        Timeframe.M1: "1m",
        Timeframe.M5: "5m",
        Timeframe.M15: "15m",
        Timeframe.H1: "1h",
        Timeframe.H4: "4h",
        Timeframe.D1: "1d",
    }

    def __init__(self, timeout_seconds: float = 8.0) -> None:
        self.timeout_seconds = timeout_seconds
        self._closed = False

    def _request_page(self, symbol: str, interval: str, limit: int, end_time: int | None) -> list[list]:
        params: dict[str, object] = {"symbol": symbol, "interval": interval, "limit": limit}
        if end_time is not None:
            params["endTime"] = end_time
        request = Request(
            self.BASE_URL + "?" + urlencode(params),
            headers={"User-Agent": "AURUM-Market-Observer/1.0"},
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise CryptoDataError(f"Kripto veri servisi HTTP {exc.code} döndürdü.") from exc
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise CryptoDataError(f"Kripto veri servisine ulaşılamadı: {exc}") from exc
        if not isinstance(payload, list):
            raise CryptoDataError(f"Kripto veri servisi geçersiz cevap verdi: {payload}")
        return payload

    def fetch_bars(self, requested: str, timeframe: Timeframe, count: int = 2500) -> MarketFetch:
        if self._closed:
            raise CryptoDataError("Kripto veri istemcisi kapatıldı.")
        if count < 50:
            raise ValueError("En az 50 bar istenmelidir.")
        logical = requested.strip().upper().replace("/", "")
        exchange_symbol = self.SYMBOLS.get(logical)
        if exchange_symbol is None:
            raise CryptoDataError(f"Desteklenmeyen kripto sembolü: {requested}")
        remaining = int(count)
        end_time: int | None = None
        pages: list[list] = []
        while remaining > 0:
            page = self._request_page(exchange_symbol, self.INTERVALS[timeframe], min(1000, remaining), end_time)
            if not page:
                break
            pages.extend(page)
            remaining -= len(page)
            oldest = min(int(row[0]) for row in page)
            end_time = oldest - 1
            if len(page) < min(1000, remaining + len(page)):
                break
        if len(pages) < 50:
            raise CryptoDataError(f"{exchange_symbol} için yeterli mum alınamadı ({len(pages)}).")
        rows = {
            int(row[0]): {
                "open": float(row[1]), "high": float(row[2]), "low": float(row[3]),
                "close": float(row[4]), "volume": float(row[5]),
            }
            for row in pages
        }
        frame = pd.DataFrame.from_dict(rows, orient="index").sort_index().tail(count)
        frame.index = pd.to_datetime(frame.index, unit="ms", utc=True)
        frame.index.name = "timestamp"
        close_text = str(pages[-1][4]).rstrip("0")
        digits = len(close_text.partition(".")[2]) if "." in close_text else 0
        digits = max(2, min(8, digits))
        point = 10.0 ** (-digits)
        metadata = SymbolMetadata(
            requested=logical, resolved=exchange_symbol,
            description=f"{logical} spot piyasa verisi", digits=digits,
            point=point, tick_size=point, tick_value=0.0,
            contract_size=1.0, volume_min=0.00001, volume_max=1_000_000.0,
            volume_step=0.00001, currency_profit="USDT",
        )
        return MarketFetch(logical, normalize_bars(frame), metadata, "Binance Public")

    def close(self) -> None:
        self._closed = True
