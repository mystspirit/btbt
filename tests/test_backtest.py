from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from bot.backtest import Backtester, Candle
from bot.config import BotConfig


def test_backtest_runs_on_31d_sample() -> None:
    cfg = BotConfig()
    b = Backtester(cfg)
    candles = b.load_csv(str(Path("data/sample_31d.csv")))
    result = b.run(candles)
    assert result.trades > 0
    assert result.end_equity > 0


def test_backtest_rejects_short_horizon(tmp_path: Path) -> None:
    fp = tmp_path / "short.csv"
    fp.write_text(
        "timestamp,close\n"
        "2025-01-01T00:00:00+00:00,100\n"
        "2025-01-15T00:00:00+00:00,101\n",
        encoding="utf-8",
    )
    b = Backtester(BotConfig())
    with pytest.raises(ValueError, match=r">= 30 days"):
        b.load_csv(str(fp))


def test_grid_does_not_refill_same_level_every_candle() -> None:
    cfg = BotConfig(grid_levels=2, grid_spacing_bps=100.0, order_size_quote=100.0, max_inventory_base=5.0)
    b = Backtester(cfg)
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    # Price stays below long trigger for multiple candles; should fill once,
    # then re-arm only after rebound.
    candles = [
        Candle(start, 100.0),
        Candle(start + timedelta(hours=1), 98.8),
        Candle(start + timedelta(hours=2), 98.7),
        Candle(start + timedelta(hours=3), 100.2),
        Candle(start + timedelta(hours=4), 98.8),
        Candle(start + timedelta(hours=5), 99.0),
    ]
    result = b.run(candles, start_equity=10_000)
    assert result.trades <= 2
