"""Safety tests of strategy orchestration with deterministic broker stand-ins."""
import tempfile, threading, time, unittest
from pathlib import Path
from unittest.mock import patch
from naked_strategies import sample_candles
from strategy_extension import StrategySupervisor
from deriv_bridge import BridgeError,DerivTransport

class RiskStandIn:
    def __init__(self):self.killed=False;self.calendar_allowed=True
    def status(self,account,mode):return {'killed':False,'global':{'killed':self.killed}}
    def calendar_status(self,account,mode,symbol,market_kind):
        return {'allowed':self.calendar_allowed,'fresh':self.calendar_allowed,'required':True,
                'reasons':[] if self.calendar_allowed else ['Test calendar unavailable']}

class BrokerStandIn:
    def __init__(self):
        self.lock=threading.RLock();self.mode='demo';self.account_id='DEMO_ACCOUNT'
        self.allowed_symbols=[{'symbol':'R_100'}];self.automation=False;self.risk=RiskStandIn()
        self.buys=[];self.context=None;self.quote=None;self.after_quote=None
    def available_durations(self,symbol):return {'UP':list(range(1,16)),'DOWN':list(range(1,16))}
    def new_quote(self,symbol,side,stake,minutes,*,internal=False,context=None):
        self.context=context;self.quote={'token':'test-only','ask_price':1,'payout':1.8}
        if self.after_quote:self.after_quote()
        return self.quote
    def buy_quote(self,token,*,internal=False):self.buys.append(token);return {'contract_id':'mock-contract'}

ELIGIBLE={'regime':'ranging','trading_allowed':True,'eligible_strategies':['kangaroo'],'reasons':['fixture']}
BLOCKED={'regime':'uncertain','trading_allowed':False,'eligible_strategies':[],'reasons':['Mixed evidence']}

class SupervisorSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'signals.db'
        self.b=BrokerStandIn();self.s=StrategySupervisor(self.b,self.path)
        self.rows=sample_candles(120,300);last=(int(time.time())//300-1)*300
        self.rows=[{**r,'time':last-(len(self.rows)-1-i)*300} for i,r in enumerate(self.rows)]
        self.s.read_closed=lambda *a,**kw:self.rows
        self.sig={'side':'UP','stop':self.rows[-1]['close']*.99,'trigger':self.rows[-1]['close'],
                  'confirmed_at':last,'explanation':'Confirmed test-only deterministic setup'}
    def tearDown(self):self.tmp.cleanup()
    def configure(self,action='demo_trade'):
        return self.s.configure({'strategy':'kangaroo','profile':'scalping','timeframe':'5m',
                                 'symbol':'R_100','action':action,'stake':1,'expiry_minutes':3})
    def tick(self,regime=ELIGIBLE):
        with patch('strategy_extension.confirmed_signal',return_value=self.sig),patch('strategy_extension.classify_regime',return_value=regime):self.s.tick()
    def test_regime_blocks_broker_and_virtual_new_entries(self):
        self.configure();self.tick(BLOCKED)
        self.assertEqual(self.b.buys,[])
        self.assertEqual(self.s.status()['events'][0]['action'],'BLOCKED_REGIME')
        self.s.stop();self.configure('paper_trade');self.tick(BLOCKED)
        self.assertEqual(self.s.paper.positions(self.b.account_id),[])
    def test_monitor_records_signal_and_linked_evidence_without_order(self):
        self.configure('monitor');self.tick(BLOCKED)
        event=self.s.status()['events'][0]
        self.assertEqual(event['action'],'SIGNAL_ONLY');self.assertEqual(len(event['data_hash']),64)
        self.assertTrue(event['strategy_version']);self.assertEqual(event['regime'],'uncertain')
        self.assertEqual(self.b.buys,[])
    def test_accepted_demo_order_context_and_restart_duplicate(self):
        self.configure();self.tick();self.assertEqual(self.b.buys,['test-only'])
        self.assertEqual(self.b.context['strategy'],'kangaroo');self.assertEqual(self.b.context['regime'],'ranging')
        self.assertEqual(self.s.status()['events'][0]['action'],'BROKER_ACCEPTED')
        self.s.stop();self.s=StrategySupervisor(self.b,self.path);self.s.read_closed=lambda *a,**kw:self.rows
        self.configure();self.tick();self.assertEqual(self.b.buys,['test-only'])
    def test_paper_signal_queues_instead_of_claiming_fill(self):
        self.configure('paper_trade');self.tick()
        self.assertEqual(self.s.paper.positions(self.b.account_id)[0]['status'],'PENDING')
        self.assertEqual(self.s.status()['events'][0]['action'],'PAPER_PENDING')
        self.assertEqual(self.b.buys,[])
    def test_global_kill_survives_reconfiguration(self):
        self.b.risk.killed=True
        for action in ('paper_trade','demo_trade'):
            with self.subTest(action=action),self.assertRaises(BridgeError):self.configure(action)
        self.configure('monitor');self.tick();self.assertEqual(self.b.buys,[])
    def test_paper_calendar_outage_blocks_and_cancels_pending_entries(self):
        self.configure('paper_trade');self.b.risk.calendar_allowed=False;self.tick()
        self.assertEqual(self.s.status()['events'][0]['action'],'BLOCKED_CALENDAR')
        self.assertEqual(self.s.paper.positions(self.b.account_id),[])
        self.b.risk.calendar_allowed=True
        self.s.last_candle=None
        self.sig['confirmed_at']+=300
        self.rows=[{**r,'time':r['time']+300} for r in self.rows]
        # Keep the fixture closed rather than depending on wall-clock boundaries.
        with patch('strategy_extension.time.time',return_value=self.rows[-1]['time']+600):self.tick()
        self.assertEqual(self.s.paper.positions(self.b.account_id)[0]['status'],'PENDING')
        self.b.risk.calendar_allowed=False
        with patch('strategy_extension.time.time',return_value=self.rows[-1]['time']+600):self.tick()
        self.assertEqual(self.s.paper.positions(self.b.account_id)[0]['status'],'CANCELLED')
    def test_kill_while_running_and_mode_switch_stop(self):
        self.configure();self.b.risk.killed=True;self.tick()
        self.assertFalse(self.s.active);self.assertEqual(self.b.buys,[])
        self.b.risk.killed=False;self.configure();self.b.mode='real';self.tick()
        self.assertFalse(self.s.active);self.assertEqual(self.b.buys,[])
    def test_stop_between_quote_and_buy_prevents_purchase(self):
        self.configure();self.b.after_quote=lambda:self.s.stop('test user stop during quotation')
        self.tick();self.assertEqual(self.b.buys,[]);self.assertIsNone(self.b.quote)
    def test_stale_history_never_becomes_a_new_signal(self):
        self.configure();self.rows=[{**r,'time':r['time']-86400} for r in self.rows]
        self.tick();self.assertEqual(self.b.buys,[]);self.assertEqual(self.s.status()['events'],[])
        self.assertIn('Stale',self.s.last_note)
    def test_nan_and_fractional_expiry_rejected(self):
        base={'strategy':'kangaroo','profile':'scalping','timeframe':'5m','symbol':'R_100','action':'monitor'}
        for update in ({'stake':float('nan')},{'expiry_minutes':1.5},{'stake':True}):
            with self.subTest(update=update),self.assertRaises(ValueError):self.s.configure({**base,**update})
    def test_signal_must_match_completed_candle(self):
        self.configure();self.sig['confirmed_at']-=300;self.tick()
        self.assertEqual(self.b.buys,[]);self.assertFalse(self.s.active)
        self.assertIn('latest completed',self.s.last_error)
    def test_research_cost_and_provenance_forwarded(self):
        opts={'source':'synthetic','timeframe':'5m','profile':'scalping','strategy':'kangaroo',
              'commission_per_trade':.2,'spread_bps':3,'slippage_bps':2,'parameters':{'wick_fraction':.6}}
        report=self.s.research(opts)
        self.assertIn('Synthetic',report['source'])
        self.assertIn('provenance',report)
    def test_actual_transport_history_bounds_for_research_weekly_and_monthly(self):
        # Exercise the real adapter validation, replacing only its network RPC.
        # Permissive FakeTransport used by legacy tests missed the >2500 bug.
        transport=DerivTransport();requests=[]
        def rpc(payload):
            requests.append(payload)
            gran=payload['granularity'];count=payload['count']
            last=(int(time.time())//gran-1)*gran
            return {'candles':[{'epoch':last-(count-1-i)*gran,
                                'open':100,'high':101,'low':99,'close':100}
                               for i in range(count)]}
        transport.rpc=rpc;self.b.transport=transport
        for frame in ('5m','1w','1mo'):
            with self.subTest(frame=frame):
                rows=StrategySupervisor.read_closed(self.s,'R_100',frame,research=True)
                self.assertEqual(requests[-1]['count'],2500)
                self.assertGreater(len(rows),60)
                self.assertTrue(all(a['time']<b['time'] for a,b in zip(rows,rows[1:])))
                if frame=='1mo':self.assertLess(len(rows),100)  # Honest finite-history limitation.
    def test_scan_does_not_truncate_fractional_horizon(self):
        with self.assertRaises(ValueError):
            self.s.scan_all({'source':'synthetic','timeframe':'5m','profile':'scalping','expiry_bars':1.5})
    def test_account_switch_during_research_cannot_bind_previous_history(self):
        def comparison(*args,**kwargs):
            self.b.account_id='OTHER_ACCOUNT'
            return {'qualified':True,'winner':'kangaroo'}
        with patch('strategy_extension.compare_all',side_effect=comparison):
            report=self.s.scan_all({'source':'deriv','symbol':'R_100','timeframe':'5m','profile':'scalping'})
        self.assertFalse(report['auto_eligible']);self.assertIsNone(self.s.best_selection['winner'])

if __name__=='__main__':unittest.main()
