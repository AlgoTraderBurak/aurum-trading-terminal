from __future__ import annotations

import math

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from aurum.domain.models import BacktestConfig, BacktestResult
from aurum.ui.chart import EquityChart
from aurum.ui.theme import AMBER, GREEN, RED
from aurum.ui.widgets import MetricCard


class BacktestTab(QWidget):
    run_requested = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        header = QHBoxLayout()
        title = QLabel("Backtest")
        title.setObjectName("sectionTitle")
        header.addWidget(title)
        header.addStretch()
        self.context = QLabel("Önce canlı grafikten sembol ve zaman dilimi yükleyin.")
        self.context.setObjectName("muted")
        self.context.setMinimumWidth(0)
        self.context.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        header.addWidget(self.context)
        root.addLayout(header)

        controls = QHBoxLayout()
        account_form = QFormLayout()
        cost_form = QFormLayout()
        self.balance = QDoubleSpinBox(); self.balance.setRange(100, 100_000_000); self.balance.setValue(10_000); self.balance.setDecimals(2)
        self.currency = QComboBox(); self.currency.addItems(("USD", "TRY", "EUR"))
        self.risk = QDoubleSpinBox(); self.risk.setRange(0.1, 10); self.risk.setValue(1); self.risk.setSuffix(" %")
        self.spread = QDoubleSpinBox(); self.spread.setRange(0, 10000); self.spread.setValue(0); self.spread.setSuffix(" point")
        self.slippage = QDoubleSpinBox(); self.slippage.setRange(0, 10000); self.slippage.setValue(0); self.slippage.setSuffix(" point")
        self.commission = QDoubleSpinBox(); self.commission.setRange(0, 1000); self.commission.setValue(0); self.commission.setSuffix(" / lot")
        self.max_hold = QSpinBox(); self.max_hold.setRange(1, 5000); self.max_hold.setValue(200); self.max_hold.setSuffix(" bar")
        for name, widget in (("Başlangıç", self.balance), ("Para birimi", self.currency), ("Risk / işlem", self.risk), ("Azami süre", self.max_hold)):
            account_form.addRow(name, widget)
        for name, widget in (("Spread", self.spread), ("Slippage", self.slippage), ("Komisyon", self.commission)):
            cost_form.addRow(name, widget)
        controls.addLayout(account_form)
        controls.addSpacing(24)
        controls.addLayout(cost_form)
        controls.addStretch()
        self.run = QPushButton("Backtest Çalıştır")
        self.run.setMinimumHeight(42)
        controls.addWidget(self.run)
        root.addLayout(controls)

        cards = QGridLayout()
        cards.setSpacing(8)
        self.metric_cards = {
            "final_balance": MetricCard("Son Bakiye"), "net_profit": MetricCard("Net K/Z"),
            "return_pct": MetricCard("Getiri"), "max_drawdown_cash": MetricCard("Parasal Maks. DD"),
            "max_drawdown_pct": MetricCard("Maks. DD"), "trade_count": MetricCard("İşlem"),
            "win_rate": MetricCard("Kazanma"), "profit_factor": MetricCard("Kâr Faktörü"),
            "expectancy_r": MetricCard("Beklenti"), "net_r": MetricCard("Toplam R"),
        }
        for index, card in enumerate(self.metric_cards.values()):
            cards.addWidget(card, index // 5, index % 5)
        root.addLayout(cards)
        self.diagnostics = QTextBrowser()
        self.diagnostics.setMaximumHeight(88)
        self.diagnostics.setPlaceholderText("Backtest sonrası sayısal teşhis burada gösterilir.")
        root.addWidget(self.diagnostics)
        self.equity = EquityChart()
        root.addWidget(self.equity)
        self.table = QTableWidget(0, 11)
        self.table.setHorizontalHeaderLabels(["Sinyal", "Giriş", "Çıkış", "Yön", "Entry", "Exit", "Lot", "Net R", "K/Z", "Bakiye", "Neden"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(10, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        root.addWidget(self.table, 1)
        self.warning = QLabel("Gelecek mum kullanılmaz; giriş sonraki mum açılışıdır; aynı mumda stop ve hedef görülürse stop önce sayılır.")
        self.warning.setObjectName("muted")
        self.warning.setWordWrap(True)
        self.warning.setMinimumWidth(0)
        self.warning.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        root.addWidget(self.warning)
        self.run.clicked.connect(self._emit_run)

    def _emit_run(self) -> None:
        self.run_requested.emit(
            BacktestConfig(
                initial_balance=self.balance.value(), risk_percent=self.risk.value(),
                spread_points=self.spread.value(), slippage_points=self.slippage.value(),
                commission_per_lot=self.commission.value(), max_hold_bars=self.max_hold.value(),
                currency=self.currency.currentText(),
            )
        )

    def set_context(self, text: str) -> None:
        self.context.setText(text)

    def set_loading(self, loading: bool) -> None:
        self.run.setEnabled(not loading)
        self.run.setText("Hesaplanıyor…" if loading else "Backtest Çalıştır")

    def set_result(self, result: BacktestResult) -> None:
        m = result.metrics
        currency = {"USD": "$", "TRY": "₺", "EUR": "€"}.get(result.config.currency, result.config.currency)
        money = lambda value: f"{currency}{value:,.2f}"
        values = {
            "final_balance": money(m["final_balance"]), "net_profit": money(m["net_profit"]),
            "return_pct": f"%{m['return_pct']:.2f}", "max_drawdown_cash": money(m["max_drawdown_cash"]),
            "max_drawdown_pct": f"%{m['max_drawdown_pct']:.2f}", "trade_count": f"{int(m['trade_count'])}", "win_rate": f"%{m['win_rate']:.1f}",
            "profit_factor": "∞" if math.isinf(m["profit_factor"]) else f"{m['profit_factor']:.2f}",
            "expectancy_r": f"{m['expectancy_r']:.2f} R", "net_r": f"{m['net_r']:.2f} R",
        }
        for key, value in values.items():
            if key in ("max_drawdown_cash", "max_drawdown_pct"):
                color = RED if m[key] > 0 else GREEN
            elif key in ("net_profit", "return_pct", "expectancy_r", "net_r"):
                color = GREEN if m[key] > 0 else RED if m[key] < 0 else AMBER
            elif key == "profit_factor":
                color = GREEN if m[key] >= 1 else RED
            else:
                color = GREEN
            self.metric_cards[key].set_value(value, color)
        self.equity.set_series(result.equity)
        if result.diagnostics:
            self.diagnostics.setHtml("<b>Strateji teşhisi</b><br>" + "<br>".join(f"• {text}" for text in result.diagnostics))
        else:
            self.diagnostics.setText("Teşhis verisi oluşturulmadı.")
        balance_after: list[float] = []
        running_balance = result.config.initial_balance
        for trade in result.trades:
            running_balance += trade.pnl
            balance_after.append(running_balance)
        recent = list(reversed(list(zip(result.trades[-500:], balance_after[-500:]))))
        self.table.setRowCount(len(recent))
        for row, (trade, after) in enumerate(recent):
            vals = (
                trade.signal_time.strftime("%d.%m %H:%M"), trade.entry_time.strftime("%d.%m %H:%M"),
                trade.exit_time.strftime("%d.%m %H:%M"), trade.direction.tr,
                f"{trade.entry:g}", f"{trade.exit:g}", f"{trade.quantity:g}",
                f"{trade.net_r:.2f}", money(trade.pnl), money(after), trade.exit_reason,
            )
            for col, value in enumerate(vals):
                item = QTableWidgetItem(value)
                if col in (7, 8):
                    item.setForeground(QColor(GREEN if trade.net_r > 0 else RED))
                if col == 7:
                    item.setToolTip(f"MFE: {trade.mfe_r:.2f} R\nMAE: {trade.mae_r:.2f} R")
                self.table.setItem(row, col, item)
        self.warning.setStyleSheet("")
        if result.warnings:
            shown = " · ".join(result.warnings[:3])
            remaining = len(result.warnings) - 3
            self.warning.setText(f"{len(result.warnings)} uyarı · {shown}" + (f" · +{remaining} uyarı daha" if remaining > 0 else ""))
            self.warning.setToolTip("\n".join(result.warnings))
        else:
            self.warning.setText("Maliyet ve MT5 kontrat bilgileri hesaba katıldı.")
            self.warning.setToolTip("")

    def set_error(self, message: str) -> None:
        self.warning.setText(message.splitlines()[0])
        self.warning.setStyleSheet(f"color:{RED};")
