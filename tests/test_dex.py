from bot.dex import DriftDexClient


def test_drift_client_defaults_to_mainnet_env() -> None:
    client = DriftDexClient(
        rpc_url="https://api.mainnet-beta.solana.com",
        private_key_b58="dummy",
        market_index=0,
    )
    assert client.drift_env == "mainnet"
