# Public product and strategy research

Research date: **30 October 2026**. This record separates material actually read from product claims that could not be checked. It is not evidence of trading profitability or of access to another application's private implementation.

## The Qumatix app supplied by the user

The user supplied this Google Play listing:

- [Google Play — package `com.qexpress.tool`](https://play.google.com/store/apps/details?id=com.qexpress.tool&pcampaignid=web_share)

A normal HTTPS request to the same listing, with English language selected, was attempted with TLS verification enabled. The cloud egress proxy rejected the tunnel with **HTTP 403**, before a Google Play response was obtained. No dedicated web-search/browser research connector was available in this task.

Consequently, the following remain **unverified**:

- The current listing title, developer, version, update date, screenshots, supported brokers and feature descriptions.
- Which strategies the app actually implements, its indicator parameters, its entry/exit rules or its historical/live performance.
- Any claims about its internal algorithms, accuracy, proprietary code, account integration or signal generation.

The package identifier above comes from the user's URL, not from a successful store lookup. This report does not attribute the new strategies to Qumatix, claim to reproduce Qumatix, or infer its features from similarly named sites. Completing product-specific research requires readable public listing material or working authorized access to `play.google.com`; a proxy rejection does not establish that the app or listing is unavailable to the public.

No app binary was downloaded, decompiled or used to extract private endpoints. No credentials, paid content or broker orders were involved.

## Sources successfully retrieved

The official **TA-Lib** public repository was accessible through normal verified HTTPS. Its native Git `HEAD` was read successfully and resolved to:

```text
ccd3172940ed1d9daa4e7197f2265810852e8910
```

The following references are pinned to that revision rather than a moving branch:

1. [Official TA-Lib project description](https://github.com/TA-Lib/ta-lib/blob/ccd3172940ed1d9daa4e7197f2265810852e8910/README.md). The retrieved README describes a technical-analysis library with over 200 indicators, including ADX, MACD, RSI, Stochastic and Bollinger Bands. The number of functions in a library is not a number of validated trading strategies.
2. [Official function metadata](https://github.com/TA-Lib/ta-lib/blob/ccd3172940ed1d9daa4e7197f2265810852e8910/ta_func_api.xml). The XML was retrieved in full and parsed. It specifies names, input data, parameter defaults, bounds and output types for the indicators below.
3. [RSI reference implementation](https://github.com/TA-Lib/ta-lib/blob/ccd3172940ed1d9daa4e7197f2265810852e8910/src/ta_func/ta_RSI.c).
4. [MACD reference implementation](https://github.com/TA-Lib/ta-lib/blob/ccd3172940ed1d9daa4e7197f2265810852e8910/src/ta_func/ta_MACD.c).
5. [Bollinger Bands reference implementation](https://github.com/TA-Lib/ta-lib/blob/ccd3172940ed1d9daa4e7197f2265810852e8910/src/ta_func/ta_BBANDS.c).
6. [ADX reference implementation](https://github.com/TA-Lib/ta-lib/blob/ccd3172940ed1d9daa4e7197f2265810852e8910/src/ta_func/ta_ADX.c).
7. [ATR reference implementation](https://github.com/TA-Lib/ta-lib/blob/ccd3172940ed1d9daa4e7197f2265810852e8910/src/ta_func/ta_ATR.c).

The metadata and project description support the availability and input requirements of standard technical indicators. They do **not** prove that a particular combination earns money, establish the behavior of Qumatix, or certify this app's independently implemented calculations as numerically identical to TA-Lib. Such parity requires explicit comparison tests; matching an indicator name is insufficient.

Retrieved artifact identity (SHA-256):

| Pinned artifact | SHA-256 |
|---|---|
| `ta_func_api.xml` | `b9d2cd5c91511c78eb471202b4adfee15f213e82b02f7232fe3f892814ae6a45` |
| `README.md` | `652e2dffb3430c078233d499b00b1bac25bc06cee28767360a7deff366b5757d` |
| `ta_RSI.c` | `3615579001c957bb0056ef2e074aa39492690bc763aef5a6624d7b0eec05ac77` |
| `ta_MACD.c` | `fcc83a0aa98f3e3fb48b4c78e707564abf0f67dd70955539e968101782cd4393` |
| `ta_BBANDS.c` | `eaa02bada44dfff5f73734f555b4e74fc08f62148769879b17107cd4201b787c` |
| `ta_ADX.c` | `ec1b4bc9891e1d8d9f368244953e1893a6d714735d3a90f40e3620ae356cd7ed` |
| `ta_ATR.c` | `aa70876d7158be94d58fb4637e983a180ae3c992a297151acd6978c25f071174` |

## Indicator families supported by the public metadata

Defaults below are TA-Lib metadata defaults, **not** a claim that every application uses them or that they are optimal. An app may deliberately choose different bounded parameters if it records that choice in its rule version and research provenance.

| Indicator | Verified inputs | Metadata defaults / useful distinction |
|---|---|---|
| RSI | Price series | Period 14; oscillator values alone are not an execution rule. |
| MACD | Price series | Fast 12, slow 26, signal 9; crossover, zero-line and trend-filter rules are separate hypotheses. |
| CCI | High, low, close | Period 14; an app's prior period-20 rule must be disclosed as that app's setting. |
| SMA / EMA | Price series | Period 30 in the abstract interface; crossovers require at least two explicit periods. |
| Stochastic | High, low, close | Fast K 5, slow K 3, slow D 3; smoothing choices matter. |
| Stochastic RSI | Price series | RSI 14, fast K 5, fast D 3; not equivalent to ordinary Stochastic. |
| Williams %R | High, low, close | Period 14. |
| ROC / Momentum | Price series | Period 10; ROC is percentage change and Momentum is a price difference. |
| ADX / +DI / −DI | High, low, close | Period 14; ADX measures directional strength rather than trade direction by itself. |
| ATR | High, low, close | Period 14; a volatility measure, not an independent buy/sell prediction. |
| Bollinger Bands | Price series | Period 20, upper/lower deviations 2, simple moving-average type. |
| Aroon | High, low | Period 14; a transparent up/down comparison can form a testable directional rule. |
| Parabolic SAR | High, low | Acceleration 0.02, maximum 0.2; gap and reversal assumptions must be explicit. |
| TRIX | Price series | Period 30; triple-smoothed EMA rate of change. |
| PPO | Price series | Fast 12, slow 26, EMA type by default; normalization differs from MACD. |
| Ultimate Oscillator | High, low, close | Periods 7, 14 and 28. |
| Linear regression slope | Price series | Period 14; sign/crossing thresholds require separate validation. |
| DEMA / TEMA | Price series | Period 30; smoothing alternatives do not independently validate an execution strategy. |

### Data requirements that must not be fabricated

The same official metadata explicitly requires **volume** for Money Flow Index, On Balance Volume, Chaikin A/D and the Chaikin A/D Oscillator. A close-only or OHLC-only feed does not provide that input. VWAP likewise requires an appropriately defined price/volume stream and session boundary.

These volume-dependent features should remain unavailable until authentic, relevant volume is supplied and validated. Constant, random or invented volume must not be substituted. A synthetic instrument's tick count must not be silently relabelled exchange-traded volume.

## Engineering consequences

- Expand the app with independently defined, named indicator rules across trend, momentum, mean-reversion, breakout and volatility families. Record their parameters, warm-up requirements, eligible regimes, rationale and version.
- Use only information available by the signal's closed bar. Any next-bar entry, displaced indicator or rolling high/low must avoid future-data leakage.
- Treat each rule as a research hypothesis. Compare net expectancy, costs, drawdown, sample size and out-of-sample uncertainty; do not select solely by historical win rate.
- Preserve independent train/holdout funding, training-only ranking, walk-forward checks and an honest “no validated strategy” outcome. More indicators do not imply higher accuracy.
- Keep risk approval, calendar controls, account classification, order recovery and live-execution restrictions independent of any strategy or explanatory model.
- Remove the seven Naked Forex interpretations from this app rather than renaming them as new indicator strategies. Prior versions remain available in repository history for a separate future application.

The `ta-lib.org` function-list page and a TradingView help reference were also attempted, but their HTTPS tunnels were blocked by the same cloud proxy policy. Their live content is not counted as retrieved evidence here. The successfully retrieved official GitHub material supplies the methodology references; Qumatix-specific product research remains blocked as described above.
