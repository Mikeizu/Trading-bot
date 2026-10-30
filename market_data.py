"""Shared validated OHLC history, UTC timeframes and explicitly synthetic fixtures.

This module contains no trading-pattern detectors or broker execution.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
import math
import random

class StrategyError(ValueError):
    pass


TIMEFRAMES={'1m':60,'5m':300,'15m':900,'1h':3600,'4h':14400,'1d':86400,'1w':604800,'1mo':2592000}

PROFILES={
 'scalping':{'name':'Scalping','timeframes':['1m','5m'],'default':'5m','description':'Very short-duration research; costs and execution timing can erase small edges'},
 'intraday':{'name':'Intraday','timeframes':['15m','1h'],'default':'15m','description':'Short-term setups monitored within trading sessions'},
 'swing':{'name':'Swing','timeframes':['4h','1d'],'default':'4h','description':'Multi-day analysis and monitoring; broker options expiry is NOT assumed'},
 'position':{'name':'Long-term','timeframes':['1w','1mo'],'default':'1w','description':'Weekly/monthly analysis only; requires an instrument supporting long holding periods'},
}

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
    if frame not in ('1w','1mo'):return candles_valid(rows)
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
        if i==len(groups)-1 and group['last']+86400<bar_end(group['start'],frame):continue
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

def bar_end(epoch,frame):
    if frame=='1mo':
        d=datetime.fromtimestamp(epoch,timezone.utc)
        return int(datetime(d.year+(d.month==12),1 if d.month==12 else d.month+1,1,tzinfo=timezone.utc).timestamp())
    return epoch+TIMEFRAMES[frame]
