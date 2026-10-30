"""Transparent technical-rule interpretations on closed OHLC bars.

These are independently programmed research rules, not Qumatix proprietary
algorithms, calibrated forecasts, or evidence of profitability. No volume is
invented. All evidence uses the supplied current/past candles only.
"""
from __future__ import annotations

import math

STRATEGY_VERSION = '3.0.0'
TREND = ['trending_up', 'trending_down']
RANGE = ['ranging']
NORMAL = TREND + RANGE


def _p(default, minimum, maximum, description, *, integer=False, step=None):
    return {'default': default, 'min': minimum, 'max': maximum,
            'step': step if step is not None else (1 if integer else .1),
            'type': 'int' if integer else 'float', 'description': description}


PERIODS = {
    'rsi_period': _p(14, 5, 50, 'Wilder RSI lookback', integer=True),
    'macd_fast': _p(12, 3, 40, 'MACD fast EMA period', integer=True),
    'macd_slow': _p(26, 8, 100, 'MACD slow EMA period', integer=True),
    'macd_signal_period': _p(9, 2, 30, 'MACD signal EMA period', integer=True),
    'cci_period': _p(20, 5, 80, 'CCI typical-price lookback', integer=True),
    'sma_fast_period': _p(8, 3, 40, 'Fast SMA period', integer=True),
    'sma_slow_period': _p(21, 8, 150, 'Slow SMA period', integer=True),
    'ema_fast_period': _p(12, 3, 50, 'Fast EMA period', integer=True),
    'ema_mid_period': _p(21, 5, 80, 'Middle EMA period', integer=True),
    'ema_slow_period': _p(26, 8, 150, 'Slow EMA period', integer=True),
    'trend_period': _p(50, 20, 200, 'Trend-filter EMA period', integer=True),
    'bb_period': _p(20, 10, 80, 'Bollinger close-price lookback', integer=True),
    'bb_deviations': _p(2., 1., 4., 'Population standard-deviation band multiplier'),
    'stoch_period': _p(14, 5, 50, 'Raw stochastic %K lookback', integer=True),
    'stoch_rsi_period': _p(14, 5, 50, 'Stochastic normalization of RSI', integer=True),
    'williams_period': _p(14, 5, 50, 'Williams %R lookback', integer=True),
    'roc_period': _p(12, 3, 80, 'Percentage rate-of-change lookback', integer=True),
    'momentum_period': _p(20, 5, 100, 'Price momentum lookback', integer=True),
    'accel_period': _p(5, 1, 20, 'Lag used to measure momentum acceleration', integer=True),
    'adx_period': _p(14, 5, 50, 'Wilder DMI and ADX period', integer=True),
    'channel_period': _p(20, 5, 100, 'Prior-bar Donchian channel lookback', integer=True),
    'atr_period': _p(14, 5, 50, 'Wilder true-range averaging period', integer=True),
    'atr_multiple': _p(1.5, .5, 5., 'ATR threshold or trailing-band multiplier'),
    'keltner_period': _p(20, 5, 100, 'Keltner EMA middle period', integer=True),
    'tenkan_period': _p(9, 3, 20, 'Ichimoku conversion midpoint period', integer=True),
    'kijun_period': _p(26, 10, 60, 'Ichimoku baseline midpoint period', integer=True),
    'senkou_period': _p(52, 20, 120, 'Ichimoku span B midpoint period', integer=True),
    'cloud_displacement': _p(26, 1, 60, 'Past computed spans used for today\'s displayed cloud', integer=True),
    'aroon_period': _p(25, 5, 80, 'Aroon high/low age period', integer=True),
}


def _entry(name, family, description, keys, *, eligible=None, overrides=None, warmup=35):
    params = {key: dict(PERIODS[key]) for key in keys}
    for key, value in (overrides or {}).items():
        params[key] = dict(value)
    return {'name': name, 'family': family, 'description': description,
            'rules': description, 'parameters': params, 'warmup_bars': warmup,
            'eligible_regimes': list(eligible or NORMAL), 'version': STRATEGY_VERSION,
            'limitations': 'Closed-bar deterministic rule; not a calibrated probability or profit guarantee.'}


STRATEGIES = {
    'RSI': _entry('RSI recovery', 'mean_reversion', 'Enter when Wilder RSI recovers through oversold or falls through overbought.', ['rsi_period'], eligible=RANGE,
        overrides={'oversold': _p(30, 5, 45, 'Lower RSI recovery threshold'), 'overbought': _p(70, 55, 95, 'Upper RSI recovery threshold')}),
    'MACD': _entry('MACD signal crossover', 'momentum', 'Enter when MACD crosses its signal EMA; averages use first-observation causal EMA seeds.', ['macd_fast', 'macd_slow', 'macd_signal_period'], eligible=TREND, warmup=37),
    'CCI': _entry('CCI recovery', 'mean_reversion', 'Enter when CCI crosses back through a configurable extreme.', ['cci_period'], eligible=RANGE,
        overrides={'cci_level': _p(100, 50, 250, 'Symmetric CCI extreme level')}),
    'SMA': _entry('Dual SMA crossover', 'trend', 'Enter on fast/slow simple moving-average crossover.', ['sma_fast_period', 'sma_slow_period'], eligible=TREND),
    'BOLLINGER': _entry('Bollinger outer-band fade', 'mean_reversion', 'A close outside its close-price population-deviation bands proposes a contrarian candidate.', ['bb_period', 'bb_deviations'], eligible=RANGE),
    'STOCHASTIC': _entry('Stochastic %K recovery', 'mean_reversion', 'Raw stochastic %K crosses back through an extreme; this is not a smoothed slow-stochastic replica.', ['stoch_period'], eligible=RANGE,
        overrides={'oversold': _p(20, 5, 40, 'Lower %K threshold'), 'overbought': _p(80, 60, 95, 'Upper %K threshold')}),
    'EMA_CROSS': _entry('Dual EMA crossover', 'trend', 'Enter on fast/slow exponentially weighted moving-average crossover.', ['ema_fast_period', 'ema_slow_period'], eligible=TREND),
    'EMA_PULLBACK': _entry('EMA trend pullback', 'trend', 'A price recovery through the fast EMA must agree with the slower trend EMA and its slope.', ['ema_fast_period', 'trend_period'], eligible=TREND,
        overrides={'ema_fast_period': _p(20, 5, 40, 'Pullback EMA period', integer=True)}, warmup=52),
    'TRIPLE_EMA': _entry('Triple EMA alignment', 'trend', 'Fast EMA crosses the middle EMA while both agree with the slow EMA ordering.', ['ema_fast_period', 'ema_mid_period', 'ema_slow_period'], eligible=TREND,
        overrides={'ema_fast_period': _p(9, 3, 30, 'Fast EMA period', integer=True), 'ema_slow_period': _p(50, 20, 150, 'Slow EMA period', integer=True)}, warmup=52),
    'RSI_TREND': _entry('RSI trend confirmation', 'momentum', 'RSI crosses its midpoint while price and the trend EMA slope agree.', ['rsi_period', 'trend_period'], eligible=TREND,
        overrides={'rsi_midpoint': _p(50, 40, 60, 'RSI trend threshold')}, warmup=52),
    'STOCH_RSI': _entry('Stochastic RSI recovery', 'mean_reversion', 'RSI normalized against its own recent range recovers through an extreme.', ['rsi_period', 'stoch_rsi_period'], eligible=RANGE,
        overrides={'oversold': _p(20, 5, 40, 'Lower stochastic-RSI threshold'), 'overbought': _p(80, 60, 95, 'Upper stochastic-RSI threshold')}),
    'WILLIAMS_R': _entry('Williams %R midpoint confirmation', 'mean_reversion', 'Williams %R must cross its -50 midpoint after visiting an extreme in the recent confirmation window.', ['williams_period'], eligible=RANGE,
        overrides={'oversold': _p(-80, -95, -60, 'Required recent lower %R extreme'), 'overbought': _p(-20, -40, -5, 'Required recent upper %R extreme'), 'recovery_window': _p(5, 2, 20, 'Recent bars allowed for extreme-to-midpoint confirmation', integer=True)}),
    'ROC': _entry('Rate-of-change threshold', 'momentum', 'Percentage price change crosses a signed neutral threshold.', ['roc_period'], eligible=TREND,
        overrides={'roc_threshold': _p(0., 0., 10., 'Symmetric percentage ROC threshold')}),
    'MOMENTUM': _entry('Momentum acceleration', 'momentum', 'Momentum acceleration crosses zero in the same direction as longer-horizon price momentum.', ['momentum_period', 'accel_period'], eligible=TREND),
    'ADX_DMI': _entry('ADX directional crossover', 'trend', 'Positive/negative Wilder directional indices cross while ADX exceeds the research threshold.', ['adx_period'], eligible=TREND,
        overrides={'adx_min': _p(20, 10, 50, 'Minimum ADX trend-strength threshold')}),
    'DONCHIAN': _entry('Prior-channel breakout', 'breakout', 'Close breaks the high/low channel built strictly before the signal bar.', ['channel_period'], eligible=TREND),
    'ATR_BREAKOUT': _entry('ATR displacement breakout', 'breakout', 'Close displaces beyond the previous close by a multiple of the previous ATR.', ['atr_period', 'atr_multiple'], eligible=TREND),
    'KELTNER': _entry('Keltner channel breakout', 'breakout', 'Close crosses an EMA plus/minus a Wilder ATR envelope.', ['keltner_period', 'atr_period', 'atr_multiple'], eligible=TREND,
        overrides={'atr_multiple': _p(2., .5, 5., 'Keltner ATR multiplier')}),
    'BOLLINGER_REENTRY': _entry('Bollinger band re-entry', 'mean_reversion', 'Require a prior close outside the band followed by a closed-bar recovery inside it.', ['bb_period', 'bb_deviations'], eligible=RANGE),
    'BOLLINGER_SQUEEZE': _entry('Bollinger squeeze breakout', 'volatility', 'A low prior bandwidth must precede a close breaking the prior bands.', ['bb_period', 'bb_deviations'], eligible=TREND,
        overrides={'squeeze_width_pct': _p(2., .1, 20., 'Maximum prior band width as percent of middle')}),
    'SUPERTREND': _entry('ATR trailing trend flip', 'trend', 'Enter only when the causal ATR-based trailing-band direction changes.', ['atr_period', 'atr_multiple'], eligible=TREND,
        overrides={'atr_period': _p(10, 5, 50, 'Trailing true-range period', integer=True), 'atr_multiple': _p(3., 1., 5., 'Trailing ATR multiplier')}),
    'ICHIMOKU': _entry('Ichimoku cloud confirmation', 'trend', 'Conversion/baseline crossover must agree with the current displayed cloud, using spans computed displacement bars in the past; no future or lagging-span leakage.', ['tenkan_period', 'kijun_period', 'senkou_period', 'cloud_displacement'], eligible=TREND, warmup=80),
    'AROON': _entry('Aroon trend emergence', 'trend', 'Aroon up/down cross with the winning high/low-age measure above a minimum.', ['aroon_period'], eligible=TREND,
        overrides={'aroon_min': _p(70, 50, 95, 'Minimum winning Aroon value')}),
    'CONSENSUS': _entry('Transparent rule consensus', 'composite', 'Require a new threshold of agreement among trend EMA, RSI midpoint, MACD histogram and prior-channel breakout. Votes are correlated rules, not a probability.', ['trend_period', 'rsi_period', 'channel_period'], eligible=TREND,
        overrides={'consensus_votes': _p(3, 2, 4, 'Required agreeing rule votes, not confidence', integer=True)}, warmup=52),
}


def validate_parameters(strategy, parameters=None):
    if not isinstance(strategy, str) or strategy.upper() not in STRATEGIES:
        raise ValueError('Unsupported indicator strategy')
    name = strategy.upper()
    if parameters is not None and not isinstance(parameters, dict):
        raise ValueError('Strategy parameters must be an object')
    parameters = parameters or {}
    specs = STRATEGIES[name]['parameters']
    if set(parameters) - set(specs):
        raise ValueError('Unknown strategy parameter: ' + ', '.join(sorted(map(str, set(parameters)-set(specs)))))
    result = {}
    for key, spec in specs.items():
        value = parameters.get(key, spec['default'])
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(key+' must be a finite number')
        if not spec['min'] <= value <= spec['max'] or not math.isfinite(value) or (spec['type']=='int' and value!=int(value)):
            raise ValueError(key+' is outside its supported range')
        result[key] = int(value) if spec['type']=='int' else float(value)
    for fast, slow in [('sma_fast_period','sma_slow_period'),('ema_fast_period','ema_slow_period'),('ema_fast_period','trend_period'),('macd_fast','macd_slow'),('tenkan_period','kijun_period'),('kijun_period','senkou_period')]:
        if fast in result and slow in result and result[fast]>=result[slow]:
            raise ValueError(f'{fast} must be below {slow}')
    if 'ema_mid_period' in result and not result['ema_fast_period']<result['ema_mid_period']<result['ema_slow_period']:
        raise ValueError('Triple EMA periods must be strictly increasing')
    if 'oversold' in result and result['oversold']>=result['overbought']:
        raise ValueError('Oversold threshold must be below overbought')
    return result


def warmup_bars(strategy, parameters=None):
    p=validate_parameters(strategy,parameters);name=strategy.upper()
    required=max([35]+[int(v)+2 for k,v in p.items() if k.endswith('_period')])
    if name=='MACD':required=max(required,p['macd_slow']+p['macd_signal_period']+2)
    if name=='ADX_DMI':required=max(required,2*p['adx_period']+2)
    if name=='STOCH_RSI':required=max(required,p['rsi_period']+p['stoch_rsi_period']+2)
    if name=='ICHIMOKU':required=max(required,p['senkou_period']+p['cloud_displacement']+2)
    if name=='MOMENTUM':required=max(required,p['momentum_period']+p['accel_period']+2)
    return required


def evaluate_signal(candles, values, idx, strategy, parameters=None):
    """Evaluate one CLOSED candle; UP/DOWN is a candidate, never broker approval."""
    p=validate_parameters(strategy,parameters);name=strategy.upper()
    if not isinstance(candles,list) or isinstance(idx,bool) or not isinstance(idx,int) or not 0<=idx<len(candles):
        raise ValueError('Signal index is outside candle history')
    def candle(at):
        row=candles[at]
        if not isinstance(row,dict) or any(isinstance(row.get(key),bool) for key in ('time','open','high','low','close')):
            raise ValueError('Signal candles must contain numeric OHLC and timestamps')
        try:
            prices={key:float(row[key]) for key in ('open','high','low','close')}
            stamp=float(row['time'])
        except (ValueError,TypeError,KeyError,OverflowError):
            raise ValueError('Signal candles must contain numeric OHLC and timestamps') from None
        if (not math.isfinite(stamp) or stamp!=int(stamp) or not -62135596800<=stamp<=253370764800
                or not all(math.isfinite(v) and 1e-100<=v<=1e100 for v in prices.values())
                or prices['low']>min(prices['open'],prices['close'])
                or prices['high']<max(prices['open'],prices['close'])):
            raise ValueError('Signal candle is outside the supported OHLC/time range')
        return {**prices,'time':int(stamp)}
    current=candle(idx)
    previous=candle(idx-1) if idx else None
    if previous is not None and previous['time']>=current['time']:
        raise ValueError('Signal candles must have increasing timestamps')
    if values is None:
        from engine import indicators
        values=indicators(candles,p)
    if not isinstance(values,dict):raise ValueError('Indicator values must be an object')
    required=warmup_bars(name,p)
    result={'side':None,'strategy':name,'strategy_version':STRATEGY_VERSION,
            'parameters':p,'rule_parameters':p,'warmup_bars':required,
            'eligible_regimes':STRATEGIES[name]['eligible_regimes'],
            'signal_at':current['time'],'confirmed_at':current['time'],
            'explanation':'No completed rule transition; no trade candidate.',
            'evidence':{},'confidence':None,'execution_authorized':False,'stop':None}
    if idx+1<required:
        result['explanation']=f'Need at least {required} closed bars for this parameter set; no candidate.'
        return result
    def value(key, at=idx):
        sequence=values.get(key)
        if not isinstance(sequence,(list,tuple)) or len(sequence)!=len(candles):
            raise ValueError('Indicator series does not match candle history: '+key)
        raw=sequence[at]
        if raw is None:return None
        if isinstance(raw,bool) or not isinstance(raw,(int,float)) or abs(raw)>1e250 or not math.isfinite(raw):
            raise ValueError('Indicator evidence must be finite')
        return raw
    def cross(a,b,level=0.):
        if a is None or b is None:return None
        return 'UP' if a<=level<b else 'DOWN' if a>=level>b else None
    def series_cross(key, level=0.):return cross(value(key,idx-1),value(key),level)
    def difference_cross(a,b):
        old=(value(a,idx-1),value(b,idx-1));new=(value(a),value(b))
        if None in old+new:return None
        return cross(old[0]-old[1],new[0]-new[1])
    close=current['close'];prior=previous['close']
    side=None;used=[]
    if name in ('RSI','STOCHASTIC','STOCH_RSI'):
        key={'RSI':'rsi','STOCHASTIC':'stoch','STOCH_RSI':'stoch_rsi'}[name]
        a,b=value(key,idx-1),value(key);used=[key]
        if a is not None and b is not None:
            side='UP' if a<p['oversold']<=b else 'DOWN' if a>p['overbought']>=b else None
    elif name=='WILLIAMS_R':
        crossed=series_cross('williams_r',-50);recent=[value('williams_r',j) for j in range(max(0,idx-p['recovery_window']),idx)];used=['williams_r']
        if None not in recent:
            side=crossed if (crossed=='UP' and min(recent)<=p['oversold']) or (crossed=='DOWN' and max(recent)>=p['overbought']) else None
    elif name=='CCI':
        a,b=value('cci',idx-1),value('cci');used=['cci']
        if a is not None and b is not None:side='UP' if a<-p['cci_level']<=b else 'DOWN' if a>p['cci_level']>=b else None
    elif name=='MACD':side=difference_cross('macd','macd_signal');used=['macd','macd_signal']
    elif name=='SMA':side=difference_cross('sma_fast','sma_slow');used=['sma_fast','sma_slow']
    elif name=='EMA_CROSS':side=difference_cross('ema_fast','ema_slow');used=['ema_fast','ema_slow']
    elif name=='EMA_PULLBACK':
        a,b=value('pullback_ema',idx-1),value('pullback_ema');trend,oldtrend=value('trend_ema'),value('trend_ema',idx-1);used=['pullback_ema','trend_ema']
        if None not in (a,b,trend,oldtrend):
            side='UP' if prior<=a and close>b and close>trend and trend>oldtrend else 'DOWN' if prior>=a and close<b and close<trend and trend<oldtrend else None
    elif name=='TRIPLE_EMA':
        crossed=difference_cross('triple_fast','triple_mid');mid,slow=value('triple_mid'),value('triple_slow');used=['triple_fast','triple_mid','triple_slow']
        if mid is not None and slow is not None:side=crossed if (crossed=='UP' and mid>slow) or (crossed=='DOWN' and mid<slow) else None
    elif name=='RSI_TREND':
        crossed=series_cross('rsi',p['rsi_midpoint']);trend,old=value('trend_ema'),value('trend_ema',idx-1);used=['rsi','trend_ema']
        if trend is not None and old is not None:side=crossed if (crossed=='UP' and close>trend>old) or (crossed=='DOWN' and close<trend<old) else None
    elif name=='ROC':
        a,b=value('roc',idx-1),value('roc');used=['roc']
        if a is not None and b is not None:side='UP' if a<=p['roc_threshold']<b else 'DOWN' if a>=-p['roc_threshold']>b else None
    elif name=='MOMENTUM':
        crossed=series_cross('momentum_accel');momentum=value('momentum');used=['momentum','momentum_accel']
        if momentum is not None:side=crossed if (crossed=='UP' and momentum>0) or (crossed=='DOWN' and momentum<0) else None
    elif name=='ADX_DMI':
        crossed=difference_cross('plus_di','minus_di');strength=value('adx');used=['plus_di','minus_di','adx']
        if strength is not None and strength>=p['adx_min']:side=crossed
    elif name=='DONCHIAN':
        top,bottom=value('donchian_upper'),value('donchian_lower');oldtop,oldbottom=value('donchian_upper',idx-1),value('donchian_lower',idx-1);used=['donchian_upper','donchian_lower']
        if None not in (top,bottom,oldtop,oldbottom):side='UP' if close>top and prior<=oldtop else 'DOWN' if close<bottom and prior>=oldbottom else None
    elif name=='ATR_BREAKOUT':
        atr=value('atr',idx-1);used=['atr']
        if atr is not None and atr>0:side='UP' if close>prior+p['atr_multiple']*atr else 'DOWN' if close<prior-p['atr_multiple']*atr else None
    elif name=='KELTNER':
        top,bottom=value('keltner_upper'),value('keltner_lower');oldtop,oldbottom=value('keltner_upper',idx-1),value('keltner_lower',idx-1);used=['keltner_upper','keltner_lower']
        if None not in (top,bottom,oldtop,oldbottom):side='UP' if close>top and prior<=oldtop else 'DOWN' if close<bottom and prior>=oldbottom else None
    elif name in ('BOLLINGER','BOLLINGER_REENTRY','BOLLINGER_SQUEEZE'):
        top,bottom=value('bb_upper'),value('bb_lower');oldtop,oldbottom=value('bb_upper',idx-1),value('bb_lower',idx-1);used=['bb_upper','bb_lower','bb_width_pct']
        if None not in (top,bottom,oldtop,oldbottom):
            if name=='BOLLINGER':side='UP' if close<bottom else 'DOWN' if close>top else None
            elif name=='BOLLINGER_REENTRY':side='UP' if prior<oldbottom and bottom<=close<top else 'DOWN' if prior>oldtop and bottom<close<=top else None
            elif value('bb_width_pct',idx-1) is not None and value('bb_width_pct',idx-1)<=p['squeeze_width_pct']:
                side='UP' if close>oldtop and prior<=oldtop else 'DOWN' if close<oldbottom and prior>=oldbottom else None
    elif name=='SUPERTREND':
        old,new=value('supertrend_direction',idx-1),value('supertrend_direction');used=['supertrend','supertrend_direction','atr']
        if old is not None and new is not None:side='UP' if old<0<new else 'DOWN' if old>0>new else None
    elif name=='ICHIMOKU':
        crossed=difference_cross('tenkan','kijun');a,b=value('cloud_a'),value('cloud_b');used=['tenkan','kijun','cloud_a','cloud_b']
        if a is not None and b is not None:side=crossed if (crossed=='UP' and close>max(a,b)) or (crossed=='DOWN' and close<min(a,b)) else None
    elif name=='AROON':
        crossed=difference_cross('aroon_up','aroon_down');up,down=value('aroon_up'),value('aroon_down');used=['aroon_up','aroon_down']
        if up is not None and down is not None:side=crossed if (crossed=='UP' and up>=p['aroon_min']) or (crossed=='DOWN' and down>=p['aroon_min']) else None
    elif name=='CONSENSUS':
        def votes(at):
            vals=[value(k,at) for k in ('trend_ema','rsi','macd','macd_signal','donchian_upper','donchian_lower')]
            if None in vals:return (0,0)
            trend,r,macd,sig,top,bottom=vals;c=float(candles[at]['close'])
            return (sum((c>trend,r>50,macd>sig,c>top)),sum((c<trend,r<50,macd<sig,c<bottom)))
        old,new=votes(idx-1),votes(idx);used=['trend_ema','rsi','macd','macd_signal','donchian_upper','donchian_lower']
        side='UP' if old[0]<p['consensus_votes']<=new[0] else 'DOWN' if old[1]<p['consensus_votes']<=new[1] else None
        result['evidence']['votes']={'up':new[0],'down':new[1],'required':p['consensus_votes'],'probability':None}
    result['evidence'].update({'bar_open_at':current['time'],
        'bar_time_semantics':'UTC opening epoch; caller must supply completed bars only','close':close,
        'previous_close':prior,'indicator_values':{key:{'previous':value(key,idx-1),'current':value(key)} for key in used}})
    result['side']=side
    result['trigger']=close
    if side:
        atr=value('atr')
        distance=2*atr if atr is not None and atr>0 else None
        # A virtual protective boundary is evidence for paper sizing only, not
        # a broker stop on fixed-stake options. Do not invent one on flat data.
        if distance is not None and distance<close*.25:
            result['stop']=close-distance if side=='UP' else close+distance
        result['explanation']=f'{STRATEGIES[name]["name"]}: {side} candidate. '+STRATEGIES[name]['description']+' Risk, calendar, regime and broker checks are still required.'
    return result


# Keep visible default warmups consistent with the same validation used at
# execution time. Configured periods may require a longer warmup.
for _strategy_id, _definition in STRATEGIES.items():
    _definition['warmup_bars']=warmup_bars(_strategy_id)
