# Archived v4.3 release notes

These notes preserve the supplied ZIP documentation. They describe the archive before the safety improvements in this repository. In particular, manual live opt-in, cost-free paper trading, 1% paper risk, and win-rate promotion thresholds are historical descriptions. Use the current [README](../README.md), [operations guide](OPERATIONS.md), and [audit](APPLICATION_AUDIT.md) for this version.

---

# Update: v4.3 Deriv contract duration compatibility

The Deriv Broker tab now includes **Check supported expiries**. The backend uses the official `contracts_for` API to identify which barrier-free CALL/PUT contract durations the selected market advertises. It validates the exact direction and expiry before a quote, with no automatic substitution. Deriv can still decline a proposal due to market hours or other restrictions. Read `DERIV_DURATION_FIX.md` for troubleshooting, details, and upgrade steps.

# Previous v4.2 — Deriv Market Compatibility Fix

Seven-Strategy Auto Selector + Naked Forex + official Deriv Options integration. Includes prior v4.1 authentication diagnostics.

**Build date:** 28 October 2026
**Platform:** Windows 11 private localhost Python application (also runnable on macOS/Linux with Python).
**Delivery:** Entire editable source package, **not** a signed .exe or Android APK.
**Based on:** `Naked Forex: High-Probability Techniques for Trading without Indicators` by Alex Nekritin and Walter Peters (Wiley, 2012). This is an independently coded interpretation of educational concepts; it is not associated with the authors or publisher.

## Fast start on Windows

1. Extract the entire ZIP in a private folder (avoid Program Files or OneDrive sync directories, if possible).
2. Install Python **3.10–3.14** from https://www.python.org/downloads/ if not already installed. Select **Add Python to PATH** where offered.
3. Double-click `START_WINDOWS.bat`. It creates `.venv` and installs `websocket-client` (first run requires internet).
4. Visit `http://127.0.0.1:8765` if the dashboard does not open automatically.
5. Open **Naked Strategy PRO** in the left sidebar.
6. Begin with **Synthetic sample** and **Backtest all 7 strategies** to inspect the full ranking without any account. Sample rankings are research-only; no automatic execution is enabled.
7. For **genuine Deriv historical candles**, open **Deriv Broker**, connect your authorized **DEMO** account with a registered App ID and Personal Access Token, then return to the Naked Strategy tab and select **Actual Deriv history** and a broker market.
8. If you prefer your own OHLC data, choose **My local CSV** with `time,open,high,low,close` columns (100–10,000 rows; seconds since Unix epoch or ISO dates). Use a CSV with data already aggregated to the chosen chart timeframe.

To stop the application, close the startup terminal or press Ctrl+C. **Closing the browser tab alone does not necessarily stop the backend.** Strategy automation is not persisted as an active toggle across application restarts.

## NEW in v4 — Backtest all 7 strategies and automatically select a winner

In **Naked Strategy PRO**, click **Backtest all 7 strategies**. The app reads one history set and compares all seven price-action strategies under the same timeframe, payout and expiry assumptions. It ranks candidates on the **first 70%** of historical data and validates the top training candidate against the last **30%**. The leaderboard shows every strategy (including unsuccessful ones), counts, win rate, theoretical P&L and the train-only risk score. Export the complete comparison to JSON.

**Automatic adoption is deliberately gated.** The Deriv DEMO contract expiry must match the researched timeframe × holding bars, and its actual quote must meet the assumed payout before purchase.  The **Use best validated strategy** button starts the stored best candidate with your chosen Monitor/Paper/Deriv DEMO action *only* if stringent train/holdout criteria pass on **fresh Deriv broker history**. Synthetic and imported-CSV results are informative but cannot authorize broker auto-deployment. No eligible candidate means no auto start. No real-money automated trading is possible. There is no guaranteed 65% return or win rate. Consult [AUTO_SELECTOR_GUIDE.md](../AUTO_SELECTOR_GUIDE.md) for exact score, qualification rules, limits, and operating instructions.

## New Naked Forex Strategy workspace

Seven separate selectable algorithmic interpretations: **Kangaroo Tail**, **Big Shadow**, **Big Belt**, **Wammie**, **Moolah**, **Last Kiss**, **Trendy Kangaroo**. See [STRATEGY_GUIDE.md](../STRATEGY_GUIDE.md) for rules from the book, the programmatic approximations, and their differences. The authors' hand-selected support/resistance zones and discretionary pattern criteria are not exactly reproducible; **these are new quantified strategies, not verified replicas**.

Timeframe presets:

| Mode | Chart timeframe | Automated behavior |
|---|---|---|
| Scalping | 1 minute, 5 minutes | Signal monitoring, paper practice; short-expiry Deriv DEMO options orders permitted |
| Intraday | 15 minutes, 1 hour | Signal monitoring, paper practice; DEMO options orders permitted only for 15 minutes |
| Swing | 4 hours, daily | Real-market signal monitoring or automated **paper** positions, no broker buy |
| Long-term | Weekly, monthly | Real-market signal monitoring or automated **paper** positions, no broker buy |

Weekly and monthly candles are aggregated from broker daily candles, **not** native Deriv weekly/monthly endpoints. The program rejects incomplete candles. Availability/history length may prevent detecting any signals for a long period; monthly monitoring needs years of historical bars to initialize.

Choose between three distinct execution paths:

1. **Monitor only:** polls closed Deriv candles around every 25 seconds, records confirmed signals in `naked_signals.db`, places no broker orders.
2. **Automatic paper positions:** opens an **internal virtual** long/short position on a confirmed signal, using an extreme-of-pattern stop and fixed 2R target, risking 1% of a **separate $10,000 virtual equity ledger**. The monitor checks subsequent closed candles, settles when the stop/target is touched, and assumes stop-first whenever both are hit during one bar. This can run on any timeframe, including daily/weekly/monthly, but never controls money with Deriv. **Stops and targets are virtual, with no slippage, spread, financing, swap, or order-fill modeling.** They are not Deriv MT5 positions.
3. **Buy Deriv DEMO options:** only enabled with a connected Deriv Options account explicitly labelled **DEMO**, short chart timeframes 1m/5m/15m, supported broker symbol, a selected 1–15 minute broker contract expiry, individual stake $0.35–$5, and a confirmed candle. Buys use the same official `proposal` → `buy` implementation as v2 with portfolio validation and an order journal. **This is a short-duration Rise/Fall contract, not the original book's stop/target forex order.** A failure or ambiguous buy result stops further entries for manual investigation. The code cannot guarantee Deriv permits a given contract on a given symbol.

**ALL unattended live-account purchases are prohibited** in every mode. The separate v2-style broker panel retains its locked-by-default, manual one-trade-live capability, which should not be used until end-to-end DEMO tests are complete. To avoid surprises, the normal launcher always starts with live disabled.

## Research backtest: 65% is a target, not a promise

Backtest supports official Deriv historical candles (when connected), imported user CSV, or explicitly **synthetic demonstration** candles. For the selected pattern, the research model:

- Evaluates OHLC prices and support/resistance formed **only before the signal**.
- Requires a completed **following candle** to close beyond the pattern trigger. This is a quantification choice that differs from the book's pending stop orders.
- Assumes a trade at the **open of the next candle** following confirmation, with a user-selected theoretical 1–20-candle expiry.
- Simulates theoretical Rise/Fall payouts; winning trades earn `stake × assumed payout fraction` while losing trades cost the entire stake. A tie is conservatively counted as a loss. Trading positions are not overlapped.
- Splits observations chronologically: first 70% of time bars for in-sample and final 30% for holdout assessment. Uses constant, manually chosen strategy parameters—not parameter-fitting on the holdout period.
- Reports trade count, win rate, theoretical P&L, return on a $1,000 virtual baseline, max drawdown, and 95% Wilson lower bound on win rate. A **research threshold pass** requires at least 30 trades in **each** segment, holdout win rate meeting your target, positive holdout simulated P&L, Wilson lower bound above the assumed payout breakeven rate, and holdout drawdown at most 15%.

**Even when every check passes, historical results do not establish future profit or performance.** A 65% win rate is not a 65% profit or investment return. The assumed payout is **not an actual Deriv quote**. Real costs, bid/ask, price jumps, broker symbol constraints, execution delay, limited history, and market changes can completely alter results. This study is not a backtest of the paper-position 2R model, MT5 forex or long-duration CFD trading. Do not compare it to the actual Deriv broker journal as if it were executed P&L.

The report can be exported to JSON. Honest empty/insufficient-signal results remain **NOT VALIDATED**; the program does not make up wins or optimize settings until the target is reached.

## Original v2 capabilities retained

- Local synthetic simulator with six conventional indicators and a separate virtual account.
- Official Deriv Options PAT/OTP authentication, Deriv DEMO balances, symbols, 1-minute candles, broker proposals and broker demo buys.
- Deriv demo indicator robot (independent from Naked Forex robot); the app rejects simultaneous use of both broker-buying robots.
- Manual broker orders, live manual opt-in (requires explicit environment variable and extra arm/confirmation), local order journal, and conservative duplicate/uncertain-order controls.

### Deriv authorized setup

1. Go to https://developers.deriv.com and create a personal-use app registered for **PAT** authentication.
2. Generate a personal access token with the narrowest needed scope (trade scope for demo options). Do not share it or commit it to Git.
3. On the **Deriv Broker** page, type the official App ID and PAT, click **Find my Deriv accounts**, select the explicit **DEMO** account, and connect.
4. In **Naked Strategy PRO**, choose your broker symbol, strategy and timeframe, then select **Monitor**, **Paper positions** or, only on a suitable demo account, **DEMO options**.
5. Start with Monitor mode. Review historical testing and actual closed-bar signals, then optionally try virtual paper positions, and only after testing try DEMO broker purchases.

Credentials remain in application process memory, are cleared from the browser login controls after connecting and are never stored in the SQLite trade journals. The app accepts requests only on localhost with host/origin checks and should **never** be deployed to a public web server without a complete security redesign.

## What was actually tested

- Automated Python unit tests across the simulator, broker fake transports, signal patterns, no-future-data check, CSV/candle validation, backtest statistics, paper-loss-first handling, and blocked automatic live execution.
- Server HTTP endpoints and frontend loads locally. This environment **has not** authenticated to your account or sent a real broker DEMO order; the Deriv adapter's real account compatibility is **not verified end to end**.

Run locally:

```bash
python -m unittest discover -s tests -v
```


## v4.2 Deriv markets compatibility repair (recommended update)

The v4.1 connection workflow could return **"Deriv returned no available markets"** despite successfully finding accounts and opening the authenticated session. Deriv renamed the market symbol fields from `symbol` to `underlying_symbol` and `display_name` to `underlying_symbol_name`. The v4.2 broker adapter now parses those fields and retains legacy field support. **Refresh balance & markets** updates the actual symbol list on demand. If Deriv really returns zero markets, the account remains connected with trading disabled. See `DERIV_MARKETS_FIX.md` for details, safe upgrade steps, and checks. The existing App ID and PAT can be reused when valid; do not regenerate tokens simply to correct a parsing bug.

## Deriv HTTP 401 account discovery fix

If clicking **Find my Deriv accounts** displays HTTP 401, Deriv has rejected authentication. MIKEIZU v4.1 supplies more helpful diagnostics; it does not bypass Deriv authentication. Check that the App ID was created as a **new PAT-type application** on https://developers.deriv.com, not a legacy/OAuth app. Generate a fresh **Personal Access Token** in that dashboard with `trade` permission; paste it with the corresponding new App ID into the Deriv Broker screen. Do not use an account password, MT5 password, or OAuth client secret. Restart MIKEIZU after replacing the files. Never share a PAT or screenshot containing one. See `DERIV_401_FIX.md`.

## Installation troubleshooting

- For `python not found`, install a supported Python release and retry. For a specific interpreter, open a terminal in this folder and run `py -3.13 -m venv .venv` (substitute the installed version).
- For pip connection problems, run `.venv\\Scripts\\python.exe -m pip install -r requirements.txt` after checking internet.
- For Deriv 401/403, confirm the App ID is registered on `developers.deriv.com` for the token's auth type, that you chose the correct account and token scopes, and that the account is available for API trading.
- If no broker market appears, use the Broker page to refresh and confirm your account is truly connected.
- If there are no strategy trades, that is an acceptable research outcome: the filters intentionally require rare, confirmed price-action setups. Increase *legitimate historical data length*, not invented results. Trading monthly may require many years of candles.
- The app's automation needs the Python server running. Keeping a Windows machine from sleeping or restarting is your responsibility. Reconnect and restart strategies after shutdown; the journals survive.

## Developer map

- `naked_strategies.py`: deterministic patterns, causal support/resistance zone clustering, timeframe aggregation and research backtests.
- `strategy_selector.py`: compare all seven rules, risk-adjusted training-only score, single-candidate holdout verification and no-fallback deployment rule.
- `AUTO_SELECTOR_GUIDE.md`: detailed v4 selector methodology and safe workflow.
- `strategy_extension.py`: live-market polling, broker account-mode gating, persistent signal log, DEMO-only option execution, and paper-position orchestration.
- `paper_engine.py`: virtual position journal, 1% risk unit, stop/target event matching.
- `deriv_bridge.py`: official Deriv PAT/OTP and authenticated trading RPC.
- `deriv_server.py`: localhost request routing and monitor threads.
- `static/strategy_ui.js` and `static/index.html`: browser strategy selection and reporting.
- `tests/test_naked.py`: regression/safety tests.

Official API references:

- https://developers.deriv.com/docs/intro/api-overview/
- https://developers.deriv.com/docs/workflows/
- https://developers.deriv.com/docs/data/ticks-history/
- https://developers.deriv.com/docs/trading/buy/

**Important:** Trading options and leveraged foreign exchange is risky. No profits, returns, or win rates are guaranteed by this software, its backtests or the uploaded book.
