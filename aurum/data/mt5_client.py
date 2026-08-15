from __future__ import annotations

import os
import pickle
import subprocess
import sys
import threading
from pathlib import Path

from aurum.data.provider import MarketFetch
from aurum.data.quality import normalize_bars
from aurum.domain.models import SymbolMetadata, Timeframe


class MT5Error(RuntimeError):
    pass


MT5Fetch = MarketFetch


class MT5ReadOnlyClient:
    """MT5 reads isolated in a subprocess so a native IPC hang cannot freeze Qt."""

    def __init__(self, timeout_seconds: float = 12.0) -> None:
        self.timeout_seconds = timeout_seconds
        self.root = Path(__file__).resolve().parents[2]
        self._fetch_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._active: set[subprocess.Popen] = set()
        self._closed = False

    def fetch_bars(self, requested: str, timeframe: Timeframe, count: int = 2500) -> MT5Fetch:
        if count < 50:
            raise ValueError("En az 50 bar istenmelidir.")
        command = [
            sys.executable,
            "-m",
            "aurum.data.mt5_process",
            requested,
            timeframe.label,
            str(int(count)),
        ]
        env = os.environ.copy()
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(self.root) + (os.pathsep + existing if existing else "")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        with self._fetch_lock:
            with self._state_lock:
                if self._closed:
                    raise MT5Error("MT5 istemcisi kapatıldı.")
            try:
                process = subprocess.Popen(
                    command,
                    cwd=self.root,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=flags,
                )
                with self._state_lock:
                    self._active.add(process)
                try:
                    stdout, stderr = process.communicate(timeout=self.timeout_seconds)
                except subprocess.TimeoutExpired as exc:
                    process.kill()
                    process.communicate()
                    raise MT5Error(
                        f"MT5 {self.timeout_seconds:g} saniye içinde yanıt vermedi; yardımcı süreç durduruldu."
                    ) from exc
                finally:
                    with self._state_lock:
                        self._active.discard(process)
            except OSError as exc:
                raise MT5Error(f"MT5 yardımcı süreci başlatılamadı: {exc}") from exc
        if not stdout:
            detail = stderr.decode("utf-8", errors="replace").strip()
            raise MT5Error(detail or f"MT5 yardımcı süreci kod {process.returncode} ile kapandı.")
        try:
            payload = pickle.loads(stdout)
        except Exception as exc:
            detail = stderr.decode("utf-8", errors="replace").strip()
            raise MT5Error(f"MT5 cevabı okunamadı: {detail or exc}") from exc
        if not payload.get("ok"):
            raise MT5Error(str(payload.get("error", "MT5 verisi alınamadı.")))
        metadata = SymbolMetadata(**payload["metadata"])
        return MarketFetch(payload["symbol"], normalize_bars(payload["frame"]), metadata, "MT5")

    def close(self) -> None:
        with self._state_lock:
            self._closed = True
            active = list(self._active)
        for process in active:
            if process.poll() is None:
                process.terminate()
