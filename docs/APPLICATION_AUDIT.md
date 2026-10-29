# Application audit

The source was imported from `MIKEIZU_TradeLab_PRO_v4_3_Deriv_Duration_Compatibility_Fix.zip` into the existing `Mikeizu/Trading-bot` checkout. The repository previously contained only a README and MIT license. The original license remains intact.

Archive SHA-256: `94102b99f79e769da4d387da371944b75a897c0ce41191298dc58dd31257eb97`.

This report distinguishes source implementation from operational proof. “Locally tested” refers to deterministic tests and local requests, never authenticated broker success. The supplied [master brief](MASTER_PROMPT.md) is a requirements specification, not a record of existing features.

## Capabilities and evidence

| Capability | Supplied archive | Current status and evidence | Practical limit |
|---|---|---|---|
| Browser application | Implemented: stdlib HTTP server and static UI | Retained and improved; `deriv_server.py`, `server.py`, `static/` | Single-user localhost only; no public service authentication |
| Synthetic simulator | Implemented: generated candles, six indicators, independent ledger | Retained; source explicitly labels synthetic data in `server.py` | Generated prices are not market history |
| Seven Naked Forex rules | Implemented algorithmic interpretations in `naked_strategies.py` | Retained with research/version/provenance improvements | Not verified replicas of discretionary methods |
| Scalping through monthly charts | Implemented profiles and daily aggregation | Research/monitoring supported where sufficient valid history exists | No universal broker duration entitlement; monthly scans need years of history |
| Broker account discovery | PAT HTTP account listing and OTP WebSocket setup | Validation, sanitized failures, mode checks retained/hardened in `deriv_bridge.py` | Authentic token/account compatibility remains unverified |
| Active markets | New and legacy broker symbol-field normalization | Retained and covered by mocked compatibility tests | Broker may legitimately provide zero markets; no invented fallback |
| Duration compatibility | `contracts_for` advertised CALL/PUT duration checks | Retained and stricter validation | Metadata is not an execution guarantee; proposal remains authoritative |
| Demo purchases | Proposal → buy flow, manual/demo robots | Persistent risk gate, strict state checks, one-use quotes, uncertain-outcome lockout | No authorized real demo purchase was made here |
| Manual live purchase | Environment opt-in plus confirmation permitted real buys | Disabled in this version, including former opt-in route | Real accounts are read-only; production approval remains future work |
| Broker reconciliation | Contract-status polling and SQLite order journal | Hardened to reject malformed/missing state and never blindly retry buys | Unknown outcomes require broker investigation; no automatic certainty manufactured |
| Risk management | Fixed balance %, daily dollars/trade counts; mostly process-session controls | Independent persistent risk engine and per-account/mode limits in `risk_engine.py` | Broker Options stakes only; CFD stop sizing/margin engine absent |
| Emergency stop | Separate robot stop buttons | Persistent risk halt plus automation stop and quote cancellation | Halts entries; does not close broker positions |
| Paper positions | Virtual stop/2R target, 1% risk, confirmation-close entry, no costs | Improved virtual entry/cost/risk handling in `paper_engine.py` | Not a broker fill simulator or MT5 position manager; matching instrument/timeframe bars are required for virtual reconciliation |
| Historical backtest | Causal pattern detection, next-open entry, 70/30 holdout, assumed payouts | Cost-aware analytics, purged chronological/walk-forward evidence, provenance | Costs are assumptions; no historical broker payouts/bid-ask/financing |
| Strategy ranking | Train-only score and single-candidate holdout; 65% a pass condition | Multi-criteria evidence and uncertainty; 65% informational | No guaranteed winner or automatic promotion to live |
| Market regime | Absent as independent module | Deterministic heuristic classification and reasons in `market_regime.py` | No calibrated probability, external fundamentals, or predictive certainty |
| Economic news | Absent | Calendar input/freshness fail-safe policy in risk layer | No licensed/automatic economic calendar feed implemented |
| Explainable decisions | Basic signal explanation and signal SQLite log | Versioned evidence, risk decisions, regime reasons, durable audit records | Not a language-model forecasting system |
| Journals | Separate simulator, paper, signals, and broker databases | Retained with risk/audit persistence and expanded order context | Local tamper evidence is not external notarization or complete broker statement history |
| MT5/CFD execution | Not implemented | Not implemented; explicitly unsupported | Requires separate official adapter, sizing, financing, and permission validation |
| Machine learning/AI forecasts | No trained model | No fabricated model or confidence added | Transparent deterministic research remains the implemented intelligence |
| Deployment | Windows/macOS/Linux source launchers | Source delivery, local setup, tests and operational docs | No signed executable, installer, VPS service, or production certification |

## Important defects identified in the archive

1. **Critical: incomplete persistent risk boundary.** Daily dollar caps did not provide independent daily/weekly equity/drawdown protection, emergency-stop persistence, calendar freshness, or complete restart-resistant risk state. The new risk module is a separate gate, not strategy advice.
2. **Critical: ambiguous execution and malformed broker data.** Non-finite balance values, invalid portfolio/settlement fields, unexpected buy responses, and exceptions could leave misleading state. Broker checks now fail closed and retain unresolved outcomes for investigation.
3. **Critical: live route exceeded verified capability.** The original manual one-trade real-money opt-in existed despite no authenticated demo evidence. Real purchases are disabled pending a future separately validated release.
4. **High: optimistic research/paper assumptions.** Fixed payouts, omitted costs and confirmation-close virtual entry could overstate performance. Research now discloses assumptions, uses chronology, and reports evidence rather than a marketing benchmark.
5. **High: 65% benchmark conflated with qualification.** The old holdout gate required the research win-rate target. Qualification now prioritizes net expectancy, uncertainty, drawdown, sample adequacy and stability; a win-rate target is informational.
6. **High: market/news suitability not a control.** The archive lacked an independent regime/news gate. Deterministic regime analysis and explicit missing/stale-calendar handling now expose reasons to pause.
7. **Medium: interface could imply readiness without evidence.** Static connection labels and manual-live UI were misleading. Account-mode, risk and system-health information now distinguish local implementation from verified broker behavior.

## Integration issues: diagnosed versus unverified

- **HTTP 401:** Source diagnostics identify rejected PAT/App-ID pairing or permissions. No actual user 401 response was available, so no account-specific root cause or successful resolution is claimed.
- **Account found but connection fails:** Account listing, OTP URL/mode verification, WebSocket establishment, fresh balance, symbols and reconciliation are separate checks. A listed account does not prove every later step works.
- **No markets:** Archive normalization already supports current `underlying_symbol` fields and legacy `symbol` fields. A genuinely empty catalogue stays empty and blocks entries. No broker-provided empty response was available here.
- **Unsupported duration:** Broker-advertised CALL/PUT ranges are checked per direction and exact minute expiry. The app does not substitute another expiry or infer permissions from symbols.
- **MT5 authorization:** There is no MT5 adapter in the supplied source. An MT5 authorization fix cannot be claimed; passwords/credentials for another API are not a substitute.

## Readiness boundary

The development workflow and deterministic tests can validate code behavior, fault handling, and local HTTP integration. They cannot establish broker entitlements, real execution, legal availability, profitability, secure public hosting, or loss-free operation. See [VALIDATION.md](VALIDATION.md) for the executed-check ledger and remaining evidence gates.
