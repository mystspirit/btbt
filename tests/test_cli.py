from argparse import Namespace

import pytest

from bot.main import _load_last_price_from_csv, run_live


def test_load_last_price_from_csv() -> None:
    assert _load_last_price_from_csv("data/sample_31d.csv") > 0


def test_live_requires_private_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DRIFT_PRIVATE_KEY_B58", raising=False)
    args = Namespace(
        rpc_url="https://api.mainnet-beta.solana.com",
        market_index=0,
        sub_account_id=0,
        private_key_b58="",
        price_csv="data/sample_31d.csv",
        max_orders=1,
        sleep_ms=1,
        user_sync_timeout_s=1.0,
        user_sync_poll_ms=1,
        submit_retries=1,
        retry_backoff_ms=1,
    )
    with pytest.raises(ValueError, match="Missing private key"):
        run_live(args)
