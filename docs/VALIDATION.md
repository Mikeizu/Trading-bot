# Validation ledger and reproducible procedures

This release replaces the previous strategy engine and workspace. The prior release at commit `615e273` passed 282 Python tests and 42 browser scenarios; those results are historical baseline evidence only, not a pass claim for this changed release. Current-release executed results must identify the tested source, actual commands and observed outcomes.

## Executed v6 results

- **313 Python tests passed in 40.389 seconds:** 0 failures, 0 errors, 0 skipped.
- **24 offline + 20 mocked integration browser scenarios passed:** 160 controls inventoried, no unreviewed entries, no JavaScript exceptions, no external orders.
- Browser smoke confirmed eight pages, mobile layouts and service-worker startup. The new library has 24 strategies with UP/DOWN and causal-data tests.
- Statement coverage: **89.23% across 13 core modules, unittest processes only.
- Six migration checks confirmed retained original ledgers, consistent WAL copies, non-overwrite/repeatability and no published partial target on corruption.
- JavaScript syntax, Python compilation, launcher syntax, dependency consistency and source whitespace checks passed.

## Current checks and honest boundaries

| Check | Required evidence |
|---|---|
| Python unit/integration/fault suite | Run `python -m unittest discover -s tests -v`; record executed count, failures/errors/skips and source version |
| Strategy library | Each catalog entry evaluated with causal fixtures, numeric/parameter/warm-up refusal, prefix invariance and explicit rationale |
| Research | Independent split/fold capital, next-open entry, expiry gaps, costs/stress, sample/uncertainty gates and training-only selection |
| Browser controls | Actual server checks for changed library, research parameters, exports, navigation and retained risk/broker controls |
| Broker fixtures | Distinguish fictional account/price/order replies from authenticated broker evidence; do not let fixtures enter production paths |
| Package | Clean source revision, verified wheel/manifest, fresh extraction and offline install/startup on the recorded OS |
| Real broker | Account-authorized authentication, catalogue, quote, any separately permitted purchase, settlement and reconciliation; not satisfied by mocks |

No authenticated Deriv purchase, actual future strategy accuracy or profitability has been established by this development work. The current cloud proxy denied the official Deriv API and the exact Google Play comparison-product listing before authenticated responses. See [PUBLIC_RESEARCH.md](PUBLIC_RESEARCH.md). Saved domain settings do not execute requests, apply runtime changes or publish a snapshot.

## Reproduce research

1. Preserve the licensed input dataset, instrument, UTC timestamp format, timeframe and source. Use completed, ordered, unique OHLC rows and enough history for the selected rule's warm-up. Do not invent missing volume, sessions, prices or broker payouts.
2. Fix the strategy version, parameters, holding bars, payout and execution-cost assumptions before inspecting the held-out interval. A 65% win-rate target is an annotation, not an order permission.
3. Run selected/all strategy research and export the complete report: net metrics, sample counts, uncertainty, costs, capital model, trades, split/fold boundaries, hashes, active rule and reasons for rejection.
4. Training and holdout each receive their own declared initial capital. Overall equity/return uses both allocations. Boundary-crossing trades are purged before balance or occupancy changes; training outcomes cannot fund or starve holdout entries.
5. Rank on training evidence only. Check one predeclared training candidate against the untouched holdout. Do not replace a failed candidate using the best held-out outcome.
6. Inspect training-only purged walk-forward folds and worse-cost sensitivity. These are not independent future observations, parameter stability proof or a liquidity model.
7. Preserve previous versions and already-used intervals. After tuning on a holdout, label it used and collect new untouched data.

Reports describe fixed-expiry Options simulations under assumed costs. They do not recreate actual historical bid/ask, broker contract payouts, partial fills, financing, liquidity or future returns. Closed-trade equity is not intrabar mark-to-market equity. Undefined ratios remain undefined rather than fabricated confidence.

## Separately authorized demo acceptance — unverified here

Connect an explicitly classified demo account with valid matching App ID/PAT and account/product permission. Confirm identity/currency, fresh balance/portfolio, exact symbols/contract durations, risk limits, calendar and no unresolved orders. Observe monitoring and paper behavior first. Any broker purchase requires a separately explicit authorization and an independently auditable quote, order, contract and actual settlement record. A timeout requires investigation, not a repeated buy.

No real-account purchase is supported. Demo results alone would not complete a production security/legal review or justify live activation. MT5/CFD, licensed automatic news ingestion, remote authentication, signed installers and Windows execution remain unverified or absent unless a later specific result is recorded.
