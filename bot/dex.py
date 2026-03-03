from __future__ import annotations

from dataclasses import dataclass

from bot.grid import Side


@dataclass(slots=True)
class Fill:
    side: Side
    qty_base: float
    price: float
    tx_id: str


class DexClient:
    """Base DEX connector for wallet-driven execution (no CEX)."""

    def submit_perp_order(self, side: Side, qty_base: float, limit_price: float) -> Fill:
        raise NotImplementedError


class MockDexClient(DexClient):
    def __init__(self) -> None:
        self.counter = 0

    def submit_perp_order(self, side: Side, qty_base: float, limit_price: float) -> Fill:
        self.counter += 1
        return Fill(side=side, qty_base=qty_base, price=limit_price, tx_id=f"mock-tx-{self.counter}")


class DriftDexClient(DexClient):
    """
    Placeholder for a real Solana perp DEX integration (e.g., Drift protocol).
    You connect only with your wallet and execute on-chain orders.
    """

    def __init__(self, rpc_url: str, wallet_pubkey: str):
        self.rpc_url = rpc_url
        self.wallet_pubkey = wallet_pubkey

    def submit_perp_order(self, side: Side, qty_base: float, limit_price: float) -> Fill:
        raise NotImplementedError(
            "Implement Solana tx signing + Drift instruction packing for live trading."
        )
