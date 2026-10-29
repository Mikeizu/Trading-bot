"""Deterministic virtual-ledger tests; no network or broker orders."""
import math, tempfile, unittest
from pathlib import Path
from paper_engine import PaperBook, PaperError

class PaperSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'paper.db';self.p=PaperBook(self.path)
    def tearDown(self):self.tmp.cleanup()
    def queue(self,*,stamp=1000,symbol='EURUSD',side='UP'):
        return self.p.open('account',symbol,'5m','kangaroo',{'side':side,'stop':99 if side=='UP' else 101,'confirmed_at':stamp},100)
    def bars(self,stamp=1300,**kwargs):
        return [{'time':stamp,'open':100,'high':100.5,'low':99.5,'close':100,**kwargs}]
    def test_no_fill_on_confirmation_close(self):
        self.queue();self.p.reconcile('account','EURUSD','5m',self.bars(stamp=1000))
        row=self.p.positions('account')[0]
        self.assertEqual(row['status'],'PENDING');self.assertIsNone(row['quantity'])
        self.assertEqual(row['risk_amount'],50)
    def test_next_open_costs_and_stop_first(self):
        self.queue();self.p.reconcile('account','EURUSD','5m',self.bars(high=104,low=98))
        row=self.p.positions('account')[0]
        self.assertEqual(row['status'],'CLOSED');self.assertEqual(row['pnl'],-50)
        self.assertEqual(row['opened_candle'],1300);self.assertGreater(row['costs'],0)
        self.assertGreater(row['entry'],100);self.assertLess(row['exit'],99)
    def test_downward_position_adverse_gap_costs(self):
        self.queue(side='DOWN');self.p.reconcile('account','EURUSD','5m',self.bars())
        self.p.reconcile('account','EURUSD','5m',self.bars(stamp=1600,open=104,high=105,low=103,close=104))
        row=self.p.positions('account')[0]
        self.assertLess(row['pnl'],-50);self.assertGreater(row['exit'],104)
    def test_stop_gap_can_exceed_nominal_risk(self):
        self.queue();self.p.reconcile('account','EURUSD','5m',self.bars())
        self.p.reconcile('account','EURUSD','5m',self.bars(stamp=1600,open=96,high=97,low=95,close=96))
        self.assertLess(self.p.positions('account')[0]['pnl'],-100)
    def test_restart_preserves_pending_and_duplicate_closed_signal(self):
        self.queue();self.p=PaperBook(self.path)
        self.assertIsNone(self.queue())
        self.p.reconcile('account','EURUSD','5m',self.bars(high=104,low=98))
        self.p=PaperBook(self.path);self.assertIsNone(self.queue())
        self.assertEqual(len(self.p.positions('account')),1)
    def test_halt_cancels_pending_and_survives_restart(self):
        self.queue();self.p.halt('account','test kill');self.p=PaperBook(self.path)
        self.assertEqual(self.p.positions('account')[0]['status'],'CANCELLED')
        with self.assertRaises(PaperError):self.queue(stamp=1400)
        with self.assertRaises(PaperError):self.p.resume('account','yes')
        self.p.resume('account','RESUME DEMO TRADING');self.assertIsInstance(self.queue(stamp=1500),int)
    def test_position_count_and_account_isolation(self):
        for symbol in ('EURUSD','GBPUSD','AUDUSD'):self.queue(symbol=symbol)
        with self.assertRaises(PaperError):self.queue(symbol='NZDUSD')
        idx=self.p.open('other','EURUSD','5m','kangaroo',{'side':'UP','stop':99,'confirmed_at':1000},100)
        self.assertIsInstance(idx,int)
    def test_daily_loss_budget_includes_reserved_risk(self):
        for i in range(4):
            self.queue(stamp=1000+i*1000)
            self.p.reconcile('account','EURUSD','5m',self.bars(stamp=1300+i*1000,low=98))
        with self.assertRaisesRegex(PaperError,'daily'):self.queue(stamp=6000)
    def test_invalid_inputs_fail_closed(self):
        for entry in (float('nan'),float('inf'),-1,True):
            with self.subTest(entry=entry),self.assertRaises(PaperError):
                self.p.open('account','EURUSD','5m','kangaroo',{'side':'UP','stop':99,'confirmed_at':1000},entry)
        self.queue()
        with self.assertRaises(PaperError):self.p.reconcile('account','EURUSD','5m',[{'time':1300,'high':101,'low':99}])
        with self.assertRaises(PaperError):self.p.reconcile('account','EURUSD','5m',self.bars(close=float('nan')))
        self.assertEqual(self.p.positions('account')[0]['status'],'PENDING')
    def test_invalid_gap_cancels_instead_of_inventing_fill(self):
        self.queue();self.p.reconcile('account','EURUSD','5m',self.bars(open=98,high=98.5,low=97,close=98))
        self.assertEqual(self.p.positions('account')[0]['status'],'CANCELLED')
        self.assertEqual(self.p.balance('account'),10000)

if __name__=='__main__':unittest.main()
