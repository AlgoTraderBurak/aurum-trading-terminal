from __future__ import annotations

from pathlib import Path

import pandas as pd

from aurum.data.cache import BarCache
from aurum.data.crypto_client import BinancePublicClient, CryptoDataError
from aurum.data.mt5_client import MT5Error, MT5ReadOnlyClient
from aurum.data.provider import MarketDataClient
from aurum.data.quality import split_closed_bars, validate_bars
from aurum.domain.instruments import is_continuous, is_crypto
from aurum.domain.models import MarketDataBundle, SymbolMetadata, Timeframe


class DataUnavailableError(RuntimeError):
    pass


class DataService:
    def __init__(self, data_dir: str | Path, client: MarketDataClient | None = None) -> None:
        self.data_dir = Path(data_dir)
        self.cache = BarCache(self.data_dir / "aurum_cache.sqlite3")
        self.client = client
        self.mt5_client: MT5ReadOnlyClient | None = None
        self.crypto_client: BinancePublicClient | None = None

    def _client(self, symbol: str) -> MarketDataClient:
        if self.client is not None:
            return self.client
        if is_crypto(symbol):
            if self.crypto_client is None:
                self.crypto_client = BinancePublicClient()
            return self.crypto_client
        if self.mt5_client is None:
            self.mt5_client = MT5ReadOnlyClient()
        return self.mt5_client

    def fetch(
        self,
        symbol: str,
        timeframe: Timeframe | str,
        *,
        count: int = 2500,
        allow_cache: bool = True,
    ) -> MarketDataBundle:
        tf = Timeframe.parse(timeframe)
        now = pd.Timestamp.now(tz="UTC")
        provider_error: Exception | None = None
        try:
            result = self._client(symbol).fetch_bars(symbol, tf, count)
            incoming_quality = validate_bars(
                result.frame, tf, continuous=is_continuous(symbol), now=now
            )
            if not incoming_quality.valid_for_signals:
                return MarketDataBundle(
                    requested_symbol=symbol,
                    symbol=result.symbol,
                    timeframe=tf,
                    bars=result.frame,
                    closed_bars=result.frame,
                    current_bar=None,
                    source=result.source,
                    metadata=result.metadata,
                    quality=incoming_quality,
                    fetched_at=now,
                )
            closed, current = split_closed_bars(result.frame, tf, now)
            # Merge prior closed history with the latest provider window. The still-open
            # bar remains separate and is never persisted or analyzed.
            cached = self.cache.load(result.symbol, tf, max(2500, count))
            if not cached.empty:
                closed = pd.concat([cached, closed])
                closed = closed[~closed.index.duplicated(keep="last")].sort_index().tail(max(2500, count))
            quality = validate_bars(closed, tf, continuous=is_continuous(symbol), now=now)
            if quality.valid_for_signals:
                self.cache.store(result.symbol, tf, closed)
                if result.symbol != symbol:
                    self.cache.store(symbol, tf, closed)
            bars = closed.copy()
            if current is not None:
                bars.loc[result.frame.index[-1]] = current
            return MarketDataBundle(
                requested_symbol=symbol,
                symbol=result.symbol,
                timeframe=tf,
                bars=bars,
                closed_bars=closed,
                current_bar=current,
                source=result.source,
                metadata=result.metadata,
                quality=quality,
                fetched_at=now,
            )
        except (MT5Error, CryptoDataError, ValueError, TypeError) as exc:
            provider_error = exc

        if allow_cache:
            cached = self.cache.load(symbol, tf, count)
            if not cached.empty:
                quality = validate_bars(cached, tf, continuous=is_continuous(symbol), now=now)
                return MarketDataBundle(
                    requested_symbol=symbol,
                    symbol=symbol,
                    timeframe=tf,
                    bars=cached,
                    closed_bars=cached,
                    current_bar=None,
                    source=f"Önbellek (sağlayıcı hatası: {provider_error})",
                    metadata=SymbolMetadata(symbol, symbol),
                    quality=quality,
                    fetched_at=now,
                )
        raise DataUnavailableError(str(provider_error or "Piyasa verisi bulunamadı."))

    def close(self) -> None:
        for client in (self.client, self.mt5_client, self.crypto_client):
            if client is not None:
                client.close()
