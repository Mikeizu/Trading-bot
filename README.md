# MIKEIZU TradeLab PRO — multi-strategy research terminal

A private, local trading research and demo application with a configurable technical-indicator library, chronological strategy comparisons, virtual paper positions, and an optional Deriv Options connector. The earlier book-pattern workspace and its seven detectors have been removed from this application; their previous source remains available in Git history.

**Real-money purchases remain disabled.** Real accounts are read-only. Synthetic prices, historical simulations, virtual paper results and broker demo records stay separate. More strategies do not establish higher forecast accuracy or future profit.

## Start

Requires **Python 3.10+**. Extract the complete application ZIP, then run `START_WINDOWS.bat` on Windows or `bash START_MAC_LINUX.sh` on macOS/Linux. The downloadable package includes a hash-verified dependency wheel for offline installation. This is a Python application package, not a signed standalone executable.

From a source checkout:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.lock
.venv/bin/python deriv_server.py --no-browser
```

Open the loopback address printed by the launcher on the same machine. Stop with Ctrl+C; closing the browser alone does not stop the backend. Do not expose the server publicly. Cloud tasks should use the existing checkout: each task is already isolated, so another Git worktree is unnecessary.

## Work with evidence

1. Explore synthetic research without credentials. Use the strategy library to inspect each rule, family, warm-up requirement and bounded parameters.
2. Compare strategies under the same dataset, holding period, payout and execution-cost assumptions. Review net expectancy, drawdown, sample size, uncertainty, chronological holdout, walk-forward and cost-stress results. `NO VALIDATED STRATEGY` is a valid outcome.
3. Import properly licensed, chronological OHLC data to study authentic history. A checksum identifies the input; it does not authenticate its supplier. A win-rate target is an informational benchmark, never a profit guarantee or an order permit.
4. Connect an authorized Deriv demo account for authentic broker data. Start with monitoring, then separate virtual paper positions. Demo purchases require explicit activation, supported contracts, fresh data, calendar clearance and persistent risk approval.
5. Use **Risk & Health** to inspect account identity, limits, unresolved orders and audit status. The emergency stop halts new entries and persists across restarts; it does not close broker contracts.

The library contains **24 strategies** across trend, momentum, mean-reversion, breakout, volatility and composite rules. Rules use available OHLC evidence; missing volume is not replaced with invented data. See [strategy rules and parameters](docs/STRATEGIES.md) and the runtime `/api/strategy/catalog` for the authoritative catalog.

## Retained safeguards

Persistent account/mode limits, daily/weekly loss budgets, drawdown and exposure checks, cooldowns, calendar freshness, closed-bar signals, next-open paper entries, cost assumptions, one-use quotes, durable order reservations, uncertain-order lockout, audit records and risk controls remain part of the application. Backtests retain independently funded train/holdout experiments, purging, training-only ranking and no holdout runner-up substitution.

## Scope and verification

The user-provided comparison app is identified by Google Play package `com.qexpress.tool`. Its public listing was blocked by this cloud network's proxy, so proprietary algorithms, current features and performance could not be verified. The strategy library contains explicit independently implemented technical rules, not a claim to reproduce that app. See [public research and sources](docs/PUBLIC_RESEARCH.md).

This is a local development/research terminal, not a certified worldwide brokerage or autonomous trading service. Authenticated Deriv demo execution, real account entitlements, jurisdictional approval, MT5/CFD execution, remote multi-user authentication, a licensed automatic news feed and calibrated predictive AI remain unverified or unimplemented. Historical option-payout research does not reproduce actual bid/ask, financing, liquidity or every broker fill.

## Test and document

```bash
python -m unittest discover -s tests -v
```

Current checks passed **313 Python tests and 44 browser scenarios**, with **160 controls audited**. Use the virtual environment's Python when needed. Current-release outcomes and their limits belong in [VALIDATION.md](docs/VALIDATION.md), [CONTROL_AUDIT.md](docs/CONTROL_AUDIT.md) and [FUNCTION_AUDIT.md](docs/FUNCTION_AUDIT.md). Earlier release counts are not evidence for this changed strategy engine.

- [Strategy rules](docs/STRATEGIES.md)
- [Application audit](docs/APPLICATION_AUDIT.md)
- [Architecture](docs/ARCHITECTURE.md)
- [API and data contracts](docs/API_AND_DATA.md)
- [Operations and recovery](docs/OPERATIONS.md)
- [Gaps](docs/GAP_ANALYSIS.md) and [roadmap](docs/ROADMAP.md)
- [Download instructions](DOWNLOAD_README.txt)

MIT licensed; see [LICENSE](LICENSE). Third-party dependency licenses remain with their packages.
