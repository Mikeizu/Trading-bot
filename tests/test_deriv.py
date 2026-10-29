"""Deterministic tests. No real Deriv order is sent."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from deriv_bridge import (BrokerController,DerivTransport,BridgeError,UnknownExecution,check_otp_url,normalize_accounts)
from deriv_server import Journal

class FakeTransport:
    def __init__(self):
        self.buy_count=0;self.closed=False;self.mode=None;self.account=None
        self.contract_sold=False;self.throw_unknown=False
    def accounts(self,appid,pat):
        if pat!='demo-test-token':raise BridgeError('Invalid PAT')
        return [{'account_id':'DOT90000001','account_type':'demo','currency':'USD'},
                {'account_id':'DOT90000002','account_type':'real','currency':'USD'}]
    def connect(self,appid,pat,aid,mode):
        acc=next((a for a in self.accounts(appid,pat) if a['account_id']==aid and a['account_type']==mode),None)
        if not acc:raise BridgeError('Wrong account')
        self.mode=mode;self.account=acc;return acc
    def close(self):self.closed=True
    def balance(self):return {'balance':'10000.00','currency':'USD'}
    def portfolio(self):return {'contracts':[]}
    def symbols(self):return [{'symbol':'R_100','name':'Volatility 100 Index'}]
    def contracts_for(self,symbol):
        return {'symbol':symbol,'UP':list(range(1,16)),'DOWN':list(range(1,16)),
                'contract_types':['CALL','PUT'],'note':'mock offers'}
    def proposal(self,symbol,side,stake,minutes,currency):
        return {'id':'proposal-123','ask_price':stake,'payout':'1.80','longcode':'Rise/fall'}
    def buy(self,pid,ask):
        self.buy_count+=1
        if self.throw_unknown:raise UnknownExecution('Unknown execution')
        return {'contract_id':123456,'buy_price':ask}
    def contract(self,cid):return {'is_sold':1 if self.contract_sold else 0,'profit':'0.80','status':'sold' if self.contract_sold else 'open'}
    def candles(self,symbol,count=140):return []

class DerivTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=Journal(Path(self.tmp.name)/'journal.db')
        self.transport=FakeTransport()
        self.b=BrokerController(self.db,self.transport)
    def tearDown(self):self.tmp.cleanup()
    def connect(self,real=False):
        if real:self.b.allow_live=True
        self.b.connect('my-app-id','demo-test-token','DOT90000002' if real else 'DOT90000001','real' if real else 'demo')
    def test_normalize_accounts_rejects_unknown_types(self):
        raw={'data':[{'account_id':'DOT90000001','account_type':'demo'}, {'account_id':'CR1234','account_type':'mt5'}]}
        self.assertEqual(len(normalize_accounts(raw)),1)
    def test_otp_url_requires_exact_host_and_mode(self):
        good='wss://api.derivws.com/trading/v1/options/ws/demo?otp=1234'
        self.assertEqual(check_otp_url(good,'demo'),good)
        for url in ['wss://evil.com/trading/v1/options/ws/demo?otp=X','wss://api.derivws.com/trading/v1/options/ws/real?otp=X','ws://api.derivws.com/trading/v1/options/ws/demo?otp=X']:
            with self.assertRaises(BridgeError):check_otp_url(url,'demo')
    def test_demo_buy_consumes_quote(self):
        self.connect()
        q=self.b.new_quote('R_100','UP',1,2)
        result=self.b.buy_quote(q['token'])
        self.assertEqual(result['contract_id'],'123456')
        self.assertEqual(self.transport.buy_count,1)
        with self.assertRaises(BridgeError):self.b.buy_quote(q['token'])
        with self.assertRaises(BridgeError):self.b.new_quote('R_100','DOWN',1,2)
    def test_reconcile_closes_trade(self):
        self.connect()
        q=self.b.new_quote('R_100','DOWN',1,2)
        self.b.buy_quote(q['token'])
        self.transport.contract_sold=True
        r=self.b.reconcile()
        self.assertEqual(r[0]['status'],'CLOSED')
        self.assertAlmostEqual(r[0]['pnl'],.8)
    def test_unknown_purchase_stops_all_further_trading(self):
        self.connect()
        self.transport.throw_unknown=True
        q=self.b.new_quote('R_100','UP',1,2)
        with self.assertRaises(UnknownExecution):self.b.buy_quote(q['token'])
        self.assertEqual(self.db.orders('DOT90000001')[0]['status'],'UNCERTAIN')
        with self.assertRaises(BridgeError):self.b.new_quote('R_100','UP',1,2)
    def test_live_disabled_by_default(self):
        status=self.b.connect('my-app-id','demo-test-token','DOT90000002','real')
        self.assertEqual(status['mode'],'real')
        self.assertFalse(status['allow_live'])
        with self.assertRaises(BridgeError):self.b.new_quote('R_100','UP',1,2)
    def test_real_remains_read_only_even_with_old_opt_in(self):
        self.connect(real=True)
        with self.assertRaises(BridgeError):self.b.new_quote('R_100','UP',1,2)
        with self.assertRaises(BridgeError):self.b.arm('AUTHORIZE')
        with self.assertRaises(BridgeError):self.b.arm('I AUTHORIZE ONE REAL TRADE')
        with self.assertRaises(BridgeError):self.b.buy_quote('invented-token',internal=True)
        self.assertEqual(self.transport.buy_count,0)
        self.assertEqual(self.db.orders('DOT90000002'),[])
    def test_all_real_stakes_blocked(self):
        self.connect(real=True)
        for stake in (.35,1,10):
            with self.subTest(stake=stake),self.assertRaises(BridgeError):
                self.b.new_quote('R_100','UP',stake,2)
    def test_live_arm_cannot_be_enabled_by_legacy_phrase(self):
        self.connect(real=True)
        with self.assertRaises(BridgeError):self.b.arm('I AUTHORIZE ONE REAL TRADE')
        self.assertFalse(self.b.status()['armed'])
        self.assertEqual(self.transport.buy_count,0)

if __name__=='__main__':unittest.main()
