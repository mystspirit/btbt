import asyncio

import pytest

from bot.dex import DriftDexClient
from bot.grid import Side


class _KwargClient:
    async def place_perp_order(
        self,
        market_index: int,
        direction: object,
        base_asset_amount: int,
        price: int,
        order_type: object,
        market_type: object,
        reduce_only: bool,
    ) -> str:
        return f"kw-{market_index}-{base_asset_amount}-{price}-{reduce_only}"


class _UnsupportedClient:
    async def place_perp_order(self, foo: int) -> str:
        return "x"


class _ReadyClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def add_user(self, sub_account_id: int) -> None:
        self.calls.append(f"add_user:{sub_account_id}")

    async def fetch_accounts(self) -> None:
        self.calls.append("fetch_accounts")

    def get_user_account(self, sub_account_id: int) -> object:
        self.calls.append(f"get_user_account:{sub_account_id}")
        return object()


class _BrokenUserAccountClient:
    def get_user_account(self, sub_account_id: int) -> object:
        raise AttributeError("NoneType has no attribute data")


def test_drift_client_defaults_to_mainnet_env() -> None:
    client = DriftDexClient(
        rpc_url="https://api.mainnet-beta.solana.com",
        private_key_b58="dummy",
        market_index=0,
    )
    assert client.drift_env == "mainnet"


def test_place_perp_order_compat_kwargs_path() -> None:
    c = DriftDexClient("rpc", "k", 0)
    res = asyncio.run(
        c._place_perp_order_compat(
            client=_KwargClient(),
            market_index=2,
            direction=Side.LONG,
            base_asset_amount=10,
            price=11,
            order_type="limit",
            market_type="perp",
            reduce_only=False,
        )
    )
    assert res.startswith("kw-2-")


def test_place_perp_order_compat_unsupported_signature() -> None:
    c = DriftDexClient("rpc", "k", 0)
    with pytest.raises(RuntimeError, match="Unsupported driftpy"):
        asyncio.run(
            c._place_perp_order_compat(
                client=_UnsupportedClient(),
                market_index=2,
                direction=Side.LONG,
                base_asset_amount=10,
                price=11,
                order_type="limit",
                market_type="perp",
                reduce_only=False,
            )
        )


def test_ensure_user_ready_calls_sync_methods() -> None:
    c = DriftDexClient("rpc", "k", 0, sub_account_id=7)
    fake = _ReadyClient()
    asyncio.run(c._ensure_user_ready(fake))
    assert "add_user:7" in fake.calls
    assert "fetch_accounts" in fake.calls
    assert "get_user_account:7" in fake.calls


def test_ensure_user_ready_raises_clear_error_on_missing_subscriber() -> None:
    c = DriftDexClient("rpc", "k", 0, sub_account_id=1)
    with pytest.raises(RuntimeError, match="subscriber is not initialized"):
        asyncio.run(c._ensure_user_ready(_BrokenUserAccountClient()))
