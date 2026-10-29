import math,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from engine import sma,ema,rsi,indicators,signal_at,backtest
class IndicatorTests(unittest.TestCase):
    def setUp(self):
        self.candles=[]
        for i in range(140):
            close=100 + 5*math.sin(i/7) + .07*i
            prev=100 + 5*math.sin((i-1)/7)+.07*(i-1)
            self.candles.append({'asset':'TEST','time':i,'tick':i,'open':prev,'close':close,'high':max(prev,close)+.1,'low':min(prev,close)-.1})
    def test_rsi_rising_prices(self):
        self.assertEqual(rsi(list(range(40)))[-1],100)
    def test_sma(self):self.assertEqual(sma([1,2,3,4],3),[None,None,2.,3.])
    def test_indicators_length(self):
        result=indicators(self.candles)
        for v in result.values():self.assertEqual(len(v),len(self.candles))
    def test_backtest_counts_and_account(self):
        for name in ('RSI','MACD','CCI','SMA','BOLLINGER','STOCHASTIC'):
            r=backtest(self.candles,name,10,3,.8)
            self.assertEqual(r['trade_count'],r['wins']+r['losses'])
            self.assertAlmostEqual(r['ending_balance'],10000+r['net_pnl'],places=2)
            self.assertTrue(0<=r['win_rate']<=100)
            self.assertTrue(0<=r['max_drawdown_pct']<=100)
    def test_no_look_ahead(self):
        for name in ('RSI','MACD','CCI','SMA','BOLLINGER','STOCHASTIC'):
            initial=backtest(self.candles[:100],name,10,3,.8)
            later=backtest(self.candles,name,10,3,.8)
            # All trades with expiry before the first test's end must be identical.
            early=[t for t in later['trades'] if t['index']+3<100]
            self.assertEqual([(t['index'],t['pnl']) for t in initial['trades']],[(t['index'],t['pnl']) for t in early])

if __name__=='__main__':unittest.main()
