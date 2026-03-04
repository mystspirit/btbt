from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from time import monotonic
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
        user_sync_timeout_s: float = 30.0,
        user_sync_poll_ms: int = 300,
        submit_retries: int = 2,
        retry_backoff_ms: int = 900,
    ) -> None:
        self.rpc_url = rpc_url
        self.private_key_b58 = private_key_b58
        self.market_index = market_index
        self.sub_account_id = sub_account_id
        self.drift_env = drift_env
        self.user_sync_timeout_s = user_sync_timeout_s
        self.user_sync_poll_ms = user_sync_poll_ms
        self.submit_retries = max(1, submit_retries)
        self.retry_backoff_ms = max(1, retry_backoff_ms)

    def submit_perp_order(self, side: Side, qty_base: float, limit_price: float) -> Fill:
        last_exc: Exception | None = None
        for attempt in range(1, self.submit_retries + 1):
            try:
                tx_sig = asyncio.run(self._submit_perp_order_async(side, qty_base, limit_price))
                return Fill(side=side, qty_base=qty_base, price=limit_price, tx_id=tx_sig)
            except RuntimeError as exc:
                last_exc = exc
                if "subscriber is not initialized" not in str(exc) or attempt >= self.submit_retries:
                    raise
                asyncio.run(asyncio.sleep(self.retry_backoff_ms / 1000))

        raise RuntimeError("Live order submission failed") from last_exc

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
        deadline = monotonic() + self.user_sync_timeout_s
        last_exc: Exception | None = None

        while monotonic() < deadline:
            await self._call_client_method(client, "add_user", self.sub_account_id)
            await self._call_client_method(client, "add_and_subscribe_user", self.sub_account_id)
            await self._call_client_method(client, "fetch_accounts")
            await self._call_client_method(client, "sync")
            await self._call_client_method(client, "resubscribe")

            ready, exc = await self._probe_user_ready(client)
            if ready:
                return
            if exc is not None:
                last_exc = exc

            await asyncio.sleep(max(self.user_sync_poll_ms, 1) / 1000)

        raise RuntimeError(
            "Drift user account subscriber is not initialized after waiting. "
            "Websocket snapshot may still be syncing OR Drift sub-account may be missing/unfunded. "
            "Increase --user-sync-timeout-s and verify sub-account + collateral."
        ) from last_exc

    async def _probe_user_ready(self, client: object) -> tuple[bool, Exception | None]:
        get_user_account = getattr(client, "get_user_account", None)
        if callable(get_user_account):
            try:
                user = get_user_account(self.sub_account_id)
                if user is not None:
                    return True, None
            except AttributeError as exc:
                # Typical driftpy race: account_subscriber still has None data.
                pass
            except Exception as exc:
                return False, exc

        get_user = getattr(client, "get_user", None)
        if callable(get_user):
            try:
                user_obj = get_user(self.sub_account_id)
                if user_obj is None:
                    return False, None

                # Some versions require user-level subscribe.
                subscribe = getattr(user_obj, "subscribe", None)
                if callable(subscribe):
                    maybe = subscribe()
                    if inspect.isawaitable(maybe):
                        await maybe

                get_user_account = getattr(user_obj, "get_user_account", None)
                if callable(get_user_account):
                    ua = get_user_account()
                    if ua is not None:
                        return True, None
            except AttributeError as exc:
                return False, exc
            except Exception as exc:
                return False, exc

        return False, None

    async def _call_client_method(self, client: object, method_name: str, *args: object) -> None:
        method = getattr(client, method_name, None)
        if not callable(method):
            return

        try:
            result = method(*args)
        except TypeError:
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
