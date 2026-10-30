"""Paper-ledger boundary and recovery regressions. No broker/network access."""
from datetime import datetime, timezone
from pathlib import Path
import json
import tempfile
import unittest

from paper_engine import PaperBook, PaperError


class PaperEdgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'private'/'paper.db'
        self.book=PaperBook(self.path)

    def tearDown(self):self.tmp.cleanup()

    def queue(self,stamp=1000,frame='5m'):
        return self.book.open('account','EURUSD',frame,'RSI',
            {'side':'UP','stop':99,'confirmed_at':stamp},100)

    @staticmethod
    def candle(stamp=1300,**changes):
        return {'time':stamp,'open':100,'high':100.5,'low':99.5,'close':100,**changes}

    def test_invalid_signal_shapes_reject_without_database_rows(self):
        for signal in (None,[],True,'signal'):
            with self.subTest(signal=signal),self.assertRaises(PaperError):
                self.book.open('account','EURUSD','5m','RSI',signal,100)
        self.assertEqual(self.book.positions('account'),[])

    def test_invalid_row_shapes_reject_without_advancing_pending_order(self):
        self.queue()
        for rows in (None,{},'rows',[None],[[]],[True]):
            with self.subTest(rows=rows),self.assertRaises(PaperError):
                self.book.reconcile('account','EURUSD','5m',rows)
        self.assertEqual(self.book.positions('account')[0]['status'],'PENDING')

    def test_identity_and_timeframe_validation(self):
        for account in (None,[],True,'',' '):
            for operation in (lambda:self.book.balance(account),lambda:self.book.positions(account),
                              lambda:self.book.halt(account),lambda:self.book.cancel_pending(account)):
                with self.subTest(account=account),self.assertRaises(PaperError):operation()
        with self.assertRaises(PaperError):self.queue(frame='unknown')
        self.assertEqual(self.book.positions('account'),[])

    def test_invalid_signal_and_bar_epochs_reject(self):
        for stamp in (-1,True,1.5,1e30,253402300799):
            with self.subTest(stamp=stamp),self.assertRaises(PaperError):self.queue(stamp)
        self.queue()
        for stamp in (-1,True,1300.5,1e30):
            with self.subTest(stamp=stamp),self.assertRaises(PaperError):
                self.book.reconcile('account','EURUSD','5m',[self.candle(stamp)])
        self.assertEqual(self.book.positions('account')[0]['status'],'PENDING')

    def test_numeric_range_and_cost_bounds_reject_unusable_models(self):
        for key,value in (('spread_bps',101),('slippage_bps',1e200),
                          ('commission_per_unit',1e7),('risk_pct',1e-200)):
            with self.subTest(key=key),self.assertRaises(PaperError):
                PaperBook(Path(self.tmp.name)/'rejected.db',**{key:value})
        for entry in (1e-200,1e200):
            with self.subTest(entry=entry),self.assertRaises(PaperError):
                self.book.open('account','EURUSD','5m','RSI',
                    {'side':'UP','stop':entry*.99,'confirmed_at':1000},entry)
        self.assertEqual(self.book.positions('account'),[])

    def test_missing_next_bar_cancels_without_inventing_late_fill(self):
        self.queue()
        self.book.reconcile('account','EURUSD','5m',[self.candle(1600,high=104,low=98)])
        row=self.book.positions('account')[0]
        self.assertEqual(row['status'],'CANCELLED')
        self.assertIsNone(row['quantity']);self.assertIsNone(row['pnl'])
        self.assertIn('Missing next candle',row['detail'])
        self.assertEqual(self.book.balance('account'),10000)

    def test_processed_bars_cannot_retroactively_create_a_fill(self):
        self.queue()
        self.book.reconcile('account','EURUSD','5m',[self.candle(1300),self.candle(1600)])
        self.assertEqual(self.book.positions('account')[0]['status'],'OPEN')
        self.book=PaperBook(self.path)
        self.book.reconcile('account','EURUSD','5m',[self.candle(1600,high=104,low=98)])
        row=self.book.positions('account')[0]
        self.assertEqual(row['status'],'OPEN');self.assertEqual(row['last_checked_candle'],1600)
        self.book.reconcile('account','EURUSD','5m',[self.candle(1900,high=104,low=98)])
        self.assertEqual(self.book.positions('account')[0]['status'],'CLOSED')

    def test_persisted_malformed_costs_never_mutate_position(self):
        self.queue()
        for value in ('invalid JSON','[]',json.dumps({'spread_bps':-1,
                     'slippage_bps':.5,'commission_per_unit_per_side':0})):
            with self.book.db() as c:c.execute('UPDATE paper_positions SET assumptions=?',(value,))
            with self.subTest(value=value),self.assertRaises(PaperError):
                self.book.reconcile('account','EURUSD','5m',[self.candle(high=104,low=98)])
            self.assertEqual(self.book.positions('account')[0]['status'],'PENDING')

    def test_invalid_persisted_open_quantity_cannot_settle(self):
        self.queue();self.book.reconcile('account','EURUSD','5m',[self.candle()])
        with self.book.db() as c:c.execute('UPDATE paper_positions SET quantity=-1')
        with self.assertRaises(PaperError):
            self.book.reconcile('account','EURUSD','5m',[self.candle(1600,high=104,low=98)])
        self.assertEqual(self.book.positions('account')[0]['status'],'OPEN')

    def test_corrupted_stop_cannot_turn_a_stop_loss_into_a_profit(self):
        self.queue();self.book.reconcile('account','EURUSD','5m',[self.candle()])
        with self.book.db() as c:c.execute('UPDATE paper_positions SET stop=101')
        with self.assertRaises(PaperError):
            self.book.reconcile('account','EURUSD','5m',[self.candle(1600)])
        row=self.book.positions('account')[0]
        self.assertEqual(row['status'],'OPEN');self.assertIsNone(row['pnl'])

    def test_missing_legacy_settlement_profit_cannot_be_reported_as_zero(self):
        self.queue();self.book.reconcile('account','EURUSD','5m',[self.candle(high=104,low=98)])
        with self.book.db() as c:c.execute('UPDATE paper_positions SET pnl=NULL')
        with self.assertRaises(PaperError):self.book.balance('account')
        with self.assertRaises(PaperError):self.queue(stamp=2000)

    def test_monthly_entry_uses_real_calendar_boundary(self):
        signal=int(datetime(2026,1,1,tzinfo=timezone.utc).timestamp())
        next_stamp=int(datetime(2026,2,1,tzinfo=timezone.utc).timestamp())
        self.queue(signal,'1mo')
        self.book.reconcile('account','EURUSD','1mo',[self.candle(next_stamp)])
        self.assertEqual(self.book.positions('account')[0]['status'],'OPEN')
        with self.assertRaises(PaperError):self.queue(signal+86400,'1mo')


if __name__=='__main__':unittest.main()
