"""Deterministic rule/indicator checks, not evidence of trading accuracy.

Controlled indicator vectors isolate the published entry rules. Separate tests
exercise actual OHLC calculations and prove that future bars do not change past
values or signals. No broker or network is used.
"""
import copy
import json
import math
import unittest
from unittest.mock import patch

from engine import backtest, indicators, signal_at
from indicator_strategies import (STRATEGIES, STRATEGY_VERSION, evaluate_signal,
                                  validate_parameters, warmup_bars)
from market_data import sample_candles


def flat_rows(count=150):
    return [{'time':1_700_000_000+i*60,'open':100.,'high':101.,'low':99.,'close':100.}
            for i in range(count)]


def rule_fixture(name,side):
    """Controlled rule evidence; fictional values never shown as market data."""
    rows=flat_rows();i=120;up=side=='UP'
    p=validate_parameters(name);v=indicators(rows,p)
    def pair(key,previous,current):v[key][i-1]=previous;v[key][i]=current
    def close(previous,current):
        for at,value in ((i-1,previous),(i,current)):
            rows[at].update(open=value,close=value,high=max(101.,value+1),low=min(99.,value-1))
    close(100.,100.5 if up else 99.5)
    if name in ('RSI','STOCHASTIC','STOCH_RSI'):
        key={'RSI':'rsi','STOCHASTIC':'stoch','STOCH_RSI':'stoch_rsi'}[name]
        pair(key,p['oversold']-1,p['oversold']+1) if up else pair(key,p['overbought']+1,p['overbought']-1)
    elif name=='WILLIAMS_R':
        pair('williams_r',-55 if up else -45,-45 if up else -55)
        v['williams_r'][i-3]=p['oversold']-1 if up else p['overbought']+1
    elif name=='CCI':pair('cci',-110 if up else 110,-90 if up else 90)
    elif name=='MACD':pair('macd',-1 if up else 1,1 if up else -1);pair('macd_signal',0,0)
    elif name in ('SMA','EMA_CROSS'):
        fast,slow=('sma_fast','sma_slow') if name=='SMA' else ('ema_fast','ema_slow')
        pair(fast,99 if up else 101,101 if up else 99);pair(slow,100,100)
    elif name=='EMA_PULLBACK':
        close(99 if up else 101,101 if up else 99)
        pair('pullback_ema',100,100);pair('trend_ema',99 if up else 101,100)
    elif name=='TRIPLE_EMA':
        pair('triple_fast',99 if up else 101,101 if up else 99)
        pair('triple_mid',100,100);pair('triple_slow',99 if up else 101,99 if up else 101)
    elif name=='RSI_TREND':
        pair('rsi',49 if up else 51,51 if up else 49)
        pair('trend_ema',98 if up else 102,99 if up else 101)
    elif name=='ROC':pair('roc',-1 if up else 1,1 if up else -1)
    elif name=='MOMENTUM':
        pair('momentum_accel',-1 if up else 1,1 if up else -1)
        pair('momentum',10 if up else -10,10 if up else -10)
    elif name=='ADX_DMI':
        pair('plus_di',5 if up else 15,15 if up else 5)
        pair('minus_di',10,10);pair('adx',25,25)
    elif name in ('DONCHIAN','KELTNER'):
        prefix='donchian' if name=='DONCHIAN' else 'keltner'
        close(100,101 if up else 99)
        pair(prefix+'_upper',100 if up else 102,100.5 if up else 102)
        pair(prefix+'_lower',98 if up else 100,98 if up else 99.5)
    elif name=='ATR_BREAKOUT':close(100,104 if up else 96);pair('atr',1,1)
    elif name=='BOLLINGER':close(100,98 if up else 102);pair('bb_upper',101,101);pair('bb_lower',99,99)
    elif name=='BOLLINGER_REENTRY':close(98 if up else 102,100);pair('bb_upper',101,101);pair('bb_lower',99,99)
    elif name=='BOLLINGER_SQUEEZE':
        close(100,102 if up else 98);pair('bb_upper',101,101);pair('bb_lower',99,99);pair('bb_width_pct',1,1)
    elif name=='SUPERTREND':pair('supertrend_direction',-1 if up else 1,1 if up else -1)
    elif name=='ICHIMOKU':
        pair('tenkan',99 if up else 101,101 if up else 99);pair('kijun',100,100)
        pair('cloud_a',99 if up else 101,99 if up else 101)
        pair('cloud_b',98 if up else 102,98 if up else 102)
    elif name=='AROON':
        pair('aroon_up',50 if up else 70,80 if up else 20)
        pair('aroon_down',70 if up else 50,20 if up else 80)
    elif name=='CONSENSUS':
        pair('trend_ema',99 if up else 101,99 if up else 101)
        pair('rsi',60 if up else 40,60 if up else 40)
        pair('macd',-1 if up else 1,1 if up else -1);pair('macd_signal',0,0)
        pair('donchian_upper',110,110);pair('donchian_lower',90,90)
    else:raise AssertionError('Missing explicit rule fixture for '+name)
    return rows,v,i,p


class IndicatorCatalogTests(unittest.TestCase):
    def test_original_six_ids_preserved_and_book_patterns_removed(self):
        self.assertTrue({'RSI','MACD','CCI','SMA','BOLLINGER','STOCHASTIC'}<=set(STRATEGIES))
        self.assertEqual(len(STRATEGIES),24)
        self.assertEqual(len({v['name'] for v in STRATEGIES.values()}),len(STRATEGIES))
        self.assertFalse({'kangaroo','shadow','belt','wammie','moolah','last_kiss','trendy_kangaroo'}&set(STRATEGIES))

    def test_catalog_metadata_is_json_and_default_warmup_matches_runtime(self):
        json.dumps(STRATEGIES,allow_nan=False)
        for name,definition in STRATEGIES.items():
            with self.subTest(strategy=name):
                self.assertEqual(definition['warmup_bars'],warmup_bars(name))
                self.assertEqual(definition['version'],STRATEGY_VERSION)
                self.assertTrue(definition['description'])
                self.assertTrue(definition['eligible_regimes'])
                self.assertEqual(set(validate_parameters(name)),set(definition['parameters']))

    def test_every_rule_has_explicit_up_and_down_positive_case(self):
        for name in STRATEGIES:
            for side in ('UP','DOWN'):
                with self.subTest(strategy=name,side=side):
                    rows,values,index,parameters=rule_fixture(name,side)
                    result=evaluate_signal(rows,values,index,name,parameters)
                    self.assertEqual(result['side'],side)
                    self.assertEqual(signal_at(rows,values,index,name,parameters),side)
                    self.assertEqual(result['strategy'],name)
                    self.assertIsNone(result['confidence'])
                    self.assertFalse(result['execution_authorized'])
                    self.assertIn('Risk, calendar, regime',result['explanation'])
                    self.assertTrue(result['evidence']['indicator_values'])
                    if result['stop'] is not None:
                        self.assertLess(result['stop'],rows[index]['close']) if side=='UP' else self.assertGreater(result['stop'],rows[index]['close'])
                    json.dumps(result,allow_nan=False)

    def test_flat_actual_ohlc_produces_no_signal_in_every_rule(self):
        rows=flat_rows(200)
        for name in STRATEGIES:
            with self.subTest(strategy=name):
                p=validate_parameters(name);v=indicators(rows,p)
                self.assertIsNone(signal_at(rows,v,len(rows)-1,name,p))

    def test_each_parameter_rejects_bool_nan_infinity_and_outside_bounds(self):
        for name,definition in STRATEGIES.items():
            for key,spec in definition['parameters'].items():
                for value in (True,float('nan'),float('inf'),10**1000,spec['min']-1,spec['max']+1):
                    with self.subTest(strategy=name,key=key,value=value),self.assertRaises(ValueError):
                        validate_parameters(name,{key:value})
                if spec['type']=='int':
                    with self.subTest(strategy=name,key=key),self.assertRaises(ValueError):
                        validate_parameters(name,{key:spec['min']+.5})

    def test_parameter_relationships_and_unknown_keys_are_rejected(self):
        invalid=[('SMA',{'sma_fast_period':30,'sma_slow_period':20}),
                 ('MACD',{'macd_fast':30,'macd_slow':20}),
                 ('TRIPLE_EMA',{'ema_fast_period':25,'ema_mid_period':21}),
                 ('ICHIMOKU',{'kijun_period':40,'senkou_period':30})]
        for name,params in invalid:
            with self.subTest(name=name),self.assertRaises(ValueError):validate_parameters(name,params)
        for params in ([],True,{'made_up':1}):
            with self.assertRaises(ValueError):validate_parameters('RSI',params)

    def test_warmup_is_a_closed_bar_count_and_expands_with_parameters(self):
        self.assertEqual(warmup_bars('ICHIMOKU'),80)
        self.assertEqual(warmup_bars('ICHIMOKU',{'senkou_period':120,'cloud_displacement':60}),182)
        rows=flat_rows(200);p=validate_parameters('RSI');v=indicators(rows,p)
        required=warmup_bars('RSI',p)
        v['rsi'][required-3]=29;v['rsi'][required-2]=31
        self.assertIsNone(evaluate_signal(rows,v,required-2,'RSI',p)['side'])
        v['rsi'][required-2]=29;v['rsi'][required-1]=31
        self.assertEqual(evaluate_signal(rows,v,required-1,'RSI',p)['side'],'UP')

    def test_invalid_current_or_previous_candle_fails_cleanly(self):
        for field,value in [('close',True),('high',float('inf')),('time',1.5),('low',200)]:
            rows=flat_rows();v=indicators(rows);rows[120][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):evaluate_signal(rows,v,120,'RSI')
        rows=flat_rows();v=indicators(rows);rows[120]=None
        with self.assertRaises(ValueError):evaluate_signal(rows,v,120,'RSI')

    def test_missing_or_nonfinite_indicator_vectors_are_rejected(self):
        rows,values,index,p=rule_fixture('RSI','UP')
        for bad in (None,True,float('nan'),float('inf'),1e300,10**1000):
            modified=copy.deepcopy(values)
            if bad is None:modified['rsi']=[]
            else:modified['rsi'][index]=bad
            with self.subTest(value=bad),self.assertRaises(ValueError):evaluate_signal(rows,modified,index,'RSI',p)

    def test_extreme_period_and_direct_indicator_parameter_fail_cleanly(self):
        from engine import sma
        with self.assertRaises(ValueError):sma([1,2,3],10**1000)
        with self.assertRaises(ValueError):indicators(flat_rows(),{'rsi_period':10**1000})


class CausalIndicatorTests(unittest.TestCase):
    def test_all_actual_indicator_vectors_and_signals_are_prefix_causal(self):
        rows=sample_candles(300,60)
        for name in STRATEGIES:
            with self.subTest(strategy=name):
                parameters=validate_parameters(name)
                first=indicators(rows[:200],parameters);later=indicators(rows,parameters)
                for key in first:self.assertEqual(first[key],later[key][:200],key)
                self.assertEqual(evaluate_signal(rows[:200],first,180,name,parameters),
                                 evaluate_signal(rows,later,180,name,parameters))

    def test_ichimoku_cloud_uses_historical_spans_not_future_prices(self):
        rows=sample_candles(150,60);p=validate_parameters('ICHIMOKU')
        values=indicators(rows,p);at=120;origin=at-p['cloud_displacement']
        high=max(c['high'] for c in rows[origin-p['senkou_period']+1:origin+1])
        low=min(c['low'] for c in rows[origin-p['senkou_period']+1:origin+1])
        self.assertEqual(values['cloud_b'][at],(high+low)/2)
        changed=copy.deepcopy(rows)
        for c in changed[origin+1:]:
            for field in ('open','high','low','close'):c[field]*=2
        self.assertEqual(indicators(changed,p)['cloud_b'][at],values['cloud_b'][at])

    def test_donchian_excludes_signal_bar_and_aroon_ties_choose_latest(self):
        rows=flat_rows(70);rows[60].update(open=100,close=110,high=111,low=99)
        values=indicators(rows)
        self.assertEqual(values['donchian_upper'][60],101)
        flat=indicators(flat_rows(70))
        self.assertEqual(flat['aroon_up'][-1],100)
        self.assertEqual(flat['aroon_down'][-1],100)

    def test_wilder_atr_and_dmi_known_directional_fixture(self):
        rows=[{'time':i*60,'open':100+i,'high':102+i,'low':99+i,'close':101+i} for i in range(90)]
        values=indicators(rows)
        self.assertEqual(values['atr'][14],3)
        self.assertAlmostEqual(values['plus_di'][14],100/3)
        self.assertEqual(values['minus_di'][14],0)
        self.assertEqual(values['adx'][27],100)

    def test_every_strategy_can_backtest_with_finite_accounting(self):
        rows=sample_candles(280,60)
        for name in STRATEGIES:
            with self.subTest(strategy=name):
                report=backtest(rows,name,1,3,.8)
                self.assertEqual(report['ending_balance'],10000+report['net_pnl'])
                self.assertEqual(report['trade_count'],len(report['trades']))
                self.assertEqual(report['provenance']['configuration']['strategy'],name)
                json.dumps(report,allow_nan=False)

    def test_future_cadence_change_cannot_reclassify_past_legacy_trades(self):
        rows=flat_rows(110);later=copy.deepcopy(rows)
        # The appended 30-second interval must not retroactively change the
        # declared 60-second cadence used by the original 100 bars.
        later[-1]['time']=later[-2]['time']+30
        with patch('engine.signal_at',return_value='UP'):
            prefix=backtest(rows[:100],'RSI',1,1,.8)
            full=backtest(later,'RSI',1,1,.8)
        early=[t for t in full['trades'] if t['exit_index']<100]
        self.assertEqual(prefix['trades'],early)
        self.assertEqual(full['data_integrity']['inferred_bar_interval_seconds'],60)


if __name__=='__main__':unittest.main()
