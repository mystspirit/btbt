from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol

from bot.grid import Side


@dataclass(slots=True)
class Fill:
    side: Side
    qty_base: float
    price: float
    tx_id: str


class DexClient(Protocol):
    def submit_perp_order(self, side: Side, qty_base: float, limit_price: float) -> Fill: ...


class MockDexClient:
    def __init__(self) -> None:
        self.counter = 0

    def submit_perp_order(self, side: Side, qty_base: float, limit_price: float) -> Fill:
        self.counter += 1
        return Fill(side=side, qty_base=qty_base, price=limit_price, tx_id=f"mock-tx-{self.counter}")


class DriftDexClient:
    """Live Solana perp execution over Drift (wallet-signed, no CEX)."""

    def __init__(
        self,
        rpc_url: str,
        private_key_b58: str,
        market_index: int,
        sub_account_id: int = 0,
        drift_env: str = "mainnet",
    ) -> None:
        self.rpc_url = rpc_url
        self.private_key_b58 = private_key_b58
        self.market_index = market_index
        self.sub_account_id = sub_account_id
        self.drift_env = drift_env

    def submit_perp_order(self, side: Side, qty_base: float, limit_price: float) -> Fill:
        tx_sig = asyncio.run(self._submit_perp_order_async(side, qty_base, limit_price))
        return Fill(side=side, qty_base=qty_base, price=limit_price, tx_id=tx_sig)

    async def _submit_perp_order_async(self, side: Side, qty_base: float, limit_price: float) -> str:
        try:
            from driftpy.drift_client import DriftClient
            from driftpy.types import MarketType, OrderType, PositionDirection
            from solana.rpc.async_api import AsyncClient
            from solders.keypair import Keypair
        except Exception as exc:  # pragma: no cover - import error path
            raise RuntimeError(
                "Live trading dependencies missing. Install with: pip install -e .[live]"
            ) from exc

        try:
            import base58
        except Exception as exc:  # pragma: no cover - import error path
            raise RuntimeError("Missing base58 dependency. Install with: pip install -e .[live]") from exc

        key_bytes = base58.b58decode(self.private_key_b58)
        wallet = Keypair.from_bytes(key_bytes)

        connection = AsyncClient(self.rpc_url)
        try:
            client = DriftClient(
                connection=connection,
                wallet=wallet,
                env=self.drift_env,
                active_sub_account_id=self.sub_account_id,
            )
            await client.subscribe()

            direction = PositionDirection.Long() if side is Side.LONG else PositionDirection.Short()
            base_asset_amount = int(qty_base * 1_000_000_000)
            price = int(limit_price * 1_000_000)

            tx_sig = await client.place_perp_order(
                market_index=self.market_index,
                direction=direction,
                base_asset_amount=base_asset_amount,
                price=price,
                order_type=OrderType.Limit(),
                market_type=MarketType.Perp(),
                reduce_only=False,
            )
            await client.unsubscribe()
            return str(tx_sig)
        finally:
            await connection.close()
