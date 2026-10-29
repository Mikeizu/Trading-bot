# MIKEIZU TradeLab PRO — Deriv research edition

A private, local Python trading research application with seven measurable price-action strategies, historical comparisons, virtual paper positions, and an opt-in Deriv **demo** connector. Imported from the supplied v4.3 source package and improved around persistent risk controls, execution recovery, honest research, and clear account modes.

**Real-money order execution is disabled in this version.** A real account, if connected, is read-only. Historical results, synthetic prices, and virtual paper profits are separate from broker demo records. No performance target guarantees profit.

## Start locally

Requires Python 3.10 or newer. On Windows, install Python from [python.org](https://www.python.org/downloads/) and run `START_WINDOWS.bat`.

On macOS/Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.lock
.venv/bin/python deriv_server.py --no-browser
```

Open `http://127.0.0.1:8765` on the same machine. The application listens only on loopback. Stop it with Ctrl+C; closing a browser tab does not stop the server. For a different port, add `--port 8766`.

For cloud development, use the existing checkout. Each task already has an isolated environment; another Git worktree is unnecessary. Validate HTTP endpoints internally; this application is not a publicly hosted trading service.

## Begin safely

1. Explore the **synthetic simulator** and **Naked Strategy PRO** research tools without credentials. Synthetic data is labelled and cannot authorize broker deployment.
2. Compare all seven rules under the same costs and chronological validation assumptions. `NO VALIDATED STRATEGY` is a legitimate result. The 65% win-rate benchmark is informational.
3. To inspect authentic data, connect an authorized Deriv demo account in **Deriv Broker**, using a matching PAT-type App ID and personal access token. Tokens are entered locally, kept in process memory, and never committed.
4. Review **Risk & Health** before enabling demo automation. Inspect account identity, persisted limits, news/calendar policy, and outstanding orders. Unknown or stale essential information blocks orders.
5. Start with **monitor only**, then virtual paper positions. Demo purchases require explicit action, supported short-expiry contracts, fresh broker state, and approval by the independent risk engine.
6. Use the always-accessible emergency stop to halt new entries. It does not claim to close existing broker contracts; those must settle or be managed through the authorized broker interface.

## What is included

- Seven quantified Naked Forex interpretations: Last Kiss, Big Shadow, Wammies, Moolahs, Kangaroo Tail, Big Belt, and Trendy Kangaroo.
- Scalping, intraday, swing, weekly, and monthly **research/monitoring** timeframes. Broker demo option purchases remain limited to supported 1–15 minute durations; chart timeframe and contract duration are distinct.
- Persistent account/mode risk state, emergency halt, auditable decisions, daily/weekly loss and exposure checks, and conservative demo defaults.
- Causal, cost-aware fixed-expiry research, independently funded training/holdout segments, training-only ranking, uncertainty estimates, walk-forward checks, and dataset/configuration provenance.
- Virtual paper-position tracking, deterministic market-regime explanations, broker order journaling, and fail-closed handling of ambiguous purchases.
- A responsive local interface with explicit simulation/demo/read-only mode labels and system health information.

## Important limits

This is a development and research application, **not a production-certified autonomous trading system**. Automated tests use deterministic broker doubles. No authenticated Deriv demo purchase, real broker compatibility, or profitability has been verified in this environment. Deriv MT5/CFD position execution, a licensed economic-news feed, jurisdictional approval, production remote authentication, and calibrated predictive AI are not implemented.

The historical model uses assumed costs and fixed-expiry option payouts. It does not recreate broker tick execution, authentic bid/ask history, partial fills, liquidity, swaps, financing, margin, or real future payouts. Heuristic regime classifications are uncertain and are not forecasts. See the [capability audit](docs/APPLICATION_AUDIT.md) before using results.

## Test

```bash
python -m unittest discover -s tests -v
```

Use the virtual environment's Python when dependencies are installed there. Local validation passed **196 tests** on Python 3.12.14 plus the actual-server Chromium workflow smoke. See [validation evidence](docs/VALIDATION.md) for executed checks and their limits.

## Documentation

- [Application audit and capability status](docs/APPLICATION_AUDIT.md)
- [Gap analysis and requirement traceability](docs/GAP_ANALYSIS.md)
- [Architecture and execution boundaries](docs/ARCHITECTURE.md)
- [Seven-phase roadmap and acceptance criteria](docs/ROADMAP.md)
- [Operations, risk controls, backups, and demo procedures](docs/OPERATIONS.md)
- [Database and API contracts](docs/API_AND_DATA.md)
- [Validation and reproducible trading research](docs/VALIDATION.md)
- [Original user development brief](docs/MASTER_PROMPT.md)

`STRATEGY_GUIDE.md`, `AUTO_SELECTOR_GUIDE.md`, and `DERIV_*_FIX.md` arrived with the archive. Their strategy background and historical diagnostics remain useful, but old live opt-in, cost assumptions, paper-risk, and promotion descriptions are superseded by the current documentation. [Archived release notes](docs/ARCHIVE_RELEASE_NOTES.md) preserve that source history.

MIT licensed; see [LICENSE](LICENSE).
