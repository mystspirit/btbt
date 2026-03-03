# Solana USDC Grid Arbitrage Bot (DEX-only)

Bot pre **USDC na Solane** s:
- grid obchodovaním v oboch smeroch (**long + short**),
- vstavaným backtestom s validáciou min. **30 dní**,
- live obchodovaním **out of the box** na Drift perps (wallet + RPC, bez CEX).

## Čo je implementované
- `GridEngine`: symetrické long/short grid úrovne.
- `Backtester`: načítanie CSV, 30+ dní horizon check, fees/slippage, DD/PnL.
- Anti-overfill gating: level sa nefilluje na každej sviečke, až po re-arm.
- `DriftDexClient`: reálne odoslanie limit perp orderu na Drift cez podpísaný wallet tx.
- CLI: `backtest`, `paper-live`, `live`.

## Inštalácia
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Pre live trading nainštaluj live extra:
```bash
pip install -e .[live]
```

## Backtest
```bash
gridbot backtest --csv data/sample_31d.csv
```

## Paper live
```bash
gridbot paper-live --price 150
```

## Live trading (out of the box)
1. Priprav Drift private key v base58 (`DRIFT_PRIVATE_KEY_B58`).
2. Spusť live command:

```bash
export DRIFT_PRIVATE_KEY_B58='...'
gridbot live \
  --rpc-url https://api.mainnet-beta.solana.com \
  --market-index 0 \
  --sub-account-id 0 \
  --price-csv data/sample_31d.csv \
  --max-orders 3
```

> Poznámka: short na spot DEX-e bez marginu nie je natívny, preto je live vrstva riešená cez perp DEX (Drift), stále wallet-first a bez CEX.
