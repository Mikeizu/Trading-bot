"""Persistent, deterministic safeguards for fixed-stake research/demo contracts.

This module does not submit orders, infer broker permissions, model CFD margin,
close positions, or certify a strategy. Broker snapshots must be fresh and
complete. All UTC loss windows, interlocks and reservations survive restarts.
The SQLite hash chain detects casual journal edits; it is not externally signed.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import threading
import time


class RiskError(ValueError):
    """Invalid risk configuration, untrusted snapshot, or a denied decision."""


DEFAULTS = {
    'risk_per_trade_pct': .5,
    'daily_loss_pct': 2.,
    'weekly_loss_pct': 5.,
    'max_drawdown_pct': 10.,
    'max_positions': 3,
    'max_trades_per_day': 12,
    'max_order_size': 50.,
    'max_asset_exposure_pct': 1.5,
    'max_group_exposure_pct': 1.5,
    'consecutive_loss_limit': 3,
    'cooldown_minutes': 60,
    'calendar_policy': 'required',
}
# Enforced ceilings are intentionally conservative and cannot be bypassed in UI.
BOUNDS = {
    'risk_per_trade_pct': (.01, 1.),
    'daily_loss_pct': (.1, 5.),
    'weekly_loss_pct': (.1, 10.),
    'max_drawdown_pct': (.1, 20.),
    'max_positions': (1, 3),
    'max_trades_per_day': (1, 100),
    'max_order_size': (.01, 50.),
    'max_asset_exposure_pct': (.01, 3.),
    'max_group_exposure_pct': (.01, 3.),
    'consecutive_loss_limit': (1, 5),
    'cooldown_minutes': (1, 1440),
}
INTEGER_FIELDS = {'max_positions', 'max_trades_per_day', 'consecutive_loss_limit', 'cooldown_minutes'}
ACTIVE = {'APPROVED', 'OPEN', 'UNCERTAIN', 'PENDING'}
FINAL = {'CLOSED', 'REJECTED'}


def _number(value, name, *, minimum=None):
    if isinstance(value, bool):
        raise RiskError(f'{name} must be a finite number')
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        raise RiskError(f'{name} must be a finite number') from None
    if not math.isfinite(result) or (minimum is not None and result < minimum):
        raise RiskError(f'{name} must be a finite number' + (f' >= {minimum:g}' if minimum is not None else ''))
    return result


def _identity(account_id, mode):
    if not isinstance(account_id, str) or not account_id.strip() or len(account_id) > 128:
        raise RiskError('A verified account identity is required')
    if mode not in ('demo', 'real', 'paper'):
        raise RiskError('A verified account mode is required')
    return account_id, mode


def _encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _windows(now):
    dt = datetime.fromtimestamp(now, timezone.utc)
    day = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return day.timestamp(), day.timestamp() - dt.weekday() * 86400


class RiskEngine:
    """Each approval is based on explicit data; no network or credentials here.

    ``evaluate``/``require`` inspect a snapshot. Immediately before sending a buy,
    ``reserve`` repeats the same checks under a write transaction and consumes a
    unique nonce. ``resolve`` records known broker outcomes; uncertainty continues
    to block entries. The application must reconcile broker orders first.
    """
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as c:
            c.execute('PRAGMA journal_mode=WAL')
            c.execute('''CREATE TABLE IF NOT EXISTS risk_state (
                account_id TEXT NOT NULL, mode TEXT NOT NULL, state TEXT NOT NULL,
                PRIMARY KEY(account_id, mode))''')
            c.execute('''CREATE TABLE IF NOT EXISTS risk_reservations (
                nonce TEXT PRIMARY KEY, account_id TEXT NOT NULL, mode TEXT NOT NULL,
                symbol TEXT NOT NULL, group_name TEXT NOT NULL, stake REAL NOT NULL,
                status TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL)''')
            c.execute('''CREATE TABLE IF NOT EXISTS risk_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT, account_id TEXT NOT NULL,
                mode TEXT NOT NULL, event TEXT NOT NULL, event_at REAL NOT NULL,
                payload TEXT NOT NULL, previous_hash TEXT NOT NULL, hash TEXT NOT NULL)''')
            c.execute('''CREATE TABLE IF NOT EXISTS risk_global (
                id INTEGER PRIMARY KEY CHECK(id=1), state TEXT NOT NULL)''')
            c.execute('PRAGMA user_version=1')

    @contextmanager
    def _db(self):
        with self.lock:
            c = sqlite3.connect(self.path, timeout=20)
            c.row_factory = sqlite3.Row
            c.execute('PRAGMA busy_timeout=20000')
            try:
                yield c
                c.commit()
            except Exception:
                c.rollback()
                raise
            finally:
                c.close()

    @staticmethod
    def _default_state():
        return {
            'config': dict(DEFAULTS), 'killed': False, 'kill_reason': '',
            'baseline_equity': None, 'peak_equity': None,
            'day_start_equity': None, 'week_start_equity': None,
            'day_start': None, 'week_start': None, 'last_equity': None,
            'last_check': None, 'last_decision': None, 'calendar': None,
        }

    def _load(self, c, account_id, mode):
        row = c.execute('SELECT state FROM risk_state WHERE account_id=? AND mode=?', (account_id, mode)).fetchone()
        if row is None:
            return self._default_state()
        checkpoint = c.execute('SELECT payload FROM risk_audit WHERE account_id=? AND mode=? ORDER BY id DESC LIMIT 1', (account_id, mode)).fetchone()
        try:
            expected = json.loads(checkpoint['payload']).get('_state_hash') if checkpoint else None
            if expected != hashlib.sha256(row['state'].encode()).hexdigest():
                raise RiskError('Risk state integrity failed; trading is blocked')
            state = json.loads(row['state'])
        except (ValueError, TypeError, KeyError):
            raise RiskError('Risk state integrity failed; trading is blocked') from None
        if not isinstance(state, dict) or not all(k in state for k in self._default_state()):
            raise RiskError('Risk state is incomplete; trading is blocked')
        self._validate_config(state['config'])
        return state

    @staticmethod
    def _save(c, account_id, mode, state):
        c.execute('''INSERT INTO risk_state VALUES (?,?,?) ON CONFLICT(account_id,mode)
                     DO UPDATE SET state=excluded.state''', (account_id, mode, _encode(state)))

    @staticmethod
    def _reservation_hash(c):
        rows = [dict(row) for row in c.execute('SELECT * FROM risk_reservations ORDER BY nonce')]
        return hashlib.sha256(_encode(rows).encode()).hexdigest()

    @staticmethod
    def _append(c, account_id, mode, event, payload, now):
        prior = c.execute('SELECT hash FROM risk_audit ORDER BY id DESC LIMIT 1').fetchone()
        previous = prior['hash'] if prior else '0' * 64
        payload = dict(payload)
        state_row = c.execute('SELECT state FROM risk_state WHERE account_id=? AND mode=?', (account_id, mode)).fetchone()
        global_row = c.execute('SELECT state FROM risk_global WHERE id=1').fetchone()
        payload['_state_hash'] = hashlib.sha256(state_row['state'].encode()).hexdigest() if state_row else None
        payload['_global_hash'] = hashlib.sha256(global_row['state'].encode()).hexdigest() if global_row else None
        payload['_reservation_hash'] = RiskEngine._reservation_hash(c)
        encoded = _encode(payload)
        envelope = _encode([account_id, mode, event, now, encoded, previous])
        digest = hashlib.sha256(envelope.encode()).hexdigest()
        c.execute('''INSERT INTO risk_audit(account_id,mode,event,event_at,payload,previous_hash,hash)
                     VALUES (?,?,?,?,?,?,?)''', (account_id, mode, event, now, encoded, previous, digest))

    @staticmethod
    def _validate_config(config):
        if not isinstance(config, dict) or set(config) != set(DEFAULTS):
            raise RiskError('Risk settings must use the documented fields')
        out = {}
        for key, limits in BOUNDS.items():
            value = _number(config[key], key)
            if not limits[0] <= value <= limits[1]:
                raise RiskError(f'{key} must be within {limits[0]:g}–{limits[1]:g}')
            if key in INTEGER_FIELDS:
                if value != int(value):
                    raise RiskError(f'{key} must be an integer')
                value = int(value)
            out[key] = value
        if config['calendar_policy'] not in ('required', 'synthetic_exempt'):
            raise RiskError('calendar_policy must be required or synthetic_exempt')
        out['calendar_policy'] = config['calendar_policy']
        if out['daily_loss_pct'] > out['weekly_loss_pct']:
            raise RiskError('Daily loss limit must not exceed weekly loss limit')
        if out['weekly_loss_pct'] > out['max_drawdown_pct']:
            raise RiskError('Weekly loss limit must not exceed drawdown limit')
        return out

    def configure(self, account_id, mode, updates):
        account_id, mode = _identity(account_id, mode)
        if not isinstance(updates, dict) or not updates or set(updates) - set(DEFAULTS):
            raise RiskError('Supply documented risk configuration fields')
        now = time.time()
        with self._db() as c:
            c.execute('BEGIN IMMEDIATE')
            if not self._verify_audit(c)['valid']:
                raise RiskError('Risk audit integrity failed; configuration is blocked')
            state = self._load(c, account_id, mode)
            state['config'] = self._validate_config({**state['config'], **updates})
            self._save(c, account_id, mode, state)
            self._append(c, account_id, mode, 'CONFIGURED', {'config': state['config']}, now)
        return self.status(account_id, mode)

    @staticmethod
    def _global(c):
        row = c.execute('SELECT state FROM risk_global WHERE id=1').fetchone()
        latest = c.execute('SELECT payload FROM risk_audit ORDER BY id DESC LIMIT 1').fetchone()
        expected = json.loads(latest['payload']).get('_global_hash') if latest else None
        actual = hashlib.sha256(row['state'].encode()).hexdigest() if row else None
        if actual != expected:
            return {'killed': True, 'kill_reason': 'Application emergency-stop state integrity failed', 'integrity': False}
        return json.loads(row['state']) if row else {'killed': False, 'kill_reason': ''}

    def global_status(self):
        with self._db() as c:
            if not self._verify_audit(c)['valid']:
                return {'killed': True, 'kill_reason': 'Risk audit integrity failed; new entries are blocked', 'integrity': False}
            return self._global(c)

    def observe(self, account_id, mode, *, equity, now=None):
        """Record authenticated equity at connect/snapshot, never approve a trade.

        Existing baselines cannot be reset by reconnects, config changes or
        historical imports. A zero-balance read-only account stays observable;
        a positive balance is required before establishing its trading baseline.
        """
        account_id, mode = _identity(account_id, mode)
        amount = _number(equity, 'Broker equity', minimum=0)
        current = time.time() if now is None else _number(now, 'Current timestamp', minimum=0)
        with self._db() as c:
            c.execute('BEGIN IMMEDIATE')
            if not self._verify_audit(c)['valid']:
                raise RiskError('Risk audit integrity failed; trading is blocked')
            state = self._load(c, account_id, mode)
            if state['last_check'] is not None and current < state['last_check'] - 1:
                raise RiskError('Clock moved backward; trading is blocked until timestamps recover')
            day, week = _windows(current)
            if state['baseline_equity'] is None and amount > 0:
                state.update(baseline_equity=amount, peak_equity=amount,
                             day_start_equity=amount, week_start_equity=amount,
                             day_start=day, week_start=week)
            if state['baseline_equity'] is not None:
                if state['day_start'] != day:
                    state.update(day_start=day, day_start_equity=amount)
                if state['week_start'] != week:
                    state.update(week_start=week, week_start_equity=amount)
                state['peak_equity'] = max(state['peak_equity'], amount)
            state.update(last_equity=amount, last_check=current)
            self._save(c, account_id, mode, state)
            self._append(c, account_id, mode, 'EQUITY_OBSERVED', {'equity': amount}, current)
            return {'equity': amount, 'baseline_equity': state['baseline_equity'], 'peak_equity': state['peak_equity']}

    def kill_all(self, reason='Application emergency stop requested by user'):
        reason = str(reason).strip()[:240] or 'Application emergency stop requested by user'
        result = {'killed': True, 'kill_reason': reason}
        with self._db() as c:
            c.execute('BEGIN IMMEDIATE')
            integrity = self._verify_audit(c)['valid']
            c.execute('INSERT INTO risk_global VALUES(1,?) ON CONFLICT(id) DO UPDATE SET state=excluded.state', (_encode(result),))
            # Emergency protection remains writable during audit failure, but
            # must never establish fresh checkpoints over corrupted records.
            if integrity:
                self._append(c, '__application__', 'global', 'GLOBAL_EMERGENCY_STOP', {'reason': reason}, time.time())
        return result

    def resume_all(self, confirmation):
        if confirmation != 'RESUME DEMO TRADING':
            raise RiskError('Type RESUME DEMO TRADING to clear the application emergency stop')
        result = {'killed': False, 'kill_reason': ''}
        with self._db() as c:
            c.execute('BEGIN IMMEDIATE')
            if not self._verify_audit(c)['valid']:
                raise RiskError('Risk audit integrity failed; cannot resume trading')
            if c.execute("SELECT 1 FROM risk_reservations WHERE status IN ('APPROVED','PENDING','UNCERTAIN') LIMIT 1").fetchone():
                raise RiskError('Reconcile pending or uncertain orders before resuming')
            c.execute('INSERT INTO risk_global VALUES(1,?) ON CONFLICT(id) DO UPDATE SET state=excluded.state', (_encode(result),))
            self._append(c, '__application__', 'global', 'GLOBAL_RESUMED', {}, time.time())
        return result

    def kill(self, account_id, mode, reason='Emergency stop requested by user'):

        account_id, mode = _identity(account_id, mode)
        reason = str(reason).strip()[:240] or 'Emergency stop requested by user'
        with self._db() as c:
            c.execute('BEGIN IMMEDIATE')
            if not self._verify_audit(c)['valid']:
                raise RiskError('Risk audit integrity failed; use the application emergency stop')
            state = self._load(c, account_id, mode)
            state.update(killed=True, kill_reason=reason)
            self._save(c, account_id, mode, state)
            self._append(c, account_id, mode, 'EMERGENCY_STOP', {'reason': reason}, time.time())
        return self.status(account_id, mode)

    def resume(self, account_id, mode, confirmation):
        account_id, mode = _identity(account_id, mode)
        if mode == 'real' or confirmation != 'RESUME DEMO TRADING':
            raise RiskError('Type RESUME DEMO TRADING to clear the demo emergency stop')
        with self._db() as c:
            c.execute('BEGIN IMMEDIATE')
            if not self._verify_audit(c)['valid']:
                raise RiskError('Risk audit integrity failed; cannot resume trading')
            if c.execute("SELECT 1 FROM risk_reservations WHERE account_id=? AND mode=? AND status IN ('APPROVED','PENDING','UNCERTAIN') LIMIT 1", (account_id, mode)).fetchone():
                raise RiskError('Reconcile pending or uncertain orders before resuming')
            state = self._load(c, account_id, mode)
            state.update(killed=False, kill_reason='')
            self._save(c, account_id, mode, state)
            self._append(c, account_id, mode, 'RESUMED', {}, time.time())
        return self.status(account_id, mode)

    def set_calendar(self, account_id, mode, events, updated_at, valid_until, source):
        """Install explicitly sourced UTC event coverage; no implied live feed.

        Each event: {time: epoch, currencies: ['USD'], impact: 'high',
        before_minutes: 30, after_minutes: 30, name: 'FOMC'}. Wildcard currency
        '*' protects all products. Coverage may span at most seven days and must
        be refreshed every 24h. Empty events still require explicit coverage.
        """
        account_id, mode = _identity(account_id, mode)
        updated = _number(updated_at, 'Calendar updated_at', minimum=0)
        until = _number(valid_until, 'Calendar valid_until', minimum=0)
        now = time.time()
        if updated > now + 60 or until <= updated or until - updated > 7 * 86400:
            raise RiskError('Calendar coverage must be current and span at most seven days')
        if not isinstance(source, str) or not source.strip() or len(source) > 200:
            raise RiskError('An economic-calendar source is required')
        if not isinstance(events, list) or len(events) > 2000:
            raise RiskError('Calendar events must be a list of at most 2000 entries')
        clean = []
        for event in events:
            if not isinstance(event, dict):
                raise RiskError('Invalid calendar event')
            when = _number(event.get('time'), 'Event time', minimum=0)
            currencies = event.get('currencies')
            if (not isinstance(currencies, list) or not currencies or len(currencies) > 20 or
                any(not isinstance(x, str) or (x != '*' and (len(x) != 3 or not x.isalpha() or not x.isupper())) for x in currencies)):
                raise RiskError('Event currencies must be uppercase three-letter codes or *')
            impact = event.get('impact', 'high')
            if impact not in ('high', 'medium', 'low'):
                raise RiskError('Event impact must be high, medium, or low')
            before = _number(event.get('before_minutes', 30), 'Event before_minutes', minimum=0)
            after = _number(event.get('after_minutes', 30), 'Event after_minutes', minimum=0)
            if before > 1440 or after > 1440:
                raise RiskError('Event blackout windows cannot exceed 24h')
            clean.append({'time': when, 'currencies': sorted(set(currencies)), 'impact': impact,
                          'before_minutes': before, 'after_minutes': after,
                          'name': str(event.get('name', 'Economic event'))[:100]})
        with self._db() as c:
            c.execute('BEGIN IMMEDIATE')
            if not self._verify_audit(c)['valid']:
                raise RiskError('Risk audit integrity failed; calendar changes are blocked')
            state = self._load(c, account_id, mode)
            state['calendar'] = {'source': source.strip(), 'updated_at': updated,
                                 'valid_until': until, 'events': clean}
            self._save(c, account_id, mode, state)
            self._append(c, account_id, mode, 'CALENDAR_UPDATED',
                         {'source': source.strip(), 'updated_at': updated, 'valid_until': until,
                          'event_count': len(clean)}, now)
        return self.status(account_id, mode)

    @staticmethod
    def _calendar_fresh(calendar, now):
        return bool(calendar and calendar['updated_at'] <= now + 60 and
                    now - calendar['updated_at'] <= 86400 and now <= calendar['valid_until'])

    @staticmethod
    def _group(symbol, market_kind):
        return 'SYNTHETIC' if market_kind == 'synthetic' else 'FX_AND_OTHER'

    @staticmethod
    def _currencies(symbol):
        # Deriv names such as frxEURUSD and standard EUR/USD remain auditable.
        letters = ''.join(ch for ch in str(symbol).upper() if ch.isalpha())
        for prefix in ('FRX', 'FOREX'):
            if letters.startswith(prefix):
                letters = letters[len(prefix):]
        return {letters[:3], letters[3:6]} if len(letters) == 6 else None

    @classmethod
    def _calendar_decision(cls, state, symbol, market_kind, now):
        calendar = state['calendar']
        fresh = cls._calendar_fresh(calendar, now)
        exempt = market_kind == 'synthetic' and state['config']['calendar_policy'] == 'synthetic_exempt'
        reasons = []
        if not exempt:
            if not fresh:
                reasons.append('Economic-calendar coverage is missing or stale; automatic entries are blocked')
            else:
                currencies = cls._currencies(symbol)
                for event in calendar['events']:
                    relevant = currencies is None or '*' in event['currencies'] or bool(currencies.intersection(event['currencies']))
                    if relevant and event['impact'] == 'high' and event['time'] - event['before_minutes'] * 60 <= now <= event['time'] + event['after_minutes'] * 60:
                        reasons.append('High-impact news blackout: ' + event['name'])
        return {'allowed': not reasons, 'reasons': reasons, 'fresh': fresh,
                'policy': state['config']['calendar_policy'], 'required': not exempt}

    def calendar_status(self, account_id, mode, symbol, market_kind='unknown', now=None):
        """Read calendar policy for automated monitoring/paper without sizing an order."""
        account_id, mode = _identity(account_id, mode)
        current = time.time() if now is None else _number(now, 'Current timestamp', minimum=0)
        if market_kind not in ('synthetic', 'forex', 'unknown') or not isinstance(symbol, str) or not symbol:
            raise RiskError('A verified market classification and symbol are required')
        with self._db() as c:
            if not self._verify_audit(c)['valid']:
                return {'allowed': False, 'reasons': ['Risk audit integrity failed; trading is blocked'],
                        'fresh': False, 'policy': 'required', 'required': True}
            state = self._load(c, account_id, mode)
            return self._calendar_decision(state, symbol, market_kind, current)

    def _assess(self, c, account_id, mode, *, equity, stake, symbol, positions,
                orders, automatic=False, market_kind='unknown', now=None):
        current = time.time() if now is None else _number(now, 'Current timestamp', minimum=0)
        integrity = self._verify_audit(c)
        if not integrity['valid']:
            return {'allowed': False, 'reasons': ['Risk audit integrity failed; trading is blocked'],
                    'checks': {'audit_integrity': False}, 'checked_at': current}
        state = self._load(c, account_id, mode)
        reasons, checks = [], {}
        try:
            equity = _number(equity, 'Broker equity', minimum=.01)
            stake = _number(stake, 'Maximum at-risk stake', minimum=.01)
            if not isinstance(symbol, str) or not symbol.strip() or len(symbol) > 80:
                raise RiskError('A broker-verified instrument is required')
            if not isinstance(positions, list) or not isinstance(orders, list):
                raise RiskError('Complete broker positions and order history are required')
            if not isinstance(automatic, bool):
                raise RiskError('Automatic order flag must be a boolean')
            if market_kind not in ('synthetic', 'forex', 'unknown'):
                raise RiskError('Unknown market classification')
            if state['last_check'] is not None and current < state['last_check'] - 1:
                raise RiskError('Clock moved backward; trading is blocked until timestamps recover')
        except RiskError as exc:
            decision = {'allowed': False, 'reasons': [str(exc)], 'checks': {}, 'checked_at': current}
            state['last_decision'] = decision
            self._save(c, account_id, mode, state)
            self._append(c, account_id, mode, 'ORDER_BLOCKED', decision, current)
            return decision

        day, week = _windows(current)
        if state['baseline_equity'] is None:
            state.update(baseline_equity=equity, peak_equity=equity,
                         day_start_equity=equity, week_start_equity=equity,
                         day_start=day, week_start=week)
        if state['day_start'] != day:
            state.update(day_start=day, day_start_equity=equity)
        if state['week_start'] != week:
            state.update(week_start=week, week_start_equity=equity)
        state['peak_equity'] = max(state['peak_equity'], equity)
        state['last_equity'], state['last_check'] = equity, current
        conf = state['config']
        if mode == 'real':
            reasons.append('Real-money execution is disabled; this risk engine authorizes research/demo only')
        global_state = self._global(c)
        if global_state['killed']:
            reasons.append('Application emergency stop is active: ' + global_state['kill_reason'])
        if state['killed']:
            reasons.append('Emergency stop is active: ' + state['kill_reason'])

        day_pnl = week_pnl = 0.
        day_trades = 0
        closed = []
        exposures = []
        tracked_nonces = set()
        try:
            for order in orders:
                if not isinstance(order, dict):
                    raise RiskError('Order history contains invalid rows')
                if order.get('account_id', account_id) != account_id or order.get('mode', mode) != mode:
                    continue
                status = order.get('status')
                if status not in ACTIVE | FINAL:
                    raise RiskError('Order history contains an unknown execution state')
                nonce = order.get('nonce')
                if nonce:
                    tracked_nonces.add(nonce)
                opened = _number(order.get('opened_at'), 'Order opened_at', minimum=0)
                if opened > current + 60:
                    raise RiskError('Order history has future timestamps')
                if status != 'REJECTED' and opened >= day:
                    day_trades += 1
                if status == 'CLOSED':
                    pnl = _number(order.get('pnl'), 'Settled order profit')
                    settled = _number(order.get('settled_at') or order.get('updated_at') or opened,
                                      'Settlement timestamp', minimum=0)
                    if settled > current + 60:
                        raise RiskError('Settlement timestamp is in the future')
                    if settled >= day:
                        day_pnl += pnl
                    if settled >= week:
                        week_pnl += pnl
                    closed.append((settled, pnl))
                elif status in ACTIVE:
                    amount = _number(order.get('ask_price', order.get('stake')), 'Open order maximum loss', minimum=.01)
                    exposures.append((order.get('symbol', ''), self._group(order.get('symbol', ''), market_kind), amount))
                    if status in ('UNCERTAIN', 'PENDING', 'APPROVED'):
                        reasons.append('Pending or uncertain broker order requires reconciliation')
            # When broker positions match journal rows, count the more conservative
            # portfolio/journal aggregate rather than double-counting known orders.
            portfolio_exposures = []
            for position in positions:
                if not isinstance(position, dict):
                    raise RiskError('Invalid broker position')
                amount = _number(position.get('max_loss', position.get('stake')), 'Broker position maximum loss', minimum=.01)
                portfolio_exposures.append((position.get('symbol', ''), self._group(position.get('symbol', ''), market_kind), amount))
            if portfolio_exposures:
                # Product-level reconciliation cannot be inferred from matching
                # counts: require every broker contract to match a recorded ID.
                known_ids = {str(o.get('contract_id')) for o in orders if isinstance(o, dict) and o.get('status') == 'OPEN' and o.get('contract_id')}
                if any(str(p.get('contract_id')) not in known_ids for p in positions):
                    reasons.append('Broker portfolio contains an untracked position; reconcile before new entries')
                if sum(x[2] for x in portfolio_exposures) > sum(x[2] for x in exposures):
                    exposures = portfolio_exposures
            for reservation in c.execute("SELECT * FROM risk_reservations WHERE account_id=? AND mode=? AND status IN ('APPROVED','PENDING','OPEN','UNCERTAIN')", (account_id, mode)):
                if reservation['nonce'] not in tracked_nonces:
                    exposures.append((reservation['symbol'], reservation['group_name'], reservation['stake']))
                    if reservation['created_at'] >= day:
                        day_trades += 1
                    reasons.append('A reserved order is absent from the broker journal; reconcile before new entries')
                elif reservation['status'] in ('APPROVED', 'PENDING', 'UNCERTAIN'):
                    reasons.append('Pending or uncertain risk reservation requires reconciliation')
        except RiskError as exc:
            reasons.append(str(exc))

        group = self._group(symbol, market_kind)
        total_risk = sum(amount for _, _, amount in exposures)
        asset_risk = sum(amount for sym, _, amount in exposures if sym == symbol)
        group_risk = sum(amount for _, exposure_group, amount in exposures if exposure_group == group)
        daily_loss = max(0., -day_pnl, state['day_start_equity'] - equity)
        weekly_loss = max(0., -week_pnl, state['week_start_equity'] - equity)
        drawdown_pct = 100 * max(0., state['peak_equity'] - equity) / state['peak_equity']
        checks.update(equity=equity, stake=stake, risk_per_trade_pct=100 * stake / equity,
                      daily_loss=daily_loss, weekly_loss=weekly_loss,
                      daily_loss_limit=state['day_start_equity'] * conf['daily_loss_pct'] / 100,
                      weekly_loss_limit=state['week_start_equity'] * conf['weekly_loss_pct'] / 100,
                      drawdown_pct=drawdown_pct, open_positions=len(exposures),
                      maximum_at_risk=total_risk + stake, day_trades=day_trades,
                      asset_at_risk=asset_risk + stake, group_at_risk=group_risk + stake,
                      calendar_fresh=self._calendar_fresh(state['calendar'], current))
        if stake > equity * conf['risk_per_trade_pct'] / 100 + 1e-9:
            reasons.append('Stake exceeds per-trade equity risk limit')
        if stake > conf['max_order_size'] + 1e-9:
            reasons.append('Stake exceeds maximum permissible order size')
        if len(exposures) >= conf['max_positions']:
            reasons.append('Maximum simultaneous position limit reached')
        if daily_loss + total_risk + stake > checks['daily_loss_limit'] + 1e-9:
            reasons.append('Daily loss budget would be exceeded (including maximum open risk)')
        if weekly_loss + total_risk + stake > checks['weekly_loss_limit'] + 1e-9:
            reasons.append('Weekly loss budget would be exceeded (including maximum open risk)')
        if drawdown_pct >= conf['max_drawdown_pct'] - 1e-9:
            reasons.append('Maximum account drawdown reached')
        if day_trades >= conf['max_trades_per_day']:
            reasons.append('Maximum new trades per UTC day reached')
        if asset_risk + stake > equity * conf['max_asset_exposure_pct'] / 100 + 1e-9:
            reasons.append('Maximum instrument exposure would be exceeded')
        if group_risk + stake > equity * conf['max_group_exposure_pct'] / 100 + 1e-9:
            reasons.append('Maximum correlated-group exposure would be exceeded')

        streak = 0
        for settled, pnl in sorted(closed, reverse=True):
            if pnl < 0:
                streak += 1
            else:
                break
        if streak >= conf['consecutive_loss_limit'] and closed:
            latest_loss = max(t for t, _ in closed)
            if current < latest_loss + conf['cooldown_minutes'] * 60:
                reasons.append('Consecutive-loss cooldown is active')
                checks['cooldown_until'] = latest_loss + conf['cooldown_minutes'] * 60
        checks['consecutive_losses'] = streak
        # Calendar outages protect automated entries. Manual quotes still show
        # freshness, but require an explicit user interaction for each order.
        if automatic:
            reasons.extend(self._calendar_decision(state, symbol, market_kind, current)['reasons'])
        decision = {'allowed': not reasons, 'reasons': list(dict.fromkeys(reasons)),
                    'checks': checks, 'checked_at': current,
                    'model': 'fixed_stake_maximum_loss_v1',
                    'limitations': 'Free broker balance is treated conservatively as eligible equity. CFD leverage, margin and stop-loss sizing are unsupported.'}
        state['last_decision'] = decision
        self._save(c, account_id, mode, state)
        self._append(c, account_id, mode, 'ORDER_APPROVED' if decision['allowed'] else 'ORDER_BLOCKED',
                     {'symbol': symbol, 'automatic': automatic, **decision}, current)
        return decision

    def evaluate(self, account_id, mode, **snapshot):
        account_id, mode = _identity(account_id, mode)
        with self._db() as c:
            c.execute('BEGIN IMMEDIATE')
            return self._assess(c, account_id, mode, **snapshot)

    def require(self, account_id, mode, **snapshot):
        decision = self.evaluate(account_id, mode, **snapshot)
        if not decision['allowed']:
            raise RiskError('; '.join(decision['reasons']))
        return decision

    def reserve(self, nonce, account_id, mode, **snapshot):
        account_id, mode = _identity(account_id, mode)
        if not isinstance(nonce, str) or not nonce or len(nonce) > 128:
            raise RiskError('A unique order nonce is required')
        with self._db() as c:
            c.execute('BEGIN IMMEDIATE')
            if not self._verify_audit(c)['valid']:
                return {'allowed': False, 'reasons': ['Risk audit integrity failed; trading is blocked'],
                        'checks': {'audit_integrity': False}, 'checked_at': time.time()}
            if c.execute('SELECT 1 FROM risk_reservations WHERE nonce=?', (nonce,)).fetchone():
                decision = {'allowed': False, 'reasons': ['Order nonce has already been consumed'], 'checks': {}, 'checked_at': time.time()}
                self._append(c, account_id, mode, 'DUPLICATE_BLOCKED', {'nonce': nonce}, decision['checked_at'])
                return decision
            decision = self._assess(c, account_id, mode, **snapshot)
            if decision['allowed']:
                now = decision['checked_at']
                c.execute('''INSERT INTO risk_reservations VALUES(?,?,?,?,?,?,?,?,?)''',
                          (nonce, account_id, mode, snapshot['symbol'], self._group(snapshot['symbol'], snapshot.get('market_kind', 'unknown')),
                           float(snapshot['stake']), 'APPROVED', now, now))
                self._append(c, account_id, mode, 'ORDER_RESERVED', {'nonce': nonce, 'stake': snapshot['stake'], 'symbol': snapshot['symbol']}, now)
            return decision

    def resolve(self, nonce, status):
        if status not in ('PENDING', 'OPEN', 'UNCERTAIN', 'CLOSED', 'REJECTED'):
            raise RiskError('Invalid risk reservation status')
        with self._db() as c:
            c.execute('BEGIN IMMEDIATE')
            if not self._verify_audit(c)['valid']:
                raise RiskError('Risk audit integrity failed; reservation changes are blocked')
            row = c.execute('SELECT * FROM risk_reservations WHERE nonce=?', (nonce,)).fetchone()
            if row is None:
                # Existing journals imported before risk-engine migration need no
                # invented reservation; snapshot exposure still counts the order.
                return False
            if row['status'] in FINAL:
                if row['status'] != status:
                    raise RiskError('A finalized order cannot be reopened')
                return True
            if row['status'] in ('OPEN', 'UNCERTAIN') and status == 'REJECTED':
                raise RiskError('Accepted or uncertain execution requires broker reconciliation, not rejection')
            now = time.time()
            c.execute('UPDATE risk_reservations SET status=?,updated_at=? WHERE nonce=?', (status, now, nonce))
            self._append(c, row['account_id'], row['mode'], 'ORDER_' + status, {'nonce': nonce}, now)
            return True

    def audit(self, account_id=None, mode=None, limit=200):
        if account_id is not None:
            _identity(account_id, mode)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100000:
            raise RiskError('Audit limit must be within 1–100000')
        with self._db() as c:
            if account_id is None:
                rows = c.execute('SELECT * FROM risk_audit ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
            else:
                rows = c.execute('SELECT * FROM risk_audit WHERE account_id=? AND mode=? ORDER BY id DESC LIMIT ?', (account_id, mode, limit)).fetchall()
            return [{**dict(row), 'payload': json.loads(row['payload'])} for row in rows]

    @staticmethod
    def _verify_audit(c):
        previous, count = '0' * 64, 0
        state_hashes = {}
        global_hash = None
        reservation_hash = None
        try:
            for row in c.execute('SELECT * FROM risk_audit ORDER BY id'):
                expected = hashlib.sha256(_encode([row['account_id'], row['mode'], row['event'], row['event_at'], row['payload'], previous]).encode()).hexdigest()
                if row['previous_hash'] != previous or row['hash'] != expected:
                    return {'valid': False, 'count': count, 'last_hash': previous, 'invalid_id': row['id']}
                payload = json.loads(row['payload'])
                state_hashes[(row['account_id'], row['mode'])] = payload.get('_state_hash')
                global_hash = payload.get('_global_hash')
                reservation_hash = payload.get('_reservation_hash')
                previous = row['hash']
                count += 1
            observed_accounts = set()
            for row in c.execute('SELECT account_id,mode,state FROM risk_state'):
                observed_accounts.add((row['account_id'], row['mode']))
                if state_hashes.get((row['account_id'], row['mode'])) != hashlib.sha256(row['state'].encode()).hexdigest():
                    return {'valid': False, 'count': count, 'last_hash': previous, 'invalid_state': row['account_id']}
            if observed_accounts != {key for key, value in state_hashes.items() if value is not None}:
                return {'valid': False, 'count': count, 'last_hash': previous, 'invalid_state': 'missing_account_state'}
            row = c.execute('SELECT state FROM risk_global WHERE id=1').fetchone()
            actual = hashlib.sha256(row['state'].encode()).hexdigest() if row else None
            if actual != global_hash:
                return {'valid': False, 'count': count, 'last_hash': previous, 'invalid_state': '__application__'}
            if count:
                if reservation_hash != RiskEngine._reservation_hash(c):
                    return {'valid': False, 'count': count, 'last_hash': previous, 'invalid_state': 'risk_reservations'}
            elif c.execute('SELECT 1 FROM risk_reservations LIMIT 1').fetchone():
                return {'valid': False, 'count': count, 'last_hash': previous, 'invalid_state': 'unrecorded_risk_reservations'}
        except (TypeError, ValueError, KeyError):
            return {'valid': False, 'count': count, 'last_hash': previous}
        return {'valid': True, 'count': count, 'last_hash': previous}

    def verify_audit(self):
        with self._db() as c:
            return self._verify_audit(c)

    def status(self, account_id, mode, *, now=None):
        account_id, mode = _identity(account_id, mode)
        current = time.time() if now is None else _number(now, 'Current timestamp', minimum=0)
        with self._db() as c:
            state = self._load(c, account_id, mode)
            calendar = state.pop('calendar')
            state['calendar'] = {'source': calendar['source'] if calendar else None,
                                 'updated_at': calendar['updated_at'] if calendar else None,
                                 'valid_until': calendar['valid_until'] if calendar else None,
                                 'event_count': len(calendar['events']) if calendar else 0,
                                 'fresh': self._calendar_fresh(calendar, current)}
            counts = {row['status']: row['n'] for row in c.execute('SELECT status,COUNT(*) n FROM risk_reservations WHERE account_id=? AND mode=? GROUP BY status', (account_id, mode))}
            state['reservations'] = {'pending': counts.get('APPROVED', 0) + counts.get('PENDING', 0),
                                     'open': counts.get('OPEN', 0), 'uncertain': counts.get('UNCERTAIN', 0)}
        state['global'] = self.global_status()
        state['audit'] = self.verify_audit()
        state['account_id'], state['mode'] = account_id, mode
        state['execution_supported'] = mode != 'real'
        return state
