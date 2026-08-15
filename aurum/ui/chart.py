from __future__ import annotations

import math

import numpy as np
import pandas as pd
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPainterPath, QPen, QPolygonF, QWheelEvent
from PySide6.QtWidgets import QWidget

from aurum.domain.models import (
    AnalysisSnapshot,
    Direction,
    MarketDataBundle,
    SignalAction,
    SignalStage,
    ZoneKind,
)
from aurum.ui.theme import AMBER, BG, BLUE, GREEN, GRID, MUTED, PANEL, PANEL_2, PURPLE, RED, TEXT


class MarketChart(QWidget):
    """Katmanlı, yakınlaştırılabilir ve yalnızca eldeki veriyi çizen piyasa grafiği."""

    SESSION_COLORS = {
        "Asya": "#3b82f6",
        "Londra": "#22d3ee",
        "New York": "#a78bfa",
    }
    ZONE_COLORS = {
        ZoneKind.FVG: BLUE,
        ZoneKind.IFVG: PURPLE,
        ZoneKind.ORDER_BLOCK: AMBER,
        ZoneKind.BREAKER: RED,
        ZoneKind.LIQUIDITY: GREEN,
        ZoneKind.RANGE: MUTED,
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(500)
        self.setMouseTracking(True)
        self.snapshot: AnalysisSnapshot | None = None
        self.bundle: MarketDataBundle | None = None
        self.visible_bars = 150
        self.offset = 0
        self.drag_origin: QPoint | None = None
        self.hover: QPoint | None = None
        self.layers = {
            "trend": True,
            "ema": False,
            "vwap": False,
            "sessions": True,
            "structure": True,
            "zones": True,
            "levels": True,
            "signals": True,
            "rsi": False,
            "panel": True,
        }

    def set_data(self, bundle: MarketDataBundle, snapshot: AnalysisSnapshot) -> None:
        self.bundle = bundle
        self.snapshot = snapshot
        self.offset = 0
        self.update()

    def set_layer(self, name: str, enabled: bool) -> None:
        self.layers[name] = enabled
        self.update()

    def reset_view(self) -> None:
        self.visible_bars = 150
        self.offset = 0
        self.update()

    def wheelEvent(self, event: QWheelEvent) -> None:
        old = self.visible_bars
        factor = 0.82 if event.angleDelta().y() > 0 else 1.22
        self.visible_bars = max(35, min(650, int(round(old * factor))))
        self.update()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.reset_view()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.drag_origin = event.position().toPoint()
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        self.hover = pos
        if self.drag_origin is not None:
            delta = pos.x() - self.drag_origin.x()
            bars = int(delta / max(3.0, self.width() / max(1, self.visible_bars)))
            if bars:
                max_offset = max(0, len(self.snapshot.frame) - 20) if self.snapshot is not None else 0
                self.offset = max(0, min(max_offset, self.offset + bars))
                self.drag_origin = pos
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self.drag_origin = None
        self.unsetCursor()

    def leaveEvent(self, event) -> None:
        self.hover = None
        self.drag_origin = None
        self.unsetCursor()
        self.update()

    @staticmethod
    def _line(painter: QPainter, xs: np.ndarray, ys: np.ndarray, color: str, width: float = 1.2) -> None:
        valid = np.isfinite(ys)
        path = QPainterPath()
        started = False
        for x, y, ok in zip(xs, ys, valid):
            if not ok:
                started = False
                continue
            if not started:
                path.moveTo(float(x), float(y))
                started = True
            else:
                path.lineTo(float(x), float(y))
        painter.setPen(QPen(QColor(color), width))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

    @staticmethod
    def _safe_number(value: object, decimals: int = 1, suffix: str = "") -> str:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return "—"
        return f"{number:.{decimals}f}{suffix}" if np.isfinite(number) else "—"

    @staticmethod
    def _session_spans(index: pd.DatetimeIndex, labels: pd.Series) -> list[tuple[int, int, str]]:
        if len(index) == 0:
            return []
        values = labels.reindex(index).fillna("Kapalı/Geçiş").astype(str).tolist()
        spans: list[tuple[int, int, str]] = []
        start = 0
        for pos in range(1, len(values) + 1):
            if pos == len(values) or values[pos] != values[start]:
                if values[start] in MarketChart.SESSION_COLORS:
                    spans.append((start, pos - 1, values[start]))
                start = pos
        return spans

    def _draw_status_panel(self, painter: QPainter, rect: QRectF, view: pd.DataFrame) -> None:
        assert self.snapshot is not None
        snapshot = self.snapshot
        painter.fillRect(rect, QColor("#0d1421"))
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(GRID), 1))
        painter.drawRect(rect)

        header = QRectF(rect.left(), rect.top(), rect.width(), 34)
        painter.fillRect(header, QColor(PANEL_2))
        painter.setPen(QColor(TEXT))
        painter.drawText(header.adjusted(9, 0, -8, 0), Qt.AlignVCenter | Qt.AlignLeft, "AURUM CORE")
        painter.setPen(QColor(AMBER))
        painter.drawText(header.adjusted(9, 0, -8, 0), Qt.AlignVCenter | Qt.AlignRight, "Gözlemci • Sinyal")

        # Açık mum yalnızca fiyat çiziminde bulunur; durum paneli her zaman son
        # kapanmış ve indikatörleri tamamlanmış analiz satırını kullanır.
        row = snapshot.frame.iloc[-1]
        internal = int(row.get("structure_bias", 0))
        internal_text = "Yükseliş" if internal > 0 else "Düşüş" if internal < 0 else "Nötr"
        internal_color = GREEN if internal > 0 else RED if internal < 0 else AMBER
        direction_color = GREEN if snapshot.direction is Direction.LONG else RED if snapshot.direction is Direction.SHORT else AMBER
        vwap = row.get("vwap", np.nan)
        atr = row.get("atr", np.nan)
        vwap_distance = (snapshot.price - float(vwap)) / float(atr) if np.isfinite(vwap) and np.isfinite(atr) and atr else np.nan
        vwap_text = (
            f"{'Alıcı' if vwap_distance > 0 else 'Satıcı'} · {vwap_distance:+.2f} ATR"
            if np.isfinite(vwap_distance)
            else "—"
        )
        vwap_color = GREEN if np.isfinite(vwap_distance) and vwap_distance > 0 else RED if np.isfinite(vwap_distance) else MUTED
        zones = snapshot.zones
        zone_counts = {kind: sum(z.kind is kind for z in zones) for kind in ZoneKind}
        zone_text = f"FVG {zone_counts[ZoneKind.FVG]} · IFVG {zone_counts[ZoneKind.IFVG]} · OB {zone_counts[ZoneKind.ORDER_BLOCK]}"
        latest = snapshot.latest_signal
        signal_age = (
            (snapshot.asof - latest.timestamp).total_seconds() / snapshot.timeframe.seconds
            if latest is not None else float("inf")
        )
        current_signal = latest if signal_age <= 8 else None
        stage_text = {
            SignalStage.CONFIRMED: "Onaylandı",
            SignalStage.WATCHING: "Gözlemde",
            SignalStage.INVALIDATED: "Geçersiz",
        }.get(current_signal.stage, "—") if current_signal else "Kurulum bekleniyor"
        signal_color = GREEN if current_signal and current_signal.action is SignalAction.BUY else RED if current_signal and current_signal.action is SignalAction.SELL else AMBER
        recent_event = snapshot.structure_events[-1] if snapshot.structure_events else None
        event_name = self._event_label(recent_event.kind) if recent_event else "—"
        event_time = f" · {recent_event.timestamp:%d.%m %H:%M}" if recent_event else ""
        relationship = "Hizalı" if internal == snapshot.direction.value and internal else "Karışık"
        relationship_color = GREEN if relationship == "Hizalı" else AMBER
        volatility = self._safe_number(snapshot.metrics.get("ATR Yüzdesi"), 0, "%")
        digits = max(2, min(8, self.bundle.metadata.digits)) if self.bundle is not None else 5
        preferred_mtf = [label for label in ("H1", "H4", "D1", "M15", "M5") if label in snapshot.mtf_context]
        mtf_parts = []
        for label in preferred_mtf[:3]:
            item = snapshot.mtf_context[label]
            arrow = "↑" if int(item["direction_value"]) > 0 else "↓" if int(item["direction_value"]) < 0 else "•"
            mtf_parts.append(f"{label} {arrow}{int(item['score'])}")
        mtf_text = " · ".join(mtf_parts) if mtf_parts else "Yeterli üst TF verisi yok"
        mtf_aligned = snapshot.metrics.get("Üst TF Hizası") != "Hizalı üst TF yok"

        rows = [
            ("Seans", str(snapshot.metrics.get("Seans", "—")), MUTED),
            ("Dış yapı", snapshot.direction.tr, direction_color),
            ("İç yapı", internal_text, internal_color),
            ("Yapı ilişkisi", relationship, relationship_color),
            ("Üst TF", mtf_text, GREEN if mtf_aligned else AMBER),
            ("Rejim", snapshot.regime, AMBER),
            ("Volatilite", f"ATR yüzdelik {volatility}", TEXT),
            ("VWAP", vwap_text, vwap_color),
            ("Aktif bölgeler", zone_text, BLUE),
            ("Kurulum", current_signal.setup if current_signal else "—", TEXT),
            ("Durum", stage_text, signal_color),
            ("Beklenen", current_signal.action.tr if current_signal else "İŞLEM YOK", signal_color),
            ("Giriş", self._safe_number(current_signal.entry, digits) if current_signal else "—", TEXT),
            ("Stop", self._safe_number(current_signal.stop, digits) if current_signal else "—", RED),
            ("Hedef", self._safe_number(current_signal.target, digits) if current_signal else "—", GREEN),
            ("Net R:R", self._safe_number(current_signal.rr, 2) if current_signal else "—", AMBER),
            ("Sinyal puanı", f"{current_signal.score}/100" if current_signal else f"{snapshot.score}/100 görünüm", signal_color),
            ("Son olay", event_name + event_time, TEXT),
            ("Veri", f"{snapshot.source} · {snapshot.quality.status_tr}", GREEN if snapshot.quality.valid_for_signals else RED),
        ]

        row_height = max(17.0, min(22.0, (rect.height() - header.height() - 4) / len(rows)))
        label_width = min(98.0, rect.width() * 0.39)
        y = header.bottom()
        for label, value, color in rows:
            cell = QRectF(rect.left(), y, rect.width(), row_height)
            painter.setPen(QPen(QColor(GRID), 1))
            painter.drawLine(QPointF(cell.left(), cell.bottom()), QPointF(cell.right(), cell.bottom()))
            painter.drawLine(QPointF(cell.left() + label_width, cell.top()), QPointF(cell.left() + label_width, cell.bottom()))
            painter.setPen(QColor(MUTED))
            painter.drawText(cell.adjusted(7, 0, -rect.width() + label_width, 0), Qt.AlignVCenter | Qt.AlignLeft, label)
            painter.setPen(QColor(color))
            value_rect = cell.adjusted(label_width + 7, 0, -7, 0)
            painter.drawText(value_rect, Qt.AlignVCenter | Qt.AlignRight, value)
            y += row_height

    @staticmethod
    def _event_label(kind: str) -> str:
        return {
            "BOS_BULL": "BOS ↑",
            "BOS_BEAR": "BOS ↓",
            "CHOCH_BULL": "CHoCH ↑",
            "CHOCH_BEAR": "CHoCH ↓",
            "SWEEP_HIGH": "LQ süpürme ↓",
            "SWEEP_LOW": "LQ süpürme ↑",
        }.get(kind, kind.replace("_", " "))

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(BG))
        if self.snapshot is None or self.snapshot.frame.empty:
            painter.setPen(QColor(MUTED))
            painter.drawText(self.rect(), Qt.AlignCenter, "MT5 verisi bekleniyor…")
            return

        df = self.snapshot.frame.copy()
        current_ts = None
        if self.bundle is not None and self.bundle.current_bar is not None:
            current_ts = self.bundle.bars.index[-1]
            current = self.bundle.current_bar.copy()
            for col in df.columns:
                if col not in current.index:
                    current[col] = np.nan
            df.loc[current_ts] = current.reindex(df.columns)
        end = max(1, len(df) - self.offset)
        start = max(0, end - self.visible_bars)
        view = df.iloc[start:end]
        if view.empty:
            return

        left, axis_width, top, bottom = 12.0, 78.0, 44.0, 31.0
        panel_width = 286.0 if self.layers.get("panel") and self.width() >= 1040 else 0.0
        panel_gap = 9.0 if panel_width else 0.0
        rsi_height = 88.0 if self.layers.get("rsi") else 0.0
        plot_width = self.width() - left - axis_width - panel_width - panel_gap
        price_rect = QRectF(left, top, max(260.0, plot_width), self.height() - top - bottom - rsi_height)
        rsi_rect = QRectF(left, price_rect.bottom() + 8, price_rect.width(), max(0.0, rsi_height - 8))
        axis_rect = QRectF(price_rect.right(), top, axis_width, price_rect.height())
        panel_rect = QRectF(axis_rect.right() + panel_gap, top, panel_width, price_rect.height() + rsi_height)

        low = float(view["low"].min())
        high = float(view["high"].max())
        if self.layers.get("zones"):
            relevant = [z for z in self.snapshot.zones if z.born_at <= view.index[-1]][-8:]
            for zone in relevant:
                low, high = min(low, zone.lower), max(high, zone.upper)
        span = max(high - low, abs(high) * 1e-6, 1e-8)
        low -= span * 0.075
        high += span * 0.075
        count = len(view)
        step = price_rect.width() / max(1, count)

        def x_at(pos: int) -> float:
            return price_rect.left() + (pos + 0.5) * step

        def y_at(value: float) -> float:
            return price_rect.bottom() - (value - low) / (high - low) * price_rect.height()

        # Seans aralıkları en arkada ve düşük opaklıkta kalır.
        if self.layers.get("sessions") and "session" in view:
            for first, last, name in self._session_spans(view.index, view["session"]):
                color = QColor(self.SESSION_COLORS[name])
                color.setAlpha(7)
                session_column = QRectF(x_at(first) - step / 2, price_rect.top(), (last - first + 1) * step, price_rect.height())
                painter.fillRect(session_column, color)
                session_high = float(view["high"].iloc[first : last + 1].max())
                session_low = float(view["low"].iloc[first : last + 1].min())
                session_rect = QRectF(
                    session_column.left(), y_at(session_high), session_column.width(),
                    max(1.0, y_at(session_low) - y_at(session_high)),
                )
                range_fill = QColor(self.SESSION_COLORS[name]); range_fill.setAlpha(12)
                painter.fillRect(session_rect, range_fill)
                edge = QColor(self.SESSION_COLORS[name]); edge.setAlpha(65)
                painter.setPen(QPen(edge, 1, Qt.DotLine))
                painter.drawRect(session_rect)
                if session_rect.width() >= 54:
                    painter.setPen(QColor(self.SESSION_COLORS[name]))
                    label_rect = QRectF(session_rect.left(), max(price_rect.top(), session_rect.top() - 18), session_rect.width(), 17)
                    painter.drawText(label_rect, Qt.AlignCenter, name)

        # Izgara ve zaman/fiyat ölçekleri.
        painter.setPen(QPen(QColor(GRID), 1, Qt.DotLine))
        for k in range(7):
            y = price_rect.top() + k * price_rect.height() / 6
            painter.drawLine(QPointF(price_rect.left(), y), QPointF(price_rect.right(), y))
            value = high - k * (high - low) / 6
            painter.setPen(QColor(MUTED))
            painter.drawText(QRectF(axis_rect.left() + 5, y - 9, axis_rect.width() - 8, 18), Qt.AlignRight, f"{value:.6g}")
            painter.setPen(QPen(QColor(GRID), 1, Qt.DotLine))
        tick_positions = sorted(set(int(round(x)) for x in np.linspace(0, count - 1, min(7, count))))
        for pos in tick_positions:
            x = x_at(pos)
            painter.setPen(QPen(QColor(GRID), 1, Qt.DotLine))
            painter.drawLine(QPointF(x, price_rect.top()), QPointF(x, price_rect.bottom()))
            painter.setPen(QColor(MUTED))
            stamp = view.index[pos]
            label = stamp.strftime("%d %b\n%H:%M") if pos == 0 or stamp.date() != view.index[max(0, pos - 1)].date() else stamp.strftime("%H:%M")
            painter.drawText(QRectF(x - 37, price_rect.bottom() + 3, 74, bottom - 3), Qt.AlignTop | Qt.AlignHCenter, label)

        # Aktif dengesizlik ve emir bölgeleri.
        if self.layers.get("zones"):
            zones = [
                z for z in self.snapshot.zones
                if z.born_at <= view.index[-1] and z.upper >= low and z.lower <= high
            ][-6:]
            for zone in zones:
                born = int(np.searchsorted(view.index.values, zone.born_at.to_datetime64()))
                born = max(0, min(count - 1, born))
                color_name = self.ZONE_COLORS.get(zone.kind, MUTED)
                color = QColor(color_name); color.setAlpha(28)
                zone_rect = QRectF(
                    x_at(born) - step / 2,
                    y_at(zone.upper),
                    price_rect.right() - (x_at(born) - step / 2),
                    max(1.0, y_at(zone.lower) - y_at(zone.upper)),
                )
                painter.fillRect(zone_rect, color)
                edge = QColor(color_name); edge.setAlpha(130)
                painter.setPen(QPen(edge, 1, Qt.DashLine))
                painter.drawRect(zone_rect)
                if self.visible_bars <= 260:
                    direction = "▲" if zone.direction is Direction.LONG else "▼"
                    painter.setPen(QColor(color_name))
                    painter.drawText(zone_rect.adjusted(4, 1, -4, -1), Qt.AlignLeft | Qt.AlignTop, f"{zone.kind.value} {direction}")

        # Destek/direnç yatay seviyeleri.
        if self.layers.get("levels"):
            for col, label, color in (("support", "DESTEK", GREEN), ("resistance", "DİRENÇ", RED)):
                value = view[col].dropna().iloc[-1] if col in view and not view[col].dropna().empty else np.nan
                if np.isfinite(value) and low <= float(value) <= high:
                    y = y_at(float(value))
                    pen_color = QColor(color); pen_color.setAlpha(130)
                    painter.setPen(QPen(pen_color, 1, Qt.DashLine))
                    painter.drawLine(QPointF(price_rect.left(), y), QPointF(price_rect.right(), y))
                    painter.setPen(QColor(color))
                    painter.drawText(QRectF(price_rect.right() - 94, y - 17, 90, 16), Qt.AlignRight, label)

        opens = view["open"].to_numpy(float)
        closes = view["close"].to_numpy(float)
        highs = view["high"].to_numpy(float)
        lows = view["low"].to_numpy(float)
        candle_width = max(1.1, min(10.0, step * 0.64))
        for j in range(count):
            color = GREEN if closes[j] >= opens[j] else RED
            x = x_at(j)
            painter.setPen(QPen(QColor(color), 1))
            painter.drawLine(QPointF(x, y_at(lows[j])), QPointF(x, y_at(highs[j])))
            y1, y2 = y_at(opens[j]), y_at(closes[j])
            body = QRectF(x - candle_width / 2, min(y1, y2), candle_width, max(1.2, abs(y2 - y1)))
            painter.fillRect(body, QColor(color))
            if current_ts is not None and view.index[j] == current_ts:
                painter.setPen(QPen(QColor(AMBER), 1, Qt.DashLine))
                painter.drawRect(body.adjusted(-2, -2, 2, 2))

        xs = np.array([x_at(i) for i in range(count)])
        if self.layers.get("trend") and "kernel" in view:
            self._line(painter, xs, np.array([y_at(x) if np.isfinite(x) else np.nan for x in view["kernel"]]), AMBER, 2.0)
        if self.layers.get("ema"):
            self._line(painter, xs, np.array([y_at(x) if np.isfinite(x) else np.nan for x in view["ema20"]]), BLUE, 1.1)
            self._line(painter, xs, np.array([y_at(x) if np.isfinite(x) else np.nan for x in view["ema50"]]), PURPLE, 1.0)
        if self.layers.get("vwap"):
            self._line(painter, xs, np.array([y_at(x) if np.isfinite(x) else np.nan for x in view["vwap"]]), BLUE, 1.15)

        # BOS, CHoCH ve likidite süpürmeleri. Çok uzak görünümde etiketler kendiliğinden kapanır.
        if self.layers.get("structure") and self.visible_bars <= 340:
            event_limit = 9 if self.visible_bars <= 180 else 6
            visible_events = [e for e in self.snapshot.structure_events if view.index[0] <= e.timestamp <= view.index[-1]][-event_limit:]
            for structure_event in visible_events:
                try:
                    pos = int(view.index.get_loc(structure_event.timestamp))
                except KeyError:
                    continue
                bullish = structure_event.direction is Direction.LONG
                color_name = GREEN if bullish else RED
                level = float(structure_event.level)
                if not (low <= level <= high):
                    continue
                y = y_at(level)
                source_pos = max(0, min(count - 1, structure_event.source_bar - start))
                line_color = QColor(color_name); line_color.setAlpha(125)
                painter.setPen(QPen(line_color, 1, Qt.DashLine))
                painter.drawLine(QPointF(x_at(source_pos), y), QPointF(x_at(pos), y))
                label = self._event_label(structure_event.kind)
                label_rect = QRectF(x_at(pos) - 48, y - 19 if bullish else y + 2, 96, 17)
                fill = QColor(PANEL); fill.setAlpha(205)
                painter.fillRect(label_rect, fill)
                painter.setPen(QColor(color_name))
                painter.drawText(label_rect, Qt.AlignCenter, label)

        # Sinyal işaretleri ve son sinyalin işlem geometrisi.
        position = {ts: j for j, ts in enumerate(view.index)}
        if self.layers.get("signals"):
            for signal in self.snapshot.signals[-100:]:
                j = position.get(signal.timestamp)
                if j is None or signal.action not in (SignalAction.BUY, SignalAction.SELL):
                    continue
                x = x_at(j)
                bullish = signal.action is SignalAction.BUY
                y = y_at(lows[j] if bullish else highs[j]) + (11 if bullish else -11)
                points = [
                    QPointF(x, y - 7 if bullish else y + 7),
                    QPointF(x - 6, y + 5 if bullish else y - 5),
                    QPointF(x + 6, y + 5 if bullish else y - 5),
                ]
                painter.setBrush(QColor(GREEN if bullish else RED))
                painter.setPen(Qt.NoPen)
                painter.drawPolygon(QPolygonF(points))
            latest = self.snapshot.latest_signal
            if latest and latest.timestamp in position and latest.stage is SignalStage.CONFIRMED:
                for value, label, color in (
                    (latest.entry, "GİRİŞ", BLUE),
                    (latest.stop, "STOP", RED),
                    (latest.target, "HEDEF", GREEN),
                ):
                    if value is not None and low <= value <= high:
                        y = y_at(value)
                        painter.setPen(QPen(QColor(color), 1, Qt.DashLine))
                        painter.drawLine(QPointF(x_at(position[latest.timestamp]), y), QPointF(price_rect.right(), y))
                        painter.drawText(QRectF(price_rect.right() - 58, y - 16, 55, 15), Qt.AlignRight, label)

        # Son fiyat çizgisi ve eksen rozeti.
        last_price = float(closes[-1])
        if low <= last_price <= high:
            price_color = GREEN if closes[-1] >= opens[-1] else RED
            y = y_at(last_price)
            painter.setPen(QPen(QColor(price_color), 1, Qt.DotLine))
            painter.drawLine(QPointF(price_rect.left(), y), QPointF(price_rect.right(), y))
            badge = QRectF(axis_rect.left() + 2, y - 10, axis_rect.width() - 4, 20)
            painter.fillRect(badge, QColor(price_color))
            painter.setPen(QColor("white"))
            painter.drawText(badge, Qt.AlignCenter, f"{last_price:.6g}")

        # RSI ayrı bir alt panel olarak isteğe bağlıdır.
        if self.layers.get("rsi") and rsi_rect.height() > 0:
            painter.fillRect(rsi_rect, QColor(PANEL))
            for level in (30, 50, 70):
                y = rsi_rect.bottom() - level / 100 * rsi_rect.height()
                painter.setPen(QPen(QColor(GRID), 1, Qt.DotLine))
                painter.drawLine(QPointF(rsi_rect.left(), y), QPointF(rsi_rect.right(), y))
            rsi_y = np.array([
                rsi_rect.bottom() - x / 100 * rsi_rect.height() if np.isfinite(x) else np.nan
                for x in view["rsi"]
            ])
            self._line(painter, xs, rsi_y, BLUE, 1.2)
            painter.setPen(QColor(MUTED))
            painter.drawText(QRectF(rsi_rect.left() + 5, rsi_rect.top() + 2, 90, 18), "RSI 14")

        # Başlık ve gösterge lejandı.
        painter.setPen(QColor(TEXT))
        title = f"{self.snapshot.symbol} · {self.snapshot.timeframe.label} · {view.index[0]:%d.%m %H:%M} — {view.index[-1]:%d.%m %H:%M} UTC"
        painter.drawText(QRectF(price_rect.left() + 6, 4, price_rect.width() - 12, 19), title)
        legend: list[str] = []
        if self.layers.get("trend"):
            trend_value = view["kernel"].dropna().iloc[-1] if "kernel" in view and not view["kernel"].dropna().empty else np.nan
            legend.append(f"AURUM Trend {trend_value:.6g}" if np.isfinite(trend_value) else "AURUM Trend")
        if self.layers.get("vwap"):
            legend.append("VWAP")
        if self.layers.get("ema"):
            legend.append("EMA 20/50")
        painter.setPen(QColor(AMBER))
        painter.drawText(QRectF(price_rect.left() + 6, 23, price_rect.width() - 12, 18), " · ".join(legend))
        if current_ts is not None and current_ts in view.index:
            painter.setPen(QColor(AMBER))
            painter.drawText(QRectF(price_rect.right() - 125, 4, 120, 19), Qt.AlignRight, "AÇIK MUM")

        # Yüksek/düşük işaretleri.
        hi_pos, lo_pos = int(np.argmax(highs)), int(np.argmin(lows))
        painter.setPen(QColor(BLUE))
        painter.drawText(QRectF(x_at(hi_pos) - 45, y_at(highs[hi_pos]) - 19, 90, 17), Qt.AlignCenter, f"Yüksek {highs[hi_pos]:.6g}")
        painter.drawText(QRectF(x_at(lo_pos) - 45, y_at(lows[lo_pos]) + 3, 90, 17), Qt.AlignCenter, f"Düşük {lows[lo_pos]:.6g}")

        if panel_width:
            self._draw_status_panel(painter, panel_rect, view)

        # Fare artı işareti ve seçili mum OHLC kutusu en üst katmandadır.
        if self.hover is not None and price_rect.contains(QPointF(self.hover)):
            j = max(0, min(count - 1, int((self.hover.x() - price_rect.left()) / step)))
            x = x_at(j)
            hover_price = high - (self.hover.y() - price_rect.top()) / price_rect.height() * (high - low)
            painter.setPen(QPen(QColor(MUTED), 1, Qt.DashLine))
            painter.drawLine(QPointF(x, price_rect.top()), QPointF(x, price_rect.bottom()))
            painter.drawLine(QPointF(price_rect.left(), self.hover.y()), QPointF(price_rect.right(), self.hover.y()))
            row = view.iloc[j]
            text = f"{view.index[j]:%d.%m.%Y %H:%M} UTC   A {row.open:.6g}  Y {row.high:.6g}  D {row.low:.6g}  K {row.close:.6g}"
            box = QRectF(price_rect.left() + 7, price_rect.bottom() - 25, min(580.0, price_rect.width() - 14), 21)
            painter.fillRect(box, QColor(PANEL_2))
            painter.setPen(QColor(TEXT))
            painter.drawText(box.adjusted(7, 0, -4, 0), Qt.AlignVCenter, text)
            hover_badge = QRectF(axis_rect.left() + 2, self.hover.y() - 9, axis_rect.width() - 4, 18)
            painter.fillRect(hover_badge, QColor(PANEL_2))
            painter.drawText(hover_badge, Qt.AlignCenter, f"{hover_price:.6g}")


class EquityChart(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(160)
        self.series = pd.Series(dtype=float)

    def set_series(self, series: pd.Series) -> None:
        self.series = series
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(PANEL))
        if self.series.empty:
            painter.setPen(QColor(MUTED))
            painter.drawText(self.rect(), Qt.AlignCenter, "Backtest sonucu bekleniyor")
            return
        values = self.series.to_numpy(float)
        low, high = float(values.min()), float(values.max())
        if math.isclose(low, high):
            low -= 1
            high += 1
        rect = QRectF(12, 12, self.width() - 24, self.height() - 28)
        path = QPainterPath()
        for i, value in enumerate(values):
            x = rect.left() + i / max(1, len(values) - 1) * rect.width()
            y = rect.bottom() - (value - low) / (high - low) * rect.height()
            path.moveTo(x, y) if i == 0 else path.lineTo(x, y)
        painter.setPen(QPen(QColor(BLUE), 2))
        painter.drawPath(path)
        painter.setPen(QColor(MUTED))
        painter.drawText(QRectF(15, self.height() - 20, self.width() - 30, 18), f"{low:,.0f} — {high:,.0f}")
