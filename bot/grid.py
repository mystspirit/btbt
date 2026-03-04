from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from bot.config import BotConfig


class Side(str, Enum):
    LONG = "long"
    SHORT = "short"


@dataclass(slots=True)
class GridOrder:
    level: int
    side: Side
    trigger_price: float
    qty_base: float


class GridEngine:
    def __init__(self, config: BotConfig, anchor_price: float):
        self.config = config
        self.anchor_price = anchor_price

    def generate_orders(self) -> list[GridOrder]:
        spacing = self.config.grid_spacing_bps / 10_000
        half = self.config.grid_levels // 2
        orders: list[GridOrder] = []
        for idx in range(1, half + 1):
            long_price = self.anchor_price * (1 - spacing * idx)
            short_price = self.anchor_price * (1 + spacing * idx)
            long_qty = self.config.order_size_quote / max(long_price, 1e-9)
            short_qty = self.config.order_size_quote / max(short_price, 1e-9)
            orders.append(GridOrder(level=idx, side=Side.LONG, trigger_price=long_price, qty_base=long_qty))
            orders.append(GridOrder(level=idx, side=Side.SHORT, trigger_price=short_price, qty_base=short_qty))
        return sorted(orders, key=lambda o: o.trigger_price)

    def should_fill(self, order: GridOrder, price: float) -> bool:
        if order.side is Side.LONG:
            return price <= order.trigger_price
        return price >= order.trigger_price
