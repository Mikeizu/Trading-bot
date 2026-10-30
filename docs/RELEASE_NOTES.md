# Multi-strategy terminal release notes

## Product change

The earlier book-pattern workspace and its seven detectors have been removed from the current app. Their previous source and documentation remain available at Git commit `615e273` for a future separate project; current catalog and API requests do not reactivate those rule IDs.

The replacement is a general technical-indicator library with explicit rule metadata, configurable bounded parameters, warm-up requirements, source/version evidence, chronological research and dynamic UI controls. The library draws on documented technical-analysis methods; it is not claimed to reproduce proprietary algorithms of the user-provided Google Play app.

## Preserved controls

Persistent risk limits and emergency halt, account/mode isolation, calendar freshness, no blind buy retries, durable journals, tamper checks, paper next-open/cost/gap handling, train/holdout separation and read-only real accounts remain required. A broader library cannot bypass these boundaries or silently promote itself to live trading.

## Upgrade data

Current filenames are `strategy_signals.db` and `paper_positions.db`. The startup migration preserves original legacy database files and copies retained historical state when a current file is absent. Historical rows retain their original labels; they are records, not selectable strategies. Stop the app and back up its complete state set before upgrading. Never delete risk/order state to bypass an unresolved trade or loss limit.

See [VALIDATION.md](VALIDATION.md) for release evidence and [OPERATIONS.md](OPERATIONS.md) for safe use. No claim of guaranteed accuracy, profit, worldwide product availability or production certification is made.
