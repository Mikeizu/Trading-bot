# Seven Naked Forex strategies: reading notes and quantified interpretations

Source: *Naked Forex* (Alex Nekritin and Walter Peters, Wiley, 2012), supplied by the user. The book's chapter numbers are referenced for study. No copyrighted charts or long passages are reproduced. This is **not** a verified exact automation of the authors' discretionary approach.

## Fundamental: confirmed support/resistance areas (Chapter 4)
The book treats zones as **areas rather than single prices**, often established by repeated turning points, with higher timeframes used for confirmation. In v4, `zone_levels()` finds historical 2-candle swing highs/lows, combines nearby levels using a tolerance derived from the median recent candle range, and requires two or more past pivot touches. **Difference:** a skilled human sees visually important zones on much longer history and may use line charts; this mathematical tolerance is a simplified, testable approximation. The program never uses later candles to establish the zone for an earlier test.

## 1. The Last Kiss (Chapter 5, page 73)
**Book:** Price consolidates inside a box, touches both boundaries at least twice, breaks out, retests the edge, and produces a last-kiss candle. Entry is a pending stop beyond that candle; the emergency stop is near the box midpoint and target is the next zone.

**Program:** Uses 24 historical candles to estimate a box with two upper and two lower touches, looks for a close beyond the range, a retest and a rejection candle. The following completed candle must close beyond the pattern's high or low. The v4 fixed-expiry research test does **not** model the book's midpoint stop or zone-target exit. Paper tracking uses a pattern-extreme stop and 2R target instead.

## 2. The Big Shadow (Chapter 6, page 95)
**Book:** Two-candlestick setup; second candle has a higher high and lower low, prints at an important zone, closes strongly near an extreme, and ideally has larger range and room to the left. Entry beyond pattern extreme, stop beyond the other extreme and nearest-zone exit.

**Program:** Requires outside candle, range at least 1.2× recent median, close in upper/lower quarter, and a repeated support/resistance zone. Confirmation on following close.

## 3. Wammies (Chapter 7, page 111)
**Book:** Special double bottom where the second support touch makes a **higher low**. The relationship to the critical zone and confirmation are important.

**Program:** Looks for two swing lows separated by 3–16 candles, the second higher within a tolerance of the first, a repeated support zone and a closing breakout over intervening highs. The extra following close rule is applied. A strict ruleset can miss discretionary textbook examples.

## 4. Moolahs (Chapter 7, page 111)
**Book:** Double-top counterpart to the Wammie, with a **lower second high** at resistance.

**Program:** Looks for two swing highs separated by 3–16 candles, second lower by a bounded amount, historic repeated resistance, and a closing breakdown below intervening lows. Confirms again on next close.

## 5. Kangaroo Tails (Chapter 8, page 131)
**Book:** One-candle long-tail rejection; the open and close are in the top third for bullish setups and bottom third for bearish setups. It should print at a zone and ideally exceed surrounding candle ranges, with ample space to the left.

**Program:** The wick must cover at least 58% of the candle range, open/close be in the appropriate third, at least 85% of median recent candle range, and touch a historic zone. Human 'room to left' assessment is not precisely duplicated.

## 6. The Big Belt (Chapter 9, page 151)
**Book:** One substantial directional candle with open near one extreme, close near the other, at an important zone. Entry and stop beyond opposite candle extremes, next-zone target. Some bearish examples involve a higher opening gap.

**Program:** Body covers >=70% of candle, total range >=1.45× median, open and close are near opposing extremes, and wick tests a repeated zone. Gap and market-context distinctions are simplified.

## 7. Trendy Kangaroo (Chapter 10, page 163)
**Book:** After an established trend pauses for roughly 3–10 candles, a kangaroo tail extends beyond the small consolidation in the direction of trend continuation. This is different from a zone-reversal Kangaroo Tail.

**Program:** Tests previous 20-bar direction, six quiet range-bound candles, and a rejection tail extending out of that range. The rule is a mechanical approximation of discretionary trend identification.

## Backtesting and position management (Chapters 3, 11 and 16)
The book warns about hindsight bias, overfitting and the need for substantial testing and meaningful exits/risk management. The v4 research model has chronological held-out analysis and rejects future information in setup detection. **Two distinct simulated exit models are present:**

- **Research backtester:** a theoretical short-expiry **directional options payout**, based on a manually assumed payout. Entry occurs at the next open after a confirmation close, and exit is at a fixed number of bars. No stop/zone-target is used; this is not a faithful simulation of a long forex trade.
- **Broker-candle paper positions:** after a confirmed candle, create a virtual position at its close, stop beyond the signal pattern extreme, take profit at fixed **2R**, and risk 1% of paper equity. Conservative stop-first treatment if stop and target fall in the same candle. This **does not reproduce** the authors' nearest-zone targets or trailing/running exits and has no spreads/financing/slippage.

**No optimization is provided to 'force' a 65% win rate.** A score only counts if it appears in an adequate out-of-sample set under fixed assumptions, and even then real-world earning power is unverified.

## When to use each timeframe

- **Scalping (1m/5m):** quantized variations of these patterns; the book does *not* validate the app's exact rules on every ultra-short timeframe.
- **Intraday (15m/1h):** short-term analysis of repeated zones and wick patterns.
- **Swing (4h/1d):** closer to many of the book's examples; paper positions can run through multiple sessions.
- **Long term (1w/1mo):** weekly/monthly pattern scans using broker daily OHLC aggregation, with virtual stop/target positions; **no claim of real long-held broker orders**.

For actual long-held forex/CFD positions, a separate officially authorized Deriv MT5 implementation and broker-supported stops, sizing, execution acknowledgements, reconciliation and financing adjustments would be required. This v4 package does **not** contain that integration.
