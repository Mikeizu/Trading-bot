# Current control and integration audit

**313 Python tests passed** (40.389 seconds; no failures, errors or skips). **24 offline and 20 mocked broker browser scenarios passed**, with zero JavaScript exceptions. **160 DOM controls have an explicit outcome; none remain unreviewed in this inventory.** These results belong to the current technical strategy release, not the removed workspace.

The 31 disconnected-run controls that require a broker session map to connected fixture evidence. The broker fixture uses fictional prices, credentials and purchases through real local handlers; it sent zero external orders. Protective refusals, unsupported features and reviewed links are not counted as successful executions.

| Outcome | Controls |
|---|---:|
| local verified | 104 |
| local and mocked verified | 21 |
| mocked integration verified | 31 |
| protective gate verified only | 1 |
| external link reviewed only | 1 |
| unsupported disabled | 2 |

The new library tests cover 24 rules, every strategy in both directions, all exposed parameter bounds, causal indicator histories, catalogue search/family filtering, eight chart timeframes, custom-parameter provenance, costs, exports, delayed-result invalidation, risk/calendar controls, emergency stop, account isolation and recovery.

Source reports, source hashes, callable inventory, missing statement lines and per-control evidence are retained in [control_audit.json](control_audit.json). Real Deriv access and the exact Qumatix Play listing remain unverified because the cloud proxy denied those destinations. Windows execution and future profitability/accuracy are not established.

## Control matrix

| Control | Page | Outcome | Evidence |
|---|---|---|---|
| `a:#main-content:Skip to main content` | global | local verified | Keyboard skip link |
| `a:#overview:M✦MIKEIZU TRADELAB PRO` | global | local verified | Quick navigation controls and brand |
| `nav:overview` | global | local verified | All navigation buttons, deep links and reload persistence |
| `nav:strategies` | global | local verified | All navigation buttons, deep links and reload persistence |
| `nav:deriv` | global | local verified | All navigation buttons, deep links and reload persistence |
| `nav:robot` | global | local verified | All navigation buttons, deep links and reload persistence |
| `nav:backtest` | global | local verified | All navigation buttons, deep links and reload persistence |
| `nav:history` | global | local verified | All navigation buttons, deep links and reload persistence |
| `nav:risk` | global | local verified | All navigation buttons, deep links and reload persistence |
| `nav:settings` | global | local verified | All navigation buttons, deep links and reload persistence |
| `#view-toggle` | global | local verified | Beginner and advanced views persist; disclosures open |
| `#global-kill` | global | local and mocked verified | Global emergency stop, reload, bad phrase, explicit resume; Money formatting and every mobile page retain stop control; Connected emergency stop persists and explicit resume restarts no robot |
| `#refresh-overview` | page-overview | local verified | Refresh, manual candle advance and every built-in watchlist market |
| `#chart-next` | page-overview | local verified | Refresh, manual candle advance and every built-in watchlist market |
| `#overview-start` | page-overview | local verified | Overview robot toggle starts and stops |
| `go:robot` | page-overview | local verified | Quick navigation controls and brand |
| `go:settings` | page-overview | local verified | Quick navigation controls and brand |
| `market:EUR/USD` | page-overview | local verified | Refresh, manual candle advance and every built-in watchlist market |
| `market:GBP/USD` | page-overview | local verified | Refresh, manual candle advance and every built-in watchlist market |
| `market:XAU/USD` | page-overview | local verified | Refresh, manual candle advance and every built-in watchlist market |
| `market:BTC/USD` | page-overview | local verified | Refresh, manual candle advance and every built-in watchlist market |
| `go:history` | page-overview | local verified | Quick navigation controls and brand |
| `#lab-profile` | page-strategies | local and mocked verified | All catalog indicator backtests and all eight timeframes; Every trading horizon starts in monitor mode with broker fixture capability |
| `#lab-family` | page-strategies | local verified | Strategy family/search filters, every parameter control and default restoration |
| `#lab-search` | page-strategies | local verified | Strategy family/search filters, every parameter control and default restoration |
| `#lab-strategy` | page-strategies | local and mocked verified | All catalog indicator backtests and all eight timeframes; Catalog indicator strategies can each start and stop monitor mode |
| `summary::Strategy parameters and rule set` | page-strategies | local verified | Execution-cost disclosure toggled; Research assumptions/provenance disclosures inspected |
| `#lab-param-rsi_period` | page-strategies | local verified | Catalog bounds and defaults tested: RSI; Catalog bounds and defaults tested: RSI_TREND; Catalog bounds and defaults tested: STOCH_RSI; Catalog bounds and defaults tested: CONSENSUS; Strategy family/search filters, every parameter control and default restoration |
| `#lab-param-oversold` | page-strategies | local verified | Catalog bounds and defaults tested: RSI; Catalog bounds and defaults tested: STOCHASTIC; Catalog bounds and defaults tested: STOCH_RSI; Catalog bounds and defaults tested: WILLIAMS_R; Strategy family/search filters, every parameter control and default restoration |
| `#lab-param-overbought` | page-strategies | local verified | Catalog bounds and defaults tested: RSI; Catalog bounds and defaults tested: STOCHASTIC; Catalog bounds and defaults tested: STOCH_RSI; Catalog bounds and defaults tested: WILLIAMS_R; Strategy family/search filters, every parameter control and default restoration |
| `#lab-reset-parameters` | page-strategies | local verified | Strategy family/search filters, every parameter control and default restoration |
| `#lab-timeframe` | page-strategies | local and mocked verified | All catalog indicator backtests and all eight timeframes; Every trading horizon starts in monitor mode with broker fixture capability |
| `#lab-source` | page-strategies | local verified | All catalog indicator backtests and all eight timeframes; Research CSV validation, import, and local-source backtest |
| `#lab-csv-input` | page-strategies | local verified | Research CSV validation, import, and local-source backtest |
| `#lab-symbol` | page-strategies | mocked integration verified | Catalog indicator strategies can each start and stop monitor mode |
| `#lab-payout` | page-strategies | local verified | All catalog indicator backtests and all eight timeframes |
| `#lab-target` | page-strategies | local verified | All catalog indicator backtests and all eight timeframes |
| `#lab-stake` | page-strategies | local and mocked verified | All catalog indicator backtests and all eight timeframes; Paper/demo action and expiry controls configure separately from real execution |
| `#lab-expiry-bars` | page-strategies | local verified | All catalog indicator backtests and all eight timeframes |
| `#lab-regime-filter` | page-strategies | local verified | Regime filter reaches the research model and delayed input changes discard stale results |
| `summary::Execution-cost assumptions` | page-strategies | local verified | Execution-cost disclosure toggled; Research assumptions/provenance disclosures inspected |
| `#research-commission` | page-strategies | local verified | Research cost inputs, invalid backend settings, JSON export |
| `#research-spread` | page-strategies | local verified | Research cost inputs, invalid backend settings, JSON export |
| `#research-slippage` | page-strategies | local verified | Research cost inputs, invalid backend settings, JSON export |
| `#lab-backtest` | page-strategies | local verified | All catalog indicator backtests and all eight timeframes |
| `#lab-action` | page-strategies | local and mocked verified | Disconnected strategy activation rejects and no demo-mode option; Paper/demo action and expiry controls configure separately from real execution |
| `#lab-expiry-minutes` | page-strategies | mocked integration verified | Paper/demo action and expiry controls configure separately from real execution |
| `#lab-start` | page-strategies | local and mocked verified | Disconnected strategy activation rejects and no demo-mode option; Catalog indicator strategies can each start and stop monitor mode |
| `#lab-stop` | page-strategies | mocked integration verified | Catalog indicator strategies can each start and stop monitor mode |
| `summary::Latest signal and decision evidence` | page-strategies | local verified | Execution-cost disclosure toggled; Research assumptions/provenance disclosures inspected |
| `#lab-scan-all` | page-strategies | local and mocked verified | Indicator-library comparison, export, and insufficient-evidence disabled start; Broker-data research comparison refuses unsupported strategy promotion |
| `#lab-export-all` | page-strategies | local and mocked verified | valid json download; Indicator-library comparison, export, and insufficient-evidence disabled start; Broker-data research comparison refuses unsupported strategy promotion |
| `#lab-start-best` | page-strategies | protective gate verified only | Indicator-library comparison, export, and insufficient-evidence disabled start; No validated fixture strategy means activation stays disabled; no forged qualification or claimed successful deployment. |
| `#lab-report-export` | page-strategies | local verified | valid json download; Research cost inputs, invalid backend settings, JSON export |
| `summary::Dataset, configuration and assumptions` | page-strategies | local verified | Research assumptions/provenance disclosures inspected |
| `#deriv-refresh` | page-deriv | local and mocked verified | Disconnected broker controls remain safe; Purchase timeout durably blocks retry and survives browser/account reconnect |
| `#deriv-auth-form` | page-deriv | mocked integration verified | Demo account discovery/connect clears browser credentials |
| `#deriv-app-id` | page-deriv | mocked integration verified | Invalid broker authentication gives actionable error without a session |
| `#deriv-pat` | page-deriv | mocked integration verified | Invalid broker authentication gives actionable error without a session |
| `#deriv-list` | page-deriv | local and mocked verified | Disconnected broker controls remain safe; Invalid broker authentication gives actionable error without a session |
| `#deriv-account` | page-deriv | mocked integration verified | Account disconnect and real-account connection remain strictly read-only |
| `button:submit:2. Connect selected account` | page-deriv | mocked integration verified | Demo account discovery/connect clears browser credentials |
| `#deriv-disconnect` | page-deriv | local and mocked verified | Disconnected broker controls remain safe; Purchase timeout durably blocks retry and survives browser/account reconnect |
| `a:https://developers.deriv.com/:Deriv Developer Portal` | page-deriv | external link reviewed only | Official HTTPS destination and safe new-tab behavior reviewed; Official developer portal destination and safe external link; HTTPS destination and safe target/rel inspected; external service not navigated or verified. |
| `#deriv-order-form` | page-deriv | mocked integration verified | Changing stake or expiry invalidates a previously reviewed quote |
| `#deriv-symbol` | page-deriv | mocked integration verified | No-offer market disables quoting; offered directions and all expiry choices work |
| `#deriv-side` | page-deriv | mocked integration verified | No-offer market disables quoting; offered directions and all expiry choices work |
| `#deriv-minutes` | page-deriv | mocked integration verified | Changing stake or expiry invalidates a previously reviewed quote |
| `#deriv-check-durations` | page-deriv | local and mocked verified | Disconnected broker controls remain safe; No-offer market disables quoting; offered directions and all expiry choices work |
| `#deriv-stake` | page-deriv | mocked integration verified | Changing stake or expiry invalidates a previously reviewed quote |
| `button:submit:Get live broker price proposal` | page-deriv | mocked integration verified | Changing stake or expiry invalidates a previously reviewed quote |
| `#deriv-buy` | page-deriv | mocked integration verified | Purchase timeout durably blocks retry and survives browser/account reconnect |
| `#deriv-arm-phrase` | page-deriv | unsupported disabled | Live execution intentionally unsupported in production. |
| `#deriv-arm` | page-deriv | unsupported disabled | Live execution intentionally unsupported in production. |
| `#deriv-strategy` | page-deriv | mocked integration verified | Every indicator robot strategy configures and stops without autonomous fixture fills |
| `#deriv-auto-stake` | page-deriv | mocked integration verified | Every indicator robot strategy configures and stops without autonomous fixture fills |
| `#deriv-auto-start` | page-deriv | local and mocked verified | Disconnected broker controls remain safe; Every indicator robot strategy configures and stops without autonomous fixture fills |
| `#deriv-auto-stop` | page-deriv | local and mocked verified | Disconnected broker controls remain safe; Every indicator robot strategy configures and stops without autonomous fixture fills |
| `#deriv-candle-fetch` | page-deriv | local and mocked verified | Disconnected broker controls remain safe; Candle history control loads well-formed closed fixture bars |
| `#robot-form` | page-robot | local verified | Synthetic robot parameters, invalid input, save and start/stop |
| `#robot-asset` | page-robot | local verified | Synthetic robot parameters, invalid input, save and start/stop |
| `#robot-strategy` | page-robot | local verified | Synthetic robot parameters, invalid input, save and start/stop |
| `#robot-stake` | page-robot | local verified | Synthetic robot parameters, invalid input, save and start/stop |
| `#robot-duration` | page-robot | local verified | Synthetic robot parameters, invalid input, save and start/stop |
| `#robot-loss` | page-robot | local verified | Synthetic robot parameters, invalid input, save and start/stop |
| `#robot-profit` | page-robot | local verified | Synthetic robot parameters, invalid input, save and start/stop |
| `#robot-risk` | page-robot | local verified | Synthetic robot parameters, invalid input, save and start/stop |
| `#robot-limit` | page-robot | local verified | Synthetic robot parameters, invalid input, save and start/stop |
| `#robot-payout` | page-robot | local verified | Synthetic robot parameters, invalid input, save and start/stop |
| `#save-robot` | page-robot | local verified | Synthetic robot parameters, invalid input, save and start/stop |
| `#robot-start` | page-robot | local verified | Synthetic robot parameters, invalid input, save and start/stop |
| `#robot-stop` | page-robot | local verified | Synthetic robot parameters, invalid input, save and start/stop |
| `#backtest-form` | page-backtest | local verified | All six indicator backtests and all backtest inputs |
| `#test-asset` | page-backtest | local verified | All six indicator backtests and all backtest inputs |
| `#test-strategy` | page-backtest | local verified | All six indicator backtests and all backtest inputs |
| `#test-stake` | page-backtest | local verified | All six indicator backtests and all backtest inputs |
| `#test-duration` | page-backtest | local verified | All six indicator backtests and all backtest inputs |
| `button:submit:⌁ Run historical test` | page-backtest | local verified | All six indicator backtests and all backtest inputs |
| `a:/api/export:↓ Export CSV` | page-history | local verified | valid csv download; Trade journal CSV export |
| `#risk-refresh` | page-risk | local and mocked verified | Risk refresh, invalid disconnected calendar, audit export; Connected risk refresh and audit download contain valid isolated records |
| `#risk-config-form` | page-risk | mocked integration verified | Connected default risk form is valid and saves every configurable hard limit |
| `#limit-risk_per_trade_pct` | page-risk | mocked integration verified | Connected default risk form is valid and saves every configurable hard limit |
| `#limit-daily_loss_pct` | page-risk | mocked integration verified | Connected default risk form is valid and saves every configurable hard limit |
| `#limit-weekly_loss_pct` | page-risk | mocked integration verified | Connected default risk form is valid and saves every configurable hard limit |
| `#limit-max_drawdown_pct` | page-risk | mocked integration verified | Connected default risk form is valid and saves every configurable hard limit |
| `#limit-max_positions` | page-risk | mocked integration verified | Connected default risk form is valid and saves every configurable hard limit |
| `#limit-max_trades_per_day` | page-risk | mocked integration verified | Connected default risk form is valid and saves every configurable hard limit |
| `#limit-max_order_size` | page-risk | mocked integration verified | Connected default risk form is valid and saves every configurable hard limit |
| `#limit-max_asset_exposure_pct` | page-risk | mocked integration verified | Connected default risk form is valid and saves every configurable hard limit |
| `#limit-max_group_exposure_pct` | page-risk | mocked integration verified | Connected default risk form is valid and saves every configurable hard limit |
| `#limit-consecutive_loss_limit` | page-risk | mocked integration verified | Connected default risk form is valid and saves every configurable hard limit |
| `#limit-cooldown_minutes` | page-risk | mocked integration verified | Connected default risk form is valid and saves every configurable hard limit |
| `#limit-calendar_policy` | page-risk | mocked integration verified | Synthetic calendar exception needs confirmation and persists only after approval |
| `button:submit:Save account risk limits` | page-risk | mocked integration verified | Connected default risk form is valid and saves every configurable hard limit |
| `summary::Import a licensed economic-calendar snapshot` | page-risk | local verified | Beginner and advanced views persist; disclosures open |
| `#risk-calendar-file` | page-risk | local and mocked verified | Risk refresh, invalid disconnected calendar, audit export; Calendar import rejects malformed JSON and accepts explicit current fixture coverage |
| `#risk-resume-form` | page-risk | local verified | Global emergency stop, reload, bad phrase, explicit resume |
| `#risk-resume-phrase` | page-risk | local and mocked verified | Global emergency stop, reload, bad phrase, explicit resume; Connected emergency stop persists and explicit resume restarts no robot |
| `#risk-resume` | page-risk | local and mocked verified | Global emergency stop, reload, bad phrase, explicit resume; Connected emergency stop persists and explicit resume restarts no robot |
| `summary::Operational details` | page-risk | local verified | Beginner and advanced views persist; disclosures open |
| `#audit-export` | page-risk | local and mocked verified | valid json download; Risk refresh, invalid disconnected calendar, audit export; Connected risk refresh and audit download contain valid isolated records |
| `#csv-upload` | page-settings | local verified | Simulator CSV valid/invalid import, backtest-only history, reset cancel/confirm |
| `#reset-demo` | page-settings | local verified | Simulator CSV valid/invalid import, backtest-only history, reset cancel/confirm |
| `#lab-param-macd_fast` | page-strategies | local verified | Catalog bounds and defaults tested: MACD |
| `#lab-param-macd_slow` | page-strategies | local verified | Catalog bounds and defaults tested: MACD |
| `#lab-param-macd_signal_period` | page-strategies | local verified | Catalog bounds and defaults tested: MACD |
| `#lab-param-cci_period` | page-strategies | local verified | Catalog bounds and defaults tested: CCI |
| `#lab-param-cci_level` | page-strategies | local verified | Catalog bounds and defaults tested: CCI |
| `#lab-param-sma_fast_period` | page-strategies | local verified | Catalog bounds and defaults tested: SMA |
| `#lab-param-sma_slow_period` | page-strategies | local verified | Catalog bounds and defaults tested: SMA |
| `#lab-param-bb_period` | page-strategies | local verified | Catalog bounds and defaults tested: BOLLINGER; Catalog bounds and defaults tested: BOLLINGER_REENTRY; Catalog bounds and defaults tested: BOLLINGER_SQUEEZE |
| `#lab-param-bb_deviations` | page-strategies | local verified | Catalog bounds and defaults tested: BOLLINGER; Catalog bounds and defaults tested: BOLLINGER_REENTRY; Catalog bounds and defaults tested: BOLLINGER_SQUEEZE |
| `#lab-param-stoch_period` | page-strategies | local verified | Catalog bounds and defaults tested: STOCHASTIC |
| `#lab-param-ema_fast_period` | page-strategies | local verified | Catalog bounds and defaults tested: EMA_CROSS; Catalog bounds and defaults tested: EMA_PULLBACK; Catalog bounds and defaults tested: TRIPLE_EMA |
| `#lab-param-ema_slow_period` | page-strategies | local verified | Catalog bounds and defaults tested: EMA_CROSS; Catalog bounds and defaults tested: TRIPLE_EMA |
| `#lab-param-trend_period` | page-strategies | local verified | Catalog bounds and defaults tested: EMA_PULLBACK; Catalog bounds and defaults tested: RSI_TREND; Catalog bounds and defaults tested: CONSENSUS |
| `#lab-param-ema_mid_period` | page-strategies | local verified | Catalog bounds and defaults tested: TRIPLE_EMA |
| `#lab-param-rsi_midpoint` | page-strategies | local verified | Catalog bounds and defaults tested: RSI_TREND |
| `#lab-param-stoch_rsi_period` | page-strategies | local verified | Catalog bounds and defaults tested: STOCH_RSI |
| `#lab-param-williams_period` | page-strategies | local verified | Catalog bounds and defaults tested: WILLIAMS_R |
| `#lab-param-recovery_window` | page-strategies | local verified | Catalog bounds and defaults tested: WILLIAMS_R |
| `#lab-param-roc_period` | page-strategies | local verified | Catalog bounds and defaults tested: ROC |
| `#lab-param-roc_threshold` | page-strategies | local verified | Catalog bounds and defaults tested: ROC |
| `#lab-param-momentum_period` | page-strategies | local verified | Catalog bounds and defaults tested: MOMENTUM |
| `#lab-param-accel_period` | page-strategies | local verified | Catalog bounds and defaults tested: MOMENTUM |
| `#lab-param-adx_period` | page-strategies | local verified | Catalog bounds and defaults tested: ADX_DMI |
| `#lab-param-adx_min` | page-strategies | local verified | Catalog bounds and defaults tested: ADX_DMI |
| `#lab-param-channel_period` | page-strategies | local verified | Catalog bounds and defaults tested: DONCHIAN; Catalog bounds and defaults tested: CONSENSUS |
| `#lab-param-atr_period` | page-strategies | local verified | Catalog bounds and defaults tested: ATR_BREAKOUT; Catalog bounds and defaults tested: KELTNER; Catalog bounds and defaults tested: SUPERTREND |
| `#lab-param-atr_multiple` | page-strategies | local verified | Catalog bounds and defaults tested: ATR_BREAKOUT; Catalog bounds and defaults tested: KELTNER; Catalog bounds and defaults tested: SUPERTREND |
| `#lab-param-keltner_period` | page-strategies | local verified | Catalog bounds and defaults tested: KELTNER |
| `#lab-param-squeeze_width_pct` | page-strategies | local verified | Catalog bounds and defaults tested: BOLLINGER_SQUEEZE |
| `#lab-param-tenkan_period` | page-strategies | local verified | Catalog bounds and defaults tested: ICHIMOKU |
| `#lab-param-kijun_period` | page-strategies | local verified | Catalog bounds and defaults tested: ICHIMOKU |
| `#lab-param-senkou_period` | page-strategies | local verified | Catalog bounds and defaults tested: ICHIMOKU |
| `#lab-param-cloud_displacement` | page-strategies | local verified | Catalog bounds and defaults tested: ICHIMOKU |
| `#lab-param-aroon_period` | page-strategies | local verified | Catalog bounds and defaults tested: AROON |
| `#lab-param-aroon_min` | page-strategies | local verified | Catalog bounds and defaults tested: AROON |
| `#lab-param-consensus_votes` | page-strategies | local verified | Catalog bounds and defaults tested: CONSENSUS |
| `market:CUSTOM` | page-overview | local verified | Dynamically imported CSV market can be selected |
