import json,os,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import server
class ApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.old=server.DB_FILE
        server.DB_FILE=Path(self.tmp.name)/'test.db';server.BOT_ACTIVE=False
        server.db_initialize()
    def tearDown(self):
        server.BOT_ACTIVE=False;server.DB_FILE=self.old;self.tmp.cleanup()
    def test_bootstrap_and_settings(self):
        with server.conn() as c:
            self.assertEqual(server.get_settings(c)['balance'],10000)
            self.assertEqual(len(server.candles_for(c,'EUR/USD',400)),360)
            vals=server.indicators(server.candles_for(c,'EUR/USD',200))
            self.assertEqual(len(vals['rsi']),200)
            self.assertEqual(len(server.candles_for(c,'CUSTOM',1)),0)
    def test_market_advance_and_balance(self):
        with server.conn() as c:
            prior=server.candles_for(c,'EUR/USD',1)[0]
        server.market_advance()
        with server.conn() as c:
            after=server.candles_for(c,'EUR/USD',1)[0]
            self.assertEqual(after['tick'],prior['tick']+1)
            self.assertEqual(after['time'],prior['time']+60)
            self.assertGreater(after['low'],0)
    def test_csv_import(self):
        rows=['open,high,low,close']+['100,102,99,101' for i in range(100)]
        n=server.import_csv(('\n'.join(rows)+'\n').encode())
        self.assertEqual(n,100)
        with server.conn() as c:self.assertEqual(server.get_settings(c)['asset'],'CUSTOM')
    def test_invalid_csv(self):
        with self.assertRaises(ValueError): server.import_csv(b'open,high,low,close\n0,0,0,0\n')
    def test_validation(self):
        for v in [-1,0,5.1]:
            with self.assertRaises(ValueError):server.normalize_update({'max_stake_pct':v})
        with self.assertRaises(ValueError):server.normalize_update({'strategy':'HACK'})

if __name__=='__main__':unittest.main()
