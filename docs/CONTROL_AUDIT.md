# Control and integration audit

All **115 inventoried DOM controls** have an outcome and linked test evidence. **282 Python tests passed** in 40.015 seconds, with zero failures, errors or skips. Two browser suites passed **42 scenarios** with zero JavaScript exceptions. This is a factual test report, not a guarantee that every possible input, platform or external integration works perfectly.

## What passed and what remains unverified

| Outcome | Controls | Meaning |
|---|---:|---|
| Local pass | 59 | Successful local/offline control behavior. |
| Local + mocked pass | 21 | Successful local behavior plus connected behavior using the test-only fictional broker. |
| Mocked broker pass | 31 | Successful actual local HTTP/UI behavior against fictional broker responses only. |
| Protective gate only | 1 | Expected protective refusal/disabled state verified; actual authorized strategy promotion not demonstrated. |
| External link reviewed only | 1 | Destination/HTML attributes reviewed; external service availability/authentication not tested. |
| Unsupported; locked | 2 | Unavailable feature deliberately disabled; this is a verified lock, not successful execution. |

The 31 controls originally deferred by the disconnected browser run are mapped to connected fixture evidence; **zero controls remain unreviewed in this inventory**. Connected tests use fictional accounts, balances, markets, credentials and purchases through the actual local HTTP handlers. The fixture made two simulated purchase calls and **zero broker orders**. Its form/submit aliases do not increase the 115-control DOM total.

**A disabled control is not counted as successful execution.** The best-strategy activation button was verified to stay locked without sufficient evidence. The two legacy live-arm controls remain unsupported and disabled. The developer-portal link was inspected for its HTTPS destination and safe attributes; its external service was not tested.

## Test evidence

| Check | Result and limit |
|---|---|
| Python unit, integration and fault tests | 282 passed, 0 failed, 0 errors, 0 skipped. Broker calls are deterministic doubles. |
| Offline actual-server browser suite | 22 scenarios passed; navigation, every inventoried local input/control, six indicators, seven patterns, eight research timeframes, imports/exports, robot controls, emergency stop/resume and mobile layouts. |
| Connected browser suite | 20 scenarios passed using a test-only fictional broker; authentication errors, account switching, catalogue/durations, quote invalidation, review/cancel/buy, timeout recovery, risk/calendar settings and strategy configuration. |
| JavaScript errors | Zero exceptions in both browser suites. |
| Downloads | Synthetic CSV, selected research JSON, seven-strategy comparison JSON and audit JSON downloaded and parsed successfully. |
| Release ZIP | Fresh extraction, checksum-verified bundled wheel, offline install and Linux launcher HTTP readiness passed. Python 3.10+ is required. |
| Native Windows execution | Not run. A Windows launcher is supplied; there is no claim of a tested standalone Windows executable. |
| Genuine Deriv integration | Not verified. No usable broker bindings were present; current official API HTTPS reachability was blocked by proxy HTTP 403. No external orders were submitted. |

The broker browser fixture intentionally does not launch autonomous workers. Signal-to-order worker behavior is tested separately by the Python suites. Actual Deriv permissions, prices, fills, settlement, reconnects and regional entitlements still require a separately authorized demo acceptance run.

## Complete control matrix

Identifiers are the actual element IDs or stable inventory keys. A form and its submit button can appear separately because they are separate DOM controls. “Mocked” always means a local test double, never a verified broker account. Full evidence, labels and source-report hashes are in [control_audit.json](control_audit.json).

### Global

| Control | Outcome | Evidence |
|---|---|---|
| `a:#main-content:Skip to main content` | Local pass | Keyboard skip link |
| `a:#overview:M✦MIKEIZU TRADELAB PRO` | Local pass | Quick navigation controls and brand |
| `nav:overview` | Local pass | All navigation buttons, deep links and reload persistence |
| `nav:naked` | Local pass | All navigation buttons, deep links and reload persistence |
| `nav:deriv` | Local pass | All navigation buttons, deep links and reload persistence |
| `nav:robot` | Local pass | All navigation buttons, deep links and reload persistence |
| `nav:backtest` | Local pass | All navigation buttons, deep links and reload persistence |
| `nav:history` | Local pass | All navigation buttons, deep links and reload persistence |
| `nav:risk` | Local pass | All navigation buttons, deep links and reload persistence |
| `nav:settings` | Local pass | All navigation buttons, deep links and reload persistence |
| `#view-toggle` | Local pass | Beginner and advanced views persist; disclosures open |
| `#global-kill` | Local + mocked pass | Global emergency stop, reload, bad phrase, explicit resume; Money formatting and every mobile page retain stop control; Connected emergency stop persists and e… |

### Overview

| Control | Outcome | Evidence |
|---|---|---|
| `#refresh-overview` | Local pass | Refresh, manual candle advance and every built-in watchlist market |
| `#chart-next` | Local pass | Refresh, manual candle advance and every built-in watchlist market |
| `#overview-start` | Local pass | Overview robot toggle starts and stops |
| `go:robot` | Local pass | Quick navigation controls and brand |
| `go:settings` | Local pass | Quick navigation controls and brand |
| `market:EUR/USD` | Local pass | Refresh, manual candle advance and every built-in watchlist market |
| `market:GBP/USD` | Local pass | Refresh, manual candle advance and every built-in watchlist market |
| `market:XAU/USD` | Local pass | Refresh, manual candle advance and every built-in watchlist market |
| `market:BTC/USD` | Local pass | Refresh, manual candle advance and every built-in watchlist market |
| `market:CUSTOM` | Local pass | Refresh, manual candle advance and every built-in watchlist market; Dynamically imported CSV market can be selected |
| `go:history` | Local pass | Quick navigation controls and brand |

### Naked

| Control | Outcome | Evidence |
|---|---|---|
| `#naked-profile` | Local + mocked pass | All seven pattern backtests and all eight timeframes; Every trading horizon starts in monitor mode with broker fixture capability |
| `#naked-strategy` | Local + mocked pass | All seven pattern backtests and all eight timeframes; Seven programmed strategies can each start and stop monitor mode |
| `#naked-timeframe` | Local + mocked pass | All seven pattern backtests and all eight timeframes; Every trading horizon starts in monitor mode with broker fixture capability |
| `#naked-source` | Local pass | All seven pattern backtests and all eight timeframes; Research CSV validation, import, and local-source backtest |
| `#naked-csv-input` | Local pass | Research CSV validation, import, and local-source backtest |
| `#naked-symbol` | Mocked broker pass | Seven programmed strategies can each start and stop monitor mode |
| `#naked-payout` | Local pass | All seven pattern backtests and all eight timeframes |
| `#naked-target` | Local pass | All seven pattern backtests and all eight timeframes |
| `#naked-stake` | Local + mocked pass | All seven pattern backtests and all eight timeframes; Paper/demo action and expiry controls configure separately from real execution |
| `#naked-expiry-bars` | Local pass | All seven pattern backtests and all eight timeframes |
| `summary::Execution-cost assumptions` | Local pass | Execution-cost disclosure toggled; Research assumptions/provenance disclosures inspected |
| `#research-commission` | Local pass | Research cost inputs, invalid backend settings, JSON export |
| `#research-spread` | Local pass | Research cost inputs, invalid backend settings, JSON export |
| `#research-slippage` | Local pass | Research cost inputs, invalid backend settings, JSON export |
| `#naked-backtest` | Local pass | All seven pattern backtests and all eight timeframes |
| `#naked-action` | Local + mocked pass | Disconnected strategy activation rejects and no demo-mode option; Paper/demo action and expiry controls configure separately from real execution |
| `#naked-expiry-minutes` | Mocked broker pass | Paper/demo action and expiry controls configure separately from real execution |
| `#naked-start` | Local + mocked pass | Disconnected strategy activation rejects and no demo-mode option; Seven programmed strategies can each start and stop monitor mode |
| `#naked-stop` | Mocked broker pass | Seven programmed strategies can each start and stop monitor mode |
| `#naked-scan-all` | Local + mocked pass | Seven-strategy comparison, export, and insufficient-evidence disabled start; Broker-data research comparison refuses unsupported strategy promotion |
| `#naked-export-all` | Local + mocked pass | valid json download; Seven-strategy comparison, export, and insufficient-evidence disabled start; Broker-data research comparison refuses unsupported strategy … |
| `#naked-start-best` | Protective gate only | Seven-strategy comparison, export, and insufficient-evidence disabled start; No validated fixture strategy means activation stays disabled; no forged qualifica… |
| `#naked-report-export` | Local pass | valid json download; Research cost inputs, invalid backend settings, JSON export |
| `summary::Dataset, configuration and assumptions` | Local pass | Research assumptions/provenance disclosures inspected |

### Deriv

| Control | Outcome | Evidence |
|---|---|---|
| `#deriv-refresh` | Local + mocked pass | Disconnected broker controls remain safe; Purchase timeout durably blocks retry and survives browser/account reconnect |
| `#deriv-auth-form` | Mocked broker pass | Demo account discovery/connect clears browser credentials |
| `#deriv-app-id` | Mocked broker pass | Invalid broker authentication gives actionable error without a session |
| `#deriv-pat` | Mocked broker pass | Invalid broker authentication gives actionable error without a session |
| `#deriv-list` | Local + mocked pass | Disconnected broker controls remain safe; Invalid broker authentication gives actionable error without a session |
| `#deriv-account` | Mocked broker pass | Account disconnect and real-account connection remain strictly read-only |
| `button:submit:2. Connect selected account` | Mocked broker pass | Demo account discovery/connect clears browser credentials |
| `#deriv-disconnect` | Local + mocked pass | Disconnected broker controls remain safe; Purchase timeout durably blocks retry and survives browser/account reconnect |
| `a:https://developers.deriv.com/:Deriv Developer Portal` | External link reviewed only | Official HTTPS destination and safe new-tab behavior reviewed; Official developer portal destination and safe external link; HTTPS destination and safe target/… |
| `#deriv-order-form` | Mocked broker pass | Changing stake or expiry invalidates a previously reviewed quote |
| `#deriv-symbol` | Mocked broker pass | No-offer market disables quoting; offered directions and all expiry choices work |
| `#deriv-side` | Mocked broker pass | No-offer market disables quoting; offered directions and all expiry choices work |
| `#deriv-minutes` | Mocked broker pass | Changing stake or expiry invalidates a previously reviewed quote |
| `#deriv-check-durations` | Local + mocked pass | Disconnected broker controls remain safe; No-offer market disables quoting; offered directions and all expiry choices work |
| `#deriv-stake` | Mocked broker pass | Changing stake or expiry invalidates a previously reviewed quote |
| `button:submit:Get live broker price proposal` | Mocked broker pass | Changing stake or expiry invalidates a previously reviewed quote |
| `#deriv-buy` | Mocked broker pass | Purchase timeout durably blocks retry and survives browser/account reconnect |
| `#deriv-arm-phrase` | Unsupported; locked | Account disconnect and real-account connection remain strictly read-only |
| `#deriv-arm` | Unsupported; locked | Account disconnect and real-account connection remain strictly read-only |
| `#deriv-strategy` | Mocked broker pass | Every indicator robot strategy configures and stops without autonomous fixture fills |
| `#deriv-auto-stake` | Mocked broker pass | Every indicator robot strategy configures and stops without autonomous fixture fills |
| `#deriv-auto-start` | Local + mocked pass | Disconnected broker controls remain safe; Every indicator robot strategy configures and stops without autonomous fixture fills |
| `#deriv-auto-stop` | Local + mocked pass | Disconnected broker controls remain safe; Every indicator robot strategy configures and stops without autonomous fixture fills |
| `#deriv-candle-fetch` | Local + mocked pass | Disconnected broker controls remain safe; Candle history control loads well-formed closed fixture bars |

### Robot

| Control | Outcome | Evidence |
|---|---|---|
| `#robot-form` | Local pass | Synthetic robot parameters, invalid input, save and start/stop |
| `#robot-asset` | Local pass | Synthetic robot parameters, invalid input, save and start/stop |
| `#robot-strategy` | Local pass | Synthetic robot parameters, invalid input, save and start/stop |
| `#robot-stake` | Local pass | Synthetic robot parameters, invalid input, save and start/stop |
| `#robot-duration` | Local pass | Synthetic robot parameters, invalid input, save and start/stop |
| `#robot-loss` | Local pass | Synthetic robot parameters, invalid input, save and start/stop |
| `#robot-profit` | Local pass | Synthetic robot parameters, invalid input, save and start/stop |
| `#robot-risk` | Local pass | Synthetic robot parameters, invalid input, save and start/stop |
| `#robot-limit` | Local pass | Synthetic robot parameters, invalid input, save and start/stop |
| `#robot-payout` | Local pass | Synthetic robot parameters, invalid input, save and start/stop |
| `#save-robot` | Local pass | Synthetic robot parameters, invalid input, save and start/stop |
| `#robot-start` | Local pass | Synthetic robot parameters, invalid input, save and start/stop |
| `#robot-stop` | Local pass | Synthetic robot parameters, invalid input, save and start/stop |

### Backtest

| Control | Outcome | Evidence |
|---|---|---|
| `#backtest-form` | Local pass | All six indicator backtests and all backtest inputs |
| `#test-asset` | Local pass | All six indicator backtests and all backtest inputs |
| `#test-strategy` | Local pass | All six indicator backtests and all backtest inputs |
| `#test-stake` | Local pass | All six indicator backtests and all backtest inputs |
| `#test-duration` | Local pass | All six indicator backtests and all backtest inputs |
| `button:submit:⌁ Run historical test` | Local pass | All six indicator backtests and all backtest inputs |

### History

| Control | Outcome | Evidence |
|---|---|---|
| `a:/api/export:↓ Export CSV` | Local pass | valid csv download; Trade journal CSV export |

### Risk

| Control | Outcome | Evidence |
|---|---|---|
| `#risk-refresh` | Local + mocked pass | Risk refresh, invalid disconnected calendar, audit export; Connected risk refresh and audit download contain valid isolated records |
| `#risk-config-form` | Mocked broker pass | Connected default risk form is valid and saves every configurable hard limit |
| `#limit-risk_per_trade_pct` | Mocked broker pass | Connected default risk form is valid and saves every configurable hard limit |
| `#limit-daily_loss_pct` | Mocked broker pass | Connected default risk form is valid and saves every configurable hard limit |
| `#limit-weekly_loss_pct` | Mocked broker pass | Connected default risk form is valid and saves every configurable hard limit |
| `#limit-max_drawdown_pct` | Mocked broker pass | Connected default risk form is valid and saves every configurable hard limit |
| `#limit-max_positions` | Mocked broker pass | Connected default risk form is valid and saves every configurable hard limit |
| `#limit-max_trades_per_day` | Mocked broker pass | Connected default risk form is valid and saves every configurable hard limit |
| `#limit-max_order_size` | Mocked broker pass | Connected default risk form is valid and saves every configurable hard limit |
| `#limit-max_asset_exposure_pct` | Mocked broker pass | Connected default risk form is valid and saves every configurable hard limit |
| `#limit-max_group_exposure_pct` | Mocked broker pass | Connected default risk form is valid and saves every configurable hard limit |
| `#limit-consecutive_loss_limit` | Mocked broker pass | Connected default risk form is valid and saves every configurable hard limit |
| `#limit-cooldown_minutes` | Mocked broker pass | Connected default risk form is valid and saves every configurable hard limit |
| `#limit-calendar_policy` | Mocked broker pass | Synthetic calendar exception needs confirmation and persists only after approval |
| `button:submit:Save account risk limits` | Mocked broker pass | Connected default risk form is valid and saves every configurable hard limit |
| `summary::Import a licensed economic-calendar snapshot` | Local pass | Beginner and advanced views persist; disclosures open |
| `#risk-calendar-file` | Local + mocked pass | Risk refresh, invalid disconnected calendar, audit export; Calendar import rejects malformed JSON and accepts explicit current fixture coverage |
| `#risk-resume-form` | Local pass | Global emergency stop, reload, bad phrase, explicit resume |
| `#risk-resume-phrase` | Local + mocked pass | Global emergency stop, reload, bad phrase, explicit resume; Connected emergency stop persists and explicit resume restarts no robot |
| `#risk-resume` | Local + mocked pass | Global emergency stop, reload, bad phrase, explicit resume; Connected emergency stop persists and explicit resume restarts no robot |
| `summary::Operational details` | Local pass | Beginner and advanced views persist; disclosures open |
| `#audit-export` | Local + mocked pass | valid json download; Risk refresh, invalid disconnected calendar, audit export; Connected risk refresh and audit download contain valid isolated records |

### Settings

| Control | Outcome | Evidence |
|---|---|---|
| `#csv-upload` | Local pass | Simulator CSV valid/invalid import, backtest-only history, reset cancel/confirm |
| `#reset-demo` | Local pass | Simulator CSV valid/invalid import, backtest-only history, reset cancel/confirm |

## Function coverage and limitations

The source inventory records **195 declared functions/methods across 11 core modules**. Unittest statement coverage measured **2885/3259 executable statements (88.52%; 89% rounded)**, leaving 374 statements unexecuted in that run. Browser/server child-process coverage was not combined, and branch coverage was not measured. These figures do not mean every function or fault path is proven correct. See [FUNCTION_AUDIT.md](FUNCTION_AUDIT.md).

## Remaining limits

- Genuine Deriv authentication, account permissions, WebSocket connectivity, broker quotes and purchases remain externally unverified. Apply the saved cloud network allowance before retrying connectivity; a saved draft does not apply or publish itself.
- Live purchases remain disabled, and MT5/CFD execution is not implemented.
- Calendar import, freshness and blackout safeguards work locally; there is no automatic licensed news feed.
- Paper/backtest results use disclosed OHLC and cost assumptions. They do not recreate every venue fill, spread, financing charge or liquidity event.
- Native Windows behavior, all browser/OS combinations, production remote authentication and independent security certification were not established by these runs.
- Passing software checks do not establish profitability or perfect operation. Follow the [authorized demo acceptance procedure](VALIDATION.md) before considering broker use.

## Reproduce

Run from an isolated checkout with test state separate from personal journals:

```bash
python -m unittest discover -s tests -v
MIKEIZU_BASE_URL=http://127.0.0.1:8891 node tests/browser_controls.cjs
# The connected suite starts its isolated fictional-broker fixture automatically:
node tests/browser_broker_controls.cjs
```

Inspect the scripts for fixture startup and supported environment variables. They must run against isolated test state, not a personal active broker session. Playwright/Chromium are test tools, not application runtime dependencies.
