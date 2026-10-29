"""Synthetic ledger/CSV correctness; no broker network or external orders."""
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import server


class SimulatorSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.patches=[patch.object(server,'DB_FILE',Path(self.tmp.name)/'sim.db'),
            patch.object(server,'ENTRY_GUARD',None),patch.object(server,'BOT_ACTIVE',False),
            patch.object(server,'LAST_TICK',None)]
        for p in self.patches:p.start()
        server.db_initialize()

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()

    @staticmethod
    def csv_data(times=None,price=100):
        header='time,open,high,low,close' if times else 'open,high,low,close'
        values=[f'{price},{price+2},{price-1},{price+1}' for _ in range(100)]
        return ('\n'.join([header]+[(f'{times[i]},'+v if times else v) for i,v in enumerate(values)])+'\n').encode()

    def advance_up(self):
        with patch('server.random.Random') as rng:
            rng.return_value.gauss.side_effect=[.001,0,0]
            server.market_advance()

    def test_entry_uses_only_prior_candles_and_one_bar_expiry(self):
        with server.conn() as c:
            prior=server.candles_for(c,'EUR/USD',1)[0]
            server.set_settings(c,{'stake':2,'duration':1})
        def signal(rows,values,index,strategy):
            self.assertEqual(rows[-1]['time'],prior['time'])
            self.assertEqual(index,len(rows)-1)
            return 'UP'
        server.BOT_ACTIVE=True
        with patch('server.signal_at',side_effect=signal):self.advance_up()
        with server.conn() as c:
            trade=dict(c.execute('SELECT * FROM trades').fetchone())
            self.assertEqual(trade['entry'],prior['close'])
            self.assertEqual(trade['opened_tick'],prior['tick']+1)
            self.assertEqual(trade['expiry_tick'],trade['opened_tick'])
            self.assertEqual(trade['status'],'WIN')
            self.assertEqual(trade['payout_source'],'at_entry')
            self.assertEqual(server.get_settings(c)['balance'],10001.6)

    def test_open_order_payout_does_not_follow_setting_changes(self):
        with server.conn() as c:server.set_settings(c,{'stake':2,'duration':2,'payout':.8})
        server.BOT_ACTIVE=True
        with patch('server.signal_at',return_value='UP'):self.advance_up()
        with server.conn() as c:
            self.assertEqual(c.execute('SELECT status FROM trades').fetchone()[0],'OPEN')
            server.set_settings(c,{'payout':.1})
        server.BOT_ACTIVE=False;self.advance_up()
        with server.conn() as c:
            trade=c.execute('SELECT * FROM trades').fetchone()
            self.assertEqual(trade['pnl'],1.6)
            self.assertEqual(trade['payout'],.8)
            self.assertEqual(server.get_settings(c)['balance'],10001.6)

    def test_daily_budget_blocks_full_stake_not_only_previous_loss(self):
        with server.conn() as c:server.set_settings(c,{'stake':20,'stop_loss':10})
        server.BOT_ACTIVE=True
        with patch('server.signal_at',return_value='UP'):self.advance_up()
        with server.conn() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM trades').fetchone()[0],0)
        self.assertFalse(server.BOT_ACTIVE)
        self.assertIn('remaining daily loss budget',server.BOT_MESSAGE)

    def test_import_keeps_supplied_time_and_rejects_reordered_history(self):
        epochs=[1700000000+300*i for i in range(100)]
        self.assertEqual(server.import_csv(self.csv_data(epochs)),100)
        with server.conn() as c:
            rows=server.candles_for(c,'CUSTOM',100)
            self.assertEqual([r['time'] for r in rows],epochs)
            self.assertEqual(server.get_settings(c)['custom_time_origin'],'provided')
        with self.assertRaises(ValueError):server.import_csv(self.csv_data(list(reversed(epochs))))
        with server.conn() as c:self.assertEqual(server.candles_for(c,'CUSTOM',100),rows)

    def test_timestamp_free_csv_is_honestly_marked_and_not_extended(self):
        server.import_csv(self.csv_data())
        with server.conn() as c:
            original=server.candles_for(c,'CUSTOM',100)
            self.assertEqual(server.get_settings(c)['custom_time_origin'],'inferred_one_minute_intervals')
        with self.assertRaises(ValueError):server.market_advance()
        with server.conn() as c:self.assertEqual(server.candles_for(c,'CUSTOM',100),original)

    def test_import_does_not_strand_existing_synthetic_order(self):
        server.BOT_ACTIVE=True
        with patch('server.signal_at',return_value='UP'):self.advance_up()
        server.BOT_ACTIVE=False
        with self.assertRaisesRegex(ValueError,'Settle open'):server.import_csv(self.csv_data())
        with server.conn() as c:
            self.assertEqual(server.get_settings(c)['asset'],'EUR/USD')
            self.assertEqual(c.execute("SELECT COUNT(*) FROM candles WHERE asset='CUSTOM'").fetchone()[0],0)

    def test_rejected_numeric_csv_does_not_poison_workspace(self):
        before=None
        with server.conn() as c:before=server.get_settings(c)['asset']
        bad=self.csv_data().replace(b'100,102,99,101',b'1e308,1e308,1e308,1e308')
        with self.assertRaises(ValueError):server.import_csv(bad)
        with server.conn() as c:self.assertEqual(server.get_settings(c)['asset'],before)

    def test_settings_reject_bad_types_and_fractional_integer_fields(self):
        for payload in ({'duration':1.5},{'duration':True},{'trade_limit':2.5},
                {'stake':True},{'stake':None},{'asset':[]},{'strategy':{}},{'duration':float('inf')}):
            with self.subTest(payload=payload),self.assertRaises(ValueError):server.normalize_update(payload)

    def test_csv_duplicate_headers_and_bad_shapes_are_rejected(self):
        for data in (b'open,open,low,close\n100,102,99,101\n',
                     self.csv_data().replace(b'100,102,99,101',b'100,102,99,101,extra')):
            with self.assertRaises(ValueError):server.import_csv(data)

    def test_manual_advance_updates_readiness_timestamp(self):
        self.advance_up()
        self.assertIsInstance(server.LAST_TICK,int)


if __name__=='__main__':unittest.main()
