# MIKEIZU TradeLab PRO v4 — Auto Strategy Selector

## What it actually does

1. Load one immutable set of completed OHLC candles from the selected source (Deriv if connected; otherwise synthetic or your CSV). A Deriv fetch is made **once** for the entire seven-strategy comparison.
2. Run all seven deterministic price-action interpretations from `STRATEGY_GUIDE.md` against the identical history, chart timeframe, holding period, assumed fixed-expiry option payout, and stake. No broker order is submitted during research.
3. Use **only the first chronological 70% (training)** to rank candidates; prevent a trade from leaking across the 70/30 boundary.
4. Require at least **30 completed training trades**, positive simulated P&L, Wilson lower 95% win-rate bound above the assumed break-even win rate, and max historical training drawdown <= 15% for a candidate to be eligible.
5. Rank eligible strategies by `0.7 * (training Wilson lower bound - theoretical breakeven win rate) + 0.3 * (training expectancy as % of stake) - 0.35 * training maximum drawdown %`. This is a transparent **research heuristic**, not a learned AI model or investment algorithm.
6. Take the *highest-ranked training candidate* and assess it ONCE on the remaining 30% (chronological holdout). It must have at least **30 completed holdout trades**, achieve the configurable win-rate benchmark (default 65%), positive theoretical P&L, Wilson lower 95% bound greater than theoretical payout break-even, and holdout drawdown <= 15%.
7. **If the winner fails, select nothing**. Don't use the holdout set to fall back to the next strategy: that would allow test-result cherry-picking.
8. Show ALL seven outcomes in a ranked table with training and holdout figures for transparency. Export the full evaluation as JSON.
9. When the chosen candidate qualifies *and* research used recent authentic Deriv candles from the connected account, the **Use best validated strategy** button enables. One click starts that strategy with the specified action after an explicit user confirmation.

## Using the feature

- Start Windows with `START_WINDOWS.bat`, open **Naked Strategy PRO**, connect your **Deriv demo account** under **Deriv Broker**.
- Choose **Deriv history**, the symbol (for example, a Deriv symbol returned by the connection), trading profile and chart timeframe.
- For 1m/5m/15m short-duration models, enter a **theoretical** payout, stake and contract holding period in bars. These are research assumptions and may not match executable Deriv products.
- Press **Backtest all 7 strategies**. Inspect ranking, training/holdout trade counts, maximum drawdown and selection verdict. No data source alone guarantees sufficient observations.
- Choose automation action: **Monitor** (no orders), **Paper** (internal virtual positions), or **Deriv demo options** (1m/5m/15m only; requires broker demo mode). Press **Use best validated strategy** and review confirmation. This reuses the server-held winning strategy; the browser cannot spoof the chosen strategy or symbol.
- The usual **Stop** button prevents new signals/orders; existing Deriv demo option contracts continue until expiry. The app must remain running; active strategies do not restart after a reboot.

## Why the selector may find no winner

- The Naked Forex patterns are intentionally selective. Even 2,600 bars of authentic history may yield fewer than 30 signals on the training or holdout portion.
- Strict out-of-sample checks may reject strategies with apparently excellent training returns. This is the correct result, not a software defect.
- Weekly and monthly candles are aggregated locally from Deriv **daily** candles. Monthly tests require at least 100 completed monthly bars (more than eight years); Deriv's availability of history is not guaranteed. You can evaluate sufficiently long timestamped CSV datasets, but they **cannot unlock broker auto-deployment**.
- If no candidate qualifies, do not reduce the minimum sample size or repeatedly tweak the same held-out data just to obtain 65%. Collect additional unseen data and forward-test.

## Critical distinction: "best outcome" does not mean guaranteed future profit

- The 65% setting is a **win rate**, not 65% return on invested money. Win rate alone is inadequate without the amount earned on wins, lost on losses, fees and expected drawdowns.
- This historical score compares hypothetical **fixed-expiry digital-option outcomes**. Its payout parameter is a manual assumption. It does not reproduce Deriv quote availability, actual buys and fills, early selling, spreads, overnight financing, or stop/target forex strategies.
- Automated paper positions use a separate **2R virtual stop/target** model. A backtest ranking for fixed-expiry contracts **does not validate** that paper-position model. Do not treat weekly/monthly paper profits as actual Deriv positions.
- Re-running research frequently and accepting a preferred result on the *same holdout period* contaminates validation; even a passing result needs independent forward-demo evidence.
- Multiple candidates mean multiple-comparison bias; the 70/30 split reduces but does not eliminate it.
- The automated strategy selector **never starts live real-money trades**. Deriv broker order behavior must be checked end-to-end with a user-authorized demo account.

## Engineering and security notes

- `strategy_selector.py`: training-only ranking and one-candidate holdout evaluation.
- `strategy_extension.py`: fetches genuine Deriv candles, stores the winning candidate only in process memory, and starts it through `activate_best` only if the originating broker account and mode match, historical candles were current when scanned, and the result is under one hour old.
- `deriv_server.py`: adds POST `/api/strategy/scan-all` and POST `/api/strategy/start-best`; both subject to localhost Host/Origin checks and JSON payload limits.
- Strategy switches while a monitor is already running are refused; stop first. Existing manual strategy controls remain available, but they are not represented as automatically validated choices.
- Current code's automated Deriv option execution is **demo-only**. Credentials remain in RAM and are not included in JSON backtest reports.
- Windows remains dependent on Python 3.10–3.14 and the first-run `websocket-client` installation; not a compiled installer.

**Research is not financial advice, and no win rate or financial return is promised.**

### Demo-contract parity safeguards

For **auto-selected Deriv DEMO options**, the chosen contract duration must match the bars assumed in research (e.g., a 5-minute chart × 3 bars = **15-minute** contract). Unsupported horizons cannot auto-trade. Before every automated purchase, the app checks that the **actual Deriv quotation's net payout ratio** is at least the assumed research payout; otherwise automation stops without buying. This is only a basic parity test—signal-to-fill delay, actual market behavior and other execution mismatches remain unmodeled. Monitor/Paper mode does not place contracts and does not require this duration match.
