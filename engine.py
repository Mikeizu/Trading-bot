"""MIKEIZU TradeLab PRO: deterministic indicators and paper-trading engine.

NO live broker execution, live prices, profit prediction or broker affiliation.
"""
from __future__ import annotations
import math
from statistics import fmean, pstdev


def _period(value):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value < 1 or int(value)!=value:
        raise ValueError('period must be a positive integer')
    return int(value)


def _series(values, *, allow_none=False):
    if not isinstance(values,(list,tuple)):
        raise ValueError('values must be a sequence')
    out=[]
    for value in values:
        if value is None and allow_none:
            out.append(None);continue
        if isinstance(value,bool):raise ValueError('Indicator values must be finite numbers')
        try:number=float(value)
        except (ValueError,TypeError,OverflowError):raise ValueError('Indicator values must be finite numbers') from None
        if not math.isfinite(number) or abs(number)>1e100:
            raise ValueError('Indicator values exceed the supported finite numerical range')
        out.append(number)
    return out


def ema(values, period):
    period=_period(period);values=_series(values,allow_none=True)
    out = []
    last = None
    mult = 2 / (period + 1)
    for v in values:
        if v is None:
            out.append(None)
        else:
            last = float(v) if last is None else float(v) * mult + last * (1 - mult)
            out.append(last)
    return out


def sma(values, period):
    period=_period(period);values=_series(values)
    return [None if i < period - 1 else fmean(values[i-period+1:i+1]) for i in range(len(values))]


def rsi(values, period=14):
    period=_period(period);values=_series(values)
    out = [None] * len(values)
    if len(values) <= period: return out
    gains = [max(values[i]-values[i-1], 0) for i in range(1, len(values))]
    losses = [max(values[i-1]-values[i], 0) for i in range(1, len(values))]
    avg_gain, avg_loss = fmean(gains[:period]), fmean(losses[:period])
    def calc(g, l): return 50.0 if g == 0 and l == 0 else (100.0 if l == 0 else 100 - (100/(1+g/l)))
    out[period] = calc(avg_gain, avg_loss)
    for i in range(period+1, len(values)):
        avg_gain = (avg_gain*(period-1) + gains[i-1])/period
        avg_loss = (avg_loss*(period-1) + losses[i-1])/period
        out[i] = calc(avg_gain, avg_loss)
    return out


def indicators(candles):
    from naked_strategies import candles_valid
    candles=candles_valid(candles)
    closes = [float(c['close']) for c in candles]
    e12, e26 = ema(closes, 12), ema(closes, 26)
    macd = [a-b for a,b in zip(e12, e26)]
    sig = ema(macd, 9)
    cci, upper, lower, stoch = [], [], [], []
    for i in range(len(candles)):
        if i >= 19:
            window = candles[i-19:i+1]
            typical = [(float(x['high']) + float(x['low']) + float(x['close']))/3 for x in window]
            mean = fmean(typical)
            dev = fmean([abs(v-mean) for v in typical])
            cci.append((typical[-1]-mean)/(0.015*dev) if dev else 0.0)
            s = pstdev(closes[i-19:i+1])
            # Bollinger bands are centred on CLOSES even when close variance is
            # zero. CCI's typical-price mean can differ due to asymmetric wicks.
            close_mean=fmean(closes[i-19:i+1])
            upper.append(close_mean + 2*s)
            lower.append(close_mean - 2*s)
        else:
            cci.append(None); upper.append(None); lower.append(None)
        if i >= 13:
            recent = candles[i-13:i+1]
            hi = max(float(x['high']) for x in recent)
            lo = min(float(x['low']) for x in recent)
            stoch.append(100*(closes[i]-lo)/(hi-lo) if hi > lo else 50)
        else: stoch.append(None)
    return {'rsi':rsi(closes), 'macd':macd, 'macd_signal':sig,
            'cci':cci, 'sma_fast':sma(closes, 8), 'sma_slow':sma(closes, 21),
            'bb_upper':upper, 'bb_lower':lower, 'stoch':stoch}


def signal_at(candles, values, idx, strategy):
    if not isinstance(strategy,str) or strategy.upper() not in ('RSI','MACD','CCI','SMA','BOLLINGER','STOCHASTIC'):
        raise ValueError('Unsupported indicator')
    if isinstance(idx,bool) or not isinstance(idx,int) or not 0<=idx<len(candles):
        raise ValueError('Signal index is outside candle history')
    if not isinstance(values,dict):raise ValueError('Indicator values must be an object')
    if idx < 35: return None
    name = strategy.upper()
    def v(key, at):
        sequence=values.get(key)
        if not isinstance(sequence,(list,tuple)) or len(sequence)!=len(candles):
            raise ValueError('Indicator series does not match candle history')
        result=sequence[at]
        return None if result is None else _series([result])[0]
    if name == 'RSI':
        current, prior = v('rsi',idx), v('rsi',idx-1)
        if prior is not None and current is not None:
            if prior < 30 <= current: return 'UP'
            if prior > 70 >= current: return 'DOWN'
    elif name == 'MACD':
        a,b,c,d=v('macd',idx-1),v('macd_signal',idx-1),v('macd',idx),v('macd_signal',idx)
        if any(value is None for value in (a,b,c,d)):return None
        prev = a-b
        curr = c-d
        if prev <= 0 < curr: return 'UP'
        if prev >= 0 > curr: return 'DOWN'
    elif name == 'CCI':
        prev, curr = v('cci',idx-1),v('cci',idx)
        if prev is not None and curr is not None:
            if prev < -100 <= curr: return 'UP'
            if prev > 100 >= curr: return 'DOWN'
    elif name == 'SMA':
        p, q = v('sma_fast',idx-1), v('sma_slow',idx-1)
        a, b = v('sma_fast',idx), v('sma_slow',idx)
        if all(x is not None for x in (p,q,a,b)):
            if p <= q and a > b: return 'UP'
            if p >= q and a < b: return 'DOWN'
    elif name == 'BOLLINGER':
        top, bottom = v('bb_upper',idx), v('bb_lower',idx)
        close = float(candles[idx]['close'])
        if top is not None and bottom is not None:
            if close < bottom: return 'UP'
            if close > top: return 'DOWN'
    elif name == 'STOCHASTIC':
        p, cur = v('stoch',idx-1), v('stoch',idx)
        if p is not None and cur is not None:
            if p < 20 <= cur: return 'UP'
            if p > 80 >= cur: return 'DOWN'
    else:
        raise ValueError('Unsupported indicator')
    return None


def backtest(candles, strategy='RSI', stake=10, duration=3, payout=.8, initial_balance=10000,
             *, commission_per_trade=0.0, spread_bps=1.0, slippage_bps=.5):
    """Indicator research at NEXT bar open, with disclosed hypothetical costs.

    Fixed-expiry options outcome only: not CFD execution, actual broker payouts,
    or an independently validated strategy. Trades never overlap.
    """
    from naked_strategies import candles_valid
    from research_analytics import performance_metrics, dataset_provenance
    if not isinstance(candles,list):raise ValueError('Candles must be a list')
    if len(candles) < 60: raise ValueError('At least 60 candles required for a backtest')
    cleaned=candles_valid(candles)
    for name,value in {'duration':duration,'stake':stake,'payout':payout,'initial_balance':initial_balance,
                       'commission_per_trade':commission_per_trade,'spread_bps':spread_bps,'slippage_bps':slippage_bps}.items():
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
            raise ValueError(name+' must be finite')
    if not (1 <= duration <= 20 and int(duration)==duration): raise ValueError('Invalid duration')
    duration=int(duration)
    if not (.1 <= payout <= 1): raise ValueError('Invalid payout')
    if not (1 <= stake <= 100000): raise ValueError('Invalid stake')
    if not (100<=initial_balance<=1_000_000_000):raise ValueError('Invalid initial balance')
    if not (0<=commission_per_trade<=stake and 0<=spread_bps<=100 and 0<=slippage_bps<=100):
        raise ValueError('Invalid transaction cost assumptions')
    if not isinstance(strategy,str) or strategy.upper() not in ('RSI','MACD','CCI','SMA','BOLLINGER','STOCHASTIC'):
        raise ValueError('Unsupported indicator')
    values = indicators(cleaned)
    balance = float(initial_balance)
    trades, equity = [], []
    interval=min(b['time']-a['time'] for a,b in zip(cleaned,cleaned[1:]))
    skipped_gaps=0
    idx = 35
    price_cost=(spread_bps/2+slippage_bps)/10000
    while idx + duration < len(cleaned):
        side = signal_at(cleaned, values, idx, strategy)
        if side and stake+commission_per_trade <= balance and stake <= balance * .05:
            if any(cleaned[j+1]['time']-cleaned[j]['time']!=interval for j in range(idx,idx+duration)):
                skipped_gaps+=1;idx+=1;continue
            direction=1 if side=='UP' else -1
            # Confirmation is only known after bar idx closes; next OPEN is the
            # earliest modeled entry. Exit is the final holding bar's close.
            entry = cleaned[idx+1]['open']*(1+direction*price_cost)
            exit_price = cleaned[idx+duration]['close']*(1-direction*price_cost)
            contract_win = (exit_price-entry)*direction>0
            gross=stake*payout if contract_win else -stake
            pnl = round(gross-commission_per_trade,6)
            balance = round(balance + pnl,6)
            trades.append({'index':idx,'entry_index':idx+1,'exit_index':idx+duration,
                           'time':cleaned[idx]['time'],'entered_at':cleaned[idx+1]['time'],
                           'exited_at':cleaned[idx+duration]['time']+interval,'holding_seconds':duration*interval,
                           'side':side,'entry':entry,'exit':exit_price,'pnl':pnl,
                           'gross_pnl':gross,'commission':commission_per_trade,'stake':stake,
                           'contract_win':contract_win,'win':pnl>0,'balance':balance,
                           'asset':candles[idx].get('asset','CSV'),'result_kind':'historical_simulation'})
            equity.append({'x':idx+duration,'y':balance})
            idx += duration+1
        else: idx += 1
    metrics=performance_metrics(trades,initial_balance,period_seconds=cleaned[-1]['time']-cleaned[0]['time']+interval)
    costs={'commission_per_trade':commission_per_trade,'spread_bps':spread_bps,'slippage_bps':slippage_bps}
    return {'trades':trades,'trade_count':len(trades),'wins':metrics['wins'],
            'losses':metrics['losses'],'breakeven_trades':metrics['breakeven_trades'],
            'win_rate':metrics['win_rate_pct'] if trades else 0,
            'net_pnl':metrics['pnl'],'ending_balance':metrics['ending_balance'],
            'max_drawdown_pct':metrics['max_drawdown_pct'],'equity':equity,
            'metrics':metrics,'costs':costs,
            'data_integrity':{'inferred_bar_interval_seconds':interval,'missing_holding_bars_skipped':skipped_gaps,
                              'interval_method':'Smallest supplied candle interval; no broker session calendar was provided.'},
            'provenance':dataset_provenance(cleaned,source='local_simulator_or_user_CSV',configuration={
                'strategy':strategy,'stake':stake,'duration_bars':duration,'payout':payout,
                'initial_balance':initial_balance,'costs':costs}),
            'note':'Hypothetical options results using next-bar-open entries and assumed costs. No actual broker payouts, financing, latency, liquidity or partial-fill model. Not live performance or a profit forecast.'}
