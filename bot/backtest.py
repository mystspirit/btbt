from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from bot.config import BotConfig
from bot.grid import GridEngine, Side


@dataclass(slots=True)
class Candle:
    ts: datetime
    close: float


@dataclass(slots=True)
class BacktestResult:
    start_equity: float
    end_equity: float
    pnl: float
    trades: int
    max_drawdown_pct: float


class Backtester:
    def __init__(self, config: BotConfig):
        self.config = config

    def load_csv(self, path: str) -> list[Candle]:
        candles: list[Candle] = []
        with open(path, "r", newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                ts = datetime.fromisoformat(row["timestamp"]).astimezone(timezone.utc)
                candles.append(Candle(ts=ts, close=float(row["close"])))
        if not candles:
            raise ValueError("CSV has no rows")
        ordered = sorted(candles, key=lambda c: c.ts)
        self._validate_horizon(ordered)
        return ordered

    def _validate_horizon(self, candles: list[Candle]) -> None:
        start, end = candles[0].ts, candles[-1].ts
        required = timedelta(days=self.config.min_days_backtest)
        if end - start < required:
            raise ValueError(
                f"Backtest requires >= {self.config.min_days_backtest} days, got {(end - start).days} days"
            )

    def run(self, candles: list[Candle], start_equity: float = 10_000.0) -> BacktestResult:
        anchor = candles[0].close
        grid = GridEngine(self.config, anchor)
        orders = grid.generate_orders()
        spacing = self.config.grid_spacing_bps / 10_000

        # Gate each level to avoid refilling the same order on every candle
        # while price remains beyond a trigger.
        armed = [True] * len(orders)

        cash = start_equity
        base_pos = 0.0
        peak = start_equity
        max_dd = 0.0
        trades = 0

        for candle in candles:
            for idx, order in enumerate(orders):
                price = candle.close
                trigger = order.trigger_price

                if order.side is Side.LONG:
                    if armed[idx] and price <= trigger:
                        notional = order.qty_base * price
                        fee = notional * (self.config.taker_fee_bps + self.config.slippage_bps) / 10_000
                        if base_pos + order.qty_base <= self.config.max_inventory_base and cash >= notional + fee:
                            cash -= notional + fee
                            base_pos += order.qty_base
                            trades += 1
                            armed[idx] = False
                    elif not armed[idx] and price >= trigger * (1 + spacing):
                        armed[idx] = True
                else:
                    if armed[idx] and price >= trigger:
                        notional = order.qty_base * price
                        fee = notional * (self.config.taker_fee_bps + self.config.slippage_bps) / 10_000
                        if base_pos - order.qty_base >= -self.config.max_inventory_base:
                            cash += notional - fee
                            base_pos -= order.qty_base
                            trades += 1
                            armed[idx] = False
                    elif not armed[idx] and price <= trigger * (1 - spacing):
                        armed[idx] = True

            equity = cash + base_pos * candle.close
            peak = max(peak, equity)
            if peak > 0:
                max_dd = max(max_dd, (peak - equity) / peak)

        end_equity = cash + base_pos * candles[-1].close
        return BacktestResult(
            start_equity=start_equity,
            end_equity=end_equity,
            pnl=end_equity - start_equity,
            trades=trades,
            max_drawdown_pct=max_dd * 100,
        )
