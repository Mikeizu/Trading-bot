# Technical strategy library

This app defines 24 technical-rule strategies, version `3.0.0`. The rules are our programmed interpretations of public technical-analysis methods. They are not claimed to be proprietary Qumatix algorithms or guaranteed profitable strategies. See [verified public research](PUBLIC_RESEARCH.md).

Rules use completed OHLC bars and bounded parameters. No volume is invented. A signal is a candidate; broker entries still require account, capability, risk, calendar, regime and authorization checks. Research entries occur at the next bar open. Consensus votes are correlated rules, not an accuracy probability.

## Catalog

| ID | Name | Family | Default warm-up bars | Eligible regimes |
|---|---|---|---:|---|
| `RSI` | RSI recovery | mean reversion | 35 | ranging |
| `MACD` | MACD signal crossover | momentum | 37 | trending_up, trending_down |
| `CCI` | CCI recovery | mean reversion | 35 | ranging |
| `SMA` | Dual SMA crossover | trend | 35 | trending_up, trending_down |
| `BOLLINGER` | Bollinger outer-band fade | mean reversion | 35 | ranging |
| `STOCHASTIC` | Stochastic %K recovery | mean reversion | 35 | ranging |
| `EMA_CROSS` | Dual EMA crossover | trend | 35 | trending_up, trending_down |
| `EMA_PULLBACK` | EMA trend pullback | trend | 52 | trending_up, trending_down |
| `TRIPLE_EMA` | Triple EMA alignment | trend | 52 | trending_up, trending_down |
| `RSI_TREND` | RSI trend confirmation | momentum | 52 | trending_up, trending_down |
| `STOCH_RSI` | Stochastic RSI recovery | mean reversion | 35 | ranging |
| `WILLIAMS_R` | Williams %R midpoint confirmation | mean reversion | 35 | ranging |
| `ROC` | Rate-of-change threshold | momentum | 35 | trending_up, trending_down |
| `MOMENTUM` | Momentum acceleration | momentum | 35 | trending_up, trending_down |
| `ADX_DMI` | ADX directional crossover | trend | 35 | trending_up, trending_down |
| `DONCHIAN` | Prior-channel breakout | breakout | 35 | trending_up, trending_down |
| `ATR_BREAKOUT` | ATR displacement breakout | breakout | 35 | trending_up, trending_down |
| `KELTNER` | Keltner channel breakout | breakout | 35 | trending_up, trending_down |
| `BOLLINGER_REENTRY` | Bollinger band re-entry | mean reversion | 35 | ranging |
| `BOLLINGER_SQUEEZE` | Bollinger squeeze breakout | volatility | 35 | trending_up, trending_down |
| `SUPERTREND` | ATR trailing trend flip | trend | 35 | trending_up, trending_down |
| `ICHIMOKU` | Ichimoku cloud confirmation | trend | 80 | trending_up, trending_down |
| `AROON` | Aroon trend emergence | trend | 35 | trending_up, trending_down |
| `CONSENSUS` | Transparent rule consensus | composite | 52 | trending_up, trending_down |

## RSI recovery (`RSI`)

Enter when Wilder RSI recovers through oversold or falls through overbought.

Default warm-up: 35 completed bars. Changing periods can increase it. Signals include version, parameters, indicator evidence and a plain-English reason. Virtual paper invalidation is separate from broker orders; no calibrated confidence percentage is supplied.

| Parameter | Default | Min | Max | Meaning |
|---|---:|---:|---:|---|
| `rsi_period` | 14 | 5 | 50 | Wilder RSI lookback |
| `oversold` | 30 | 5 | 45 | Lower RSI recovery threshold |
| `overbought` | 70 | 55 | 95 | Upper RSI recovery threshold |

## MACD signal crossover (`MACD`)

Enter when MACD crosses its signal EMA; averages use first-observation causal EMA seeds.

Default warm-up: 37 completed bars. Changing periods can increase it. Signals include version, parameters, indicator evidence and a plain-English reason. Virtual paper invalidation is separate from broker orders; no calibrated confidence percentage is supplied.

| Parameter | Default | Min | Max | Meaning |
|---|---:|---:|---:|---|
| `macd_fast` | 12 | 3 | 40 | MACD fast EMA period |
| `macd_slow` | 26 | 8 | 100 | MACD slow EMA period |
| `macd_signal_period` | 9 | 2 | 30 | MACD signal EMA period |

## CCI recovery (`CCI`)

Enter when CCI crosses back through a configurable extreme.

Default warm-up: 35 completed bars. Changing periods can increase it. Signals include version, parameters, indicator evidence and a plain-English reason. Virtual paper invalidation is separate from broker orders; no calibrated confidence percentage is supplied.

| Parameter | Default | Min | Max | Meaning |
|---|---:|---:|---:|---|
| `cci_period` | 20 | 5 | 80 | CCI typical-price lookback |
| `cci_level` | 100 | 50 | 250 | Symmetric CCI extreme level |

## Dual SMA crossover (`SMA`)

Enter on fast/slow simple moving-average crossover.

Default warm-up: 35 completed bars. Changing periods can increase it. Signals include version, parameters, indicator evidence and a plain-English reason. Virtual paper invalidation is separate from broker orders; no calibrated confidence percentage is supplied.

| Parameter | Default | Min | Max | Meaning |
|---|---:|---:|---:|---|
| `sma_fast_period` | 8 | 3 | 40 | Fast SMA period |
| `sma_slow_period` | 21 | 8 | 150 | Slow SMA period |

## Bollinger outer-band fade (`BOLLINGER`)

A close outside its close-price population-deviation bands proposes a contrarian candidate.

Default warm-up: 35 completed bars. Changing periods can increase it. Signals include version, parameters, indicator evidence and a plain-English reason. Virtual paper invalidation is separate from broker orders; no calibrated confidence percentage is supplied.

| Parameter | Default | Min | Max | Meaning |
|---|---:|---:|---:|---|
| `bb_period` | 20 | 10 | 80 | Bollinger close-price lookback |
| `bb_deviations` | 2.0 | 1.0 | 4.0 | Population standard-deviation band multiplier |

## Stochastic %K recovery (`STOCHASTIC`)

Raw stochastic %K crosses back through an extreme; this is not a smoothed slow-stochastic replica.

Default warm-up: 35 completed bars. Changing periods can increase it. Signals include version, parameters, indicator evidence and a plain-English reason. Virtual paper invalidation is separate from broker orders; no calibrated confidence percentage is supplied.

| Parameter | Default | Min | Max | Meaning |
|---|---:|---:|---:|---|
| `stoch_period` | 14 | 5 | 50 | Raw stochastic %K lookback |
| `oversold` | 20 | 5 | 40 | Lower %K threshold |
| `overbought` | 80 | 60 | 95 | Upper %K threshold |

## Dual EMA crossover (`EMA_CROSS`)

Enter on fast/slow exponentially weighted moving-average crossover.

Default warm-up: 35 completed bars. Changing periods can increase it. Signals include version, parameters, indicator evidence and a plain-English reason. Virtual paper invalidation is separate from broker orders; no calibrated confidence percentage is supplied.

| Parameter | Default | Min | Max | Meaning |
|---|---:|---:|---:|---|
| `ema_fast_period` | 12 | 3 | 50 | Fast EMA period |
| `ema_slow_period` | 26 | 8 | 150 | Slow EMA period |

## EMA trend pullback (`EMA_PULLBACK`)

A price recovery through the fast EMA must agree with the slower trend EMA and its slope.

Default warm-up: 52 completed bars. Changing periods can increase it. Signals include version, parameters, indicator evidence and a plain-English reason. Virtual paper invalidation is separate from broker orders; no calibrated confidence percentage is supplied.

| Parameter | Default | Min | Max | Meaning |
|---|---:|---:|---:|---|
| `ema_fast_period` | 20 | 5 | 40 | Pullback EMA period |
| `trend_period` | 50 | 20 | 200 | Trend-filter EMA period |

## Triple EMA alignment (`TRIPLE_EMA`)

Fast EMA crosses the middle EMA while both agree with the slow EMA ordering.

Default warm-up: 52 completed bars. Changing periods can increase it. Signals include version, parameters, indicator evidence and a plain-English reason. Virtual paper invalidation is separate from broker orders; no calibrated confidence percentage is supplied.

| Parameter | Default | Min | Max | Meaning |
|---|---:|---:|---:|---|
| `ema_fast_period` | 9 | 3 | 30 | Fast EMA period |
| `ema_mid_period` | 21 | 5 | 80 | Middle EMA period |
| `ema_slow_period` | 50 | 20 | 150 | Slow EMA period |

## RSI trend confirmation (`RSI_TREND`)

RSI crosses its midpoint while price and the trend EMA slope agree.

Default warm-up: 52 completed bars. Changing periods can increase it. Signals include version, parameters, indicator evidence and a plain-English reason. Virtual paper invalidation is separate from broker orders; no calibrated confidence percentage is supplied.

| Parameter | Default | Min | Max | Meaning |
|---|---:|---:|---:|---|
| `rsi_period` | 14 | 5 | 50 | Wilder RSI lookback |
| `trend_period` | 50 | 20 | 200 | Trend-filter EMA period |
| `rsi_midpoint` | 50 | 40 | 60 | RSI trend threshold |

## Stochastic RSI recovery (`STOCH_RSI`)

RSI normalized against its own recent range recovers through an extreme.

Default warm-up: 35 completed bars. Changing periods can increase it. Signals include version, parameters, indicator evidence and a plain-English reason. Virtual paper invalidation is separate from broker orders; no calibrated confidence percentage is supplied.

| Parameter | Default | Min | Max | Meaning |
|---|---:|---:|---:|---|
| `rsi_period` | 14 | 5 | 50 | Wilder RSI lookback |
| `stoch_rsi_period` | 14 | 5 | 50 | Stochastic normalization of RSI |
| `oversold` | 20 | 5 | 40 | Lower stochastic-RSI threshold |
| `overbought` | 80 | 60 | 95 | Upper stochastic-RSI threshold |

## Williams %R midpoint confirmation (`WILLIAMS_R`)

Williams %R must cross its -50 midpoint after visiting an extreme in the recent confirmation window.

Default warm-up: 35 completed bars. Changing periods can increase it. Signals include version, parameters, indicator evidence and a plain-English reason. Virtual paper invalidation is separate from broker orders; no calibrated confidence percentage is supplied.

| Parameter | Default | Min | Max | Meaning |
|---|---:|---:|---:|---|
| `williams_period` | 14 | 5 | 50 | Williams %R lookback |
| `oversold` | -80 | -95 | -60 | Required recent lower %R extreme |
| `overbought` | -20 | -40 | -5 | Required recent upper %R extreme |
| `recovery_window` | 5 | 2 | 20 | Recent bars allowed for extreme-to-midpoint confirmation |

## Rate-of-change threshold (`ROC`)

Percentage price change crosses a signed neutral threshold.

Default warm-up: 35 completed bars. Changing periods can increase it. Signals include version, parameters, indicator evidence and a plain-English reason. Virtual paper invalidation is separate from broker orders; no calibrated confidence percentage is supplied.

| Parameter | Default | Min | Max | Meaning |
|---|---:|---:|---:|---|
| `roc_period` | 12 | 3 | 80 | Percentage rate-of-change lookback |
| `roc_threshold` | 0.0 | 0.0 | 10.0 | Symmetric percentage ROC threshold |

## Momentum acceleration (`MOMENTUM`)

Momentum acceleration crosses zero in the same direction as longer-horizon price momentum.

Default warm-up: 35 completed bars. Changing periods can increase it. Signals include version, parameters, indicator evidence and a plain-English reason. Virtual paper invalidation is separate from broker orders; no calibrated confidence percentage is supplied.

| Parameter | Default | Min | Max | Meaning |
|---|---:|---:|---:|---|
| `momentum_period` | 20 | 5 | 100 | Price momentum lookback |
| `accel_period` | 5 | 1 | 20 | Lag used to measure momentum acceleration |

## ADX directional crossover (`ADX_DMI`)

Positive/negative Wilder directional indices cross while ADX exceeds the research threshold.

Default warm-up: 35 completed bars. Changing periods can increase it. Signals include version, parameters, indicator evidence and a plain-English reason. Virtual paper invalidation is separate from broker orders; no calibrated confidence percentage is supplied.

| Parameter | Default | Min | Max | Meaning |
|---|---:|---:|---:|---|
| `adx_period` | 14 | 5 | 50 | Wilder DMI and ADX period |
| `adx_min` | 20 | 10 | 50 | Minimum ADX trend-strength threshold |

## Prior-channel breakout (`DONCHIAN`)

Close breaks the high/low channel built strictly before the signal bar.

Default warm-up: 35 completed bars. Changing periods can increase it. Signals include version, parameters, indicator evidence and a plain-English reason. Virtual paper invalidation is separate from broker orders; no calibrated confidence percentage is supplied.

| Parameter | Default | Min | Max | Meaning |
|---|---:|---:|---:|---|
| `channel_period` | 20 | 5 | 100 | Prior-bar Donchian channel lookback |

## ATR displacement breakout (`ATR_BREAKOUT`)

Close displaces beyond the previous close by a multiple of the previous ATR.

Default warm-up: 35 completed bars. Changing periods can increase it. Signals include version, parameters, indicator evidence and a plain-English reason. Virtual paper invalidation is separate from broker orders; no calibrated confidence percentage is supplied.

| Parameter | Default | Min | Max | Meaning |
|---|---:|---:|---:|---|
| `atr_period` | 14 | 5 | 50 | Wilder true-range averaging period |
| `atr_multiple` | 1.5 | 0.5 | 5.0 | ATR threshold or trailing-band multiplier |

## Keltner channel breakout (`KELTNER`)

Close crosses an EMA plus/minus a Wilder ATR envelope.

Default warm-up: 35 completed bars. Changing periods can increase it. Signals include version, parameters, indicator evidence and a plain-English reason. Virtual paper invalidation is separate from broker orders; no calibrated confidence percentage is supplied.

| Parameter | Default | Min | Max | Meaning |
|---|---:|---:|---:|---|
| `keltner_period` | 20 | 5 | 100 | Keltner EMA middle period |
| `atr_period` | 14 | 5 | 50 | Wilder true-range averaging period |
| `atr_multiple` | 2.0 | 0.5 | 5.0 | Keltner ATR multiplier |

## Bollinger band re-entry (`BOLLINGER_REENTRY`)

Require a prior close outside the band followed by a closed-bar recovery inside it.

Default warm-up: 35 completed bars. Changing periods can increase it. Signals include version, parameters, indicator evidence and a plain-English reason. Virtual paper invalidation is separate from broker orders; no calibrated confidence percentage is supplied.

| Parameter | Default | Min | Max | Meaning |
|---|---:|---:|---:|---|
| `bb_period` | 20 | 10 | 80 | Bollinger close-price lookback |
| `bb_deviations` | 2.0 | 1.0 | 4.0 | Population standard-deviation band multiplier |

## Bollinger squeeze breakout (`BOLLINGER_SQUEEZE`)

A low prior bandwidth must precede a close breaking the prior bands.

Default warm-up: 35 completed bars. Changing periods can increase it. Signals include version, parameters, indicator evidence and a plain-English reason. Virtual paper invalidation is separate from broker orders; no calibrated confidence percentage is supplied.

| Parameter | Default | Min | Max | Meaning |
|---|---:|---:|---:|---|
| `bb_period` | 20 | 10 | 80 | Bollinger close-price lookback |
| `bb_deviations` | 2.0 | 1.0 | 4.0 | Population standard-deviation band multiplier |
| `squeeze_width_pct` | 2.0 | 0.1 | 20.0 | Maximum prior band width as percent of middle |

## ATR trailing trend flip (`SUPERTREND`)

Enter only when the causal ATR-based trailing-band direction changes.

Default warm-up: 35 completed bars. Changing periods can increase it. Signals include version, parameters, indicator evidence and a plain-English reason. Virtual paper invalidation is separate from broker orders; no calibrated confidence percentage is supplied.

| Parameter | Default | Min | Max | Meaning |
|---|---:|---:|---:|---|
| `atr_period` | 10 | 5 | 50 | Trailing true-range period |
| `atr_multiple` | 3.0 | 1.0 | 5.0 | Trailing ATR multiplier |

## Ichimoku cloud confirmation (`ICHIMOKU`)

Conversion/baseline crossover must agree with the current displayed cloud, using spans computed displacement bars in the past; no future or lagging-span leakage.

Default warm-up: 80 completed bars. Changing periods can increase it. Signals include version, parameters, indicator evidence and a plain-English reason. Virtual paper invalidation is separate from broker orders; no calibrated confidence percentage is supplied.

| Parameter | Default | Min | Max | Meaning |
|---|---:|---:|---:|---|
| `tenkan_period` | 9 | 3 | 20 | Ichimoku conversion midpoint period |
| `kijun_period` | 26 | 10 | 60 | Ichimoku baseline midpoint period |
| `senkou_period` | 52 | 20 | 120 | Ichimoku span B midpoint period |
| `cloud_displacement` | 26 | 1 | 60 | Past computed spans used for today's displayed cloud |

## Aroon trend emergence (`AROON`)

Aroon up/down cross with the winning high/low-age measure above a minimum.

Default warm-up: 35 completed bars. Changing periods can increase it. Signals include version, parameters, indicator evidence and a plain-English reason. Virtual paper invalidation is separate from broker orders; no calibrated confidence percentage is supplied.

| Parameter | Default | Min | Max | Meaning |
|---|---:|---:|---:|---|
| `aroon_period` | 25 | 5 | 80 | Aroon high/low age period |
| `aroon_min` | 70 | 50 | 95 | Minimum winning Aroon value |

## Transparent rule consensus (`CONSENSUS`)

Require a new threshold of agreement among trend EMA, RSI midpoint, MACD histogram and prior-channel breakout. Votes are correlated rules, not a probability.

Default warm-up: 52 completed bars. Changing periods can increase it. Signals include version, parameters, indicator evidence and a plain-English reason. Virtual paper invalidation is separate from broker orders; no calibrated confidence percentage is supplied.

| Parameter | Default | Min | Max | Meaning |
|---|---:|---:|---:|---|
| `trend_period` | 50 | 20 | 200 | Trend-filter EMA period |
| `rsi_period` | 14 | 5 | 50 | Wilder RSI lookback |
| `channel_period` | 20 | 5 | 100 | Prior-bar Donchian channel lookback |
| `consensus_votes` | 3 | 2 | 4 | Required agreeing rule votes, not confidence |

## Validation and scope

Assess trade counts, after-cost expectancy, losses, drawdown, uncertainty, cost stress, independent holdout and training-only walk-forward evidence. The 65% target is informational. Win rate alone cannot promote a strategy; insufficient evidence returns no validated strategy. Repeated use of the same holdout is not independent evidence.

Research models fixed-expiry option outcomes with assumed payouts and costs. Paper positions use a separate virtual stop/target ledger. Neither is a verified MT5/CFD or broker fill simulator. Real-money purchases are disabled; genuine broker-demo behavior and future-market accuracy require separate authorized evidence.
