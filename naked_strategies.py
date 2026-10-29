"""Deterministic research implementations inspired by Naked Forex (2012).

Not publisher software or an exact encoding of the authors' discretionary rules.
All decisions use CLOSED OHLC bars only. No external packages or network requests.
Research backtests use a configurable theoretical Rise/Fall payout and do NOT
replicate Deriv broker quotes, fills, spreads, or available expiration contracts.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
import math
import random
import statistics
from research_analytics import performance_metrics, dataset_provenance, STRATEGY_VERSION
from market_regime import classify_regime

TIMEFRAMES={'1m':60,'5m':300,'15m':900,'1h':3600,'4h':14400,'1d':86400,'1w':604800,'1mo':2592000}
STRATEGIES={
 'kangaroo':{'name':'Kangaroo Tail','chapter':'8','category':'Reversal','description':'Rejection wick at a confirmed support/resistance area'},
 'shadow':{'name':'Big Shadow','chapter':'6','category':'Reversal','description':'Large two-bar engulfing reversal at a confirmed zone'},
 'belt':{'name':'Big Belt','chapter':'9','category':'Reversal','description':'Large directional candle opening/closing near its extremes at a zone'},
 'wammie':{'name':'Wammie','chapter':'7','category':'Reversal','description':'Higher second low in a double-bottom support area'},
 'moolah':{'name':'Moolah','chapter':'7','category':'Reversal','description':'Lower second high in a double-top resistance area'},
 'last_kiss':{'name':'Last Kiss','chapter':'5','category':'Breakout','description':'Box breakout then rejection at the former boundary'},
 'trendy_kangaroo':{'name':'Trendy Kangaroo','chapter':'10','category':'Continuation','description':'Wick rejection after short consolidation within established trend'},
}

PROFILES={
 'scalping':{'name':'Scalping','timeframes':['1m','5m'],'default':'5m','description':'Very short-duration research; costs and execution timing can erase small edges'},
 'intraday':{'name':'Intraday','timeframes':['15m','1h'],'default':'15m','description':'Short-term setups monitored within trading sessions'},
 'swing':{'name':'Swing','timeframes':['4h','1d'],'default':'4h','description':'Multi-day analysis and monitoring; broker options expiry is NOT assumed'},
 'position':{'name':'Long-term','timeframes':['1w','1mo'],'default':'1w','description':'Weekly/monthly analysis only; requires an instrument supporting long holding periods'},
}

class StrategyError(ValueError): pass

# Bound numerical operations, rather than allowing finite inputs whose derived
# variances/ratios overflow JSON or manufacture non-finite indicator signals.
# The range deliberately extends far beyond financial instrument prices.
MIN_PRICE=1e-100
MAX_PRICE=1e100

def candles_valid(rows):
    if not isinstance(rows,list) or len(rows)>10000:raise StrategyError('Provide a list of at most 10,000 OHLC candles')
    out=[]
    for r in rows:
        if not isinstance(r,dict):raise StrategyError('Each candle must be an object')
        try:
            if any(isinstance(r.get(k),bool) for k in ('open','high','low','close')) or isinstance(r.get('time',r.get('epoch')),bool):
                raise ValueError('Boolean candle value')
            o,h,l,c=(float(r[k]) for k in ('open','high','low','close'))
            timestamp=float(r.get('time',r.get('epoch')))
            epoch=int(timestamp)
            if timestamp!=epoch or not -62135596800<=epoch<=253370764800:
                raise ValueError('Timestamp must be an integer Unix second within supported calendar bounds')
        except (ValueError,TypeError,KeyError,OverflowError) as e:raise StrategyError('Candles need numeric time/open/high/low/close') from e
        if not all(math.isfinite(x) and MIN_PRICE<=x<=MAX_PRICE for x in (o,h,l,c)):
            raise StrategyError('Candle prices must be within the supported numerical range 1e-100 to 1e100')
        if l>min(o,c) or h<max(o,c) or l>h:
            raise StrategyError('Candle OHLC values are inconsistent or non-positive')
        if out and epoch<=out[-1]['time']:raise StrategyError('Candles must be ordered by unique, increasing timestamps')
        out.append({'time':epoch,'open':o,'high':h,'low':l,'close':c})
    return out

def resample(rows,frame):
    """Aggregate daily bars into canonical UTC weeks/months, omitting partial edges.

    The first group is discarded when history begins after its calendar start.
    The final group is discarded unless its daily bars reach the calendar end.
    This is conservative without a broker trading calendar: a market closing on
    Friday can leave the most recent week unavailable until another week appears.
    Interior groups end before the next group; missing sessions are not invented.
    """
    if not isinstance(frame,str) or frame not in TIMEFRAMES:raise StrategyError('Unsupported resampling timeframe')
    if frame not in ('1w','1mo'):return rows
    rows=candles_valid(rows)
    groups=[]
    for r in rows:
        dt=datetime.fromtimestamp(r['time'],timezone.utc)
        anchor=(dt.replace(day=1,hour=0,minute=0,second=0,microsecond=0) if frame=='1mo'
                else (dt-timedelta(days=dt.weekday())).replace(hour=0,minute=0,second=0,microsecond=0))
        start=int(anchor.timestamp())
        if not groups or groups[-1]['start']!=start:
            groups.append({'start':start,'first':r['time'],'last':r['time'],'bar':{**r,'time':start}})
        else:
            group=groups[-1];x=group['bar'];group['last']=r['time']
            x['high']=max(x['high'],r['high']);x['low']=min(x['low'],r['low']);x['close']=r['close']
    result=[]
    for i,group in enumerate(groups):
        if i==0 and group['first']!=group['start']:continue
        if i==len(groups)-1 and group['last']+86400<_bar_end(group['start'],frame):continue
        result.append(group['bar'])
    return result


def sample_candles(count=1100,granularity=300,seed=4201):
    """Explicitly synthetic sample data: not Deriv or historical trading quotes."""
    if isinstance(count,bool) or not isinstance(count,(int,float)) or not math.isfinite(count) or int(count)!=count:
        raise StrategyError('Synthetic sample count must be an integer')
    if isinstance(granularity,bool) or not isinstance(granularity,int) or not 1<=granularity<=31_536_000:
        raise StrategyError('Synthetic granularity must be a positive integer of at most one year')
    rng=random.Random(seed)
    count=max(100,min(4000,int(count)))
    px=1.125
    start=1_700_000_000 - count*granularity
    start-=start%granularity
    if granularity==TIMEFRAMES['1w']:
        weekly_start=datetime.fromtimestamp(start,timezone.utc)
        start=int((weekly_start-timedelta(days=weekly_start.weekday())).replace(hour=0,minute=0,second=0,microsecond=0).timestamp())
    monthly_starts=None
    if granularity==TIMEFRAMES['1mo']:
        anchor=datetime.fromtimestamp(1_700_000_000,timezone.utc)
        final_month=anchor.year*12+anchor.month-1
        monthly_starts=[]
        for number in range(final_month-count,final_month):
            year,month=divmod(number,12)
            monthly_starts.append(int(datetime(year,month+1,1,tzinfo=timezone.utc).timestamp()))
    out=[]
    for i in range(count):
        # Directional periods plus chop to exercise the detectors; NOT calibrated to the market.
        tendency=math.sin(i/110)*.00028
        move=rng.gauss(tendency,.0012)
        op=px;cl=max(.1,op*(1+move))
        spread=abs(rng.gauss(.00036,.00019))
        hi=max(op,cl)*(1+spread);lo=min(op,cl)*(1-spread)
        out.append({'time':monthly_starts[i] if monthly_starts else start+i*granularity,'open':op,'high':hi,'low':lo,'close':cl})
        px=cl
    return out

def _range(c):return c['high']-c['low']
def _body(c):return abs(c['close']-c['open'])
def _bottom(c):return min(c['open'],c['close'])-c['low']
def _top(c):return c['high']-max(c['open'],c['close'])
def _near(a,b,tol):return abs(a-b)<=tol

def zone_levels(rows,end,lookback=140,*,tolerance_ratio=.34,min_touches=2):
    """Historical, confirmed pivots only. A 2-bar pivot can be used 2 bars later.
    Cluster turning-point prices with volatility-scaled tolerance, retain repeated zones.
    Zones are areas, not exact prices. No future candles are inspected.
    """
    begin=max(0,end-lookback)
    window=rows[begin:end]
    if len(window)<30:return [],0
    ranges=[_range(x) for x in window[-40:] if _range(x)>0]
    tol=max(statistics.median(ranges)*tolerance_ratio,window[-1]['close']*.00018) if ranges else window[-1]['close']*.00018
    pivots=[]
    for j in range(2,len(window)-2):
        c=window[j]
        if c['low']<=min(window[k]['low'] for k in (j-2,j-1,j+1,j+2)):
            pivots.append(('support',c['low']))
        if c['high']>=max(window[k]['high'] for k in (j-2,j-1,j+1,j+2)):
            pivots.append(('resistance',c['high']))
    clusters=[]
    for typ,price in pivots:
        pool=next((z for z in clusters if z['kind']==typ and abs(z['price']-price)<=tol),None)
        if pool:
            pool['price']=(pool['price']*pool['touches']+price)/(pool['touches']+1)
            pool['touches']+=1
        else:clusters.append({'kind':typ,'price':price,'touches':1})
    for z in clusters:z['width']=tol
    return [z for z in clusters if z['touches']>=min_touches],tol

def _matching_zone(zones,kind,price,tol):
    candidates=[z for z in zones if z['kind']==kind and abs(z['price']-price)<=max(tol*2,z['width']*2)]
    return max(candidates,key=lambda z:(z['touches'],-abs(z['price']-price))) if candidates else None


def _signal(side,pattern,bar,zone=None,detail=''):
    return {'side':side,'pattern':pattern,'signal_time':bar['time'],
            'trigger':bar['high'] if side=='UP' else bar['low'],
            'stop':bar['low'] if side=='UP' else bar['high'],
            'zone':round(zone['price'],8) if zone else None,
            'zone_touches':zone['touches'] if zone else 0,
            'explanation':detail,'strategy_version':STRATEGY_VERSION,
            'status':'signal_candidate','confidence':None,
            'invalidation':bar['low'] if side=='UP' else bar['high']}


DEFAULT_PARAMETERS = {
    'zone_lookback': 140, 'zone_tolerance_ratio': .34, 'zone_min_touches': 2,
    'wick_fraction': .58, 'belt_body_fraction': .70,
    'shadow_range_multiple': 1.20, 'belt_range_multiple': 1.45,
}


def validate_parameters(parameters=None):
    if parameters is not None and not isinstance(parameters,dict):
        raise StrategyError('Strategy parameters must be an object')
    if parameters and set(parameters)-set(DEFAULT_PARAMETERS):
        raise StrategyError('Unknown strategy parameter')
    rules={**DEFAULT_PARAMETERS,**(parameters or {})}
    limits={'zone_lookback':(60,400),'zone_tolerance_ratio':(.1,1),
            'zone_min_touches':(2,10),'wick_fraction':(.5,.9),
            'belt_body_fraction':(.5,.95),'shadow_range_multiple':(1,4),
            'belt_range_multiple':(1,4)}
    for key,value in rules.items():
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
            raise StrategyError('Strategy parameters must be finite numbers')
        low,high=limits[key]
        if not low<=value<=high:raise StrategyError('Strategy parameter outside bounds: '+key)
        if key in ('zone_lookback','zone_min_touches') and int(value)!=value:
            raise StrategyError(key+' must be an integer')
    rules['zone_lookback']=int(rules['zone_lookback'])
    rules['zone_min_touches']=int(rules['zone_min_touches'])
    return rules


def detect(rows,i,strategy,parameters=None):
    """Detect the setup on close of bar i, using only bars with indices <=i.

    A signal is actionable only after the NEXT bar CLOSES beyond the trigger.
    This intentional confirmation rule differs from the book's pending stop orders.
    """
    if not isinstance(strategy,str) or strategy not in STRATEGIES:raise StrategyError('Unsupported strategy')
    if not isinstance(rows,list) or isinstance(i,bool) or not isinstance(i,int) or not 0<=i<len(rows):
        raise StrategyError('Pattern index is outside candle history')
    rules=validate_parameters(parameters)
    if i<65:return None
    c=rows[i];prev=rows[i-1];rng=_range(c)
    if rng<=0:return None
    zones,tol=zone_levels(rows,i,rules['zone_lookback'],tolerance_ratio=rules['zone_tolerance_ratio'],min_touches=rules['zone_min_touches']) # prior bars, no self-confirming zone
    med=statistics.median([_range(x) for x in rows[max(0,i-12):i]])
    if med<=0:return None
    near_support=_matching_zone(zones,'support',c['low'],tol)
    near_resist=_matching_zone(zones,'resistance',c['high'],tol)
    if strategy=='kangaroo':
        if _bottom(c)/rng>=rules['wick_fraction'] and max(c['open'],c['close'])>=c['low']+.66*rng and rng>=.85*med and near_support:
            return _signal('UP',strategy,c,near_support,'Long lower tail rejects repeatedly tested support')
        if _top(c)/rng>=rules['wick_fraction'] and min(c['open'],c['close'])<=c['low']+.34*rng and rng>=.85*med and near_resist:
            return _signal('DOWN',strategy,c,near_resist,'Long upper tail rejects repeatedly tested resistance')
    elif strategy=='shadow':
        engulf=c['high']>prev['high'] and c['low']<prev['low'] and rng>=rules['shadow_range_multiple']*med
        if engulf and c['close']>=c['low']+.75*rng and near_support:
            return _signal('UP',strategy,c,near_support,'Outside candle closes near high at support')
        if engulf and c['close']<=c['low']+.25*rng and near_resist:
            return _signal('DOWN',strategy,c,near_resist,'Outside candle closes near low at resistance')
    elif strategy=='belt':
        if rng>=rules['belt_range_multiple']*med and _body(c)/rng>=rules['belt_body_fraction']:
            if c['close']>=c['low']+.87*rng and c['open']<=c['low']+.20*rng and near_support:
                return _signal('UP',strategy,c,near_support,'Wide bullish body at support')
            if c['close']<=c['low']+.13*rng and c['open']>=c['low']+.80*rng and near_resist:
                return _signal('DOWN',strategy,c,near_resist,'Wide bearish body at resistance')
    elif strategy in ('wammie','moolah'):
        # Evaluate most recent confirmed second pivot and earlier first pivot.
        # Second point must occur 2-4 bars before confirmation candle i.
        for j in range(i-2,max(6,i-5),-1):
            second=rows[j]
            if strategy=='wammie' and not (second['low']<=min(rows[k]['low'] for k in (j-2,j-1,j+1,j+2))):continue
            if strategy=='moolah' and not (second['high']>=max(rows[k]['high'] for k in (j-2,j-1,j+1,j+2))):continue
            for k in range(j-3,max(4,j-17),-1):
                first=rows[k]
                if strategy=='wammie':
                    zone=_matching_zone(zones,'support',first['low'],tol)
                    if not zone or not 0<second['low']-first['low']<=tol*2.5:continue
                    interim=max(x['high'] for x in rows[k+1:j])
                    if c['close']>interim and prev['close']<=interim:
                        return _signal('UP',strategy,c,zone,'Higher second low with neckline closing breakout')
                else:
                    zone=_matching_zone(zones,'resistance',first['high'],tol)
                    if not zone or not 0<first['high']-second['high']<=tol*2.5:continue
                    interim=min(x['low'] for x in rows[k+1:j])
                    if c['close']<interim and prev['close']>=interim:
                        return _signal('DOWN',strategy,c,zone,'Lower second high with neckline closing breakdown')
    elif strategy=='last_kiss':
        # Quantitative approximation of the box: at least two range-edge touches.
        for breakout_idx in (i-1,i-2,i-3):
            block=rows[breakout_idx-24:breakout_idx]
            if len(block)<24:continue
            hi=max(x['high'] for x in block);lo=min(x['low'] for x in block)
            height=hi-lo
            if height<=0 or height>med*8:continue
            touches_hi=sum(x['high']>=hi-height*.12 for x in block)
            touches_lo=sum(x['low']<=lo+height*.12 for x in block)
            if touches_hi<2 or touches_lo<2:continue
            breakbar=rows[breakout_idx]
            if breakbar['close']>hi and c['low']<=hi+tol and c['close']>hi and c['close']>=c['open']:
                z={'price':hi,'touches':touches_hi}
                return _signal('UP',strategy,c,z,'Break above two-touch box and bullish retest')
            if breakbar['close']<lo and c['high']>=lo-tol and c['close']<lo and c['close']<=c['open']:
                z={'price':lo,'touches':touches_lo}
                return _signal('DOWN',strategy,c,z,'Break below two-touch box and bearish retest')
    elif strategy=='trendy_kangaroo':
        pause=rows[i-6:i] # 6 quiet bars, in the 3–10 range discussed in the book
        before=rows[i-26:i-6]
        if not before:return None
        pause_span=max(x['high'] for x in pause)-min(x['low'] for x in pause)
        if pause_span>med*3.8:return None
        trend_delta=before[-1]['close']-before[0]['close']
        if trend_delta>med*3.5 and _bottom(c)/rng>=.53 and c['low']<min(x['low'] for x in pause)-tol*.3 and c['close']>=c['low']+.67*rng:
            return _signal('UP',strategy,c,None,'Uptrend with 6-bar pause and bullish rejection wick')
        if trend_delta< -med*3.5 and _top(c)/rng>=.53 and c['high']>max(x['high'] for x in pause)+tol*.3 and c['close']<=c['low']+.33*rng:
            return _signal('DOWN',strategy,c,None,'Downtrend with 6-bar pause and bearish rejection wick')
    return None


def confirmed_signal(rows,strategy,parameters=None):
    """Return signal if last CLOSED candle confirms prior bar's trigger with CLOSE.
    This is not the book's exact stop order entry, deliberately keeps automation
    from triggering on a wick and uses no partially formed candles.
    """
    rows=candles_valid(rows)
    if not isinstance(strategy,str) or strategy not in STRATEGIES:raise StrategyError('Unsupported strategy')
    validate_parameters(parameters)
    if len(rows)<70:return None
    previous=detect(rows,len(rows)-2,strategy,parameters)
    if not previous:return None
    last=rows[-1]
    direction=previous['side']
    if ((direction=='UP' and last['close']>previous['trigger']) or
        (direction=='DOWN' and last['close']<previous['trigger'])):
        rules=validate_parameters(parameters)
        origin=dataset_provenance(rows[-(rules['zone_lookback']+4):],configuration={'strategy':strategy,'parameters':rules})
        return {**previous,'confirmed_at':last['time'],'confirmation_close':last['close'],
                'rule_parameters':rules,'data_window_sha256':origin['dataset_sha256'],
                'configuration_sha256':origin['configuration_sha256']}
    return None


def _metric(trades,starting_balance=1000):
    """Compatibility alias for the richer, shared simulation analytics."""
    return performance_metrics(trades,starting_balance)


def _bar_end(epoch,frame):
    if frame=='1mo':
        d=datetime.fromtimestamp(epoch,timezone.utc)
        return int(datetime(d.year+(d.month==12),1 if d.month==12 else d.month+1,1,tzinfo=timezone.utc).timestamp())
    return epoch+TIMEFRAMES[frame]


def _simulate_partition(rows,start,end,*,strategy,rules,frame,stake,payout,expiry_bars,
                        initial_balance,commission_per_trade,price_cost,regime_filter,
                        instrument,partition):
    """Run one independently funded, non-overlapping, causal experiment.

    A boundary-crossing candidate is discarded BEFORE occupancy or capital is
    changed. Training losses and discarded trades cannot fund/starve a holdout.
    Exit P&L becomes available only at expiry: the next evaluation is after it.
    """
    trades=[];balance=initial_balance;next_allowed=max(66,start-1)
    skipped={'insufficient_bankroll':0,'missing_bars_or_market_closures':0,
             'regime_filter':0,'boundary_crossing':0}
    boundary_at=rows[end]['time'] if end<len(rows) else None
    for i in range(max(66,start-1),min(len(rows)-expiry_bars,end-1)):
        if i<next_allowed:continue
        pattern=detect(rows,i-1,strategy,rules)
        if not pattern:continue
        if pattern['side']=='UP' and rows[i]['close']<=pattern['trigger']:continue
        if pattern['side']=='DOWN' and rows[i]['close']>=pattern['trigger']:continue
        enter=i+1;exit_idx=enter+expiry_bars-1
        # A rejected boundary-crossing candidate does not read its future price
        # or affect the next segment's capital / non-overlap schedule.
        if exit_idx>=end:
            skipped['boundary_crossing']+=1;continue
        end_time=_bar_end(rows[exit_idx]['time'],frame)
        if boundary_at is not None and end_time>=boundary_at:
            skipped['boundary_crossing']+=1;continue
        if any(rows[j+1]['time']!=_bar_end(rows[j]['time'],frame) for j in range(i,exit_idx)):
            skipped['missing_bars_or_market_closures']+=1;continue
        regime=classify_regime(rows[max(0,i-60):i+1])
        if regime_filter and strategy not in regime['eligible_strategies']:
            skipped['regime_filter']+=1;continue
        if balance<stake+commission_per_trade:
            skipped['insufficient_bankroll']+=1;continue
        direction=1 if pattern['side']=='UP' else -1
        entry_mid=rows[enter]['open'];exit_mid=rows[exit_idx]['close']
        entry_price=entry_mid*(1+direction*price_cost)
        exit_price=exit_mid*(1-direction*price_cost)
        contract_win=(exit_price-entry_price)*direction>0
        gross=stake*payout if contract_win else -stake
        pnl=round(gross-commission_per_trade,6)
        balance+=pnl
        trades.append({'signal_at':rows[i]['time'],'entered_at':rows[enter]['time'],
           'exited_at':end_time,'side':pattern['side'],'strategy':strategy,'strategy_version':STRATEGY_VERSION,
           'entry':round(entry_price,10),'exit':round(exit_price,10),
           'entry_mid':entry_mid,'exit_mid':exit_mid,'stake':stake,
           'gross_pnl':round(gross,6),'commission':commission_per_trade,'pnl':pnl,
           'win':pnl>0,'contract_win':contract_win,'balance':round(balance,6),
           'holding_seconds':end_time-rows[enter]['time'],
           'regime':regime['regime'],'timeframe':frame,'instrument':instrument,
           'explanation':pattern['explanation'],'invalidation':pattern['stop'],
           'result_kind':'historical_simulation','partition':partition})
        next_allowed=exit_idx+1
    return trades,skipped


def _walk_forward(rows,split_bar,expiry_bars,initial_balance,simulate):
    """Fixed-parameter, independently funded validation BEFORE final holdout."""
    first=max(67,int(split_bar*.4))
    step=max(1,(split_bar-first)//3)
    folds=[]
    for number in range(3):
        train_end=first+number*step
        end=min(split_bar,first+(number+1)*step)
        begin=train_end+expiry_bars
        if begin>=end:continue
        start_at=rows[begin]['time'];end_at=rows[end]['time']
        selected,skipped=simulate(begin,end,'walk_forward_'+str(number+1))
        metrics=performance_metrics(selected,initial_balance,period_seconds=end_at-start_at)
        passed=bool(metrics['trades']>=10 and metrics['pnl']>0 and metrics['max_drawdown_pct']<=10)
        folds.append({'fold':number+1,'train_start_at':rows[0]['time'],
                      'train_end_at':rows[train_end]['time'],
                      'validation_start_at':start_at,'validation_end_at':end_at,
                      'train_dataset_sha256':dataset_provenance(rows[:train_end])['dataset_sha256'],
                      'validation_dataset_sha256':dataset_provenance(rows[begin:end])['dataset_sha256'],
                      'embargo_bars':expiry_bars,'initial_balance':initial_balance,
                      'metrics':metrics,'passed':passed,'skipped':skipped})
    passes=sum(f['passed'] for f in folds)
    return {'folds':folds,'passes':passes,'passed':len(folds)==3 and passes>=2,
            'method':'Three fixed-parameter expanding training/validation folds inside the first 70%; independently funded validation; holding-period embargo; crossing positions purged before capital mutation. Final 30% holdout untouched by folds.',
            'minimum_trades_per_fold':10,'required_positive_folds':2,
            'limitation':'Parameter stability across alternate configurations and independent demo-forward results remain unverified.'}


def backtest(rows,strategy,profile,frame,payout=.8,stake=5,expiry_bars=3,target_win_rate=65,
             *,commission_per_trade=0.0,spread_bps=1.0,slippage_bps=.5,initial_balance=1000.0,
             parameters=None,regime_filter=False,source='unspecified',instrument=None):
    """Next-bar-open theoretical fixed-expiry options research, with explicit costs.

    This is NOT a broker execution simulator or a stop-loss CFD backtest. Prices
    are shifted adversely by assumed spread and slippage; commission is deducted
    from each contract result. No real payout, latency, financing or liquidity is
    invented. Win-rate target is a research annotation, never a promotion gate.
    """
    if not isinstance(strategy,str) or strategy not in STRATEGIES:raise StrategyError('Unknown pattern')
    if not isinstance(profile,str) or not isinstance(frame,str) or profile not in PROFILES or frame not in PROFILES[profile]['timeframes']:
        raise StrategyError('Timeframe is not valid for selected trading style')
    if any(isinstance(value,bool) for value in (payout,stake,expiry_bars,target_win_rate,commission_per_trade,spread_bps,slippage_bps,initial_balance)):
        raise StrategyError('Boolean values are not numeric research settings')
    try:
        payout=float(payout);stake=float(stake);target_win_rate=float(target_win_rate)
        horizon=float(expiry_bars)
        commission_per_trade=float(commission_per_trade);spread_bps=float(spread_bps)
        slippage_bps=float(slippage_bps);initial_balance=float(initial_balance)
    except (ValueError,TypeError,OverflowError) as exc:
        raise StrategyError('Research settings must be finite numbers') from exc
    values=(payout,stake,target_win_rate,horizon,commission_per_trade,spread_bps,slippage_bps,initial_balance)
    if not all(math.isfinite(v) for v in values):raise StrategyError('Research settings must be finite numbers')
    if not(.20<=payout<=1.5 and .35<=stake<=100 and 1<=horizon<=20 and horizon==int(horizon) and 40<=target_win_rate<=95):
        raise StrategyError('Payout, stake, horizon or benchmark outside safe limits')
    if not(0<=commission_per_trade<=stake and 0<=spread_bps<=100 and 0<=slippage_bps<=100 and 100<=initial_balance<=1_000_000_000):
        raise StrategyError('Costs or initial balance outside allowed research limits')
    if not isinstance(regime_filter,bool):raise StrategyError('Regime filter must be true or false')
    if not isinstance(source,str) or len(source)>200 or (instrument is not None and (not isinstance(instrument,str) or len(instrument)>100)):
        raise StrategyError('Source and instrument must be short text labels')
    expiry_bars=int(horizon);rules=validate_parameters(parameters)
    rows=candles_valid(rows)
    if len(rows)<100:raise StrategyError('At least 100 completed candles are needed')
    if frame in ('1w','1mo'):
        for row in rows:
            stamp=datetime.fromtimestamp(row['time'],timezone.utc)
            aligned=(stamp.day==1 if frame=='1mo' else stamp.weekday()==0)
            if not aligned or any((stamp.hour,stamp.minute,stamp.second)):
                raise StrategyError('Weekly/monthly bars must start at their UTC calendar boundary; resample daily history first')
    split_bar=int(len(rows)*.7);split_at=rows[split_bar]['time']
    end_at=_bar_end(rows[-1]['time'],frame)
    price_cost=(spread_bps/2+slippage_bps)/10000
    def simulate(start,end,partition):
        return _simulate_partition(rows,start,end,strategy=strategy,rules=rules,frame=frame,
            stake=stake,payout=payout,expiry_bars=expiry_bars,initial_balance=initial_balance,
            commission_per_trade=commission_per_trade,price_cost=price_cost,
            regime_filter=regime_filter,instrument=instrument,partition=partition)
    train,train_skipped=simulate(0,split_bar,'train')
    test,test_skipped=simulate(split_bar,len(rows),'holdout')
    trades=train+test
    # Each split has its OWN funded allocation. Combined ROI uses both capital
    # allocations, rather than silently resetting cash and overstating returns.
    combined_capital=2*initial_balance
    metrics=performance_metrics(trades,combined_capital,period_seconds=end_at-rows[0]['time'])
    a=performance_metrics(train,initial_balance,period_seconds=split_at-rows[0]['time'])
    b=performance_metrics(test,initial_balance,period_seconds=end_at-split_at)
    walk=_walk_forward(rows,split_bar,expiry_bars,initial_balance,simulate)
    skipped={key:train_skipped[key]+test_skipped[key] for key in train_skipped}
    breakeven=100*(1+commission_per_trade/stake)/(payout+1)
    criteria={'minimum_train_trades':30,'minimum_holdout_trades':30,'maximum_drawdown_pct':10,
              'positive_net_expectancy_required':True,'wilson_lower_above_break_even_required':True,
              'training_walk_forward_required':True}
    stress=[]
    stress_price_cost=price_cost*2
    for trade in test:
        direction=1 if trade['side']=='UP' else -1
        stressed_entry=trade['entry_mid']*(1+direction*stress_price_cost)
        stressed_exit=trade['exit_mid']*(1-direction*stress_price_cost)
        won=(stressed_exit-stressed_entry)*direction>0
        stressed_commission=commission_per_trade*1.5
        stress.append({**trade,'pnl':round((stake*payout if won else -stake)-stressed_commission,6),
                       'commission':stressed_commission})
    stressed=performance_metrics(stress,initial_balance,period_seconds=end_at-split_at)
    stress_pass=bool(stressed['trades'] and stressed['pnl']>0 and stressed['max_drawdown_pct']<=10)
    criteria['positive_cost_stress_holdout_required']=True
    enough=a['trades']>=30 and b['trades']>=30
    qualified=bool(enough and a['pnl']>0 and b['pnl']>0 and b['wilson_lower_95_pct']>breakeven
                   and max(a['max_drawdown_pct'],b['max_drawdown_pct'])<=10 and walk['passed'] and stress_pass)
    reason=('Meets predefined simulation research gates; independent demo-forward validation is still required. This is NOT proof of future returns.' if qualified else
            'NOT VALIDATED: requires >=30 trades in both chronological splits, positive net expectancy after assumed costs, '
            'held-out 95% lower win-rate bound above fee-adjusted break-even, <=10% drawdown, and >=2 sufficient positive training walk-forward folds plus positive doubled-friction holdout. '
            'The win-rate research benchmark does not authorize trading.')
    costs={'commission_per_trade':commission_per_trade,'spread_bps':spread_bps,'slippage_bps':slippage_bps,
           'model':'Adverse half-spread plus slippage on entry and exit; fixed commission per settled contract.',
           'assumptions_verified_with_broker':False,
           'unmodeled':['Actual broker bid/ask and contract payout','latency','partial fills','rejections','liquidity','swap/financing']}
    config={'strategy':strategy,'profile':profile,'frame':frame,'payout':payout,'stake':stake,
            'expiry_bars':expiry_bars,'initial_balance_per_split':initial_balance,'combined_funded_capital':combined_capital,'costs':costs,
            'parameters':rules,'regime_filter':regime_filter,'target_win_rate':target_win_rate}
    by_regime={key:performance_metrics([t for t in trades if t['regime']==key],combined_capital)
               for key in sorted({t['regime'] for t in trades})}
    return {'strategy':strategy,'strategy_version':STRATEGY_VERSION,'profile':profile,'timeframe':frame,'bars':len(rows),
            'model':'Hypothetical cost-adjusted fixed-expiry Rise/Fall, not a Deriv contract or CFD execution backtest',
            'assumed_payout_pct':round(100*payout,1),'break_even_win_rate_pct':round(breakeven,4),
            'target_win_rate_pct':target_win_rate,'train':a,'test':b,'overall':metrics,
            'capital_model':{'initial_balance_per_split':initial_balance,'combined_funded_capital':combined_capital,
                             'description':'Train and holdout are independently funded experiments. Combined equity/ROI uses both allocations; no training profit or loss changes holdout buying power.'},
            'research_pass':qualified,'assessment':reason,'walk_forward':walk,
            'robustness':{'cost_stress_holdout':stressed,'passed':stress_pass,
                          'assumptions':'Reprice the same holdout signals at double spread/slippage and 1.5x commission. Not a new independent dataset or a liquidity simulation.'},
            'validation':{'benchmark_met':bool(b['win_rate_pct'] is not None and b['win_rate_pct']>=target_win_rate),
                          'benchmark_is_promotion_gate':False,'criteria':criteria,
                          'train_end_at':split_at,'holdout_start_at':split_at,'holdout_end_at':end_at,
                          'train_dataset_sha256':dataset_provenance(rows[:split_bar])['dataset_sha256'],
                          'holdout_dataset_sha256':dataset_provenance(rows[split_bar:])['dataset_sha256'],
                          'split_policy':'Independently funded chronological experiments; boundary-crossing trades discarded before any balance or occupancy mutation.',
                          'feature_warmup':'Earlier completed bars may inform indicators; trade outcomes remain within their own experiment.',
                          'purged_boundary_trades':skipped['boundary_crossing'],'demo_forward_verified':False,
                          'parameter_stability_verified':False,'execution_authorized':False},
            'costs':costs,'provenance':dataset_provenance(rows,source=source,instrument=instrument,timeframe=frame,configuration=config),
            'market_regime':classify_regime(rows),
            'data_integrity':{'candle_time_semantics':'UTC bar-open epochs; modeled exit at calendar bar end.',
                              'contiguous_holding_bars_required':True,'calendar_alignment_required':frame in ('1w','1mo'),
                              'missing_sessions_fabricated':False},
            'performance_breakdown':{'by_regime':by_regime,'by_timeframe':{frame:metrics},
                                     'by_instrument':{instrument or 'unspecified':metrics}},
            'skipped':skipped,
            'trades_detail':trades,'last_signal':confirmed_signal(rows,strategy,rules)}
