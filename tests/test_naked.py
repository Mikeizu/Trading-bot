"""Tests for original algorithmic interpretations. All broker interactions mocked."""
import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from naked_strategies import (STRATEGIES,PROFILES,StrategyError,backtest,
    sample_candles,candles_valid,resample,confirmed_signal,zone_levels,detect)
from strategy_extension import StrategySupervisor
from paper_engine import PaperBook
from deriv_bridge import BrokerController,BridgeError
from deriv_server import Journal
from test_deriv import FakeTransport

class StrategyUnitTests(unittest.TestCase):
    def setUp(self):self.candles=sample_candles(550,300)
    def test_all_seven_strategies_can_backtest(self):
        for strategy in STRATEGIES:
            with self.subTest(strategy=strategy):
                r=backtest(self.candles,strategy,'scalping','5m')
                self.assertEqual(r['bars'],550)
                self.assertEqual(r['overall']['trades'],r['train']['trades']+r['test']['trades'])
                self.assertFalse(r['research_pass']) # sample deliberately insufficient/unproven
    def test_no_future_bar_data_leaks_into_signal(self):
        for strategy in STRATEGIES:
            baseline=detect(self.candles,340,strategy)
            altered=self.candles[:341]+[{**c,'close':c['close']*1.2,'high':c['high']*1.2} for c in self.candles[341:]]
            self.assertEqual(baseline,detect(altered,340,strategy))
    def test_resample_consistency(self):
        t=1_700_000_000
        t=t-(t%86400)
        rows=[{'time':t+86400*i,'open':1.0,'high':1.3,'low':.8,'close':1.1+i*.01} for i in range(35)]
        weeks=resample(rows,'1w')
        self.assertLess(len(weeks),len(rows))
        self.assertEqual(weeks[0]['open'],rows[0]['open'])
    def test_invalid_data_and_params_fail(self):
        with self.assertRaises(StrategyError):candles_valid([{'time':1,'open':1,'high':.5,'low':.8,'close':1}])
        with self.assertRaises(StrategyError):backtest(self.candles,'kangaroo','position','1m')
        with self.assertRaises(StrategyError):backtest(self.candles,'kangaroo','scalping','5m',payout=100)
    def test_cannot_certify_when_no_trades(self):
        flat=[{'time':i*300,'open':1,'close':1,'high':1.00001,'low':.99999} for i in range(300)]
        r=backtest(flat,'kangaroo','scalping','5m')
        self.assertEqual(r['overall']['trades'],0)
        self.assertFalse(r['research_pass'])
    def test_research_separates_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=BrokerController(Journal(Path(tmp)/'orders.db'),FakeTransport())
            s=StrategySupervisor(b,Path(tmp)/'signals.db')
            report=s.research({'source':'synthetic','strategy':'shadow','profile':'scalping','timeframe':'5m'})
            self.assertIn('Synthetic',report['source'])

class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.t=FakeTransport()
        self.b=BrokerController(Journal(Path(self.tmp.name)/'orders.db'),self.t,allow_live=True)
        self.s=StrategySupervisor(self.b,Path(self.tmp.name)/'signals.db')
    def tearDown(self):self.tmp.cleanup()
    def connect(self,mode):
        self.b.connect('valid-app-id','demo-test-token','DOT90000001' if mode=='demo' else 'DOT90000002',mode)
    def opt(self,action='monitor',frame='5m',profile='scalping'):
        return {'strategy':'kangaroo','profile':profile,'timeframe':frame,'symbol':'R_100',
                'action':action,'stake':1,'expiry_minutes':3}
    def test_cannot_start_without_broker(self):
        with self.assertRaises(BridgeError):self.s.configure(self.opt())
    def test_real_money_cannot_be_auto_traded(self):
        self.connect('real')
        with self.assertRaises(BridgeError):self.s.configure(self.opt('demo_trade'))
        self.assertEqual(self.t.buy_count,0)
    def test_longer_period_order_rejected_even_on_demo(self):
        self.connect('demo')
        with self.assertRaises(BridgeError):self.s.configure(self.opt('demo_trade','1w','position'))
        self.assertEqual(self.t.buy_count,0)
    def test_long_term_paper_is_supported_without_broker_orders(self):
        self.connect('real')
        result=self.s.configure(self.opt('paper_trade','1w','position'))
        self.assertEqual(result['action'],'paper_trade')
        self.assertEqual(self.t.buy_count,0)
    def test_unknown_orders_not_sent(self):
        self.connect('demo');self.s.configure(self.opt('demo_trade'))
        self.s.tick() # mock returns zero candles
        self.assertEqual(self.t.buy_count,0)
    def test_paper_simulation_stop_first_and_no_duplicate(self):
        self.connect('demo')
        p=self.s.paper
        sig={'side':'UP','stop':99,'confirmed_at':1000}
        idx=p.open(self.b.account_id,'R_100','1d','kangaroo',sig,100)
        self.assertIsInstance(idx,int)
        self.assertEqual(p.positions(self.b.account_id)[0]['status'],'PENDING')
        self.assertIsNone(p.open(self.b.account_id,'R_100','1d','kangaroo',sig,100))
        # Next open fills, then both stop/target touch -> conservative .5% loss.
        p.reconcile(self.b.account_id,'R_100','1d',[{'time':2000,'open':100,'close':100,'high':103,'low':98}])
        self.assertEqual(p.positions(self.b.account_id)[0]['pnl'],-50.0)
        self.assertEqual(p.balance(self.b.account_id),9950)

if __name__=='__main__':unittest.main()
