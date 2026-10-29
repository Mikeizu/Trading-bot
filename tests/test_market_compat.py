"""Regression: Deriv renamed market schema in the new API.
No network, no credentials, no real or simulated purchases sent.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from deriv_bridge import (normalize_active_symbols, DerivTransport,
                          BrokerController, BridgeError)
from deriv_server import Journal

class FakeWS:
    def __init__(self, symbols):
        self.symbols=symbols
        self.sent=[]
        self.last_id=0
        self.closed=False
    def send(self, data):
        r=json.loads(data)
        self.sent.append(r)
        self.last_id=r['req_id']
    def recv(self):
        req=self.sent[-1]
        if 'balance' in req:
            body={'balance': {'balance':'10000.00', 'currency':'USD'}}
        elif 'active_symbols' in req:
            body={'active_symbols': self.symbols}
        elif 'portfolio' in req:
            body={'portfolio': {'contracts':[]}}
        else:
            raise AssertionError(f'Unexpected broker call: {req}')
        return json.dumps({**body,'req_id':req['req_id']})
    def close(self):self.closed=True

class MarketCompatibilityTests(unittest.TestCase):
    def test_new_api_underlying_symbol_fields(self):
        payload={'active_symbols':[
            {'underlying_symbol':'R_100','underlying_symbol_name':'Volatility 100 Index','exchange_is_open':1},
            {'underlying_symbol':'1HZ100V','underlying_symbol_name':'Volatility 100 (1s) Index'}]}
        self.assertEqual(normalize_active_symbols(payload),[
            {'symbol':'R_100','name':'Volatility 100 Index'},
            {'symbol':'1HZ100V','name':'Volatility 100 (1s) Index'}])
    def test_legacy_fields_are_still_supported(self):
        self.assertEqual(normalize_active_symbols({'active_symbols':[{'symbol':'R_50','display_name':'Vol 50'}]}),
                         [{'symbol':'R_50','name':'Vol 50'}])
    def test_new_fields_take_precedence_over_legacy(self):
        a=normalize_active_symbols({'active_symbols':[{'underlying_symbol':'R_100','symbol':'wrong',
                       'underlying_symbol_name':'New name','display_name':'Old name'}]})
        self.assertEqual(a,[{'symbol':'R_100','name':'New name'}])
    def test_malformed_markets_rejected_not_silent_empty(self):
        for body in ({}, {'active_symbols':{}}, {'active_symbols':[{'unrecognized_field':'R_100'}]}):
            with self.subTest(body=body):
                with self.assertRaises(BridgeError):normalize_active_symbols(body)
    def test_empty_list_is_valid_read_only_connection(self):
        self.assertEqual(normalize_active_symbols({'active_symbols':[]}),[])
    def test_duplicate_invalid_symbols_removed(self):
        body={'active_symbols':[{'underlying_symbol':'R_100'},
                                {'underlying_symbol':'R_100'},
                                {'underlying_symbol':'BAD SYMBOL'},
                                {'underlying_symbol':'R_50'}]}
        self.assertEqual([r['symbol'] for r in normalize_active_symbols(body)],['R_100','R_50'])
    def _make_session(self, symbols):
        ws=FakeWS(symbols)
        def http(method, path, app_id, token):
            self.assertEqual((app_id,token),('pat-app-id','sample-private-token'))
            if method=='GET':
                return {'data':[{'account_id':'DOT90000001','account_type':'demo','currency':'USD'}]}
            if method=='POST':
                return {'data':{'url':'wss://api.derivws.com/trading/v1/options/ws/demo?otp=fake-once-only'}}
            raise AssertionError('Unexpected REST action')
        transport=DerivTransport(http=http, ws_factory=lambda url:ws)
        folder=tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        broker=BrokerController(Journal(Path(folder.name)/'db.sqlite'),transport)
        return ws,broker
    def test_realistic_connection_with_current_schema(self):
        ws,broker=self._make_session([{'underlying_symbol':'R_100','underlying_symbol_name':'Volatility 100 Index'},
                                      {'underlying_symbol':'1HZ100V','underlying_symbol_name':'Volatility 100 (1s) Index'}])
        state=broker.connect('pat-app-id','sample-private-token','DOT90000001','demo')
        self.assertTrue(state['connected'])
        self.assertEqual(state['mode'],'demo')
        self.assertEqual(state['balance'],10000)
        self.assertEqual([m['symbol'] for m in state['symbols']],['R_100','1HZ100V'])
        self.assertTrue(any(r.get('active_symbols')=='brief' for r in ws.sent))
        self.assertNotIn('sample-private-token',str(state))
        self.assertNotIn('fake-once-only',str(state))
        # No purchase can occur simply by connecting or querying markets.
        self.assertFalse(any('buy' in r or 'proposal' in r for r in ws.sent))
    def test_zero_markets_connects_but_blocks_trading(self):
        ws,broker=self._make_session([])
        state=broker.connect('pat-app-id','sample-private-token','DOT90000001','demo')
        self.assertTrue(state['connected'])
        self.assertEqual(state['symbols'],[])
        with self.assertRaisesRegex(BridgeError, 'available|active'):
            broker.new_quote('R_100','UP',1,1)
        ws.symbols=[{'underlying_symbol':'R_100','underlying_symbol_name':'Volatility 100 Index'}]
        self.assertEqual(len(broker.refresh_markets()['symbols']),1)
    def test_failed_schema_does_not_leave_a_connected_session(self):
        ws,broker=self._make_session([{'unknown_market':'X'}])
        with self.assertRaisesRegex(BridgeError,'not recognized'):
            broker.connect('pat-app-id','sample-private-token','DOT90000001','demo')
        self.assertEqual(broker.status()['mode'],'disconnected')

if __name__=='__main__':unittest.main()
