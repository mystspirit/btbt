from __future__ import annotations

import argparse
from datetime import datetime, timezone

from bot.backtest import Backtester, Candle
from bot.config import BotConfig
from bot.dex import MockDexClient
from bot.grid import GridEngine


def run_backtest(csv_path: str) -> int:
    cfg = BotConfig()
    backtester = Backtester(cfg)
    candles = backtester.load_csv(csv_path)
    result = backtester.run(candles)
    print(f"Pair: {cfg.pair}")
    print(f"Trades: {result.trades}")
    print(f"PnL: {result.pnl:.2f} {cfg.quote_symbol}")
    print(f"End equity: {result.end_equity:.2f} {cfg.quote_symbol}")
    print(f"Max drawdown: {result.max_drawdown_pct:.2f}%")
    return 0


def run_paper_live(last_price: float) -> int:
    cfg = BotConfig()
    grid = GridEngine(cfg, last_price)
    client = MockDexClient()
    for order in grid.generate_orders()[:4]:
        fill = client.submit_perp_order(order.side, order.qty_base, order.trigger_price)
        print(f"{fill.tx_id}: {fill.side.value} {fill.qty_base:.4f} @ {fill.price:.4f}")
    return 0


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Solana USDC grid arbitrage bot (wallet + DEX)")
    sub = parser.add_subparsers(dest="command", required=True)

    backtest = sub.add_parser("backtest", help="Run built-in backtest (requires >=30 days CSV)")
    backtest.add_argument("--csv", required=True, help="CSV with columns: timestamp,close")

    live = sub.add_parser("paper-live", help="Run paper live order simulation")
    live.add_argument("--price", type=float, default=150.0)
    return parser


def main() -> int:
    parser = make_parser()
    args = parser.parse_args()

    if args.command == "backtest":
        return run_backtest(args.csv)
    if args.command == "paper-live":
        return run_paper_live(args.price)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
