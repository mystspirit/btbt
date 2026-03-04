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


class _FlakySubscriberClient:
    def __init__(self, succeed_after: int) -> None:
        self.calls = 0
        self.succeed_after = succeed_after

    async def fetch_accounts(self) -> None:
        return

    def get_user_account(self, sub_account_id: int) -> object:
        self.calls += 1
        if self.calls < self.succeed_after:
            raise AttributeError("NoneType has no attribute data")
        return object()


class _BrokenUserAccountClient:
    def get_user_account(self, sub_account_id: int) -> object:
        raise AttributeError("NoneType has no attribute data")


class _RetryDriftDexClient(DriftDexClient):
    def __init__(self) -> None:
        super().__init__("rpc", "k", 0, submit_retries=2, retry_backoff_ms=1)
        self.calls = 0

    async def _submit_perp_order_async(self, side: Side, qty_base: float, limit_price: float) -> str:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("Drift user account subscriber is not initialized after waiting")
        return "ok-tx"


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


def test_ensure_user_ready_retries_until_data_arrives() -> None:
    c = DriftDexClient("rpc", "k", 0, user_sync_timeout_s=1.0, user_sync_poll_ms=1)
    fake = _FlakySubscriberClient(succeed_after=3)
    asyncio.run(c._ensure_user_ready(fake))
    assert fake.calls >= 3


def test_ensure_user_ready_raises_clear_error_on_missing_subscriber() -> None:
    c = DriftDexClient("rpc", "k", 0, sub_account_id=1, user_sync_timeout_s=0.01, user_sync_poll_ms=1)
    with pytest.raises(RuntimeError, match="not initialized after waiting"):
        asyncio.run(c._ensure_user_ready(_BrokenUserAccountClient()))


def test_submit_perp_order_retries_on_subscriber_race() -> None:
    c = _RetryDriftDexClient()
    fill = c.submit_perp_order(Side.LONG, 0.1, 100.0)
    assert fill.tx_id == "ok-tx"
    assert c.calls == 2
