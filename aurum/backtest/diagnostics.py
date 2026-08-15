from __future__ import annotations

from collections import defaultdict

from aurum.domain.models import AnalysisSnapshot, BacktestResult


def diagnose_backtest(snapshot: AnalysisSnapshot, result: BacktestResult) -> list[str]:
    """Yalnızca gerçekleşen işlemlerden kanıt üretir; parametre değiştirmez."""
    trades = result.trades
    if not trades:
        return ["Onaylı ve uygulanabilir işlem oluşmadı; performans teşhisi için örneklem yok."]
    notes = [
        f"{len(trades)} işlemde beklenti {result.metrics['expectancy_r']:+.2f} R, toplam sonuç {result.metrics['net_r']:+.2f} R."
    ]
    if len(trades) < 20:
        notes.append("Örneklem 20 işlemin altında; filtre değişikliği için istatistiksel güven zayıf.")

    losses = [trade for trade in trades if trade.net_r <= 0]
    recoverable = [trade for trade in losses if trade.mfe_r >= 0.75]
    if losses:
        ratio = len(recoverable) / len(losses) * 100.0
        notes.append(
            f"Zararların %{ratio:.0f}'i kapanmadan önce en az +0.75 R lehine hareket etti "
            f"({len(recoverable)}/{len(losses)}); çıkış yönetimi ayrı test edilmeli."
        )

    signal_by_uid = {signal.uid: signal for signal in snapshot.signals}
    timeframe_label = getattr(getattr(snapshot, "timeframe", None), "label", "")
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    for trade in trades:
        signal = signal_by_uid.get(trade.signal_uid)
        grouped[("Yön", trade.direction.tr)].append(trade.net_r)
        if signal is not None:
            grouped[("Kurulum", signal.setup)].append(trade.net_r)
            if signal.timestamp in snapshot.frame.index:
                session = (
                    "Günlük" if timeframe_label == "D1"
                    else "Çoklu seans" if timeframe_label == "H4"
                    else str(snapshot.frame.loc[signal.timestamp].get("session", "Bilinmiyor"))
                )
                grouped[("Seans", session)].append(trade.net_r)

    candidates = [
        (sum(values) / len(values), kind, name, len(values), sum(values))
        for (kind, name), values in grouped.items()
        if len(values) >= 3
    ]
    if candidates:
        average, kind, name, count, total = min(candidates, key=lambda item: item[0])
        notes.append(
            f"En zayıf doğrulanabilir grup: {kind} “{name}” · {count} işlem · "
            f"ortalama {average:+.2f} R · toplam {total:+.2f} R."
        )

    notes.append(
        f"Ortalama MFE {result.metrics['avg_mfe_r']:.2f} R, ortalama MAE {result.metrics['avg_mae_r']:.2f} R; "
        "öneriler walk-forward/out-of-sample test edilmeden uygulanmamalı."
    )
    return notes
