"""Deterministic, explainable market-condition heuristics on CLOSED OHLC bars.

This module does not forecast returns, infer news from price, or fabricate model
probabilities. News status and freshness must come from an actual external feed.
"""
from __future__ import annotations

import math
import statistics
import time

STRATEGIES = ('kangaroo', 'shadow', 'belt', 'wammie', 'moolah', 'last_kiss', 'trendy_kangaroo')
DEFAULT_THRESHOLDS = {
    'lookback': 50,
    'trend_efficiency': 0.35,
    'range_efficiency': 0.22,
    'trend_displacement_atr': 2.0,
    'high_volatility_pct': 2.5,
    'low_volatility_pct': 0.015,
    'abnormal_range_multiple': 4.0,
    'gap_atr_multiple': 3.0,
}


def _result(regime, reasons, metrics, eligible=(), *, news_state='unavailable'):
    allowed = bool(eligible)
    return {
        'regime': regime, 'classification': regime, 'certainty': 'heuristic',
        'confidence': None, 'reasons': reasons, 'metrics': metrics,
        'trading_allowed': allowed, 'eligible_strategies': list(eligible),
        'suspended_strategies': [s for s in STRATEGIES if s not in eligible],
        'news_state': news_state, 'version': '1.0.0',
        'limitations': ['Price-only heuristic; classifications can be wrong.',
                       'No liquidity, spread, multi-timeframe or economic-calendar inference from OHLC.',
                       'Thresholds require independent historical validation.'],
    }


def classify_regime(rows, *, thresholds=None, news_state='unavailable', require_news=False,
                    now=None, max_age_seconds=None):
    if thresholds is not None and not isinstance(thresholds, dict):
        raise ValueError('Regime thresholds must be an object')
    if not isinstance(require_news, bool):
        raise ValueError('News requirement must be true or false')
    if news_state not in ('unavailable', 'stale', 'fresh', 'restricted'):
        raise ValueError('Unknown economic-calendar status')
    config = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    if thresholds and set(thresholds) - set(DEFAULT_THRESHOLDS):
        raise ValueError('Unknown regime threshold')
    for name, value in config.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError('Regime thresholds must be finite and positive')
    lookback = config['lookback']
    if int(lookback) != lookback or not 20 <= lookback <= 500:
        raise ValueError('Regime lookback must be an integer from 20 to 500')
    lookback = int(lookback)
    if config['range_efficiency'] >= config['trend_efficiency'] or config['trend_efficiency'] > 1:
        raise ValueError('Regime efficiency thresholds must satisfy range < trend <= 1')
    if config['low_volatility_pct'] >= config['high_volatility_pct']:
        raise ValueError('Low-volatility threshold must be below high-volatility threshold')
    if not isinstance(rows, list) or len(rows) < lookback:
        return _result('uncertain', [f'Need at least {lookback} completed bars; new entries suspended.'], {}, news_state=news_state)
    try:
        clean = []
        for row in rows[-lookback - 1:]:
            if not isinstance(row,dict) or any(isinstance(row.get(key),bool) for key in ('open','high','low','close','time')):
                raise ValueError('Invalid candle')
            o, h, l, c = (float(row[key]) for key in ('open', 'high', 'low', 'close'))
            timestamp=float(row['time']);epoch=int(timestamp)
            if timestamp!=epoch or not -62135596800<=epoch<=253370764800:
                raise ValueError('Unsupported timestamp')
            if not all(math.isfinite(v) and 1e-100<=v<=1e100 for v in (o, h, l, c)) or l > min(o, c) or h < max(o, c):
                raise ValueError('Inconsistent candle')
            if clean and epoch <= clean[-1][0]:
                raise ValueError('Unordered bars')
            clean.append((epoch, o, h, l, c))
    except (ValueError, TypeError, KeyError, OverflowError):
        return _result('uncertain', ['Invalid or unordered OHLC data; new entries suspended.'], {}, news_state=news_state)
    if max_age_seconds is not None:
        if isinstance(max_age_seconds,bool) or not isinstance(max_age_seconds,(int,float)) or not math.isfinite(max_age_seconds) or max_age_seconds <= 0:
            raise ValueError('Maximum data age must be positive')
        if now is not None and (isinstance(now,bool) or not isinstance(now,(int,float)) or not math.isfinite(now)):
            raise ValueError('Current time must be finite')
        age = (time.time() if now is None else float(now)) - clean[-1][0]
        if age < 0 or age > max_age_seconds:
            return _result('uncertain', ['Market data is stale or future-dated; new entries suspended.'], {'age_seconds': age}, news_state=news_state)
    if news_state == 'restricted':
        return _result('news_driven_or_abnormal', ['Verified news restriction is active; new entries suspended.'], {}, news_state=news_state)
    if require_news and news_state != 'fresh':
        return _result('uncertain', ['Required economic calendar is unavailable or stale; new entries suspended.'], {}, news_state=news_state)
    closes = [r[4] for r in clean]
    ranges = [max(row[2] - row[3], abs(row[2] - clean[i-1][4]), abs(row[3] - clean[i-1][4]))
              for i, row in enumerate(clean) if i]
    atr = statistics.fmean(ranges[-14:])
    atr_pct = 100 * atr / closes[-1]
    net = closes[-1] - closes[0]
    path = sum(abs(b - a) for a, b in zip(closes, closes[1:]))
    efficiency = abs(net) / path if path else 0.0
    fast = statistics.fmean(closes[-10:])
    slow = statistics.fmean(closes[-30:])
    displacement = (fast - slow) / atr if atr else 0.0
    latest_range = ranges[-1]
    normal_range = statistics.median(ranges[:-1]) if len(ranges) > 1 else atr
    gap = abs(clean[-1][1] - closes[-2])
    metrics = {'atr': round(atr, 10), 'atr_pct': round(atr_pct, 6),
               'directional_efficiency': round(efficiency, 6),
               'ma_displacement_atr': round(displacement, 6),
               'latest_range_multiple': round(latest_range / normal_range, 6) if normal_range else None,
               'gap_atr_multiple': round(gap / atr, 6) if atr else None,
               'last_bar_at': clean[-1][0], 'thresholds': config}
    if (normal_range and latest_range > normal_range * config['abnormal_range_multiple']) or (atr and gap > atr * config['gap_atr_multiple']):
        return _result('news_driven_or_abnormal', ['Abnormal price range or gap; cause unknown, new entries suspended.'], metrics, news_state=news_state)
    if atr_pct >= config['high_volatility_pct']:
        return _result('high_volatility', [f'ATR is {atr_pct:.4f}% of price, above the configured high-volatility limit.'], metrics, news_state=news_state)
    if atr_pct <= config['low_volatility_pct']:
        return _result('low_volatility', [f'ATR is {atr_pct:.4f}% of price, below the configured minimum movement.'], metrics, news_state=news_state)
    if efficiency >= config['trend_efficiency'] and abs(displacement) >= config['trend_displacement_atr']:
        state = 'trending_up' if displacement > 0 else 'trending_down'
        return _result(state, ['Directional efficiency and fast/slow average displacement exceed configured trend thresholds.'],
                       metrics, ('last_kiss', 'trendy_kangaroo'), news_state=news_state)
    if efficiency <= config['range_efficiency']:
        return _result('ranging', ['Low directional efficiency suggests a range; continuation strategy suspended.'],
                       metrics, ('kangaroo', 'shadow', 'belt', 'wammie', 'moolah', 'last_kiss'), news_state=news_state)
    return _result('uncertain', ['Trend and range rules disagree; new entries suspended.'], metrics, news_state=news_state)
