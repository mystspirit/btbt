from __future__ import annotations

import asyncio
import inspect
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
        client = None
        try:
            client = DriftClient(
                connection=connection,
                wallet=wallet,
                env=self.drift_env,
                active_sub_account_id=self.sub_account_id,
            )
            await client.subscribe()
            await self._ensure_user_ready(client)

            direction = PositionDirection.Long() if side is Side.LONG else PositionDirection.Short()
            base_asset_amount = int(qty_base * 1_000_000_000)
            price = int(limit_price * 1_000_000)

            tx_sig = await self._place_perp_order_compat(
                client=client,
                market_index=self.market_index,
                direction=direction,
                base_asset_amount=base_asset_amount,
                price=price,
                order_type=OrderType.Limit(),
                market_type=MarketType.Perp(),
                reduce_only=False,
            )
            return str(tx_sig)
        finally:
            if client is not None and hasattr(client, "unsubscribe"):
                try:
                    maybe = client.unsubscribe()
                    if inspect.isawaitable(maybe):
                        await maybe
                except Exception:
                    pass
            await connection.close()

    async def _ensure_user_ready(self, client: object) -> None:
        """Ensure drift user/subscriber state is initialized before placing orders."""

        # Some driftpy versions require an explicit add/sync call after subscribe.
        await self._call_client_method(client, "add_user", self.sub_account_id)
        await self._call_client_method(client, "add_and_subscribe_user", self.sub_account_id)
        await self._call_client_method(client, "fetch_accounts")
        await self._call_client_method(client, "sync")

        get_user_account = getattr(client, "get_user_account", None)
        if callable(get_user_account):
            try:
                get_user_account(self.sub_account_id)
            except AttributeError as exc:
                raise RuntimeError(
                    "Drift user account subscriber is not initialized. "
                    "Make sure your Drift sub-account exists and has collateral, then retry."
                ) from exc

    async def _call_client_method(self, client: object, method_name: str, *args: object) -> None:
        method = getattr(client, method_name, None)
        if not callable(method):
            return

        try:
            result = method(*args)
        except TypeError:
            # Some versions expose these methods without args.
            result = method()

        if inspect.isawaitable(result):
            await result

    async def _place_perp_order_compat(
        self,
        client: object,
        market_index: int,
        direction: object,
        base_asset_amount: int,
        price: int,
        order_type: object,
        market_type: object,
        reduce_only: bool,
    ) -> object:
        """Compatibility layer for driftpy API variants."""

        place_order = getattr(client, "place_perp_order")
        params = inspect.signature(place_order).parameters

        if "market_index" in params:
            return await place_order(
                market_index=market_index,
                direction=direction,
                base_asset_amount=base_asset_amount,
                price=price,
                order_type=order_type,
                market_type=market_type,
                reduce_only=reduce_only,
            )

        if "order_params" in params:
            try:
                from driftpy.types import OrderParams
            except Exception as exc:  # pragma: no cover - import error path
                raise RuntimeError("Unable to import driftpy OrderParams for this driftpy version") from exc

            order_params = OrderParams(
                market_index=market_index,
                direction=direction,
                base_asset_amount=base_asset_amount,
                price=price,
                order_type=order_type,
                market_type=market_type,
                reduce_only=reduce_only,
            )
            return await place_order(order_params)

        raise RuntimeError(
            "Unsupported driftpy place_perp_order signature. Please update driftpy or adapt integration."
        )
