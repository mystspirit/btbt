from pathlib import Path

from bot.backtest import Backtester
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
    try:
        b.load_csv(str(fp))
        assert False, "Expected ValueError for <30 days"
    except ValueError as exc:
        assert ">= 30 days" in str(exc)
