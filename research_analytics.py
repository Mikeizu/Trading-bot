"""Auditable analytics for simulations, never a source of broker performance.

Ratios use closed-trade observations; there is no fabricated annualized Sharpe
or intrabar mark-to-market equity when those observations are unavailable.
"""
from __future__ import annotations

import hashlib
import json
import math
import statistics

STRATEGY_VERSION = '3.0.0'


def wilson_interval(wins, count, z=1.96):
    if (isinstance(wins,bool) or isinstance(count,bool) or not isinstance(wins,int) or not isinstance(count,int)
            or not 0<=wins<=count or count<0 or isinstance(z,bool) or not isinstance(z,(int,float))
            or not math.isfinite(z) or not 0<z<=10):
        raise ValueError('Wilson interval requires valid counts and a finite positive z score')
    if not count:
        return None, None
    p = wins / count
    denominator = 1 + z * z / count
    center = (p + z * z / (2 * count)) / denominator
    radius = z * math.sqrt((p * (1 - p) + z * z / (4 * count)) / count) / denominator
    return round(100 * max(0, center - radius), 4), round(100 * min(1, center + radius), 4)


def performance_metrics(trades, starting_balance=1000.0, *, period_seconds=None):
    def numeric(value,name,*,minimum=None):
        if isinstance(value,bool):raise ValueError(name+' must be a finite number')
        try:result=float(value)
        except (TypeError,ValueError,OverflowError):raise ValueError(name+' must be a finite number') from None
        if not math.isfinite(result) or abs(result)>1e100 or (minimum is not None and result<minimum):
            raise ValueError(name+' is outside the supported numerical range')
        return result
    if not isinstance(trades,list) or len(trades)>100000:raise ValueError('Trade observations must be a bounded list')
    starting_balance = numeric(starting_balance,'Starting balance',minimum=1e-100)
    if starting_balance <= 0:
        raise ValueError('Starting balance must be finite and positive')
    if period_seconds is not None:period_seconds=numeric(period_seconds,'Period duration',minimum=1e-100)
    clean=[]
    for trade in trades:
        if not isinstance(trade,dict) or 'pnl' not in trade:raise ValueError('Each trade requires a finite P&L')
        clean.append({**trade,'pnl':numeric(trade['pnl'],'Trade P&L'),
            'holding_seconds':numeric(trade.get('holding_seconds',0),'Holding duration',minimum=0),
            'commission':numeric(trade.get('commission',0),'Commission',minimum=0),
            'stake':numeric(trade.get('stake',0),'Stake',minimum=0)})
    trades=clean
    equity = peak = starting_balance
    max_dd = max_dd_pct = 0.0
    wins = losses = longest_win = longest_loss = win_streak = loss_streak = 0
    equity_curve = [round(equity, 6)]
    drawdown_curve = [0.0]
    returns = []
    positive, negative = [], []
    for trade in trades:
        pnl = float(trade['pnl'])
        if not math.isfinite(pnl):
            raise ValueError('Non-finite trade P&L')
        returns.append(pnl / equity if equity > 0 else 0.0)
        equity += pnl
        peak = max(peak, equity)
        dd = peak - equity
        dd_pct = 100 * dd / peak if peak else 0.0
        max_dd = max(max_dd, dd)
        max_dd_pct = max(max_dd_pct, dd_pct)
        equity_curve.append(round(equity, 6))
        drawdown_curve.append(round(dd_pct, 6))
        if pnl > 0:
            wins += 1
            positive.append(pnl)
            win_streak += 1
            loss_streak = 0
        elif pnl < 0:
            losses += 1
            negative.append(pnl)
            loss_streak += 1
            win_streak = 0
        else:
            win_streak = loss_streak = 0
        longest_win = max(longest_win, win_streak)
        longest_loss = max(longest_loss, loss_streak)
    count = len(trades)
    pnl = equity - starting_balance
    lower, upper = wilson_interval(wins, count)
    profit, loss = sum(positive), -sum(negative)
    variance = statistics.pstdev(returns) if len(returns) > 1 else 0.0
    duration = sum(max(0, float(t.get('holding_seconds', 0))) for t in trades)
    costs = sum(float(t.get('commission', 0.0)) for t in trades)
    result = {
        'starting_balance':starting_balance,
        'trades': count, 'wins': wins, 'losses': losses,
        'breakeven_trades': count - wins - losses,
        'win_rate_pct': round(100 * wins / count, 4) if count else None,
        'loss_rate_pct': round(100 * losses / count, 4) if count else None,
        'wilson_lower_95_pct': lower, 'wilson_upper_95_pct': upper,
        'pnl': round(pnl, 6), 'roi_pct': round(100 * pnl / starting_balance, 6),
        'ending_balance': round(equity, 6),
        'average_winning_trade': round(statistics.fmean(positive), 6) if positive else None,
        'average_losing_trade': round(statistics.fmean(negative), 6) if negative else None,
        'profit_factor': round(profit / loss, 6) if loss else None,
        'profit_factor_note': 'Undefined when there are no losing trades; not infinity or proof of an edge.',
        'expected_value_per_trade': round(pnl / count, 6) if count else None,
        'max_drawdown': round(max_dd, 6), 'max_drawdown_pct': round(max_dd_pct, 6),
        'recovery_factor': round(pnl / max_dd, 6) if max_dd else None,
        'risk_adjusted_return': round(statistics.fmean(returns) / variance * math.sqrt(count), 6) if variance else None,
        'risk_adjusted_return_method': 'Unannualized mean closed-trade equity return / population standard deviation × sqrt(trades). Not a calendar Sharpe ratio.',
        'exposure_pct': round(min(100.0, 100 * duration / period_seconds), 6) if period_seconds else None,
        'stake_turnover': round(sum(float(t.get('stake', 0.0)) for t in trades) / starting_balance, 6),
        'trading_costs': round(costs, 6),
        'trading_costs_note': 'Explicit commissions; price spread/slippage affect outcome prices. Financing, partial fills, liquidity and real contract quotations are not modeled.',
        'longest_winning_streak': longest_win, 'longest_losing_streak': longest_loss,
        'equity_curve': equity_curve, 'drawdown_curve': drawdown_curve,
        'equity_method': 'Closed-trade equity; intrabar mark-to-market drawdown is unavailable.',
    }
    def check_finite(value):
        if isinstance(value,float) and not math.isfinite(value):raise ValueError('Derived analytics exceed supported numerical range')
        if isinstance(value,dict):
            for item in value.values():check_finite(item)
        elif isinstance(value,list):
            for item in value:check_finite(item)
    check_finite(result)
    return result


def dataset_provenance(rows, *, source='unspecified', instrument=None, timeframe=None, configuration=None):
    canonical = json.dumps(rows, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    config = configuration or {}
    encoded_config = json.dumps(config, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    return {
        'source': str(source), 'instrument': instrument, 'timeframe': timeframe,
        'dataset_sha256': hashlib.sha256(canonical).hexdigest(),
        'configuration_sha256': hashlib.sha256(encoded_config).hexdigest(),
        'first_bar_at': rows[0]['time'] if rows else None,
        'last_bar_at': rows[-1]['time'] if rows else None, 'bars': len(rows),
        'strategy_version': STRATEGY_VERSION, 'configuration': config,
        'result_kind': 'historical_simulation',
        'warning': 'Dataset identity is reproducible; it does not authenticate the supplier or validate market quality. Reusing this holdout to tune parameters invalidates untouched-test claims.',
    }
