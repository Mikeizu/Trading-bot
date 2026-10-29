"""Safety checks for the GUI integration fixture, never a broker verification."""
import unittest
from unittest.mock import patch

from fake_broker_server import MockBrokerTransport
from deriv_bridge import BridgeError, UnknownExecution


class OfflineFixtureTests(unittest.TestCase):
    def test_complete_purchase_settlement_path_needs_no_network(self):
        transport=MockBrokerTransport()
        with patch('socket.create_connection',side_effect=AssertionError('Fixture attempted a network connection')):
            accounts=transport.accounts(transport.APP_ID,transport.TOKEN)
            self.assertEqual({a['account_type'] for a in accounts},{'demo','real'})
            account=transport.connect(transport.APP_ID,transport.TOKEN,transport.DEMO,'demo')
            self.assertEqual(account['account_id'],transport.DEMO)
            start=transport.balance()['balance']
            self.assertEqual(transport.portfolio()['contracts'],[])
            self.assertTrue(all('TEST DOUBLE' in s['name'] for s in transport.symbols()))
            self.assertEqual(len(transport.candles('R_100',count=100)),100)
            proposal=transport.proposal('R_100','UP',1,2,'USD')
            self.assertIn('TEST DOUBLE',proposal['longcode'])
            purchased=transport.buy(proposal['id'],proposal['ask_price'])
            self.assertEqual(transport.buy_count,1)
            self.assertEqual(transport.balance()['balance'],start-1)
            self.assertEqual(len(transport.portfolio()['contracts']),1)
            transport.settle_all()
            self.assertEqual(transport.portfolio()['contracts'],[])
            contract=transport.contract(purchased['contract_id'])
            self.assertEqual(contract['profit'],.8)
            self.assertEqual(transport.balance()['balance'],start+.8)

    def test_credentials_and_account_mode_cannot_be_skipped_in_fixture(self):
        transport=MockBrokerTransport()
        for app,token in [(transport.APP_ID,'wrong'),('wrong',transport.TOKEN)]:
            with self.assertRaises(BridgeError):transport.accounts(app,token)
        with self.assertRaises(BridgeError):
            transport.connect(transport.APP_ID,transport.TOKEN,transport.REAL,'demo')
        self.assertEqual(transport.account_id,'')

    def test_timeout_fixture_really_has_an_ambiguous_spent_stake(self):
        transport=MockBrokerTransport()
        transport.connect(transport.APP_ID,transport.TOKEN,transport.DEMO,'demo')
        proposal=transport.proposal('R_100','UP',1,2,'USD')
        transport.fault='timeout'
        with self.assertRaises(UnknownExecution):transport.buy(proposal['id'],1)
        self.assertEqual(transport.buy_count,1)
        self.assertEqual(transport.balance()['balance'],9999)
        self.assertEqual(len(transport.portfolio()['contracts']),1)

    def test_history_cap_and_explicit_missing_capabilities(self):
        transport=MockBrokerTransport()
        with self.assertRaises(BridgeError):transport.candles('R_100',count=2501)
        self.assertEqual(transport.contracts_for('NO_DURATION')['UP'],[])
        transport.fault='markets_empty'
        self.assertEqual(transport.symbols(),[])


if __name__=='__main__':unittest.main()
