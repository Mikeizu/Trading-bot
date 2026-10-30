# Operations guide

This is a private local application. Use `deriv_server.py` for the integrated UI and broker/risk safeguards. `server.py` is the standalone synthetic simulator; it does not connect to a broker. Never expose either server publicly.

## Installation and startup

Python 3.10+ is required. Dependencies are declared in `requirements.txt`; `requirements.lock` pins the tested version and artifact hash for repeatable installation. Use a dedicated virtual environment; TLS and package verification must remain enabled.

Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements.lock
.\.venv\Scripts\python.exe deriv_server.py --no-browser
```

The supplied `START_WINDOWS.bat` also creates the virtual environment, installs dependencies and launches the app. It is editable source, not a signed installer or executable.

macOS/Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.lock
.venv/bin/python deriv_server.py --no-browser --port 8765
```

Open `http://127.0.0.1:8765` from the same machine. Stop with Ctrl+C in the server terminal. A process left running after the browser closes can continue enabled automation. On startup all robots begin stopped; authentication and explicit activation must be repeated. Prepared dependencies and databases may persist across cloud task snapshots, but running processes and authentication must not be assumed to survive.

`MIKEIZU_DATA_DIR` optionally selects a private state directory. Set it before starting the process. On Linux, for example, `MIKEIZU_DATA_DIR=/path/to/private/tradelab-state .venv/bin/python deriv_server.py --no-browser`. On Windows PowerShell, set `$env:MIKEIZU_DATA_DIR = 'C:\Users\YOUR_USER\TradeLabState'` before launching. The default is the checkout for compatibility. The app does not automatically load `.env`; `.env.example` is reference documentation only. Keep backups private and databases out of Git.

## Cloud development handoff

The prepared cloud instance has verified dependency installation, local startup, deterministic tests and browser checks. Reusable install/start instructions and an `api.derivws.com` domain addition were saved in the environment configuration draft. Draft saving does not apply the network change or publish an environment snapshot. Review and save the changes in environment settings, then publish using the product. Fresh-task restoration remains unverified; live processes and broker authentication must be restarted.

The current cloud egress proxy rejected an unauthenticated tunnel to `api.derivws.com` with HTTP 403 before a broker response. This does not diagnose a PAT error. After network settings are applied, retry the specific HTTPS/WebSocket operation before claiming broker readiness. No credentials should be entered in chat or committed.

## Choose the correct mode

| Mode | Data and position model | Broker orders |
|---|---|---|
| Synthetic simulator | Generated candles and separate practice balance | Never |
| Research | Synthetic, user OHLC CSV, or broker historical candles; theoretical fixed-expiry payout | Never |
| Signal monitoring | Completed authentic broker candles, recorded observations | Never |
| Virtual paper | Internal stop/target ledger on market OHLC, with disclosed virtual cost/fill assumptions | Never |
| Broker demo | Explicitly authorized demo identity, broker-supported contracts and fresh risk checks | Demo only |
| Real account read-only | Account/market inspection where broker permits | **All purchases blocked** |

Do not combine the performance histories. A research signal is not a submitted order, and a proposal is not a confirmed contract. Demo profitability is not evidence of live profitability.

## Connect Deriv without exposing credentials

1. Use the official [Deriv developer portal](https://developers.deriv.com/) to obtain the correct PAT-type App ID and an authorized personal access token for the account/product. Use the narrowest permissions needed.
2. Enter the App ID and token only in the local Broker screen. Do not paste tokens into chat, commit them, or save them in startup files, screenshots, logs, or CSV reports.
3. Discover accounts, select an explicitly classified **demo** account, then connect. A discovered account does not prove WebSocket, market, proposal or purchase compatibility.
4. Confirm the account ID, currency, fresh balance and broker-reported markets. An empty market list stays empty; the app never manufactures symbols.
5. Use **Check supported expiries** for the exact symbol and direction. Only broker-advertised barrier-free CALL/PUT contracts between 1 and 15 minutes are considered. The final proposal can still be rejected by the broker.
6. Start with read-only market data and monitor mode. Paper trading creates virtual entries; it does not open an MT5 position.

PAT/OTP credentials remain in memory. They are cleared on disconnect/process exit and must be supplied again after restart. A real account is read-only in this version; the former `MIKEIZU_ALLOW_LIVE` opt-in cannot enable purchases.

## Risk limits and units

Defaults are research/demo presets, not universally safe financial advice. Percentages apply to conservative eligible equity; the fixed-stake risk engine uses fresh broker free balance and does not model CFD margin.

| Field | Default | Enforced configuration range |
|---|---:|---:|
| `risk_per_trade_pct` | 0.5% | 0.01–1% |
| `daily_loss_pct` | 2% | 0.1–5% |
| `weekly_loss_pct` | 5% | 0.1–10% |
| `max_drawdown_pct` | 10% | 0.1–20% |
| `max_positions` | 3 | 1–3 |
| `max_trades_per_day` | 12 | 1–100 |
| `max_order_size` | 50 account-currency units | 0.01–50 |
| `max_asset_exposure_pct` | 1.5% | 0.01–3% |
| `max_group_exposure_pct` | 1.5% | 0.01–3% |
| `consecutive_loss_limit` | 3 | 1–5 |
| `cooldown_minutes` | 60 | 1–1440 |
| `calendar_policy` | `required` | `required` or `synthetic_exempt` |

The broker controller currently uses the stricter policy of at most one unresolved/open contract before another entry, even though the independent risk engine can cap up to three. Demo robot stake ceilings and minimum broker stakes may impose tighter limits than this table.

Loss windows use **UTC** day and Monday-based week boundaries, independent of the workstation/browser timezone. Baselines, high-water mark, halt state, reservations and account/mode configuration persist in `risk_control.db`. Restarting, reconnecting, changing strategy or switching to another view does not reset them. Missing/invalid/non-finite broker balance, portfolio, order or settlement data blocks trading.

Risk state covers activity recorded by the application plus broker position/balance snapshots. It does not import a complete external historical broker statement, and cannot reconstruct a day/week before the first trusted baseline. Deposits, withdrawals or external trades require careful account reconciliation; do not treat an app-only ledger as an independently verified full account history.

## Historical-data limits

Historical research requires at least 100 completed chart bars and enough earlier data for the selected rule's warm-up; catalog metadata supplies the requirement. Broker history depth may be too short after weekly/monthly aggregation, especially on continuously trading instruments; that must return insufficient data rather than invented candles. A legitimate longer preaggregated CSV can be used for research. Partial calendar-edge periods are omitted conservatively, including a Friday-ended week until a later period establishes its boundary.

## Economic calendar and event blackouts

No economic-news feed is bundled. Automatic entries require current declared calendar coverage unless `calendar_policy='synthetic_exempt'` is explicitly configured **and** the instrument is classified as synthetic using trusted broker metadata. A guessed symbol prefix or user label cannot grant an exemption. Manual quotes still show freshness; calendar outages specifically block automation.

Use `/api/risk/calendar` to supply events from a reputable source for which you have appropriate use rights. Timestamps are UTC epoch seconds. A record contains `time`, `currencies` (for example `['USD']` or `['*']` for all), `impact` (`high` where relevant), `before_minutes`, `after_minutes`, and `name`. The payload also requires `updated_at`, `valid_until` and `source`. Coverage is limited to at most seven days and must have been refreshed within 24 hours. In the advanced Risk & Health view, import the same JSON snapshot through the calendar file control. The app checks relevant high-impact blackout windows and fails closed when coverage is stale or missing.

An empty event list is acceptable only when a trustworthy source actually establishes event-free coverage. Do not submit invented coverage to unlock trading. Calendar correctness, licensing and ingestion remain the operator's responsibility.

## Emergency stop and resumption

The global emergency stop halts new entries, stops active robots and invalidates pending local quotes. The halt is durable, including when no broker is connected. It does **not** send a broker close-position request or display unperformed closes as complete. Existing contracts may remain open and should be inspected in the broker's official interface.

To resume, inspect account identity, portfolio, unresolved orders, risk limits, calendar and connectivity first. The explicit resume phrase is `RESUME DEMO TRADING`. Resumption clears the user emergency interlock only; it cannot override loss limits, drawdown, a pending/uncertain reservation, stale data or broker restrictions. Re-enable each robot deliberately after reviewing the resulting status.

## Unknown purchases and reconnects

The app journals a unique order nonce before sending a purchase. Never repeat a buy because the first response timed out. A `PENDING` or `UNCERTAIN` record can represent a purchase that succeeded at the broker even if the app did not receive its identifier.

1. Stop automation and keep the emergency halt active.
2. Inspect the official broker transaction/contract records for the account and time.
3. Reconnect and use snapshot/reconciliation for known contract identifiers.
4. If the original outcome cannot be established, leave new entries blocked and obtain broker support. Do not edit a row to `REJECTED`, delete databases, or reset risk to force another purchase.

No automatic retry or reconnect silently re-arms purchasing. Request IDs pair responses; they are not broker-supported purchase idempotency keys. Local unique reservations and conservative lockout reduce duplicate risk but cannot guarantee the network delivers exactly once.

Stopping a strategy or shutting down cleanly cancels its unfilled virtual pending entries; open virtual positions remain recorded. After a crash, pending rows may still exist and require review. Virtual stop/target reconciliation requires valid closed bars for the same instrument/timeframe; the app does not run a universal background paper-portfolio valuation service. Revisit the affected instrument/timeframe before treating an old displayed position as current.

Paper accounting has its own virtual controls: initially 0.5% per trade, at most three open/pending positions and one per symbol, 2%/5% day/week loss-plus-reserved-risk budgets based on UTC period-start closed virtual equity, and a 10% closed-equity high-water drawdown stop. Its initial baseline is 10,000 units. Stop gaps can exceed nominal virtual risk; costs and gap assumptions remain simulation approximations.

## Backups and recovery

State files include `tradelab.db`, `deriv_order_journal.db`, `strategy_signals.db`, `paper_positions.db` and `risk_control.db`. See [API_AND_DATA.md](API_AND_DATA.md) for schemas. Tokens are not included.

1. Stop the server cleanly and confirm its process exited. Record the software commit and data-directory path.
2. Back up all databases as one consistent set. Prefer the SQLite backup API. If copying files, include any associated `-wal` and `-shm` files rather than copying only an active `.db`.
3. Store backups privately with restrictive access and encryption appropriate to the workstation. The application does not provide automatic encrypted backups.
4. Restore only with the server stopped. Preserve the current state separately before replacement; do not mix broker/risk databases from different dates.
5. Run SQLite integrity checks and audit-chain verification, start with robots stopped, authenticate again, then reconcile broker balances, positions and orders before considering demo activation.

A restored backup can be older than the broker's current state. It is not proof that no orders were placed after the backup. Remote reconciliation remains mandatory. Local backup/restore instructions do not constitute a tested disaster-recovery guarantee unless the specific drill appears in [VALIDATION.md](VALIDATION.md).

## Troubleshooting

| Symptom | Check and supported action |
|---|---|
| HTTP 401 | App-ID/token pairing, PAT authentication type, revocation and correct permissions in the official portal. No workaround bypasses broker authorization. |
| HTTP 403 | Account/product entitlement and API scope; contact broker if access is denied. |
| Account discovered but not connected | Distinguish account list, OTP URL/mode, WebSocket/TLS, balance, markets and reconciliation stages. Inspect sanitized errors; do not regenerate tokens merely to fix parsing. |
| No active markets | Refresh broker metadata. A valid connected account can have no permitted markets; no fallback symbol is safe. |
| Unsupported duration | Select only an advertised exact side/expiry or another permitted market. Chart timeframe is not contract duration. |
| Missing/stale calendar | Refresh truthful licensed coverage, or use monitoring/paper research. Do not fabricate an empty calendar. |
| `NO VALIDATED STRATEGY` | Insufficient/negative/uncertain evidence is valid. Add legitimate unseen history, never invented wins or repeated tuning on the same holdout. |
| Pending/uncertain order | Follow the unknown-purchase procedure; do not resend, clear journals or claim rejection. |
| MT5 login fails | No MT5 adapter is implemented; an Options PAT/OTP token is not an MT5 authorization fix. |
| Browser shows stale assets | Refresh the page/service worker after an upgrade and inspect server version/status. Never rely on cached UI status as broker readiness evidence. |
| Public/VPS hosting desired | Requires a separate authentication/security/operations design; no public deployment is authorized or verified by this package. |

## Strategy-library workflow and upgrade

Use Strategy Research & Automation to browse the runtime catalog, read rule/family/warm-up metadata, change bounded parameters and test the selected configuration. Preserve identical data/cost assumptions when comparing candidates. Research evidence does not grant broker permission. Source, rule version, parameters and regime reasons should remain visible in exported decisions.

The previous book-pattern workspace is removed. Old rule IDs cannot be activated. Startup migration preserves original signal/paper files and retained historical rows while using `strategy_signals.db` and `paper_positions.db`. Stop the server and back up all state before the upgrade. Legacy history is not current-rule evidence.

Adding more strategies does not establish improved accuracy. Assess net expectancy, drawdown, uncertainty, sample sufficiency, stability, worse-cost outcomes and fresh demo-forward behavior. Repeated searches on the same held-out interval create selection bias.
