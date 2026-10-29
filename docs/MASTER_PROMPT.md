# User-supplied development specification

The following is the user-provided improvement brief. It is retained for requirements traceability. It describes desired capabilities, not evidence that they have been implemented or verified. See [APPLICATION_AUDIT.md](APPLICATION_AUDIT.md) and [ROADMAP.md](ROADMAP.md) for current status.

---

MASTER AI DEVELOPMENT, RISK MANAGEMENT & TRADING AUTOMATION PROMPT
Project: MIKEIZU TradeLab PRO — Deriv Edition
Objective: Transform my existing forex trading application into a professional, intelligent, transparent, risk-controlled, thoroughly tested, and reliable automated trading platform.
1. YOUR ROLE
Act as an integrated team of senior professionals with extensive experience in:
- Quantitative trading and algorithm development
- Forex, CFDs, derivatives, and price-action trading
- Trading risk management and capital preservation
- Python, backend development, APIs, and WebSockets
- Broker integrations, especially Deriv and Deriv MT5
- Machine learning, financial data science, and statistical validation
- High-reliability financial software engineering
- Cybersecurity, authentication, and secure credential management
- Professional UI/UX design
- Trading compliance, investor protection, and software quality assurance
Your responsibility is not simply to recommend improvements. You must thoroughly analyze my existing application and, when the source code is provided, implement, integrate, test, and document the required improvements.

Primary engineering philosophy: Trust, Control, Proof, Adaptability, and Reliability.

The system should pursue positive risk-adjusted returns while prioritizing capital protection, honest performance reporting, and reliable execution.

Never guarantee profits or assume that an attractive backtest proves future profitability.
2. UNDERSTAND MY EXISTING APPLICATION
My application is called MIKEIZU TradeLab PRO, primarily developed for private use on Windows and designed around Deriv broker integration.

Its previously described capabilities include:
- Deriv account connectivity
- Seven Naked Forex price-action strategies
- Scalping, intraday, swing, and longer-term strategy monitoring
- Automatic trade-signal generation
- Simulated and demo trading
- Historical strategy backtesting
- Trading journals and performance reports
- A configurable 65% win-rate research benchmark
Existing development notes describe automatic Deriv demo purchases for supported short-duration contracts, while longer-term forex/CFD execution through MT5 has not yet been established.

Do not assume that described features are fully implemented or working. Inspect the actual source code and verify each capability.

Preserve all existing working functionality. Do not replace the application with a simplified prototype, or claim that integration is successful without testing it.

Investigate previously encountered integration problems, including:
- HTTP 401 authentication errors
- Deriv account detected but connection unsuccessful
- "Deriv returned no available markets"
- "Trading is not offered for this duration"
- MT5 authorization failures
Identify the actual cause from logs, API responses, configuration, and authorized broker documentation. Do not bypass broker restrictions or use unsupported endpoints.

Produce a capability audit separating implemented, verified, partially working, broken, missing, and unsupported features.
3. NON-NEGOTIABLE TRADING PRINCIPLES
The application must:
1. Prioritize preserving trading capital over maximizing trade frequency.
2. Never use hidden martingale, unlimited grid recovery, or uncontrolled position averaging.
3. Never trade merely to recover previous losses.
4. Avoid trading when market conditions are unsuitable.
5. Never fabricate trading signals, prices, available instruments, or account results.
6. Never execute live trades without explicit user authorization.
7. Never promote a strategy solely because of its historical win rate.
8. Always account for fees, slippage, spreads, and execution uncertainty.
9. Stop new trading when essential risk controls or broker information become unavailable.
10. Maintain independently auditable trade decisions and execution records.
The application must distinguish between research forecasts, trading signals, submitted orders, accepted orders, and confirmed fills.
4. COMPLETE TRADING STRATEGY AUTOMATION ENGINE
Develop a professional strategy engine supporting these seven Naked Forex strategies:
Strategy	Required automation
The Last Kiss	Detect breakout, retest, support/resistance alignment, and confirmation
The Big Shadow	Detect qualifying two-candle reversal patterns at important price zones
Wammies	Identify double-bottom structures, including the higher second low
Moolahs	Identify double-top structures, including the lower second high
Kangaroo Tails	Detect long-wick rejection and confluence with significant price zones
The Big Belt	Detect strong directional candles with significant zone context
The Trendy Kangaroo	Identify trend continuation after temporary consolidation


Translate discretionary trading patterns into transparent, measurable rules.

Allow parameters for candle structure, price tolerance, support/resistance identification, confirmation, invalidation, and trade management.

Clearly distinguish these programmed interpretations from the original discretionary methods.

Each strategy must support:
- Signal-only monitoring
- Historical backtesting
- Walk-forward evaluation
- Paper trading
- Authorized demo execution
- Controlled live execution where technically and legally supported
Trading horizons
Support independently configurable operating modes:

Scalping: 1-minute and 5-minute charts
Intraday: 15-minute and 1-hour charts
Swing trading: 4-hour and daily charts
Position trading: Weekly and monthly charts

Do not assume that every instrument or broker contract supports every timeframe, contract duration, or holding period.

Keep options-contract automation separate from forex/CFD position execution, with appropriate risk and cost models for each.
5. INTELLIGENT MARKET-REGIME DETECTION
Develop a market-intelligence module that continuously evaluates conditions.

Classify markets into:
- Trending upward
- Trending downward
- Sideways or ranging
- High volatility
- Low volatility
- News-driven or abnormal
- Uncertain or unsuitable for trading
Use appropriate data and indicators, potentially including:
- Price structure, swing highs, and swing lows
- ADX and directional movement
- Moving-average slopes
- ATR and realized volatility
- Choppiness or range measurements
- Spread and liquidity proxies
- Multi-timeframe alignment
- Scheduled high-impact economic news
Use configurable thresholds and validate them historically. Never present classifications as certain.

For each regime, establish which strategies are eligible and which should be suspended.

For example, a trend-continuation strategy should not operate blindly in an established ranging market.

When market conditions deteriorate, the system should reduce permitted risk or halt new entries, not automatically compensate by taking larger trades.

Display the current regime and reasons for its classification.
6. PROFESSIONAL RISK-MANAGEMENT ENGINE
Build an independent risk engine that must approve every order before it reaches the broker.

Recommended conservative starting presets for research and demo testing:
Risk control	Initial default
Risk per trade	0.5% of eligible account equity
Maximum daily loss	2%
Maximum weekly loss	5%
Maximum strategy/account drawdown stop	10%
Maximum simultaneous positions	3
Martingale	Disabled
Unlimited grid recovery	Prohibited
Automatic revenge trading	Prohibited
Missing risk information	Block new orders
Emergency stop	Always accessible


These values are proposed defaults, not universally safe levels. They must remain configurable within enforced limits and be tested against specific instruments and account characteristics.

For stop-loss-based instruments, calculate position size using stop distance, tick value, execution costs, and broker constraints.

For fixed-stake contracts, calculate maximum at-risk stake and payout-dependent expectancy separately.

Implement:
- Hard daily and weekly loss limits
- Account equity protection
- Maximum exposure by asset and correlated asset group
- Leverage and margin checks
- Maximum spread and slippage tolerances
- Cooldowns after consecutive losses
- Maximum new trades per session
- Maximum permissible order size
- Stop-loss and take-profit validation where applicable
- Exposure reconciliation with broker positions
- One-click emergency kill switch
The kill switch must halt new trading immediately and separately offer an authorized emergency close-position action when supported by the broker.

A failed close-position request must be reported clearly, never displayed as a completed close.

Risk limits must remain effective after application restarts, API reconnects, or strategy switching.
7. REALISTIC BACKTESTING AND STRATEGY VALIDATION
Develop an event-driven backtesting system that accurately reflects the trading process.

Account for:
- Historical bid/ask spreads where available
- Spread widening
- Commissions and fees
- Swap and financing charges
- Slippage
- Order latency
- Broker execution restrictions
- Partial fills and rejected orders
- Liquidity limitations
- Volatility spikes and price gaps
- Missing data and market closures
- Real contract payouts for relevant derivative products
Prevent:
- Look-ahead bias
- Data leakage
- Repainting indicators
- Same-candle execution assumptions where invalid
- In-sample over-optimization
- Repeated selection based on the same held-out dataset
Use chronological training, validation, and untouched test periods, as well as rolling walk-forward validation.

Where appropriate, employ purged or embargoed splits to prevent leakage between overlapping trade labels.

Evaluate parameter stability, multiple-testing effects, and robustness under worsening execution conditions.
Mandatory reporting metrics
Display:
- Total net profit or loss
- Percentage return
- Win rate
- Loss rate
- Average winning trade
- Average losing trade
- Profit factor
- Expected value per trade
- Maximum drawdown
- Recovery factor
- Risk-adjusted return
- Exposure and turnover
- Trading costs
- Number of trades
- Consecutive winning and losing streaks
- Performance by instrument, regime, and timeframe
Show equity curves and drawdown charts.

Every backtest must disclose its dataset, timeframe, strategy version, configuration, assumptions, and test-period boundaries.

Simulated results must never be represented as live achievements.
8. AI STRATEGY RESEARCH AND SELECTION ENGINE
Develop an intelligence module that compares eligible strategies and recommends suitable candidates based on robust evidence.

The engine must not simply select the strategy with the highest historical profit or win rate.

Evaluate strategies across:
1. Out-of-sample profitability
2. Drawdown
3. Expected value after costs
4. Profit factor
5. Risk-adjusted returns
6. Statistical uncertainty
7. Sample size and market coverage
8. Parameter stability
9. Market-regime compatibility
10. Demo forward-testing performance
Use an explicit, configurable multi-criteria ranking model.

Introduce confidence intervals and uncertainty estimates.

If performance evidence is insufficient, return NO VALIDATED STRATEGY instead of inventing a winning recommendation.
The 65% research benchmark
I am interested in finding strategies capable of achieving a 65% win rate where sustainably possible.

However:
- A 65% win rate is not a 65% return.
- A high win rate can coexist with negative expected profit.
- The benchmark is a research target, not an execution requirement or guaranteed outcome.
- Strategies with lower win rates may be better if their risk-adjusted expectancy is stronger.
Do not artificially tune historical parameters merely to meet 65%.

Prefer validated positive expectancy and controlled drawdowns over attractive but unreliable win-rate statistics.

AI may assist with classification, comparison, forecasting, and explanations, but no language model should bypass deterministic execution and risk checks.
9. ECONOMIC NEWS AND FUNDAMENTAL ANALYSIS
Build a news-aware trading-control module.

Include major scheduled releases such as:
- Non-Farm Payrolls
- Consumer Price Index
- FOMC decisions and minutes
- Central-bank rate decisions
- GDP
- Employment releases
- Other relevant high-impact events
Use reputable, appropriately licensed data sources.

Develop configurable pre-event and post-event trading restrictions.

Evaluate:
- Event relevance to the instrument
- Time until release
- Observed spread widening
- Volatility spikes
- Price gaps
- Data freshness and reliability
Allow users to see why trading has been paused.

Do not assume that all price movements following news are predictable.

If the economic calendar becomes unavailable or outdated, apply a documented fail-safe policy instead of silently assuming that no event risk exists.
10. RELIABLE DERIV AND MT5 CONNECTIVITY
Build separate adapters for supported broker products.

For each supported instrument and contract type, verify:
- Account authentication and permissions
- Demo or live account classification
- Available symbols
- Contract specifications
- Trading hours
- Minimum and maximum stake or volume
- Supported duration units and limits
- Precision and order increments
- Margin and leverage requirements
- Required order fields
- Execution permissions
Fetch relevant capabilities from official broker interfaces rather than hardcoding universal assumptions.

Handle HTTP and WebSocket failures, authentication expiration, reconnects, rate limits, unsupported durations, and changes in market availability.

Use:
- Connection state machines
- Exponential-backoff reconnection
- Heartbeat monitoring
- Request identifiers
- Order idempotency safeguards
- Broker transaction reconciliation
- Duplicate-order prevention
- Persistent order state
Do not blindly resend a purchase request after a timeout without determining whether the original order succeeded.

On reconnection, reconcile balances, orders, positions, and contract status before permitting further automation.

Investigate and correct previously reported Deriv and MT5 connection failures using authentic test evidence.

Never bypass broker permissions, regional restrictions, account entitlements, or documented API limitations.
11. EXPLAINABLE AI AND TRADE TRANSPARENCY
For every proposed trade, show a clear explanation in plain English.

Example:

Instrument: EUR/USD
Timeframe: 15 minutes
Strategy: Last Kiss
Market regime: Uptrend
Signal: Buy candidate
Reason: Breakout and confirmed retest of a validated resistance zone
Invalidation: Price moving below the defined setup boundary
Estimated risk: Based on configured account limits
Execution status: Awaiting validation

The example must not be presented as an actual market signal without current verified data.

Display supporting price evidence, the active rule set, risk checks, expected costs, and any reasons an order was blocked.

Use calibrated model probabilities only where there is sufficient evidence for calibration.

Do not generate arbitrary AI confidence percentages.

Every explanation must be linked to the strategy version and underlying data that produced the signal.
12. PROFESSIONAL APPLICATION INTERFACE
Modernize the app with a clean, responsive trading terminal.

Develop the following sections:

Dashboard: Account overview, equity, open positions, realized/unrealized results, risk utilization, and broker connection status.

Trading Terminal: Charts, instruments, signals, order review, and execution controls.

Strategy Automation: Enable, disable, configure, and schedule individual strategies.

AI Strategy Lab: Compare validated strategies and research findings.

Backtesting Studio: Historical tests, assumptions, results, and drawdown analysis.

Market Intelligence: Market-regime conditions, volatility, spreads, and economic calendar.

Risk Control Center: All hard limits, account safeguards, emergency controls, and trading permissions.

Trade Journal: Every signal, order, fill, rejection, fee, and realized outcome.

System Health: Broker connectivity, process status, reconnection events, and incident history.

Settings: Accounts, security, notifications, configurations, data sources, and preferences.

Provide beginner and advanced views.

Beginner mode should offer guided onboarding, explanations, safe demo defaults, and minimal configuration complexity.

Advanced mode should expose research settings, strategy parameters, validation reports, and execution diagnostics without permitting the bypass of hard safety controls.

Use accessible color choices, readable charts, clear error messages, and explicit account-mode indicators.
13. TRADING MODES AND CONTROLLED ACTIVATION
Provide the following distinct operating modes:

Mode A — Research: Historical analysis with no broker orders.

Mode B — Signal Monitoring: Automatic alerts without executing trades.

Mode C — Paper Trading: Virtual positions with realistic execution simulation.

Mode D — Broker Demo: Automatic orders on a properly authorized demo account.

Mode E — Controlled Live: Real-money execution, available only after explicit activation, verified integration, and satisfactory validation.

Live trading must remain disabled by default.

To activate live mode, require:
- Verified account identity and mode
- Explicit user confirmation
- Risk-limit setup
- Broker capability verification
- Appropriate jurisdictional checks
- A clearly displayed maximum exposure
- An emergency shutdown procedure
Do not automatically promote a strategy to live trading merely because it passed a backtest.
14. INFRASTRUCTURE, CYBERSECURITY, AND RELIABILITY
Use a modular and testable architecture with independently defined responsibilities for:
- Market data ingestion
- Historical data storage
- Strategy evaluation
- Regime detection
- Backtesting
- Risk management
- Order execution
- Broker synchronization
- Performance analytics
- User interface
- Monitoring and audit records
Use secure credential storage. For Windows, consider OS-managed credential protection.

Do not store passwords, access tokens, or broker secrets in plaintext source files or logs.

Implement:
- Authentication and authorization
- Least-privilege API access
- Encrypted transport
- Database migrations
- Crash-safe state recovery
- Automatic audit logs
- Data integrity checks
- Secure application updates
- Configuration validation
- Graceful shutdown
- Monitoring alerts
- Tested restore and recovery processes
Where remote hosting or VPS execution is proposed, explain the additional infrastructure, security requirements, and actual costs.

Do not describe the system as fully autonomous or fault-tolerant unless these behaviors have been tested.
15. TRADE JOURNAL AND VERIFIABLE PERFORMANCE
Every trading event should have a durable record, including:
- Trade and order identifiers
- Broker account mode
- Instrument and contract type
- Strategy name and version
- Signal timestamp
- Market-regime classification
- Entry and exit information
- Stop-loss or maximum stake risk
- Position size
- Decision rationale
- Risk-check results
- Expected and actual transaction costs
- Execution timestamps
- Broker responses
- Final profit or loss
- Reconciliation status
Maintain separate performance histories for:
- Backtesting
- Paper trading
- Broker demo trading
- Verified live trading
Provide daily, weekly, and monthly summaries.

Include losing trades, fees, failed orders, maximum drawdowns, and trading interruptions.

Never combine simulated profits with real trading results.

Provide exportable reports and tamper-evident audit records where practical.
16. QUALITY ASSURANCE AND ACCEPTANCE TESTING
Create automated unit, integration, regression, and fault-injection tests.

At minimum test:
1. Invalid and expired broker credentials
2. Account switching between demo and live
3. Unsupported instruments and durations
4. Broker disconnection during open trades
5. Duplicate order responses and timeouts
6. API rate limiting
7. Abnormal spread and price gaps
8. Maximum daily and weekly loss breaches
9. Position-size and margin limit violations
10. Strategy parameter changes
11. Missing market data
12. Economic-calendar outages
13. Application restarts with active positions
14. Emergency trading shutdown
15. Historical data leakage
16. Out-of-sample performance calculations
17. Account-position reconciliation
18. Failed or partial broker order execution
Tests should include deterministic mocks and, where authorized, real demo-broker verification.

Record which tests were actually executed, which passed, and which remain blocked.

Never claim successful live-broker verification based only on mocked responses.
17. STRATEGY PROMOTION AND PERFORMANCE GATES
Develop an evidence-based strategy validation process.

A strategy should move through:

Research → Historical Validation → Out-of-Sample Testing → Walk-Forward Testing → Demo Forward Testing → Optional Controlled Live Approval

Create configurable promotion requirements for:
- Minimum independent trade sample
- Minimum observation period
- Positive net expectancy after costs
- Acceptable drawdown
- Parameter stability
- Stable execution performance
- No unresolved critical system errors
Use reasonable initial sample and observation requirements, but explain their statistical limitations and adapt them to trading frequency and instrument characteristics.

A 65% win rate alone must never be sufficient for promotion.

If the strategy stops meeting its conditions in demo or live use, disable new entries or return it to research status.

Do not silently re-optimize or replace a live strategy without preserving an auditable version history.
18. COMPLIANCE, ETHICAL DESIGN, AND USER PROTECTION
Do not include:
- Guaranteed-return statements
- Fake performance histories
- Claims of risk-free trading
- Hidden martingale or unlimited averaging
- Automatic stake increases after losses
- Unauthorized execution methods
- Hidden trading costs
- Inaccessible emergency controls
- Artificial confidence statistics
- Pressure to deposit more funds after losses
- Automatic live-trading activation
- Withdrawal restrictions invented by the application
Clearly disclose leverage, loss risks, broker constraints, data limitations, and the difference between simulations and live results.

Identify applicable regulatory considerations before enabling real-money execution. Do not assume that access to a broker API establishes legal permission for every product or jurisdiction.
19. IMPLEMENTATION ROADMAP
Divide all improvements into seven implementation phases.

Phase 1 — Safety and Risk Controls
Implement the independent risk engine, position limits, emergency shutdown, account-mode isolation, and basic audit logging.

Phase 2 — Realistic Backtesting
Improve the historical-data pipeline, transaction-cost modeling, walk-forward validation, and performance reporting.

Phase 3 — Market-Regime Adaptation
Implement deterministic classification and evidence-based strategy eligibility.

Phase 4 — Explainable Intelligence
Develop transparent trade rationales, strategy research comparisons, uncertainty estimates, and performance-aware signal evaluation.

Phase 5 — Professional UX
Improve dashboard functionality, risk visualization, strategy controls, onboarding, and documentation.

Phase 6 — Infrastructure and Broker Reliability
Implement secure connectivity, reconciliation, resilience testing, recovery, monitoring, and operational safeguards.

Phase 7 — Compliance and Production Readiness
Complete user protection, security review, documentation, authorized demo validation, and controlled live-readiness assessment.

For each phase, supply dependencies, technical tasks, files/modules affected, acceptance criteria, tests, and unresolved risks.

Prioritize Critical and High-risk issues before cosmetic changes.
20. REQUIRED ENGINEERING OUTPUT
After analyzing the actual application, deliver:

A. Current Application Audit
A detailed feature and defect report with supporting evidence from the supplied source code and tests.

B. Gap Analysis
For each weakness, provide:
1. Existing implementation or confirmed absence
2. Real-world risk
3. Specific improvement
4. Data, rules, models, and indicators required
5. User-visible feature
6. Protective controls
7. Validation method
8. Priority level
C. Target System Architecture
A clear description and diagram of modules, data flows, databases, APIs, and execution boundaries.

D. Improvement Roadmap
An implementation plan, ordered by dependencies and risk.

E. Implementation
When source code is available, implement the improvements directly in the existing project rather than merely supplying hypothetical code fragments.

Preserve compatible interfaces and existing tested features. Document breaking changes.

F. Database and API Changes
Provide necessary schemas, migration scripts, API contracts, and configuration structures.

G. Test Suite
Create runnable automated tests and report actual outcomes.

H. Trading Validation
Provide historical, out-of-sample, and demo-testing procedures with reproducible performance reports.

I. Deployment Package
Provide complete source files, dependency declarations, environment examples, configuration instructions, startup scripts, and Windows installation guidance.

J. Operational Documentation
Explain how to connect Deriv, resolve common connection errors, run backtests, activate demo automation, inspect risk limits, stop trading, and troubleshoot failures.

K. Remaining Limitations
Distinguish fully implemented capabilities from unverified, partially implemented, unavailable, and unsupported capabilities.
21. REQUIRED WORKING METHOD
Follow this order:

Step 1: Inspect the source code, configurations, dependencies, and available documentation.

Step 2: Build an evidence-based audit of the existing system.

Step 3: Identify dangerous defects and integration failures.

Step 4: Implement and test critical safety fixes.

Step 5: Upgrade broker connectivity and the execution-state system.

Step 6: Improve the strategy engine and historical validation.

Step 7: Add regime-aware strategy selection and explainable decisions.

Step 8: Upgrade the user interface and reporting.

Step 9: Complete integration tests, regression tests, and broker-demo testing where credentials and access are available.

Step 10: Prepare the final deployment package and a factual validation report.

If actual source code, account access, market data, or broker verification is missing, identify the dependency explicitly. Do not fabricate implementation results, performance metrics, or test successes.
FINAL OBJECTIVE
Build MIKEIZU TradeLab PRO into a dependable, professional, evidence-driven trading research and automation platform.

I want an application that can identify market opportunities, research and evaluate strategies, explain potential trades, manage risk, automate authorized demo execution, and eventually support tightly controlled real-money execution.

The system should be intelligent enough to avoid unnecessary trading when evidence is weak and disciplined enough to protect capital when conditions deteriorate.

Measure success through software reliability, transparent evidence, risk-adjusted performance, and reproducible validation—not marketing claims or guaranteed profits.

Do not stop at recommendations when implementation is possible. Deliver working, tested improvements and clearly report every remaining limitation.