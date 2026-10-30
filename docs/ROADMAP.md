# Improvement roadmap and evidence gates

The implementation is a local research/demo application. Each phase distinguishes source behavior from independent operational evidence; a successful mock does not complete an authenticated broker or financial validation gate.

| Phase | Dependencies and modules | Acceptance | Remaining evidence |
|---|---|---|---|
| 1. Preserve safety during the strategy replacement | Independent risk, broker journal, account/mode identity, state migration | No removed rule can activate; risk state, unresolved orders and historical rows survive upgrade; every buy path remains guarded | Restore/reconciliation drills with real authorized accounts |
| 2. Expand transparent rules | Valid OHLC, indicator catalog, `engine.py`, bounded parameters | Every rule has an explicit trigger, warm-up, family, rationale and causal tests; unavailable volume is never invented | Independent instrument/regime parameter studies |
| 3. Validate research honestly | `strategy_research.py`, metrics, selector | Next-open entries, cost stress, isolated split/fold capital, purged boundaries, training-only ranking and no winner when evidence is insufficient | Authentic payout/bid-ask history; multiple-testing and stability analysis |
| 4. Apply suitability controls | Fresh completed bars, regime classifier, trustworthy calendar | Unsuitable/stale/missing evidence blocks automatic entries; classification reasons remain visible | Historically calibrated thresholds and licensed feed ingestion |
| 5. Improve the terminal | Stable catalog/research/risk APIs and responsive UI | Dynamic strategy controls, exported evidence, visible account/source/mode and accessible emergency stop; regression browser checks | Full accessibility/localization and independent user studies |
| 6. Verify execution and recovery | Authorized demo account and official broker capabilities | Authentication, symbols, exact durations, quote, one permitted purchase, settlement and reconnect reconcile with broker records | Current cloud access and user account authorization; external monitoring and anchored audits |
| 7. Consider wider production use | All prior evidence, security/legal/product review | Platform-specific release validation, remote authentication/TLS if hosted, signed updates, documented jurisdiction/product entitlement | **Not complete.** MT5/CFD and all live execution remain unavailable |

## Research evidence ladder

Research → historical validation → untouched out-of-sample evaluation → training-only walk-forward checks → separately authorized demo forward observation → possible future production review.

A benchmark such as 65% wins is informational. Qualification requires sufficient samples and positive cost-adjusted evidence with controlled drawdown and uncertainty. Passing a historical gate never enables real-money trading. Collect new unseen data after a failed or reused holdout rather than substituting the best held-out performer.
