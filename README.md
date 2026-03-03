# Solana USDC Grid Arbitrage Bot (DEX-only)

Bot je pripravený na **USDC pár na Solane** s architektúrou pre:
- grid obchodovanie v oboch smeroch (**long + short**),
- ultra-rýchly decision loop (in-memory grid + low-latency execution vrstva),
- vstavaný backtest s validáciou minimálne **30 dní** dát,
- wallet-first prístup (žiadny CEX, iba DEX/perp protokol).

## Čo je implementované
- `GridEngine`: generuje long/short grid úrovne.
- `Backtester`: načíta CSV (`timestamp,close`), overí 30+ dní a spočíta PnL / DD / počet obchodov.
- `DexClient` abstrakcia + `MockDexClient` pre paper-live simuláciu.
- `DriftDexClient` skeleton pre live on-chain integráciu (wallet signing + Solana tx).

## Rýchly štart
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Paper live (simulácia)
```bash
gridbot paper-live --price 150
```

### Backtest (min. 30 dní)
```bash
gridbot backtest --csv data/sample_31d.csv
```

## Formát dát
CSV stĺpce:
- `timestamp` (ISO format, napr. `2025-01-01T00:00:00+00:00`)
- `close` (float)

## Poznámka k short smeru
Short na spot DEX-e bez marginu nie je natívne možný. Preto je navrhnutá DEX/perp vrstva (napr. Drift), kde short aj long fungujú on-chain cez wallet.
