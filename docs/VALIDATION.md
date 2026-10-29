# Validation evidence and procedures

All claims below distinguish code behavior from broker/financial proof. A local fake transport is not an authenticated account test. No broker token or account credentials were available for a real end-to-end run, and no broker orders were submitted by the development work.

## Executed checks

| Check | Evidence | Outcome and limit |
|---|---|---|
| Imported archive baseline | `python -m unittest discover -s tests -v`, Python 3.12.14, before improvements | **67 tests passed.** Confirms the supplied code's existing deterministic test baseline, not broker compatibility. |
| Expanded integrated suite | Coverage.py 7.17.0 running `unittest discover -s tests -v`, Python 3.12.14 | **282 tests passed in 40.015 seconds; 0 failures, 0 errors, 0 skipped.** Includes deterministic faults, HTTP handlers, package integrity and fixture safety. The earlier improvement run passed 196 tests. |
| Risk module | `tests/test_risk.py` | **38 tests passed**, included in the integrated suite: limits, identity isolation, calendar freshness, emergency persistence, reservation recovery/concurrency, ordering and audit tampering. |
| Broker fault coverage | New safety tests plus existing authentication/market/duration suites | Deterministic mocked responses cover invalid account state, malformed/negative/non-finite balances/portfolio, purchase timeouts/duplicates, settlement uncertainty, read-only real account and supported expiries. No external API/account verification. |
| Research and regime components | Research/regime suites plus existing indicator/strategy regressions | Deterministic chronology, next-open/cost/metric/provenance, training-only ranking/fold, insufficient-sample, cost-stress and regime tests executed. Exact final count is recorded with the full suite. |
| Browser workflow | Playwright Chromium against the actual local server, `tests/browser_smoke.cjs` | Eight pages inspected; research metrics/regime/walk-forward, advanced toggle, emergency-stop persistence over reload, explicit resume with automation stopped, five 390px layouts without horizontal overflow, and service-worker installation; **zero JavaScript exceptions** observed. This is local UI evidence, not a complete accessibility or broker test. |
| Dependency installation | Hash-locked `websocket-client` 1.9.2; SHA-256 recorded in `requirements.lock` | TLS and artifact verification retained. Installation must use `--require-hashes` for the lock. |
| Complete control inventory | `tests/browser_controls.cjs` and `tests/browser_broker_controls.cjs` | Individual controls classified in [CONTROL_AUDIT.md](CONTROL_AUDIT.md). Offline actions use the real server; connected flows use a fictional broker fixture. No external broker orders. |
| Unit-run code coverage | Eleven core modules, 3,259 statements | 2,885 statements executed: **88.52%**. Browser subprocesses and extracted-package checks are outside this measurement. Coverage does not prove every behavior is correct. |
| Fresh extracted package | `packaging/verify_install.py` | Offline installation in a new virtual environment, launcher startup, synthetic research, stored data advance, halt and explicit resume verified on Linux. Windows execution remains unrun. |

The final application was stopped and restarted using the hash-verified `START_MAC_LINUX.sh` launcher. The actual-server Chromium smoke passed again against that restarted process. Local HTTP checks confirmed all three worker threads alive, audit integrity true, seven catalogued strategies and live execution false. JavaScript syntax (`node --check`), Python compilation, Bash syntax and Git whitespace checks passed. Hash-required dependency force-reinstallation and `pip check` passed. No broker purchase was involved.

The current cloud configuration draft saved complete `install_script` and `start_skill` instructions plus the `api.derivws.com` custom domain allowance, preserving package-manager presets. Saving was confirmed, but does not apply network changes or publish a snapshot. Review/save the environment settings and publish through the product when appropriate. Neither a fresh-task restoration nor authenticated broker access has been verified.

The current cloud instance also attempted a non-destructive unauthenticated TLS connection to `api.derivws.com`. The egress proxy rejected the tunnel with HTTP 403 before an account/API response was obtained. This is a network-access observation, not a Deriv credential or entitlement failure. A saved domain allowance does not apply itself or prove WebSocket/account readiness; review/apply it in environment settings and retry before claiming broker connectivity.

The expanded audit corrected stale labels and navigation, quote invalidation while inputs change, numeric/payload validation, flat-price Bollinger calculations, expiry gaps, calendar/reservation edge cases, paper next-bar evidence, and journal integrity checks before mutation. Synthetic entries use prior closed candles and the next generated open; each order retains its entry payout. Supplied CSV timestamps are preserved and absent timestamps labelled inferred. Rejected imports cannot replace valid data or strand open practice trades. These results do not establish perfect operation under every possible system or market condition.

## Run the automated suite

From the checkout with the virtual environment prepared:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Windows uses `.\.venv\Scripts\python.exe`. These tests do not require broker credentials and must not place external orders. Temporary test state is isolated from real application journals.

JavaScript syntax:

```bash
for file in static/*.js; do node --check "$file"; done
```

The optional browser smoke script requires separately installed Playwright/Chromium tooling; it is not an application runtime dependency. The app itself has no Node build step. CI declares Linux/Windows and Python 3.10/3.12/3.13 coverage, but those remote workflow runs are not claimed as executed until GitHub reports them.

## Requested acceptance coverage

The following maps the brief’s minimum fault cases to source tests. A “covered” case is deterministic/local coverage unless stated otherwise; it is not an external broker result.

| Requested case | Coverage and remaining limit |
|---|---|
| Invalid/expired credentials | Mocked 401/403 diagnostics and token-safe error/redirect handling; actual token expiry unrun. |
| Demo/live account switching | Account identity/mode mismatch and stale quote invalidation; all real buys rejected. |
| Unsupported symbols/durations | Market normalization and exact side/expiry catalogue regression suites. |
| Disconnect during open trade | Known contract retention, malformed/missing settlement state and reconciliation fail-closed tests; actual broker outage unrun. |
| Duplicates/timeouts | One-use quote/atomic nonce, unmatched responses, ambiguous buy, durable uncertain-state and restart lockout. |
| Rate limiting | Mocked HTTP 429 reports the rate limit without retrying or reflecting secret response bodies; external broker rate-limit behavior unrun. |
| Abnormal spreads/gaps | Research doubled-friction stress, regime spike detection, adverse virtual gap fill and stop-first paper tests; no live spread feed. |
| Daily/weekly loss breach | Persistent day/week loss/exposure budgets including restarts and rollover. |
| Position size/margin | Stake/actual ask/max-order/exposure tests; CFD margin/lot sizing unsupported. |
| Strategy parameter changes | Bounded finite parameters and changed provenance; active rule switching requires stop. |
| Missing market data | Invalid/empty/out-of-order/stale candles and mismatched confirmation timestamp rejected. |
| Economic-calendar outage | Missing/stale coverage and relevant event blackout block demo/paper entries; pending paper entries cancelled. |
| Restart with active positions | Persistent open/pending paper entries, broker journals and risk reservations; robots start stopped. |
| Emergency shutdown | Global/account halt persistence, stop between quote/buy, reload/UI controls, no false broker close claim. |
| Historical data leakage | Future mutation/no-look-ahead, next-open entry, holdout separation and fold boundaries. |
| Out-of-sample calculations | Train-only ranking, no runner-up fallback, separate holdout metrics and cost stress. |
| Position reconciliation | Strict portfolio/contract IDs, unknown open positions and missing settlement P&L block entries. |
| Rejected/partial execution | Correlated broker rejection vs ambiguous response tested. Partial fills are unsupported by this fixed-stake product model; no fabricated partial-fill capability. |

## Reproduce a historical research report

1. Preserve the original OHLC dataset and its source/license. CSV rows must be chronological, unique timestamps, finite positive prices, and valid high/low ranges. Aggregate to the chosen timeframe before importing.
2. Record instrument, timezone/epoch format, timeframe, dataset period and source. Synthetic data must stay explicitly synthetic.
3. Fix strategy version/parameters and model before inspecting the holdout. Default research assumptions allocate 1,000 starting units **separately** to training and holdout (combined overall capital 2,000), plus independently funded training-only folds. Commission is 0 per trade, spread 1bp and slippage 0.5bp. These are assumptions rather than observed broker costs.
4. Run `/api/strategy/backtest` or **Compare all seven** and export the complete JSON, including trades, after-cost metrics, provenance/dataset hash, exact configuration, chronological splits, fold boundaries and warnings.
5. Research qualification requires at least 30 training and 30 holdout trades, positive after-cost evidence, Wilson lower win-rate bound above cost-adjusted breakeven, controlled drawdown and adequate positive training-only walk-forward folds. The 65% target is informational, not a promotion permit.
6. Inspect stress results with doubled spread/slippage and 1.5× commission on the same held-out signal ledger. It must remain positive with acceptable drawdown. This is a sensitivity check, **not** a fresh independent sample or a liquidity model.
7. Preserve the training candidate. If its holdout fails, do not substitute the highest holdout performer; collect new untouched data or revise the hypothesis and label prior data as already used.

Metrics include net P&L/return, win/loss rate, average win/loss, profit factor, expectancy, closed-trade drawdown/recovery, unannualized trade-return risk ratio, exposure/turnover, explicit costs, trade count/streaks and equity/drawdown arrays. Undefined ratios remain null rather than a fabricated large value. Training and holdout outcomes are independent research experiments; overall equity/return sums their starting allocations and P&L, rather than resetting a single bankroll between them. Closed-trade equity is not intrabar mark-to-market equity. Historical report boundaries and SHA-256 identify the input but do not authenticate its provider.

No supplied dataset establishes durable positive expectancy or a 65% achievable win rate. Sparse signals and empty backtests are legitimate outcomes. Authentic payout history, bid/ask, latency, partial fills, liquidity, swaps and financing remain outside the model.

## Required authorized demo acceptance run — not executed here

This procedure requires the user's explicit demo authorization, account access and broker entitlements. It is not permission for a background agent to submit orders.

1. Use an explicitly classified demo account and validate PAT/App-ID authentication, permissions, account ID/currency, fresh balance, available symbols and broker-advertised contract type/stake/duration.
2. Review risk limits, calendar source/freshness, external activity, broker portfolio and unresolved journals. Confirm the kill switch blocks a fresh quote/purchase and persists over restart; then explicitly resume.
3. Observe monitor-only closed-bar signals and compare timestamps/prices with the official broker data.
4. Run paper mode, inspect pending-next-open entry, costs and exits; keep it separate from broker records.
5. Only after explicit authorization, obtain one demo quote within conservative risk limits, review actual ask/payout/duration, and confirm a single purchase. Record the local nonce, broker contract identifier, state transitions and eventual actual P&L.
6. Reconcile the contract with official broker records. A timeout requires investigation, never an automatic retry. Test disconnection/restart recovery with controlled mocks first; avoid manufacturing real account faults or duplicate orders.
7. Forward-test for a predeclared observation period and independent sample across relevant markets/regimes. Include rejected orders, costs, interruptions and losses in the report. Define drawdown and error-rate failure gates before the run.

No real-account purchase is supported. Demo acceptance alone would not complete a production security/legal review or justify live activation.

## Unrun, blocked, or unsupported checks

- Authenticated Deriv account discovery, OTP/WebSocket establishment, real catalogue entitlements, real quote/purchase/settlement and end-to-end reconnect: **unrun; require authorized credentials, account access and usable cloud egress**. The current cloud tunnel to `api.derivws.com` was blocked by the proxy.
- Live trading: **disabled and unsupported**, not pending a token.
- MT5/CFD authorization, lot/tick/margin/stops/financing/execution: **not implemented**.
- Licensed automatic economic-calendar ingestion and historical event-feed validation: **not implemented**; manual truthful coverage/freshness controls are tested locally.
- Production remote authentication/TLS deployment, signed update/installers, external audit anchoring, regulatory/jurisdictional approval and independent penetration test: **not implemented/verified**.
- Windows launcher execution and GitHub CI matrix: documented and configured; only claim execution when a specific Windows/remote result is available.
- Statistical profitability and calibrated forecast probabilities: **not established** by software tests, simulated reports or heuristic regime labels.

A failed required test must be diagnosed; do not replace it with a syntax check, skip it to inflate the pass count, or treat an empty test run as readiness evidence.
