import asyncio

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
    try:
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
        assert False, "Expected RuntimeError"
    except RuntimeError as exc:
        assert "Unsupported driftpy" in str(exc)
