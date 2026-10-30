"""MIKEIZU TradeLab PRO: deterministic indicators and paper-trading engine.

NO live broker execution, live prices, profit prediction or broker affiliation.
"""
from __future__ import annotations
import math
from statistics import fmean, pstdev


def _period(value):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not 1<=value<=10000 or not math.isfinite(value) or int(value)!=value:
        raise ValueError('period must be an integer from 1 to 10000')
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


def _wilder(values, period):
    period=_period(period);out=[];seed=[];last=None
    for value in values:
        if value is None:out.append(None);continue
        if last is None:
            seed.append(value)
            if len(seed)<period:out.append(None);continue
            last=fmean(seed[-period:])
        else:last=(last*(period-1)+value)/period
        out.append(last)
    return out


def _rolling_mid(highs,lows,period):
    return [None if i<period-1 else (max(highs[i-period+1:i+1])+min(lows[i-period+1:i+1]))/2 for i in range(len(highs))]


def _dmi(rows,period):
    tr=[None];up=[None];down=[None]
    for i in range(1,len(rows)):
        row,prior=rows[i],rows[i-1]
        tr.append(max(row['high']-row['low'],abs(row['high']-prior['close']),abs(row['low']-prior['close'])))
        positive=row['high']-prior['high'];negative=prior['low']-row['low']
        up.append(positive if positive>negative and positive>0 else 0.)
        down.append(negative if negative>positive and negative>0 else 0.)
    if not rows:return [],[],[],[]
    atr=_wilder(tr,period);u=_wilder(up,period);d=_wilder(down,period)
    plus=[None if a is None else 100*b/a if a else 0. for a,b in zip(atr,u)]
    minus=[None if a is None else 100*b/a if a else 0. for a,b in zip(atr,d)]
    dx=[None if a is None else 100*abs(a-b)/(a+b) if a+b else 0. for a,b in zip(plus,minus)]
    return atr,plus,minus,_wilder(dx,period)


def _supertrend(rows,atr,multiple):
    upper=lower=None;direction=None;out=[];directions=[]
    for i,row in enumerate(rows):
        if atr[i] is None:
            out.append(None);directions.append(None);continue
        middle=(row['high']+row['low'])/2
        base_upper=middle+multiple*atr[i];base_lower=middle-multiple*atr[i]
        if upper is None:
            upper,lower=base_upper,base_lower
            direction=1 if row['close']>=middle else -1
        else:
            prior_close=rows[i-1]['close']
            upper=base_upper if base_upper<upper or prior_close>upper else upper
            lower=base_lower if base_lower>lower or prior_close<lower else lower
            if direction<0 and row['close']>upper:direction=1
            elif direction>0 and row['close']<lower:direction=-1
        out.append(lower if direction>0 else upper);directions.append(direction)
    return out,directions


def indicators(candles,parameters=None):
    """Causal OHLC indicators, with one value per supplied closed bar.

    Pass validate_parameters(strategy, overrides) when using configured rules.
    Default vectors include separate pullback/triple-EMA/Supertrend settings so
    a default catalog strategy also works with shared default indicator data.
    """
    from market_data import candles_valid
    from indicator_strategies import PERIODS,STRATEGIES
    if parameters is not None and not isinstance(parameters,dict):raise ValueError('Indicator parameters must be an object')
    parameters=parameters or {}
    allowed={key for entry in STRATEGIES.values() for key in entry['parameters']}
    if set(parameters)-allowed:raise ValueError('Unknown indicator parameter')
    for key,value in parameters.items():
        if isinstance(value,bool) or not isinstance(value,(int,float)) or abs(value)>1e100 or not math.isfinite(value):raise ValueError('Indicator parameters must be finite')
        if key in PERIODS:
            spec=PERIODS[key]
            if not spec['min']<=value<=spec['max'] or (spec['type']=='int' and value!=int(value)):raise ValueError('Invalid '+key)
    def p(key,default=None):return parameters.get(key,PERIODS[key]['default'] if default is None else default)
    rows=candles_valid(candles);count=len(rows)
    closes=[c['close'] for c in rows];highs=[c['high'] for c in rows];lows=[c['low'] for c in rows]
    efast=ema(closes,p('macd_fast'));eslow=ema(closes,p('macd_slow'))
    macd=[a-b for a,b in zip(efast,eslow)];sig=ema(macd,p('macd_signal_period'))
    cci=[];upper=[];lower=[];width=[];stoch=[];williams=[];roc=[];momentum=[];aroon_up=[];aroon_down=[]
    bb=int(p('bb_period'));cp=int(p('cci_period'));sp=int(p('stoch_period'));wp=int(p('williams_period'))
    rp=int(p('roc_period'));mp=int(p('momentum_period'));ap=int(p('aroon_period'))
    for i,row in enumerate(rows):
        if i>=cp-1:
            typical=[(c['high']+c['low']+c['close'])/3 for c in rows[i-cp+1:i+1]]
            mean=fmean(typical);dev=fmean(abs(v-mean) for v in typical)
            cci.append((typical[-1]-mean)/(.015*dev) if dev else 0.)
        else:cci.append(None)
        if i>=bb-1:
            window=closes[i-bb+1:i+1];middle=fmean(window);spread=pstdev(window)*p('bb_deviations')
            upper.append(middle+spread);lower.append(middle-spread);width.append(200*spread/middle)
        else:upper.append(None);lower.append(None);width.append(None)
        if i>=sp-1:
            hi=max(highs[i-sp+1:i+1]);lo=min(lows[i-sp+1:i+1]);stoch.append(100*(closes[i]-lo)/(hi-lo) if hi>lo else 50.)
        else:stoch.append(None)
        if i>=wp-1:
            hi=max(highs[i-wp+1:i+1]);lo=min(lows[i-wp+1:i+1]);williams.append(-100*(hi-closes[i])/(hi-lo) if hi>lo else -50.)
        else:williams.append(None)
        roc.append(100*(closes[i]/closes[i-rp]-1) if i>=rp else None)
        momentum.append(closes[i]-closes[i-mp] if i>=mp else None)
        if i>=ap:
            # Last occurrence wins ties; ages are bounded 0..period.
            hi=max(range(i-ap,i+1),key=lambda j:(highs[j],j));lo=min(range(i-ap,i+1),key=lambda j:(lows[j],-j))
            aroon_up.append(100*(ap-(i-hi))/ap);aroon_down.append(100*(ap-(i-lo))/ap)
        else:aroon_up.append(None);aroon_down.append(None)
    rs=rsi(closes,p('rsi_period'));srp=int(p('stoch_rsi_period'));stoch_rs=[]
    for i,current in enumerate(rs):
        block=rs[max(0,i-srp+1):i+1]
        if len(block)<srp or None in block:stoch_rs.append(None)
        else:
            hi,lo=max(block),min(block);stoch_rs.append(100*(current-lo)/(hi-lo) if hi>lo else 50.)
    lag=int(p('accel_period'))
    acceleration=[None if i<lag or momentum[i] is None or momentum[i-lag] is None else momentum[i]-momentum[i-lag] for i in range(count)]
    atr,_,_,_=_dmi(rows,int(p('atr_period')))
    _,plus_di,minus_di,adx=_dmi(rows,int(p('adx_period')))
    keltner=ema(closes,p('keltner_period'));km=parameters.get('atr_multiple',2.)
    ku=[None if a is None else k+km*a for k,a in zip(keltner,atr)]
    kl=[None if a is None else k-km*a for k,a in zip(keltner,atr)]
    channel=int(p('channel_period'))
    du=[None if i<channel else max(highs[i-channel:i]) for i in range(count)]
    dl=[None if i<channel else min(lows[i-channel:i]) for i in range(count)]
    tenkan=_rolling_mid(highs,lows,int(p('tenkan_period')));kijun=_rolling_mid(highs,lows,int(p('kijun_period')))
    span_b=_rolling_mid(highs,lows,int(p('senkou_period')))
    span_a=[None if a is None or b is None else (a+b)/2 for a,b in zip(tenkan,kijun)]
    displacement=int(p('cloud_displacement'))
    cloud_a=[None if i<displacement else span_a[i-displacement] for i in range(count)]
    cloud_b=[None if i<displacement else span_b[i-displacement] for i in range(count)]
    st_atr,_,_,_=_dmi(rows,int(parameters.get('atr_period',10)))
    supertrend,st_direction=_supertrend(rows,st_atr,parameters.get('atr_multiple',3.))
    return {'rsi':rs,'macd':macd,'macd_signal':sig,'cci':cci,
            'sma_fast':sma(closes,p('sma_fast_period')),'sma_slow':sma(closes,p('sma_slow_period')),
            'bb_upper':upper,'bb_lower':lower,'bb_width_pct':width,'stoch':stoch,
            'ema_fast':ema(closes,p('ema_fast_period')),'ema_slow':ema(closes,p('ema_slow_period')),
            'ema_mid':ema(closes,p('ema_mid_period')),'pullback_ema':ema(closes,parameters.get('ema_fast_period',20)),
            'triple_fast':ema(closes,parameters.get('ema_fast_period',9)),
            'triple_mid':ema(closes,parameters.get('ema_mid_period',21)),
            'triple_slow':ema(closes,parameters.get('ema_slow_period',50)),
            'trend_ema':ema(closes,p('trend_period')),'stoch_rsi':stoch_rs,'williams_r':williams,
            'roc':roc,'momentum':momentum,'momentum_accel':acceleration,
            'atr':atr,'plus_di':plus_di,'minus_di':minus_di,'adx':adx,
            'keltner_upper':ku,'keltner_lower':kl,'donchian_upper':du,'donchian_lower':dl,
            'supertrend':supertrend,'supertrend_direction':st_direction,'supertrend_atr':st_atr,
            'tenkan':tenkan,'kijun':kijun,'cloud_a':cloud_a,'cloud_b':cloud_b,
            'aroon_up':aroon_up,'aroon_down':aroon_down}


def signal_at(candles, values, idx, strategy, parameters=None):
    from indicator_strategies import evaluate_signal
    return evaluate_signal(candles,values,idx,strategy,parameters)['side']


def backtest(candles, strategy='RSI', stake=10, duration=3, payout=.8, initial_balance=10000,
             *, commission_per_trade=0.0, spread_bps=1.0, slippage_bps=.5,parameters=None):
    """Indicator research at NEXT bar open, with disclosed hypothetical costs.

    Fixed-expiry options outcome only: not CFD execution, actual broker payouts,
    or an independently validated strategy. Trades never overlap.
    """
    from market_data import candles_valid
    from indicator_strategies import STRATEGIES,validate_parameters,warmup_bars,STRATEGY_VERSION
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
    if not isinstance(strategy,str) or strategy.upper() not in STRATEGIES:
        raise ValueError('Unsupported indicator')
    strategy=strategy.upper();rules=validate_parameters(strategy,parameters)
    values = indicators(cleaned,rules)
    balance = float(initial_balance)
    trades, equity = [], []
    # The cadence assumption must be fixed before the first evaluated signal.
    # Looking for a minimum over future bars can retroactively change whether
    # earlier trades are considered contiguous and creates data leakage.
    interval=cleaned[1]['time']-cleaned[0]['time']
    skipped_gaps=0
    idx = warmup_bars(strategy,rules)
    price_cost=(spread_bps/2+slippage_bps)/10000
    while idx + duration < len(cleaned):
        side = signal_at(cleaned, values, idx, strategy,parameters=rules)
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
                           'strategy':strategy,'strategy_version':STRATEGY_VERSION,
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
                              'interval_method':'First supplied candle interval, fixed before signal evaluation; no broker session calendar was provided.'},
            'provenance':dataset_provenance(cleaned,source='local_simulator_or_user_CSV',configuration={
                'strategy':strategy,'stake':stake,'duration_bars':duration,'payout':payout,
                'initial_balance':initial_balance,'costs':costs,'parameters':rules,'strategy_version':STRATEGY_VERSION}),
            'note':'Hypothetical options results using next-bar-open entries and assumed costs. No actual broker payouts, financing, latency, liquidity or partial-fill model. Not live performance or a profit forecast.'}
