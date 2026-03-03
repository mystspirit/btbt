from dataclasses import dataclass


@dataclass(slots=True)
class BotConfig:
    base_symbol: str = "SOL"
    quote_symbol: str = "USDC"
    grid_levels: int = 18
    grid_spacing_bps: float = 35.0
    order_size_quote: float = 25.0
    leverage: float = 2.0
    taker_fee_bps: float = 7.0
    maker_fee_bps: float = 2.0
    slippage_bps: float = 3.0
    max_inventory_base: float = 10.0
    min_days_backtest: int = 30

    @property
    def pair(self) -> str:
        return f"{self.base_symbol}/{self.quote_symbol}"
