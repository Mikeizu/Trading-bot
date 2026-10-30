"""No network calls, credentials, or real broker trades in this test module."""
from __future__ import annotations
import sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from indicator_strategies import STRATEGIES
from market_data import sample_candles
from strategy_selector import compare_all
from strategy_extension import StrategySupervisor
from deriv_bridge import BrokerController,BridgeError
from deriv_server import Journal
from test_deriv import FakeTransport


def fake_report(strategy, training_win=75, test_success=False):
    tr={'trades':42,'wins':31,'win_rate_pct':training_win,
        'wilson_lower_95_pct':training_win-10,'pnl':100,
        'roi_pct':10,'max_drawdown_pct':4,'equity_curve':[]}
    hold={'trades':40,'wins':28,'win_rate_pct':70 if test_success else 42,
          'wilson_lower_95_pct':58 if test_success else 29,
          'pnl':80 if test_success else -100,'roi_pct':8 if test_success else -10,
          'max_drawdown_pct':5,'equity_curve':[]}
    return {'strategy':strategy,'train':tr,'test':hold,'break_even_win_rate_pct':55.56,
            'research_pass':test_success,'assessment':'fake diagnostic test',
            'walk_forward':{'passed':True,'passes':3,'folds':[{'passed':True} for _ in range(3)]}}

class ComparisonTests(unittest.TestCase):
    def setUp(self):self.rows=sample_candles(250,300)
    def test_runs_every_strategy_on_same_candles(self):
        with patch('strategy_selector.backtest',side_effect=lambda rows,strategy,*a,**kw:fake_report(strategy,70,False)) as test:
            r=compare_all(self.rows,profile='scalping',timeframe='5m')
        self.assertEqual(test.call_count,len(STRATEGIES))
        self.assertEqual({x['strategy'] for x in r['ranked']},set(STRATEGIES))
        self.assertFalse(r['qualified'])
    def test_never_promotes_runner_up_on_holdout_success(self):
        # First (RSI) has best TRAIN metrics but fails holdout.
        # Second (MACD) has lower TRAIN score but passes holdout.
        def simulate(rows,strategy,*a,**kw):
            if strategy=='RSI':return fake_report(strategy,85,False)
            if strategy=='MACD':return fake_report(strategy,75,True)
            return fake_report(strategy,50,False)
        with patch('strategy_selector.backtest',side_effect=simulate):
            r=compare_all(self.rows,profile='scalping',timeframe='5m')
        self.assertEqual(r['training_candidate'],'RSI')
        self.assertIsNone(r['winner'])
        self.assertFalse(r['qualified'])
    def test_training_winner_passed_holdout_can_be_named(self):
        def simulate(rows,strategy,*a,**kw):
            return fake_report(strategy,85 if strategy=='RSI' else 50,
                               strategy=='RSI')
        with patch('strategy_selector.backtest',side_effect=simulate):
            r=compare_all(self.rows,profile='scalping',timeframe='5m')
        self.assertEqual(r['winner'],'RSI')
        self.assertTrue(r['qualified'])
    def test_real_scan_never_validates_synthetic(self):
        result=compare_all(self.rows,profile='scalping',timeframe='5m')
        self.assertEqual(result['strategies_tested'],len(STRATEGIES))
        self.assertIsNone(result['winner'])

class RecentTransport(FakeTransport):
    def candles(self,symbol,count=600,granularity=300):
        values=sample_candles(600,granularity)
        last_complete=(int(time.time())//granularity-1)*granularity
        first=last_complete-(len(values)-1)*granularity
        return [{**x,'time':first+i*granularity} for i,x in enumerate(values)]

class BestActivationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.broker=BrokerController(Journal(Path(self.tmp.name)/'orders.db'),RecentTransport(),allow_live=True)
        self.supervisor=StrategySupervisor(self.broker,Path(self.tmp.name)/'signals.db')
        self.broker.connect('testappid','demo-test-token','DOT90000001','demo')
        self.input={'source':'deriv','symbol':'R_100','profile':'scalping','timeframe':'5m',
                    'payout':.8,'stake':1,'expiry_bars':3,'target_win_rate':65}
    def tearDown(self):self.broker.disconnect();self.tmp.cleanup()
    def _fake_comparison(self,**kwargs):
        return {'qualified':True,'winner':'RSI','training_candidate':'RSI',
                'strategies_tested':len(STRATEGIES),'ranked':[{'strategy':'RSI','name':'RSI re-entry'}],
                'selection_method':'training only','verdict':'research pass'}
    def test_selects_server_side_only_and_starts_monitor(self):
        with patch('strategy_extension.compare_all',side_effect=lambda *a,**kw:self._fake_comparison()):
            result=self.supervisor.scan_all(self.input)
        self.assertTrue(result['auto_eligible'])
        started=self.supervisor.activate_best({'strategy':'CCI','symbol':'EVIL','action':'monitor','stake':1})
        self.assertEqual(started['strategy'],'RSI')
        self.assertEqual(started['symbol'],'R_100')
        self.assertTrue(started['auto_selected'])
    def test_synthetic_comparison_never_authorizes_broker_execution(self):
        with patch('strategy_extension.compare_all',side_effect=lambda *a,**kw:self._fake_comparison()):
            result=self.supervisor.scan_all({**self.input,'source':'synthetic'})
        self.assertFalse(result['auto_eligible'])
        with self.assertRaises(BridgeError):self.supervisor.activate_best({'action':'demo_trade'})
    def test_no_approval_no_trade(self):
        with self.assertRaises(BridgeError):self.supervisor.activate_best({'action':'demo_trade'})
    def test_account_change_invalidates_selection(self):
        with patch('strategy_extension.compare_all',side_effect=lambda *a,**kw:self._fake_comparison()):
            self.supervisor.scan_all(self.input)
        self.broker.disconnect()
        with self.assertRaises(BridgeError):self.supervisor.activate_best({'action':'monitor'})
    def test_real_automation_rejected_even_after_qualified_scan(self):
        self.broker.disconnect()
        self.broker.connect('testappid','demo-test-token','DOT90000002','real')
        with patch('strategy_extension.compare_all',side_effect=lambda *a,**kw:self._fake_comparison()):
            self.supervisor.scan_all(self.input)
        with self.assertRaises(BridgeError):self.supervisor.activate_best({'action':'demo_trade'})
        self.assertEqual(self.broker.transport.buy_count,0)
    def test_demo_expiry_must_match_backtest_bars(self):
        with patch('strategy_extension.compare_all',side_effect=lambda *a,**kw:self._fake_comparison()):
            self.supervisor.scan_all(self.input)
        # 5m x 3 bars = 15-minute Deriv option; 3 minutes is invalid.
        with self.assertRaises(BridgeError):
            self.supervisor.activate_best({'action':'demo_trade','stake':1,'expiry_minutes':3})
        result=self.supervisor.activate_best({'action':'demo_trade','stake':1,'expiry_minutes':15})
        self.assertEqual(result['expiry_minutes'],15)
        self.assertTrue(result['auto_selected'])
    def test_bogus_browser_approval_flag_has_no_effect(self):
        # Browser POST /start is not allowed to claim it passed scan validation.
        result=self.supervisor.configure({'strategy':'RSI','profile':'scalping',
             'timeframe':'5m','symbol':'R_100','action':'monitor','stake':1,
             '_validated_best':True})
        self.assertFalse(result['auto_selected'])
    def test_actual_demo_quote_below_assumption_stops_bot(self):
        self.input['payout']=.9  # assume 90%; fake Deriv quote pays only 80% net
        with patch('strategy_extension.compare_all',side_effect=lambda *a,**kw:self._fake_comparison()):
            self.supervisor.scan_all(self.input)
        self.supervisor.activate_best({'action':'demo_trade','stake':1,'expiry_minutes':15})
        now=time.time()
        self.broker.risk.set_calendar(self.broker.account_id,'demo',[],now,now+3600,
                                      'Deterministic test fixture; not a production calendar')
        sig={'side':'UP','confirmed_at':int(time.time())//300*300-300,
             'explanation':'test signal','stop':1,'trigger':1.2}
        eligible={'regime':'ranging','trading_allowed':True,'eligible_strategies':['RSI'],
                  'reasons':['Deterministic eligible regime fixture']}
        with patch('strategy_extension.confirmed_signal',return_value=sig), patch('strategy_extension.classify_regime',return_value=eligible):
            self.supervisor.tick()
        state=self.supervisor.status()
        self.assertFalse(state['active'])
        self.assertIn('payout',state['error'].lower())
        self.assertEqual(self.broker.transport.buy_count,0)
    def test_stale_comparison_rejected(self):
        with patch('strategy_extension.compare_all',side_effect=lambda *a,**kw:self._fake_comparison()):
            self.supervisor.scan_all(self.input)
        self.supervisor.best_selection['created_at']-=7200
        with self.assertRaises(BridgeError):self.supervisor.activate_best({'action':'monitor'})

if __name__=='__main__':unittest.main()
