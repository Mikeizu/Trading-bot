"""Retired-workspace removal and lossless, repeatable journal migration."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

import deriv_server as app
from indicator_strategies import STRATEGIES
from market_data import candles_valid, sample_candles, TIMEFRAMES, resample


class WorkspaceMigrationTests(unittest.TestCase):
    def test_wal_history_is_copied_and_original_files_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            source=sqlite3.connect(root/'naked_signals.db')
            try:
                source.execute('PRAGMA journal_mode=WAL')
                source.execute('CREATE TABLE history(id INTEGER PRIMARY KEY,note TEXT)')
                source.execute("INSERT INTO history VALUES(1,'retained audit history')");source.commit()
                result=app.migrate_strategy_state(root)
                self.assertEqual(len(result),1)
                self.assertTrue(result[0]['original_retained'])
                self.assertTrue((root/'naked_signals.db').exists())
                with sqlite3.connect(root/'strategy_signals.db') as target:
                    self.assertEqual(target.execute('SELECT note FROM history').fetchone()[0],'retained audit history')
                    target.execute("INSERT INTO history VALUES(2,'new history')")
                self.assertEqual(app.migrate_strategy_state(root),[])
                self.assertEqual(source.execute('SELECT COUNT(*) FROM history').fetchone()[0],1)
                with sqlite3.connect(root/'strategy_signals.db') as target:
                    self.assertEqual(target.execute('SELECT COUNT(*) FROM history').fetchone()[0],2)
            finally:source.close()

    def test_both_ledgers_migrate_and_preexisting_targets_are_never_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in ('naked_signals.db','naked_paper.db'):
                with sqlite3.connect(root/name) as c:
                    c.execute('CREATE TABLE preserved(value TEXT)');c.execute('INSERT INTO preserved VALUES(?)',(name,))
            with sqlite3.connect(root/'strategy_signals.db') as c:
                c.execute('CREATE TABLE current(value TEXT)');c.execute("INSERT INTO current VALUES('keep')")
            result=app.migrate_strategy_state(root)
            self.assertEqual([x['to'] for x in result],['paper_positions.db'])
            with sqlite3.connect(root/'strategy_signals.db') as c:
                self.assertEqual(c.execute('SELECT value FROM current').fetchone()[0],'keep')
            with sqlite3.connect(root/'paper_positions.db') as c:
                self.assertEqual(c.execute('SELECT value FROM preserved').fetchone()[0],'naked_paper.db')

    def test_corrupt_legacy_ledger_does_not_publish_partial_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);original=root/'naked_signals.db';original.write_bytes(b'not a SQLite database')
            with self.assertRaises(sqlite3.DatabaseError):app.migrate_strategy_state(root)
            self.assertFalse((root/'strategy_signals.db').exists())
            self.assertEqual(original.read_bytes(),b'not a SQLite database')
            self.assertEqual(list(root.glob('.strategy-migrate-*')),[])

    def test_missing_legacy_files_need_no_migration(self):
        with tempfile.TemporaryDirectory() as directory:self.assertEqual(app.migrate_strategy_state(directory),[])

    def test_old_pattern_implementation_and_workspace_are_not_shipped(self):
        root=Path(__file__).resolve().parents[1]
        for name in ('naked_strategies.py','static/strategy_ui.js','STRATEGY_GUIDE.md','AUTO_SELECTOR_GUIDE.md'):
            self.assertFalse((root/name).exists(),name)
        html=(root/'static/index.html').read_text()
        self.assertNotIn('page-naked',html);self.assertNotIn('Naked Strategy',html)
        self.assertIn('strategies_ui.js',html)
        removed={'kangaroo','shadow','belt','wammie','moolah','last_kiss','trendy_kangaroo'}
        self.assertTrue(removed.isdisjoint(STRATEGIES))
        self.assertGreaterEqual(len(STRATEGIES),18)
        self.assertTrue({'RSI','MACD','CCI','SMA','BOLLINGER','STOCHASTIC'}.issubset(STRATEGIES))

    def test_generic_data_validation_preserves_calendar_and_numeric_guards(self):
        for frame,seconds in TIMEFRAMES.items():
            with self.subTest(frame=frame):
                rows=candles_valid(sample_candles(200,seconds))
                self.assertEqual(len(rows),200)
                self.assertEqual(rows,resample(rows,frame) if frame not in ('1w','1mo') else rows)
        with self.assertRaises(ValueError):resample([{'time':1,'open':True,'high':2,'low':1,'close':1}],'1m')


if __name__=='__main__':unittest.main()
