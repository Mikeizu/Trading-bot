"""Execution fault regressions: in-memory broker doubles only; no network/trades."""
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request

from deriv_bridge import (BridgeError, BrokerController, BrokerRejection,
                          DerivTransport, UnknownExecution, check_otp_url,
                          normalize_active_symbols, _NoCredentialRedirect)
from deriv_server import Journal
from test_deriv import FakeTransport


class BrokerSafetyTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.store = Journal(Path(self.folder.name) / 'journal.db')
        self.transport = FakeTransport()
        self.broker = BrokerController(self.store, self.transport)
        self.connect()

    def connect(self, mode='demo'):
        return self.broker.connect('test-app', 'demo-test-token',
                                   'DOT90000001' if mode == 'demo' else 'DOT90000002', mode)

    def quote(self, **kwargs):
        return self.broker.new_quote('R_100', 'UP', 1, 2, **kwargs)

    def test_real_account_is_read_only_even_after_legacy_opt_in_and_arming_mutation(self):
        self.broker.allow_live = True
        state = self.connect('real')
        self.assertTrue(state['connected'])
        self.assertFalse(state['allow_live'])
        self.assertFalse(state['live_execution_supported'])
        self.assertFalse(state['armed'])
        self.broker.live_armed_until = time.monotonic() + 10_000
        for internal in (False, True):
            with self.assertRaisesRegex(BridgeError, 'read-only'):
                self.quote(internal=internal)
        with self.assertRaisesRegex(BridgeError, 'unavailable'):
            self.broker.arm('I AUTHORIZE ONE REAL TRADE')
        self.assertEqual(self.transport.buy_count, 0)

    def test_account_switch_invalidates_demo_quote(self):
        quote = self.quote()
        self.connect('real')
        with self.assertRaises(BridgeError):
            self.broker.buy_quote(quote['token'])
        self.assertEqual(self.transport.buy_count, 0)

    def test_transport_account_identity_mismatch_cancels_connect(self):
        self.transport.connect = lambda *a: {'account_id': 'DOT90000002', 'account_type': 'real', 'currency': 'USD'}
        with self.assertRaisesRegex(BridgeError, 'identity or mode mismatch'):
            self.connect()
        self.assertFalse(self.broker.status()['connected'])

    def test_invalid_balance_never_bypasses_risk(self):
        for value in ('NaN', 'Infinity', -1, None, True):
            with self.subTest(value=value):
                self.transport.balance = lambda: {'balance': value, 'currency': 'USD'}
                with self.assertRaises(BridgeError):
                    self.quote()
        self.assertEqual(self.transport.buy_count, 0)
        self.assertEqual(self.store.history('DOT90000001'), [])

    def test_missing_currency_and_wrong_account_balance_block_orders(self):
        for payload in ({'balance': 10000},
                        {'balance': 10000, 'currency': 'EUR'},
                        {'balance': 10000, 'currency': 'USD', 'account_id': 'OTHER123'}):
            with self.subTest(payload=payload):
                self.transport.balance = lambda: payload
                with self.assertRaises(BridgeError):
                    self.quote()
        self.assertEqual(self.transport.buy_count, 0)

    def test_missing_or_malformed_portfolio_is_not_an_empty_account(self):
        for portfolio in ({}, {'contracts': None}, {'contracts': ['invalid']}, []):
            with self.subTest(portfolio=portfolio):
                self.transport.portfolio = lambda: portfolio
                with self.assertRaisesRegex(BridgeError, 'position information'):
                    self.quote()
        self.assertEqual(self.transport.buy_count, 0)

    def test_emergency_stop_between_quote_and_buy_blocks_purchase(self):
        quote = self.quote()
        self.broker.risk.kill_all('Operator emergency stop')
        with self.assertRaisesRegex(BridgeError, 'emergency stop'):
            self.broker.buy_quote(quote['token'])
        self.assertEqual(self.transport.buy_count, 0)
        self.assertEqual(self.store.history('DOT90000001'), [])

    def test_global_stop_during_journal_reservation_rejects_before_dispatch(self):
        quote = self.quote()
        reserve = self.store.reserve
        def reserve_then_halt(*args):
            order_id = reserve(*args)
            self.broker.risk.kill_all('Operator halted during disk write')
            return order_id
        with patch.object(self.store, 'reserve', side_effect=reserve_then_halt):
            with self.assertRaisesRegex(BridgeError, 'before dispatch'):
                self.broker.buy_quote(quote['token'])
        self.assertEqual(self.transport.buy_count, 0)
        self.assertEqual(self.store.history('DOT90000001')[0]['status'], 'REJECTED')
        self.assertEqual(self.broker.risk.status('DOT90000001', 'demo')['reservations']['uncertain'], 0)

    def test_account_stop_during_journal_reservation_rejects_before_dispatch(self):
        quote = self.quote()
        reserve = self.store.reserve
        def reserve_then_halt(*args):
            order_id = reserve(*args)
            self.broker.risk.kill('DOT90000001', 'demo', 'Account-specific halt')
            return order_id
        with patch.object(self.store, 'reserve', side_effect=reserve_then_halt):
            with self.assertRaisesRegex(BridgeError, 'before dispatch'):
                self.broker.buy_quote(quote['token'])
        self.assertEqual(self.transport.buy_count, 0)
        self.assertEqual(self.store.history('DOT90000001')[0]['status'], 'REJECTED')

    def test_connection_status_records_snapshot_time_without_claiming_heartbeat(self):
        state = self.broker.status()
        self.assertLessEqual(abs(state['last_verified_at'] - time.time()), 5)
        self.assertIn('not a continuous heartbeat', state['connectivity_note'])
        self.broker.disconnect()
        self.assertIsNone(self.broker.status()['last_verified_at'])

    def test_restart_does_not_reset_emergency_stop(self):
        self.broker.risk.kill_all('Persistent stop')
        self.broker = BrokerController(self.store, self.transport)
        self.connect()
        with self.assertRaisesRegex(BridgeError, 'emergency stop'):
            self.quote()

    def test_automatic_orders_require_fresh_news_coverage(self):
        with self.assertRaisesRegex(BridgeError, 'calendar'):
            self.quote(internal=True)
        self.assertEqual(self.transport.buy_count, 0)

    def test_synthetic_exemption_requires_broker_metadata_and_explicit_setting(self):
        self.broker.risk.configure('DOT90000001', 'demo', {'calendar_policy': 'synthetic_exempt'})
        with self.assertRaisesRegex(BridgeError, 'calendar'):
            self.quote(internal=True)
        self.transport.market_metadata = {'R_100': {'market': 'synthetic_index'}}
        quote = self.quote(internal=True)
        result = self.broker.buy_quote(quote['token'], internal=True)
        self.assertEqual(result['mode'], 'demo')
        self.assertEqual(self.transport.buy_count, 1)

    def test_final_ask_price_is_used_for_risk_approval(self):
        self.broker.risk.configure('DOT90000001', 'demo', {'risk_per_trade_pct': .1})
        self.transport.proposal = lambda *a: {'id': 'quote', 'ask_price': 10.05, 'payout': 20}
        quote = self.broker.new_quote('R_100', 'UP', 10, 2)
        with self.assertRaisesRegex(BridgeError, 'per-trade equity risk limit'):
            self.broker.buy_quote(quote['token'])
        self.assertEqual(self.transport.buy_count, 0)

    def test_capability_change_between_quote_and_buy_blocks_purchase(self):
        quote = self.quote()
        self.transport.contracts_for = lambda symbol: {'UP': [], 'DOWN': []}
        with self.assertRaisesRegex(BridgeError, 'does not offer'):
            self.broker.buy_quote(quote['token'])
        self.assertEqual(self.transport.buy_count, 0)

    def test_noninteger_and_boolean_durations_are_not_truncated(self):
        for duration in (True, 1.9, '2.5', float('nan'), None):
            with self.subTest(duration=duration):
                with self.assertRaises(BridgeError):
                    self.broker.new_quote('R_100', 'UP', 1, duration)

    def test_failed_quote_refresh_invalidates_previous_quote(self):
        first = self.quote()
        with self.assertRaises(BridgeError):
            self.broker.new_quote('R_100', 'UP', 1, 99)
        with self.assertRaises(BridgeError):
            self.broker.buy_quote(first['token'])
        self.assertEqual(self.transport.buy_count, 0)

    def test_quote_expiring_during_risk_check_is_rejected_before_send(self):
        quote = self.quote()
        internal_quote = self.broker.quote
        reserve = self.broker.risk.reserve
        def delayed_reservation(*args, **kwargs):
            result = reserve(*args, **kwargs)
            internal_quote['created'] = time.monotonic() - 13
            return result
        with patch.object(self.broker.risk, 'reserve', side_effect=delayed_reservation):
            with self.assertRaisesRegex(BridgeError, 'expired while validating'):
                self.broker.buy_quote(quote['token'])
        self.assertEqual(self.transport.buy_count, 0)
        self.assertEqual(self.store.history('DOT90000001')[0]['status'], 'REJECTED')

    def test_unexpected_purchase_exception_is_durable_uncertain_and_never_retried(self):
        quote = self.quote()
        def fail(*args):
            self.transport.buy_count += 1
            raise RuntimeError('socket implementation failure')
        self.transport.buy = fail
        with self.assertRaises(UnknownExecution):
            self.broker.buy_quote(quote['token'])
        self.assertEqual(self.store.history('DOT90000001')[0]['status'], 'UNCERTAIN')
        self.connect()
        with self.assertRaisesRegex(BridgeError, 'uncertain order'):
            self.quote()
        self.assertEqual(self.transport.buy_count, 1)

    def test_only_correlated_broker_rejection_is_known_failure(self):
        quote = self.quote()
        def reject(*args):
            raise BrokerRejection('Deriv InsufficientBalance: Request rejected')
        self.transport.buy = reject
        with self.assertRaises(BrokerRejection):
            self.broker.buy_quote(quote['token'])
        self.assertEqual(self.store.history('DOT90000001')[0]['status'], 'REJECTED')
        self.assertIsNotNone(self.quote()['token'])

    def test_plain_bridge_error_after_send_is_uncertain(self):
        quote = self.quote()
        self.transport.buy = lambda *a: (_ for _ in ()).throw(BridgeError('Unknown transport failure'))
        with self.assertRaises(UnknownExecution):
            self.broker.buy_quote(quote['token'])
        self.assertEqual(self.store.history('DOT90000001')[0]['status'], 'UNCERTAIN')

    def test_malformed_purchase_response_is_uncertain(self):
        quote = self.quote()
        self.transport.buy = lambda *a: []
        with self.assertRaises(UnknownExecution):
            self.broker.buy_quote(quote['token'])
        self.assertEqual(self.store.history('DOT90000001')[0]['status'], 'UNCERTAIN')

    def test_known_contract_survives_invalid_purchase_price_for_reconciliation(self):
        quote = self.quote()
        self.transport.buy = lambda *a: {'contract_id': 98765, 'buy_price': 'NaN'}
        with self.assertRaises(UnknownExecution):
            self.broker.buy_quote(quote['token'])
        order = self.store.history('DOT90000001')[0]
        self.assertEqual((order['status'], order['contract_id']), ('UNCERTAIN', '98765'))
        self.transport.contract_sold = True
        self.broker.reconcile()
        self.assertEqual(self.store.history('DOT90000001')[0]['status'], 'CLOSED')

    def test_missing_settlement_profit_is_not_recorded_as_break_even(self):
        quote = self.quote()
        self.broker.buy_quote(quote['token'])
        self.transport.contract = lambda cid: {'is_sold': 1, 'status': 'sold'}
        with self.assertRaisesRegex(BridgeError, 'settlement profit'):
            self.broker.reconcile()
        self.assertEqual(self.store.history('DOT90000001')[0]['status'], 'OPEN')

    def test_journal_tampering_blocks_orders_before_reconciliation(self):
        quote = self.quote()
        self.broker.buy_quote(quote['token'])
        with self.store.db() as connection:
            connection.execute("UPDATE orders SET stake=0 WHERE account_id='DOT90000001'")
        with self.assertRaisesRegex(BridgeError, 'integrity'):
            self.quote()
        self.assertEqual(self.transport.buy_count, 1)

    def test_journal_write_failure_after_send_stays_uncertain(self):
        quote = self.quote()
        with patch.object(self.store, 'update', side_effect=OSError('disk failure')):
            with self.assertRaises(UnknownExecution):
                self.broker.buy_quote(quote['token'])
        self.assertEqual(self.store.history('DOT90000001')[0]['status'], 'PENDING')
        with self.assertRaises(BridgeError):
            self.quote()
        self.assertEqual(self.transport.buy_count, 1)

    def test_reconciliation_rejects_wrong_contract_identity(self):
        quote = self.quote()
        self.broker.buy_quote(quote['token'])
        self.transport.contract = lambda cid: {'is_sold': 1, 'status': 'sold', 'profit': .8, 'contract_id': 'WRONG'}
        with self.assertRaisesRegex(BridgeError, 'identity mismatch'):
            self.broker.reconcile()
        self.assertEqual(self.store.history('DOT90000001')[0]['status'], 'OPEN')

    def test_rationale_is_whitelisted_and_durable(self):
        quote = self.quote(context={'strategy': 'last_kiss', 'strategy_version': '1',
                                    'rationale': 'Closed-bar retest', 'token': 'must-not-store'})
        self.broker.buy_quote(quote['token'])
        row = self.store.history('DOT90000001')[0]
        self.assertIn('Closed-bar retest', row['context_json'])
        self.assertNotIn('must-not-store', row['context_json'])


class TransportSafetyTests(unittest.TestCase):
    def socket_for(self, payload):
        class Socket:
            def send(self, raw): self.request = json.loads(raw)
            def recv(self): return json.dumps({'req_id': self.request['req_id'], **payload})
            def close(self): pass
        transport = DerivTransport()
        transport.ws = Socket()
        return transport

    def test_closed_and_suspended_symbols_are_not_offered(self):
        self.assertEqual(normalize_active_symbols({'active_symbols': [
            {'symbol': 'R_100', 'exchange_is_open': 0},
            {'symbol': 'R_50', 'is_trading_suspended': 1}]}), [])

    def test_otp_cannot_add_other_parameters_or_fragments(self):
        base = 'wss://api.derivws.com/trading/v1/options/ws/demo?otp=example'
        for suffix in ('&host=evil.com', '#fragment', '&otp=another'):
            with self.assertRaises(BridgeError):
                check_otp_url(base + suffix, 'demo')

    def test_error_responses_are_correlated_and_do_not_reflect_raw_secrets(self):
        transport = self.socket_for({'error': {'code': 'InvalidToken', 'message': 'private-PAT-secret'}})
        with self.assertRaises(BrokerRejection) as err:
            transport.rpc({'buy': 'proposal', 'price': 1}, purchasing=True)
        self.assertIn('InvalidToken', str(err.exception))
        self.assertNotIn('private-PAT-secret', str(err.exception))

    def test_rest_credentials_never_follow_a_redirect(self):
        request = Request('https://api.derivws.com/trading/v1/options/accounts',
                          headers={'Authorization': 'Bearer private-test-token'})
        with self.assertRaises(HTTPError):
            _NoCredentialRedirect().redirect_request(request, None, 302, 'Redirect', {}, 'https://other.example/accounts')

    def test_unmatched_purchase_replies_are_not_retried(self):
        class Socket:
            def __init__(self): self.sent = []; self.closed = False
            def send(self, raw): self.sent.append(json.loads(raw))
            def recv(self): return json.dumps({'req_id': 999, 'buy': {'contract_id': 1}})
            def close(self): self.closed = True
        socket = Socket()
        transport = DerivTransport()
        transport.ws = socket
        with self.assertRaises(UnknownExecution):
            transport.buy('proposal', 1)
        self.assertEqual(len(socket.sent), 1)
        self.assertTrue(socket.closed)

    def test_malformed_candles_cannot_generate_a_signal(self):
        for candles in (None, [{'open': 10, 'high': 5, 'low': 1, 'close': 9, 'epoch': 100}]):
            transport = self.socket_for({'candles': candles})
            with self.assertRaisesRegex(BridgeError, 'candle'):
                transport.candles('R_100')

    def test_out_of_order_candles_are_rejected(self):
        rows = [{'open': 2, 'high': 3, 'low': 1, 'close': 2, 'epoch': t} for t in (120, 60)]
        transport = self.socket_for({'candles': rows})
        with self.assertRaisesRegex(BridgeError, 'out of order'):
            transport.candles('R_100')

    def test_missing_portfolio_payload_is_not_silently_empty(self):
        with self.assertRaisesRegex(BridgeError, 'portfolio'):
            self.socket_for({}).portfolio()

    def test_symbols_keep_broker_market_type_provenance(self):
        transport = self.socket_for({'active_symbols': [{'symbol': 'R_100', 'market': 'synthetic_index'}]})
        self.assertEqual(transport.symbols(), [{'symbol': 'R_100', 'name': 'R_100'}])
        self.assertEqual(transport.market_metadata['R_100']['market'], 'synthetic_index')


if __name__ == '__main__':
    unittest.main()
