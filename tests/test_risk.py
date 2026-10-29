"""Deterministic risk/failure tests: these never connect to a broker."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import json
import tempfile
import time
import unittest
from unittest.mock import patch

from risk_engine import RiskEngine, RiskError


class RiskTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'risk.db'
        self.risk = RiskEngine(self.path)
        self.now = datetime(2026, 10, 29, 12, tzinfo=timezone.utc).timestamp()
        self.base = dict(equity=10000., stake=10., symbol='frxEURUSD',
                         positions=[], orders=[], automatic=False, market_kind='forex', now=self.now)

    def tearDown(self):
        self.temp.cleanup()

    def check(self, **changes):
        return self.risk.evaluate('DEMO1', 'demo', **{**self.base, **changes})

    def closed(self, pnl, *, seconds_ago=60, mode='demo', symbol='frxEURUSD'):
        return {'nonce': f'closed-{seconds_ago}-{pnl}', 'account_id': 'DEMO1', 'mode': mode,
                'status': 'CLOSED', 'symbol': symbol, 'stake': 10, 'ask_price': 10,
                'opened_at': self.now - seconds_ago - 60, 'updated_at': self.now - seconds_ago,
                'pnl': pnl, 'contract_id': str(seconds_ago)}

    def open_order(self, i, stake=10):
        return {'nonce': f'order-{i}', 'account_id': 'DEMO1', 'mode': 'demo', 'status': 'OPEN',
                'symbol': 'frxEURUSD', 'stake': stake, 'ask_price': stake,
                'opened_at': self.now - 60, 'contract_id': str(i)}

    def test_safe_default_approved_and_audit_valid(self):
        result = self.check()
        self.assertTrue(result['allowed'], result)
        self.assertAlmostEqual(result['checks']['risk_per_trade_pct'], .1)
        status = self.risk.status('DEMO1', 'demo')
        self.assertEqual(status['config']['risk_per_trade_pct'], .5)
        self.assertTrue(status['audit']['valid'])
        self.assertGreater(status['audit']['count'], 0)

    def test_per_trade_risk_and_absolute_order_size(self):
        result = self.check(stake=51)
        self.assertFalse(result['allowed'])
        self.assertTrue(any('per-trade' in reason for reason in result['reasons']))
        self.assertTrue(any('order size' in reason for reason in result['reasons']))
        self.assertFalse(self.check(equity=1000, stake=6)['allowed'])

    def test_missing_nonfinite_and_boolean_values_fail_closed(self):
        for name in ('equity', 'stake'):
            for invalid in (None, float('nan'), float('inf'), True, -1, 0):
                with self.subTest(name=name, invalid=invalid):
                    self.assertFalse(self.check(**{name: invalid})['allowed'])
        self.assertFalse(self.check(positions=None)['allowed'])
        self.assertFalse(self.check(orders=None)['allowed'])
        self.assertFalse(self.check(symbol='')['allowed'])
        self.assertFalse(self.check(automatic='yes')['allowed'])

    def test_daily_loss_cannot_be_reset_by_restart_or_strategy_change(self):
        self.assertTrue(self.check()['allowed'])
        denied = self.check(equity=9800, orders=[self.closed(-200)])
        self.assertFalse(denied['allowed'])
        self.risk = RiskEngine(self.path)
        denied = self.check(equity=9800, symbol='frxGBPUSD', orders=[self.closed(-200)])
        self.assertFalse(denied['allowed'])
        self.assertTrue(any('Daily' in r for r in denied['reasons']))
        self.assertEqual(self.risk.status('DEMO1', 'demo')['day_start_equity'], 10000)

    def test_weekly_loss_after_daily_window_rollover(self):
        self.check()
        tomorrow = self.now + 86400
        result = self.check(now=tomorrow, equity=9500, orders=[self.closed(-500, seconds_ago=120)])
        self.assertFalse(result['allowed'])
        self.assertTrue(any('Weekly' in r for r in result['reasons']))
        self.assertEqual(self.risk.status('DEMO1', 'demo')['week_start_equity'], 10000)
        self.assertEqual(self.risk.status('DEMO1', 'demo')['day_start_equity'], 9500)

    def test_equity_peak_drawdown_survives_recovery_and_restart(self):
        self.check()
        self.check(equity=11000)
        self.risk = RiskEngine(self.path)
        result = self.check(equity=9900)
        self.assertFalse(result['allowed'])
        self.assertTrue(any('drawdown' in r for r in result['reasons']))
        self.assertEqual(self.risk.status('DEMO1', 'demo')['peak_equity'], 11000)

    def test_daily_trade_limit_and_closed_profit_do_not_bypass(self):
        orders = [self.closed(1, seconds_ago=60 + i) for i in range(12)]
        result = self.check(orders=orders)
        self.assertFalse(result['allowed'])
        self.assertTrue(any('new trades' in r for r in result['reasons']))

    def test_max_positions_and_asset_exposure(self):
        result = self.check(orders=[self.open_order(i) for i in range(3)])
        self.assertFalse(result['allowed'])
        self.assertTrue(any('position limit' in r for r in result['reasons']))
        self.risk.configure('DEMO1', 'demo', {'max_asset_exposure_pct': .1})
        result = self.check(orders=[self.open_order(1)], stake=1)
        self.assertFalse(result['allowed'])
        self.assertTrue(any('instrument exposure' in r for r in result['reasons']))

    def test_correlated_group_exposure_is_separate(self):
        self.risk.configure('DEMO1', 'demo', {'max_group_exposure_pct': .1})
        order = {**self.open_order(1), 'symbol': 'frxGBPUSD'}
        result = self.check(orders=[order], stake=1)
        self.assertFalse(result['allowed'])
        self.assertTrue(any('correlated-group' in r for r in result['reasons']))

    def test_unknown_open_positions_and_pending_orders_block(self):
        self.assertFalse(self.check(positions=[{'contract_id': 'untracked', 'stake': 5}])['allowed'])
        self.assertFalse(self.check(positions=[{'contract_id': 'bad-risk'}])['allowed'])
        for status in ('PENDING', 'UNCERTAIN'):
            self.assertFalse(self.check(orders=[{**self.open_order(1), 'status': status}])['allowed'])

    def test_consecutive_losses_enforce_cooldown_then_release(self):
        orders = [self.closed(-1, seconds_ago=60 + i) for i in range(3)]
        result = self.check(orders=orders)
        self.assertFalse(result['allowed'])
        self.assertTrue(any('cooldown' in r for r in result['reasons']))
        result = self.check(orders=orders, now=self.now + 3601)
        self.assertTrue(result['allowed'], result)

    def test_emergency_stop_persists_and_isolates_account_modes(self):
        self.risk.kill('DEMO1', 'demo', 'User emergency')
        self.risk = RiskEngine(self.path)
        self.assertFalse(self.check()['allowed'])
        self.assertTrue(self.risk.evaluate('DEMO2', 'demo', **self.base)['allowed'])
        self.assertFalse(self.risk.evaluate('DEMO1', 'real', **self.base)['allowed'])
        with self.assertRaises(RiskError):
            self.risk.resume('DEMO1', 'demo', 'yes')
        self.risk.resume('DEMO1', 'demo', 'RESUME DEMO TRADING')
        self.assertTrue(self.check()['allowed'])

    def test_global_stop_survives_disconnect_account_switch_and_restart(self):
        self.risk.kill_all('Global emergency')
        self.risk = RiskEngine(self.path)
        self.assertTrue(self.risk.global_status()['killed'])
        self.assertFalse(self.check()['allowed'])
        self.assertFalse(self.risk.evaluate('DEMO2', 'demo', **self.base)['allowed'])
        with self.assertRaises(RiskError):
            self.risk.resume_all('yes')
        self.risk.resume_all('RESUME DEMO TRADING')
        self.assertTrue(self.check()['allowed'])

    def test_configuration_validation_enforces_hard_boundaries(self):
        for updates in ({'risk_per_trade_pct': 2}, {'max_positions': 4}, {'max_positions': 1.5},
                        {'daily_loss_pct': 6}, {'max_order_size': float('nan')},
                        {'martingale': True}, {'cooldown_minutes': False},
                        {'calendar_policy': 'disabled'}, {'daily_loss_pct': 4, 'weekly_loss_pct': 3}):
            with self.subTest(updates=updates), self.assertRaises(RiskError):
                self.risk.configure('DEMO1', 'demo', updates)
        self.risk.configure('DEMO1', 'demo', {'risk_per_trade_pct': .25})
        self.assertEqual(RiskEngine(self.path).status('DEMO1', 'demo')['config']['risk_per_trade_pct'], .25)

    def test_stale_or_missing_calendar_blocks_automation(self):
        self.assertFalse(self.check(automatic=True)['allowed'])
        with patch('risk_engine.time.time', return_value=self.now):
            self.risk.set_calendar('DEMO1', 'demo', [], self.now - 10, self.now + 86400, 'Licensed fixture')
        self.assertTrue(self.check(automatic=True)['allowed'])
        self.assertFalse(self.check(automatic=True, now=self.now + 86401)['allowed'])
        self.assertTrue(self.check(automatic=False, now=self.now + 86401)['allowed'])

    def test_calendar_blackout_applies_to_relevant_currency(self):
        event = {'time': self.now, 'currencies': ['USD'], 'impact': 'high', 'name': 'CPI'}
        with patch('risk_engine.time.time', return_value=self.now):
            self.risk.set_calendar('DEMO1', 'demo', [event], self.now - 10, self.now + 3600, 'Licensed fixture')
        result = self.check(automatic=True)
        self.assertFalse(result['allowed'])
        self.assertTrue(any('CPI' in r for r in result['reasons']))
        self.assertTrue(self.check(automatic=True, symbol='frxEURGBP')['allowed'])
        self.assertFalse(self.check(automatic=True, symbol='UNKNOWN')['allowed'])

    def test_synthetic_exemption_requires_explicit_config_and_metadata(self):
        self.assertFalse(self.check(automatic=True, symbol='R_100', market_kind='synthetic')['allowed'])
        self.risk.configure('DEMO1', 'demo', {'calendar_policy': 'synthetic_exempt'})
        self.assertTrue(self.check(automatic=True, symbol='R_100', market_kind='synthetic')['allowed'])
        self.assertFalse(self.check(automatic=True, symbol='R_100', market_kind='unknown')['allowed'])
        self.assertFalse(self.check(automatic=True, market_kind='forex')['allowed'])

    def test_calendar_validation_does_not_accept_future_or_unbounded_claims(self):
        with patch('risk_engine.time.time', return_value=self.now):
            for events, updated, until in [([], self.now + 1000, self.now + 2000),
                                           ([], self.now, self.now + 8 * 86400),
                                           ([{'time': self.now, 'currencies': []}], self.now, self.now + 3600)]:
                with self.assertRaises(RiskError):
                    self.risk.set_calendar('DEMO1', 'demo', events, updated, until, 'Fixture')

    def test_atomic_reservations_block_duplicate_and_unjournaled_concurrent_orders(self):
        def submit(i):
            independent = RiskEngine(self.path)
            return independent.reserve('same-nonce', 'DEMO1', 'demo', **self.base)
        with ThreadPoolExecutor(max_workers=6) as pool:
            decisions = list(pool.map(submit, range(6)))
        self.assertEqual(sum(r['allowed'] for r in decisions), 1)
        self.assertFalse(self.risk.reserve('another-nonce', 'DEMO1', 'demo', **self.base)['allowed'])
        self.assertEqual(self.risk.status('DEMO1', 'demo')['reservations']['pending'], 1)
        with self.assertRaises(RiskError):
            self.risk.resume_all('RESUME DEMO TRADING')
        self.risk.resolve('same-nonce', 'REJECTED')
        self.assertTrue(self.risk.reserve('fresh-nonce', 'DEMO1', 'demo', **self.base)['allowed'])

    def test_resolved_orders_are_counted_once_and_uncertain_interlock_persists(self):
        self.assertTrue(self.risk.reserve('order-1', 'DEMO1', 'demo', **self.base)['allowed'])
        self.risk.resolve('order-1', 'OPEN')
        result = self.check(orders=[self.open_order(1)])
        self.assertTrue(result['allowed'], result)
        self.assertEqual(result['checks']['open_positions'], 1)
        self.risk.resolve('order-1', 'UNCERTAIN')
        self.assertFalse(self.check(orders=[self.open_order(1)])['allowed'])
        with self.assertRaises(RiskError):
            self.risk.resolve('order-1', 'REJECTED')
        self.risk.resolve('order-1', 'CLOSED')
        with self.assertRaises(RiskError):
            self.risk.resolve('order-1', 'OPEN')
        self.assertFalse(self.risk.reserve('order-1', 'DEMO1', 'demo', **self.base)['allowed'])

    def test_audit_export_verifies_and_tampering_is_detected(self):
        self.check()
        self.risk.kill_all()
        self.assertTrue(self.risk.verify_audit()['valid'])
        exported = self.risk.audit('DEMO1', 'demo')
        self.assertEqual(exported[0]['event'], 'ORDER_APPROVED')
        self.assertIsInstance(exported[0]['payload'], dict)
        with sqlite3.connect(self.path) as c:
            c.execute("UPDATE risk_audit SET payload='{}' WHERE id=1")
        self.assertFalse(self.risk.verify_audit()['valid'])
        self.assertFalse(self.check()['allowed'])
        self.assertTrue(self.risk.global_status()['killed'])
        with self.assertRaises(RiskError):
            self.risk.resume_all('RESUME DEMO TRADING')

    def test_materialized_risk_state_and_deleted_accounts_cannot_reset_limits(self):
        self.check()
        with sqlite3.connect(self.path) as c:
            row = c.execute('SELECT state FROM risk_state').fetchone()
            state = json.loads(row[0])
            state['peak_equity'] = 9000
            c.execute('UPDATE risk_state SET state=?', (json.dumps(state),))
        self.assertFalse(self.risk.verify_audit()['valid'])
        self.assertFalse(self.check()['allowed'])
        with self.assertRaises(RiskError):
            self.risk.configure('DEMO1', 'demo', {'risk_per_trade_pct': .25})
        with sqlite3.connect(self.path) as c:
            c.execute('DELETE FROM risk_state')
        self.assertFalse(self.risk.verify_audit()['valid'])
        self.assertFalse(self.check()['allowed'])

    def test_reservation_tampering_cannot_be_laundered_by_duplicate_or_resolve(self):
        self.assertTrue(self.risk.reserve('test-nonce', 'DEMO1', 'demo', **self.base)['allowed'])
        with sqlite3.connect(self.path) as c:
            c.execute("UPDATE risk_reservations SET stake=1 WHERE nonce='test-nonce'")
        self.assertFalse(self.risk.verify_audit()['valid'])
        self.assertFalse(self.risk.reserve('test-nonce', 'DEMO1', 'demo', **self.base)['allowed'])
        with self.assertRaises(RiskError):
            self.risk.resolve('test-nonce', 'REJECTED')
        self.assertFalse(self.risk.verify_audit()['valid'])
        # Emergency shutdown must still persist, without repairing corrupt data.
        self.assertTrue(self.risk.kill_all('Stop during incident')['killed'])
        self.assertFalse(self.risk.verify_audit()['valid'])
        self.assertTrue(self.risk.global_status()['killed'])

    def test_removed_global_interlock_is_detected(self):
        self.check()
        self.risk.kill_all()
        with sqlite3.connect(self.path) as c:
            c.execute('DELETE FROM risk_global')
        self.assertFalse(self.risk.verify_audit()['valid'])
        self.assertTrue(self.risk.global_status()['killed'])
        self.assertFalse(self.check()['allowed'])

    def test_broker_observations_capture_pre_order_losses_without_resetting_baselines(self):
        self.risk.observe('DEMO1', 'demo', equity=10000, now=self.now)
        self.risk.observe('DEMO1', 'demo', equity=11000, now=self.now + 1)
        self.risk = RiskEngine(self.path)
        self.risk.observe('DEMO1', 'demo', equity=9800, now=self.now + 2)
        result = self.check(equity=9800, now=self.now + 3)
        self.assertFalse(result['allowed'])
        self.assertTrue(any('drawdown' in reason for reason in result['reasons']))
        status = self.risk.status('DEMO1', 'demo')
        self.assertEqual(status['baseline_equity'], 10000)
        self.assertEqual(status['peak_equity'], 11000)
        self.assertEqual(status['day_start_equity'], 10000)
        self.assertTrue(status['audit']['valid'])

    def test_zero_balance_is_observable_but_not_tradeable(self):
        self.risk.observe('DEMO1', 'demo', equity=0, now=self.now)
        self.assertFalse(self.check(equity=0)['allowed'])
        self.risk.observe('DEMO1', 'demo', equity=10000, now=self.now)
        self.assertTrue(self.check()['allowed'])

    def test_calendar_policy_query_does_not_mutate_risk_or_approve_orders(self):
        before = self.risk.verify_audit()['count']
        result = self.risk.calendar_status('DEMO1', 'demo', 'frxEURUSD', now=self.now)
        self.assertFalse(result['allowed'])
        self.assertTrue(result['required'])
        self.assertEqual(before, self.risk.verify_audit()['count'])
        self.risk.configure('DEMO1', 'demo', {'calendar_policy': 'synthetic_exempt'})
        self.assertTrue(self.risk.calendar_status('DEMO1', 'demo', 'R_100', market_kind='synthetic', now=self.now)['allowed'])

    def test_invalid_history_cannot_silently_zero_profit_or_backdate_clock(self):
        for order in ({**self.closed(1), 'pnl': float('nan')},
                      {**self.closed(1), 'status': 'UNKNOWN'},
                      {**self.closed(1), 'opened_at': self.now + 1000}):
            self.assertFalse(self.check(orders=[order])['allowed'])
        self.assertTrue(self.check()['allowed'])
        self.assertFalse(self.check(now=self.now - 60)['allowed'])

    def test_real_execution_is_denied_even_when_halt_is_clear(self):
        result = self.risk.evaluate('REAL1', 'real', **self.base)
        self.assertFalse(result['allowed'])
        self.assertTrue(any('Real-money' in r for r in result['reasons']))
        with self.assertRaises(RiskError):
            self.risk.require('REAL1', 'real', **self.base)


if __name__ == '__main__':
    unittest.main()
