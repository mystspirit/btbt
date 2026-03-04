from __future__ import annotations

import argparse
import csv
import os
import time
from datetime import datetime, timezone

from bot.backtest import Backtester
from bot.config import BotConfig
from bot.dex import DriftDexClient, MockDexClient
from bot.grid import GridEngine


def run_backtest(csv_path: str) -> int:
    cfg = BotConfig()
    backtester = Backtester(cfg)
    candles = backtester.load_csv(csv_path)
    result = backtester.run(candles)
    print(f"Pair: {cfg.pair}")
    print(f"Grid levels: {cfg.grid_levels} | spacing: {cfg.grid_spacing_bps} bps")
    print(f"Trades: {result.trades}")
    print(f"PnL: {result.pnl:.2f} {cfg.quote_symbol}")
    print(f"End equity: {result.end_equity:.2f} {cfg.quote_symbol}")
    print(f"Max drawdown: {result.max_drawdown_pct:.2f}%")
    return 0


def run_paper_live(last_price: float) -> int:
    cfg = BotConfig()
    grid = GridEngine(cfg, last_price)
    client = MockDexClient()
    print(f"Paper live on {cfg.pair} (DEX-only simulation)")
    for order in grid.generate_orders()[:4]:
        fill = client.submit_perp_order(order.side, order.qty_base, order.trigger_price)
        print(f"{fill.tx_id}: {fill.side.value} {fill.qty_base:.4f} @ {fill.price:.4f}")
    return 0


def _load_last_price_from_csv(csv_path: str) -> float:
    with open(csv_path, "r", newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise ValueError("Price CSV has no rows")
    return float(rows[-1]["close"])


def run_live(args: argparse.Namespace) -> int:
    cfg = BotConfig()
    private_key_b58 = args.private_key_b58 or os.environ.get("DRIFT_PRIVATE_KEY_B58", "")
    if not private_key_b58:
        raise ValueError("Missing private key. Pass --private-key-b58 or set DRIFT_PRIVATE_KEY_B58.")

    last_price = _load_last_price_from_csv(args.price_csv)
    grid = GridEngine(cfg, last_price)
    client = DriftDexClient(
        rpc_url=args.rpc_url,
        private_key_b58=private_key_b58,
        market_index=args.market_index,
        sub_account_id=args.sub_account_id,
        user_sync_timeout_s=args.user_sync_timeout_s,
        user_sync_poll_ms=args.user_sync_poll_ms,
        submit_retries=args.submit_retries,
        retry_backoff_ms=args.retry_backoff_ms,
    )

    print(f"[{datetime.now(timezone.utc).isoformat()}] LIVE start {cfg.pair} / market_index={args.market_index}")
    orders = grid.generate_orders()[: args.max_orders]
    for order in orders:
        fill = client.submit_perp_order(order.side, order.qty_base, order.trigger_price)
        print(f"LIVE {fill.tx_id}: {fill.side.value} {fill.qty_base:.4f} @ {fill.price:.4f}")
        time.sleep(args.sleep_ms / 1000)
    return 0


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Solana USDC grid arbitrage bot (wallet + DEX)")
    sub = parser.add_subparsers(dest="command", required=True)

    backtest = sub.add_parser("backtest", help="Run built-in backtest (requires >=30 days CSV)")
    backtest.add_argument("--csv", required=True, help="CSV with columns: timestamp,close")

    live = sub.add_parser("paper-live", help="Run paper live order simulation")
    live.add_argument("--price", type=float, default=150.0)

    real = sub.add_parser("live", help="Out-of-the-box live trading on Drift (wallet + Solana RPC)")
    real.add_argument("--rpc-url", default="https://api.mainnet-beta.solana.com")
    real.add_argument("--market-index", type=int, default=0, help="Drift perp market index")
    real.add_argument("--sub-account-id", type=int, default=0)
    real.add_argument("--private-key-b58", default="", help="Base58 private key (or DRIFT_PRIVATE_KEY_B58 env)")
    real.add_argument("--price-csv", default="data/sample_31d.csv", help="CSV used for anchor/last price")
    real.add_argument("--max-orders", type=int, default=3)
    real.add_argument("--sleep-ms", type=int, default=300)
    real.add_argument("--user-sync-timeout-s", type=float, default=30.0)
    real.add_argument("--user-sync-poll-ms", type=int, default=300)
    real.add_argument("--submit-retries", type=int, default=2)
    real.add_argument("--retry-backoff-ms", type=int, default=900)
    return parser


def main() -> int:
    parser = make_parser()
    args = parser.parse_args()

    if args.command == "backtest":
        return run_backtest(args.csv)
    if args.command == "paper-live":
        return run_paper_live(args.price)
    if args.command == "live":
        return run_live(args)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
