"""Generic indicator orchestration; all broker responses are local test doubles."""
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from market_data import sample_candles, StrategyError
from indicator_strategies import STRATEGIES, STRATEGY_VERSION, validate_parameters
from strategy_extension import StrategySupervisor, confirmed_signal
from test_supervisor_safety import BrokerStandIn, ELIGIBLE


class IndicatorSupervisorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'strategy_signals.db'
        self.broker=BrokerStandIn()
        self.supervisor=StrategySupervisor(self.broker,self.path)
        self.rows=sample_candles(350,300)
        last=(int(time.time())//300-1)*300
        self.rows=[{**r,'time':last-(len(self.rows)-1-i)*300} for i,r in enumerate(self.rows)]
        self.supervisor.read_closed=lambda *args,**kwargs:self.rows

    def tearDown(self):self.tmp.cleanup()

    def options(self,strategy='RSI',action='monitor',**overrides):
        return {'strategy':strategy,'profile':'scalping','timeframe':'5m','symbol':'R_100',
                'action':action,'stake':1,'expiry_minutes':3,**overrides}

    def signal(self,**overrides):
        return {'side':'UP','confirmed_at':self.rows[-1]['time'],'stop':self.rows[-1]['close']*.99,
                'explanation':'RSI crossed a configured threshold on a closed fixture candle.',
                'evidence':{'rsi':31.0,'threshold':30.0},'strategy_version':STRATEGY_VERSION,**overrides}

    def test_retired_strategies_cannot_be_activated_or_remapped(self):
        for strategy in ('kangaroo','shadow','belt','wammie','moolah','last_kiss','trendy_kangaroo'):
            with self.subTest(strategy=strategy):
                self.assertNotIn(strategy,STRATEGIES)
                with self.assertRaises(StrategyError):self.supervisor.configure(self.options(strategy))
                self.assertFalse(self.supervisor.active)
        self.assertEqual(self.broker.buys,[])

    def test_entire_indicator_catalog_can_explicitly_start_and_stop_monitoring(self):
        self.assertGreaterEqual(len(STRATEGIES),18)
        for strategy in STRATEGIES:
            with self.subTest(strategy=strategy):
                state=self.supervisor.configure(self.options(strategy))
                self.assertTrue(state['active'])
                self.assertEqual(state['strategy'],strategy)
                self.assertEqual(state['parameters'],validate_parameters(strategy))
                self.assertEqual(state['strategy_version'],STRATEGY_VERSION)
                self.supervisor.stop()
        self.assertEqual(self.broker.buys,[])

    def test_new_constructor_stays_stopped_and_uses_neutral_paper_journal(self):
        self.assertFalse(self.supervisor.active)
        self.assertEqual(self.supervisor.strategy,'RSI')
        self.assertEqual(self.supervisor.paper.path.name,'paper_positions.db')
        self.assertFalse((self.path.parent/'naked_paper.db').exists())

    def test_closed_signal_wraps_explanation_without_changing_direction_or_timestamp(self):
        signal=self.signal()
        params=validate_parameters('RSI')
        with patch('strategy_extension.evaluate_signal',return_value=signal) as evaluate:
            result=confirmed_signal(self.rows,'RSI',params)
        evaluate.assert_called_once_with(self.rows,None,len(self.rows)-1,'RSI',parameters=params)
        self.assertIs(result,signal)
        with patch('strategy_extension.evaluate_signal',return_value={'side':None,'explanation':'Insufficient evidence'}):
            self.assertIsNone(confirmed_signal(self.rows,'RSI',params))

    def test_malformed_indicator_results_fail_before_any_order(self):
        for invalid in (None,[],{'side':'BUY'},{'side':'UP'},self.signal(explanation=''),self.signal(evidence=[])):
            with self.subTest(result=invalid),patch('strategy_extension.evaluate_signal',return_value=invalid),self.assertRaises(StrategyError):
                confirmed_signal(self.rows,'RSI')
        self.assertEqual(self.broker.buys,[])

    def test_indicator_values_and_virtual_stop_provenance_survive_signal_audit(self):
        self.supervisor.configure(self.options())
        with patch('strategy_extension.evaluate_signal',return_value=self.signal()),patch('strategy_extension.classify_regime',return_value=ELIGIBLE):
            self.supervisor.tick()
        event=self.supervisor.book.recent(self.broker.account_id)[0]
        evidence=json.loads(event['evidence'])
        self.assertEqual(event['strategy'],'RSI')
        self.assertEqual(evidence['indicator_evidence'],{'rsi':31.,'threshold':30.})
        self.assertEqual(evidence['paper_invalidation']['kind'],'virtual_ATR_stop')
        self.assertFalse(evidence['paper_invalidation']['broker_stop_order'])
        self.assertEqual(event['action'],'SIGNAL_ONLY')
        self.assertEqual(self.broker.buys,[])

    def test_compare_all_maps_selected_parameters_only_to_its_strategy(self):
        options={'source':'synthetic','profile':'scalping','timeframe':'5m',
                 'strategy':'RSI','parameters':validate_parameters('RSI')}
        with patch('strategy_extension.compare_all',return_value={'qualified':False,'winner':None,'ranked':[]}) as compare:
            self.supervisor.scan_all(options)
        kwargs=compare.call_args.kwargs
        self.assertNotIn('parameters',kwargs)
        self.assertEqual(kwargs['parameters_by_strategy'],{'RSI':validate_parameters('RSI')})
        self.assertEqual(self.broker.buys,[])
        with self.assertRaises(StrategyError):
            self.supervisor.scan_all({**options,'parameters_by_strategy':{'RSI':validate_parameters('RSI')}})

    def test_cached_winner_keeps_actual_winner_rules_not_browser_selection(self):
        winner=next(strategy for strategy in STRATEGIES if strategy!='RSI')
        parameters=validate_parameters(winner)
        compared={'qualified':True,'winner':winner,'winner_parameters':parameters,
                  'ranked':[{'strategy':winner,'parameters':parameters}]}
        with patch('strategy_extension.compare_all',return_value=compared):
            result=self.supervisor.scan_all({'source':'deriv','symbol':'R_100',
                'profile':'scalping','timeframe':'5m','strategy':'RSI'})
        self.assertTrue(result['auto_eligible'])
        state=self.supervisor.activate_best({'action':'monitor','strategy':'RSI','parameters':{'made_up':True}})
        self.assertEqual(state['strategy'],winner)
        self.assertEqual(state['parameters'],parameters)
        self.assertEqual(self.broker.buys,[])

    def test_custom_regime_thresholds_are_forwarded_to_research(self):
        threshold={'high_volatility_pct':3.0}
        with patch('strategy_extension.backtest',return_value={}) as research:
            self.supervisor.research({'strategy':'RSI','source':'synthetic',
                                     'timeframe':'5m','profile':'scalping','regime_thresholds':threshold})
        self.assertEqual(research.call_args.kwargs['regime_thresholds'],threshold)


if __name__=='__main__':unittest.main()
