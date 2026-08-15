from __future__ import annotations

import math

import numpy as np
import pandas as pd

from aurum.domain.models import (
    BacktestConfig,
    BacktestResult,
    BacktestTrade,
    Direction,
    MarketDataBundle,
    Signal,
    SignalAction,
    SignalStage,
)


class BacktestEngine:
    """Closed-bar signal, next-bar execution, conservative intrabar resolution."""

    @staticmethod
    def _round_volume(value: float, minimum: float, maximum: float, step: float) -> float:
        if value < minimum:
            return 0.0
        if step <= 0:
            return value
        steps = math.floor(value / step + 1e-12)
        return min(maximum, steps * step)

    @staticmethod
    def _max_drawdown(equity: list[float]) -> tuple[float, float]:
        peak = equity[0]
        max_cash = 0.0
        max_pct = 0.0
        for value in equity:
            peak = max(peak, value)
            drawdown = peak - value
            max_cash = max(max_cash, drawdown)
            if peak > 0:
                max_pct = max(max_pct, drawdown / peak * 100.0)
        return max_cash, max_pct

    def run(
        self,
        bundle: MarketDataBundle,
        signals: list[Signal],
        config: BacktestConfig,
    ) -> BacktestResult:
        df = bundle.closed_bars
        warnings: list[str] = []
        if len(df) < 3:
            raise ValueError("Backtest için yeterli kapanmış mum yok.")
        if config.initial_balance <= 0 or not (0 < config.risk_percent <= 10):
            raise ValueError("Başlangıç bakiyesi pozitif, risk yüzdesi 0-10 aralığında olmalı.")

        meta = bundle.metadata
        point = meta.point if meta.point > 0 else 0.00001
        tick_size = meta.tick_size if meta.tick_size > 0 else point
        tick_value = meta.tick_value
        if tick_value <= 0:
            warnings.append(
                "Tick value alınamadı; lot temsili, parasal bakiye ise sabit yüzde risk varsayımıdır."
            )

        confirmed = [
            s for s in signals
            if s.stage is SignalStage.CONFIRMED
            and s.action in (SignalAction.BUY, SignalAction.SELL)
            and s.entry is not None and s.stop is not None and s.target is not None
        ]
        confirmed.sort(key=lambda x: x.timestamp)
        index_positions = {ts: i for i, ts in enumerate(df.index)}
        trades: list[BacktestTrade] = []
        balance = config.initial_balance
        equity_values = [balance]
        equity_times = [df.index[0]]
        occupied_until = -1

        for signal in confirmed:
            signal_bar = index_positions.get(signal.timestamp)
            if signal_bar is None or signal_bar + 1 >= len(df):
                continue
            entry_bar = signal_bar + 1
            if not config.allow_overlapping and entry_bar <= occupied_until:
                continue
            direction = signal.direction
            half_spread = config.spread_points * point / 2.0
            slippage = config.slippage_points * point
            raw_open = float(df["open"].iloc[entry_bar])
            entry = raw_open + direction.value * (half_spread + slippage)
            stop, target = float(signal.stop), float(signal.target)
            risk_distance = (entry - stop) if direction is Direction.LONG else (stop - entry)
            reward_distance = (target - entry) if direction is Direction.LONG else (entry - target)
            if risk_distance <= 0 or reward_distance <= 0:
                warnings.append(f"{signal.timestamp}: açılış boşluğu risk geometrisini bozdu; işlem atlandı.")
                continue

            risk_cash = balance * config.risk_percent / 100.0
            if tick_value > 0:
                loss_per_lot = risk_distance / tick_size * tick_value
                raw_qty = risk_cash / loss_per_lot if loss_per_lot > 0 else 0.0
                quantity = self._round_volume(
                    raw_qty, meta.volume_min, meta.volume_max, meta.volume_step
                )
                if quantity <= 0:
                    warnings.append(
                        f"{signal.timestamp}: hesaplanan lot broker minimumunun altında; işlem atlandı."
                    )
                    continue
            else:
                quantity = 1.0

            exit_bar = min(len(df) - 1, entry_bar + config.max_hold_bars)
            exit_price = float(df["close"].iloc[exit_bar])
            exit_reason = "Süre sonu"
            for i in range(entry_bar, exit_bar + 1):
                high = float(df["high"].iloc[i])
                low = float(df["low"].iloc[i])
                # Stop is deliberately resolved before target when both are touched.
                if direction is Direction.LONG:
                    if low <= stop:
                        exit_bar, exit_price, exit_reason = i, stop, "Stop"
                        break
                    if high >= target:
                        exit_bar, exit_price, exit_reason = i, target, "Hedef"
                        break
                else:
                    if high >= stop:
                        exit_bar, exit_price, exit_reason = i, stop, "Stop"
                        break
                    if low <= target:
                        exit_bar, exit_price, exit_reason = i, target, "Hedef"
                        break

            move = (exit_price - entry) * direction.value
            gross_r = move / risk_distance
            commission_cash = config.commission_per_lot * quantity
            commission_r = commission_cash / risk_cash if risk_cash > 0 else 0.0
            net_r = gross_r - commission_r
            pnl = risk_cash * net_r
            trade_window = df.iloc[entry_bar : exit_bar + 1]
            if direction is Direction.LONG:
                favorable = float(trade_window["high"].max()) - entry
                adverse = entry - float(trade_window["low"].min())
            else:
                favorable = entry - float(trade_window["low"].min())
                adverse = float(trade_window["high"].max()) - entry
            mfe_r = max(0.0, favorable / risk_distance)
            mae_r = max(0.0, adverse / risk_distance)
            balance += pnl
            trades.append(
                BacktestTrade(
                    signal_uid=signal.uid,
                    direction=direction,
                    signal_time=signal.timestamp,
                    entry_time=df.index[entry_bar],
                    exit_time=df.index[exit_bar],
                    entry=entry,
                    exit=exit_price,
                    stop=stop,
                    target=target,
                    quantity=quantity,
                    gross_r=gross_r,
                    net_r=net_r,
                    pnl=pnl,
                    exit_reason=exit_reason,
                    mfe_r=mfe_r,
                    mae_r=mae_r,
                )
            )
            occupied_until = exit_bar
            equity_times.append(df.index[exit_bar])
            equity_values.append(balance)

        net_rs = np.array([x.net_r for x in trades], dtype=float)
        wins = net_rs[net_rs > 0]
        losses = net_rs[net_rs <= 0]
        gross_profit = float(wins.sum()) if len(wins) else 0.0
        gross_loss = float(-losses.sum()) if len(losses) else 0.0
        max_dd_cash, max_dd_pct = self._max_drawdown(equity_values)
        metrics = {
            "trade_count": float(len(trades)),
            "wins": float(len(wins)),
            "losses": float(len(losses)),
            "win_rate": float(len(wins) / len(trades) * 100.0) if trades else 0.0,
            "profit_factor": gross_profit / gross_loss if gross_loss > 0 else (float("inf") if gross_profit else 0.0),
            "expectancy_r": float(net_rs.mean()) if len(net_rs) else 0.0,
            "net_r": float(net_rs.sum()) if len(net_rs) else 0.0,
            "net_profit": balance - config.initial_balance,
            "final_balance": balance,
            "return_pct": (balance / config.initial_balance - 1.0) * 100.0,
            "max_drawdown_cash": max_dd_cash,
            "max_drawdown_pct": max_dd_pct,
            "payoff_ratio": (float(wins.mean()) / abs(float(losses.mean()))) if len(wins) and len(losses) and losses.mean() != 0 else 0.0,
            "avg_mfe_r": float(np.mean([x.mfe_r for x in trades])) if trades else 0.0,
            "avg_mae_r": float(np.mean([x.mae_r for x in trades])) if trades else 0.0,
        }
        equity = pd.Series(equity_values, index=pd.DatetimeIndex(equity_times), name="equity")
        return BacktestResult(config, trades, equity, metrics, warnings)
