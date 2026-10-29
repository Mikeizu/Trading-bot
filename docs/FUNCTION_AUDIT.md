# Function-level audit and coverage

Function names were inventoried from the application source using Python AST: top-level functions and methods declared directly inside top-level classes. Nested helpers, test code and packaging tools are excluded from the callable count. This is an inventory and evidence index, **not a claim of 100% function or branch coverage**.

## Executed evidence

- Final combined unittest run: **282 passed** in **40.015 seconds**, zero failures, errors or skips.
- The additional `tests/test_function_audit.py` contains **24 regression tests** for transport parsing/correlation, authentication errors, reconciliation tampering, indicator periods and Bollinger calculations, expiry gaps, canonical candle bounds, analytics auxiliaries and regime fail-safes.
- The 24-test function audit and earlier component suites also passed as a 145-test focused run. The 282-test final run supersedes that intermediate count.
- Browser suites separately passed 42 scenarios across 115 inventoried controls, with test-only fictional broker replies for connected behavior. See [CONTROL_AUDIT.md](CONTROL_AUDIT.md).

## Statement coverage

Coverage.py 7.17.0 recorded **2885 covered / 3259 executable statements = 88.52%** (89% rounded), with **374 missing statements**. **Branch coverage was not measured.** This run instrumented unittest processes only; separately launched browser/server child processes were not combined. A covered line does not prove every input or execution branch is correct.

| Module | Declared functions/methods | Covered / statements | Statement coverage | Missing |
|---|---:|---:|---:|---:|
| `deriv_bridge.py` | 44 | 572 / 644 | 88.82% | 72 |
| `deriv_server.py` | 23 | 303 / 400 | 75.75% | 97 |
| `engine.py` | 8 | 165 / 170 | 97.06% | 5 |
| `market_regime.py` | 2 | 84 / 86 | 97.67% | 2 |
| `naked_strategies.py` | 19 | 333 / 348 | 95.69% | 15 |
| `paper_engine.py` | 15 | 185 / 200 | 92.50% | 15 |
| `research_analytics.py` | 3 | 83 / 88 | 94.32% | 5 |
| `risk_engine.py` | 35 | 541 / 578 | 93.60% | 37 |
| `server.py` | 20 | 248 / 349 | 71.06% | 101 |
| `strategy_extension.py` | 25 | 331 / 353 | 93.77% | 22 |
| `strategy_selector.py` | 1 | 40 / 43 | 93.02% | 3 |

Total declared inventory: **195** entries. The machine-readable report includes source hashes, callable names/line numbers and missing statement lines for every module. Source hashes identify this tested source snapshot; they do not authenticate a broker or certify financial results.

## Regression areas examined

| Area | Evidence and boundary |
|---|---|
| Broker transport | PAT/App-ID validation, malformed REST/OTP data, exact official URL checks, TLS/redirect policy, request IDs, error redaction, supported symbols/durations and strict candle parsing. All replies in tests are fictional. |
| Broker controller and journal | Read-only real accounts, fresh balance/portfolio, stale quote invalidation, final risk/stop check, atomic durable reservations, duplicate prevention, uncertain outcomes, settlement identity/P&L and journal tamper refusal. No genuine broker state was tested. |
| Risk | Persistent account/mode limits, day/week/drawdown/exposure budgets, loss cooldowns, UTC/calendar freshness, atomic reservations, recovery mismatches, stop/resume and audit checkpoints. Whole-database rollback remains outside an unsigned local hash chain guarantee. |
| Paper positions | Pending next-open fills, costs, stop-first ambiguity, adverse gaps, deduplication, exposure/loss budgets, halt persistence, invalid-input refusal and recovery. This is an OHLC model without real broker liquidity/financing. |
| Indicators and backtests | Six indicator modes, flat-close Bollinger centering, input periods/finite bounds, causal next-open execution, missing-bar expiry refusal, transaction-cost assumptions and provenance. |
| Seven pattern research | Quantified patterns/parameters, calendar-aligned resampling, isolated train/holdout/fold capital, pre-mutation boundary purging, stress costs, uncertainty and training-only comparison. Sparse/no validated strategy remains a valid result. |
| Market regime | Deterministic trend/range/volatility/abnormal/uncertain paths, eligibility, stale/missing data/calendar and numeric guards. Heuristics are not calibrated forecasts. |
| HTTP and controls | Valid/invalid request bodies, local host/origin protections, simulated CSV timestamps/terms, imports/exports, start/stop/configuration and separate UI/API evidence. Native Windows/browser-platform combinations are not all exercised. |

## Complete declared inventory

### deriv_bridge.py

`_NoCredentialRedirect.redirect_request`, `urlopen`, `_finite`, `_positive`, `_credentials`, `check_otp_url`, `normalize_accounts`, `normalize_active_symbols`, `_duration_seconds`, `normalize_contract_durations`, `DerivTransport.__init__`, `DerivTransport._http`, `DerivTransport._websocket`, `DerivTransport.accounts`, `DerivTransport.connect`, `DerivTransport.close`, `DerivTransport.rpc`, `DerivTransport.balance`, `DerivTransport.portfolio`, `DerivTransport.symbols`, `DerivTransport.contracts_for`, `DerivTransport.candles`, `DerivTransport.proposal`, `DerivTransport.buy`, `DerivTransport.contract`, `BrokerController.__init__`, `BrokerController.status`, `BrokerController.list_accounts`, `BrokerController.connect`, `BrokerController.refresh_markets`, `BrokerController.disconnect`, `BrokerController.arm`, `BrokerController._read_balance`, `BrokerController._positions`, `BrokerController._market_kind`, `BrokerController._precheck`, `BrokerController.get_candles`, `BrokerController.available_durations`, `BrokerController._duration_rejection`, `BrokerController.new_quote`, `BrokerController.buy_quote`, `BrokerController.reconcile`, `BrokerController.broker_snapshot`, `BrokerController.demo_auto_once`.

### deriv_server.py

`Journal.__init__`, `Journal.db`, `Journal.reserve`, `Journal.update`, `Journal._require_integrity`, `Journal._audit`, `Journal.audit`, `Journal.history`, `Journal.orders`, `Journal.unresolved`, `Journal.today`, `entry_guard`, `risk_status`, `emergency_stop`, `capabilities`, `API.check_host`, `API.check_origin`, `API.do_strategy_POST`, `API.do_GET`, `API.do_POST`, `API.do_risk_POST`, `auto_loop`, `main`.

### engine.py

`_period`, `_series`, `ema`, `sma`, `rsi`, `indicators`, `signal_at`, `backtest`.

### market_regime.py

`_result`, `classify_regime`.

### naked_strategies.py

`candles_valid`, `resample`, `sample_candles`, `_range`, `_body`, `_bottom`, `_top`, `_near`, `zone_levels`, `_matching_zone`, `_signal`, `validate_parameters`, `detect`, `confirmed_signal`, `_metric`, `_bar_end`, `_simulate_partition`, `_walk_forward`, `backtest`.

### paper_engine.py

`number`, `identity`, `epoch`, `next_bar`, `PaperBook.__init__`, `PaperBook.db`, `PaperBook.equity`, `PaperBook.positions`, `PaperBook.balance`, `PaperBook.cancel_pending`, `PaperBook.halt`, `PaperBook.resume`, `PaperBook.guard`, `PaperBook.open`, `PaperBook.reconcile`.

### research_analytics.py

`wilson_interval`, `performance_metrics`, `dataset_provenance`.

### risk_engine.py

`_number`, `_identity`, `_encode`, `_windows`, `RiskEngine.__init__`, `RiskEngine._db`, `RiskEngine._default_state`, `RiskEngine._load`, `RiskEngine._save`, `RiskEngine._reservation_hash`, `RiskEngine._append`, `RiskEngine._validate_config`, `RiskEngine.configure`, `RiskEngine._global`, `RiskEngine.global_status`, `RiskEngine.observe`, `RiskEngine.kill_all`, `RiskEngine.resume_all`, `RiskEngine.kill`, `RiskEngine.resume`, `RiskEngine.set_calendar`, `RiskEngine._calendar_fresh`, `RiskEngine._group`, `RiskEngine._currencies`, `RiskEngine._calendar_decision`, `RiskEngine.calendar_status`, `RiskEngine._assess`, `RiskEngine.evaluate`, `RiskEngine.require`, `RiskEngine.reserve`, `RiskEngine.resolve`, `RiskEngine.audit`, `RiskEngine._verify_audit`, `RiskEngine.verify_audit`, `RiskEngine.status`.

### server.py

`reject_json_constant`, `conn`, `db_initialize`, `get_settings`, `set_settings`, `candles_for`, `today_stats`, `market_advance`, `market_loop`, `normalize_update`, `import_csv`, `API.end_headers`, `API.log_message`, `API.send_json`, `API.error_json`, `API.do_GET`, `API.export_trades`, `API.serve_static`, `API.do_POST`, `main`.

### strategy_extension.py

`_request_object`, `_frame`, `_limit`, `SignalBook.__init__`, `SignalBook._connect`, `SignalBook.record`, `SignalBook.outcome`, `SignalBook.recent`, `SignalBook.history`, `StrategySupervisor.__init__`, `StrategySupervisor._execution_enabled`, `StrategySupervisor.stop`, `StrategySupervisor._calendar_status`, `StrategySupervisor.status`, `StrategySupervisor.configure`, `StrategySupervisor.read_closed`, `StrategySupervisor.sample`, `StrategySupervisor._history`, `StrategySupervisor._source_label`, `StrategySupervisor.research`, `StrategySupervisor._research_options`, `StrategySupervisor.scan_all`, `StrategySupervisor.activate_best`, `StrategySupervisor.tick`, `StrategySupervisor.loop`.

### strategy_selector.py

`compare_all`.

## Reproduce coverage

With Coverage.py installed as optional development tooling:

```bash
python -m coverage run --source=deriv_bridge,deriv_server,engine,market_regime,naked_strategies,paper_engine,research_analytics,risk_engine,server,strategy_extension,strategy_selector -m unittest discover -s tests -v
python -m coverage report
python -m coverage json -o coverage.json
```

Use an isolated data directory. Do not infer complete function/branch coverage from this statement-only command or silently exclude failing tests to improve the percentage.
