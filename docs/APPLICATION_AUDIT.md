# Current application audit

This release replaces the previous book-pattern workspace with a general technical-indicator research and automation library. The removed interface, detectors and retired release briefs are preserved in repository history at commit `615e273`; they are not current application capabilities.

A source implementation, a passing local test, a simulated broker response and an authenticated broker result are different kinds of evidence. Current execution results are recorded in [VALIDATION.md](VALIDATION.md). No software test establishes future trading accuracy or profitability.

| Capability | Current implementation | Evidence boundary |
|---|---|---|
| Local terminal | Python loopback API and responsive static interface | Single-user local operation; no public authentication service |
| Strategy library | Configurable technical rules across trend, momentum, mean-reversion, breakout and volatility families | Authoritative IDs, defaults and warm-up are supplied by `/api/strategy/catalog`; rules are quantified interpretations |
| Data integrity | Shared `market_data.py` validates OHLC, increasing timestamps, supported numeric bounds and UTC aggregation | Source labels distinguish synthetic, supplied CSV and broker history; no prices, sessions or volume are manufactured as authentic data |
| Historical research | `strategy_research.py` models next-open fixed-expiry contracts with disclosed payout/cost assumptions | Independent train/holdout capital, purging, walk-forward, stress and provenance do not substitute for authentic bid/ask or payout history |
| Strategy comparison | Training-only multi-criteria ranking and one selected candidate's held-out check | No runner-up chosen from holdout outcomes; no validated candidate is an acceptable result |
| Market regime | Deterministic classification, reasons and family-based rule eligibility | Heuristic, not a calibrated probability or news prediction |
| Monitoring | Completed broker candles and versioned signal explanations | Data availability, warm-up and freshness can legitimately prevent signals |
| Virtual paper positions | Durable pending next-open entries, costs, conservative stops/gaps and separate virtual equity | OHLC simulation; no broker position or CFD margin model |
| Deriv adapter | PAT account discovery, OTP/WebSocket, symbol/contract discovery, quotes and explicit demo purchases | Actual user account authentication, permissions, execution and settlement require separate authorized verification |
| Broker safety | Fresh snapshots, account/mode checks, one-use quotes, durable reservations and uncertainty lockout | Unknown purchases are not resent or guessed rejected |
| Persistent risk | Independent account/mode loss, drawdown, exposure, count, cooldown, calendar and emergency interlocks | Fixed-stake Options model; complete external statement history and CFD sizing are absent |
| Journal and migration | Signal, virtual position, broker and risk records remain separate | Startup migration preserves legacy files/rows; historical labels do not re-enable removed rules |
| Real accounts | Read-only connectivity where authorized | All real-money buys remain disabled |
| Packaging | Editable source with Windows/Unix launchers and verified offline dependency | Python 3.10+ required; execution is verified only on explicitly recorded platforms |

## Comparison-product research

The exact user-supplied reference is `https://play.google.com/store/apps/details?id=com.qexpress.tool`. The cloud proxy denied the listing request with HTTP 403, so its current title, developer, feature list, proprietary rules and claimed accuracy could not be verified. Public technical-methodology sources are recorded in [PUBLIC_RESEARCH.md](PUBLIC_RESEARCH.md). No proprietary strategy, code or performance claim is attributed to the reference app without evidence.

## Limits that remain

- No MT5/CFD order adapter, lot/tick/margin model, broker emergency-close operation or live activation path.
- No licensed automatic economic-calendar feed; manual truthful coverage is required when the risk policy applies.
- No calibrated AI forecast model, proven edge, automatic parameter optimizer or statistically validated accuracy improvement.
- No production remote authentication, independent security/legal approval, signed installer, external audit anchoring or universal broker entitlements.
- No claim that every strategy is suitable for every instrument, timeframe, market regime or jurisdiction.
