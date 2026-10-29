"""Regression for Deriv contract duration capability. No broker calls or real orders."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from deriv_bridge import (BridgeError, DerivTransport, BrokerController,
                          normalize_contract_durations, _duration_seconds)
from deriv_server import Journal
from test_deriv import FakeTransport
from strategy_extension import StrategySupervisor


def book(*entries):
    return {'contracts_for':{'available':list(entries)}}

def offer(side, low='15s', high='1d', barriers=0):
    return {'contract_type':side,'min_contract_duration':low,
            'max_contract_duration':high,'barriers':barriers}

class DurationNormalizationTests(unittest.TestCase):
    def test_seconds_minutes_hours_days(self):
        self.assertEqual([_duration_seconds(s) for s in ['15s','2m','2h','1d']],[15,120,7200,86400])
        for s in ['1t','0m','bad','1w','-5m',None]:
            self.assertIsNone(_duration_seconds(s))

    def test_canonical_contracts_for_response(self):
        b=normalize_contract_durations(book(offer('CALL','2m','5m'), offer('PUT','3m','4m')))
        self.assertEqual(b['UP'],[2,3,4,5])
        self.assertEqual(b['DOWN'],[3,4])

    def test_tick_only_and_unrelated_offers_not_converted(self):
        b=normalize_contract_durations(book(offer('CALL','2t','10t'),
                                             offer('MULTUP','15s','1h'),
                                             offer('PUT','2m','5m',barriers=1)))
        self.assertEqual(b['UP'],[])
        self.assertEqual(b['DOWN'],[])

    def test_broken_payload_fails_closed(self):
        for bad in [{}, {'contracts_for':{}}, {'contracts_for':[]}, None]:
            with self.subTest(bad=bad):
                with self.assertRaises(BridgeError):normalize_contract_durations(bad)

class RestrictionTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.t=FakeTransport()
        self.b=BrokerController(Journal(Path(self.folder.name)/'orders.db'),self.t)
        self.b.connect('test-app','demo-test-token','DOT90000001','demo')
    def tearDown(self):self.folder.cleanup()

    def test_advertised_bounds_block_unsupported_quote_no_proposal(self):
        self.t.contracts_for=lambda sym: normalize_contract_durations(book(offer('CALL','5m','8m'),offer('PUT','1m','3m')))
        with patch.object(self.t,'proposal', wraps=self.t.proposal) as proposals:
            with self.assertRaisesRegex(BridgeError,'Supported UP expiries'):
                self.b.new_quote('R_100','UP',1,2)
            self.assertEqual(proposals.call_count,0)
            self.assertEqual(self.b.db.orders('DOT90000001'),[])
            q=self.b.new_quote('R_100','DOWN',1,2)
            self.assertEqual(q['minutes'],2)
            self.assertEqual(proposals.call_count,1)

    def test_zero_offers_blocks_even_if_symbol_is_visible(self):
        self.t.contracts_for=lambda sym: normalize_contract_durations(book(offer('MULTUP','1m','15m')))
        with self.assertRaisesRegex(BridgeError,'none within 1–15'):
            self.b.new_quote('R_100','UP',1,2)
        self.assertEqual(self.t.buy_count,0)

    def test_broker_proposal_can_still_reject_in_advertised_range(self):
        self.t.proposal=lambda *args: (_ for _ in ()).throw(BridgeError('Deriv: Trading is not offered for this duration.'))
        with self.assertRaisesRegex(BridgeError,'despite its contract catalogue'):
            self.b.new_quote('R_100','UP',1,2)
        self.assertEqual(self.b.db.orders('DOT90000001'),[])

    def test_naked_robot_rejects_asymmetric_offers_without_start(self):
        self.t.contracts_for=lambda sym: normalize_contract_durations(book(offer('CALL','1m','15m')))
        supervisor=StrategySupervisor(self.b,Path(self.folder.name)/'signals.db')
        with self.assertRaisesRegex(BridgeError,'both Rise and Fall'):
            supervisor.configure({'strategy':'kangaroo','profile':'scalping','timeframe':'5m',
                                  'symbol':'R_100','action':'demo_trade','stake':1,'expiry_minutes':3})
        self.assertFalse(supervisor.active)

    def test_transport_uses_official_contracts_for_format(self):
        class FakeWS:
            def __init__(self):self.req=None
            def send(self,payload):self.req=json.loads(payload)
            def recv(self):return json.dumps({'req_id':self.req['req_id'],
                                              **book(offer('CALL','1m','3m'),offer('PUT','2m','5m'))})
        ws=FakeWS();t=DerivTransport();t.ws=ws
        r=t.contracts_for('R_100')
        self.assertEqual(ws.req['contracts_for'],'R_100')
        self.assertEqual(set(ws.req),{'contracts_for','req_id'})
        self.assertEqual(r['UP'],[1,2,3])
        self.assertEqual(r['DOWN'],[2,3,4,5])

if __name__=='__main__':unittest.main()
