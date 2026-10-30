# Function audit and code coverage

The current unittest run passed 313 tests. Coverage.py recorded 3075 of 3446 executable statements (89.23%). Branch coverage was not measured. The browser subprocesses and extracted-package tests are separate evidence. Executing a line does not prove every input or branch correct.

| Module | Declared functions/methods | Statement coverage |
|---|---:|---:|
| `deriv_bridge.py` | 44 | 88.82% |
| `deriv_server.py` | 24 | 76.62% |
| `engine.py` | 12 | 98.08% |
| `indicator_strategies.py` | 5 | 96.63% |
| `market_data.py` | 4 | 96.51% |
| `market_regime.py` | 3 | 97.75% |
| `paper_engine.py` | 15 | 97.00% |
| `research_analytics.py` | 3 | 94.32% |
| `risk_engine.py` | 35 | 93.60% |
| `server.py` | 20 | 71.23% |
| `strategy_extension.py` | 27 | 93.06% |
| `strategy_research.py` | 6 | 97.95% |
| `strategy_selector.py` | 1 | 92.98% |

All declared top-level functions and methods inside top-level classes are inventoried with line numbers and source hashes in [control_audit.json](control_audit.json). Nested helper functions are excluded from that inventory count.

The new rule tests include explicit bullish and bearish fixtures for all 24 strategies, flat-data rejection, bounded parameters, warm-up sufficiency, future-prefix invariance, past-shifted Ichimoku cloud evidence, prior-bar channels and Wilder ATR/DMI fixtures. Research tests cover independent split/fold capital, costs, gaps, purging, versioned provenance, missing walk-forward refusal and training-only strategy selection.

The retained integration tests cover broker authentication errors, durations, mutable quote inputs, duplicate/unknown outcomes, account switching, persistent risk limits, calendar outages, adverse paper gaps, halt/resume, audit corruption and transactional recovery. Migration tests preserve legacy WAL history and existing targets without reactivating retired strategies.

See [VALIDATION.md](VALIDATION.md) for commands, external blockers and trading-validation limitations. No calibrated accuracy, actual broker permissions/fills, universal platform correctness or production certification is inferred from these software checks.
