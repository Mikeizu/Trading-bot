"""Official Deriv Options API connector for a single-account private localhost app.

PAT credentials and the OTP URL live in RAM only, never in SQLite, logs, or responses.
No WebSocket reconnect on a buy timeout: unknown outcomes require reconciliation.
"""
from __future__ import annotations
import json
import math
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

API_ROOT = 'https://api.derivws.com'
PUBLIC_WS = 'wss://api.derivws.com/trading/v1/options/ws/public'
ACCOUNT_ID = re.compile(r'^[A-Za-z0-9_-]{4,64}$')
SYMBOL = re.compile(r'^[A-Za-z0-9_]{2,30}$')


class _NoCredentialRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # PAT headers must never be forwarded to a redirect destination.
        raise HTTPError(req.full_url, code, 'Broker redirects are not permitted', headers, fp)


def urlopen(request, timeout):
    """Default TLS verification/proxy handling, with credential redirects blocked."""
    return build_opener(_NoCredentialRedirect()).open(request, timeout=timeout)


class BridgeError(Exception):
    pass


class UnknownExecution(BridgeError):
    """The purchase response was not received; never blind-retry this purchase."""


class BrokerRejection(BridgeError):
    """An identified broker response explicitly rejected this request."""


def _finite(value, name, *, minimum=None):
    """Validate broker money without turning missing/NaN values into zero."""
    if isinstance(value, bool):
        raise BridgeError(f'Broker {name} is invalid; trading is blocked')
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError):
        raise BridgeError(f'Broker {name} is missing or invalid; trading is blocked') from None
    if not math.isfinite(result) or (minimum is not None and result < minimum):
        raise BridgeError(f'Broker {name} is invalid; trading is blocked')
    return result


def _positive(value, minimum, maximum, name):
    if isinstance(value, bool):
        raise BridgeError(f'{name} must be numeric')
    try:
        val = float(value)
    except (TypeError, ValueError, OverflowError):
        raise BridgeError(f'{name} must be numeric') from None
    if not math.isfinite(val) or not minimum <= val <= maximum:
        raise BridgeError(f'{name} must be between {minimum} and {maximum}')
    return round(val, 2)


def _credentials(app_id, pat):
    """Reject malformed headers without reflecting secret input in errors."""
    if not isinstance(app_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{3,80}', app_id):
        raise BridgeError('Invalid App ID')
    if (not isinstance(pat, str) or not 1 <= len(pat) <= 8192
            or any(ord(c) < 33 or ord(c) > 126 for c in pat)):
        raise BridgeError('A nonempty valid Personal Access Token is required')


def check_otp_url(url: str, expected_mode: str) -> str:
    """Reject untrusted URLs and avoid passing a token to a third-party host."""
    if not isinstance(url, str) or expected_mode not in ('demo','real'):
        raise BridgeError('Invalid official broker connection URL or account mode')
    try:p = urlparse(url)
    except ValueError:raise BridgeError('Invalid official broker connection URL') from None
    if p.scheme != 'wss' or p.netloc != 'api.derivws.com' or p.path != f'/trading/v1/options/ws/{expected_mode}':
        raise BridgeError('Account mode / official WebSocket URL mismatch — connection cancelled')
    if p.fragment or not re.fullmatch(r'otp=[^&#\s]+', p.query):
        raise BridgeError('Missing OTP in Deriv WebSocket URL')
    return url


def normalize_accounts(payload):
    if not isinstance(payload, dict):
        raise BridgeError('Unrecognized accounts response from Deriv')
    data = payload.get('data')
    if isinstance(data, list):
        raw = data
    elif isinstance(data, dict):
        if 'accounts' in data:
            raw=data['accounts']
        elif 'items' in data:
            raw=data['items']
        else:raw=[data]
    else:
        raise BridgeError('Unrecognized accounts response from Deriv')
    if not isinstance(raw,list):
        raise BridgeError('Unrecognized accounts response from Deriv')
    out = []
    seen = {}
    for acc in raw:
        if not isinstance(acc, dict):
            continue
        account_id = acc.get('account_id') or acc.get('id') or ''
        typ = str(acc.get('account_type') or acc.get('type') or '').lower()
        if isinstance(account_id,str) and ACCOUNT_ID.fullmatch(account_id) and typ in ('demo','real'):
            account={'account_id':account_id,'account_type':typ,'currency':acc.get('currency'), 'balance':acc.get('balance')}
            if account_id in seen:
                if seen[account_id] != account:
                    raise BridgeError('Broker account catalogue contains conflicting account identities')
                continue
            seen[account_id]=account
            out.append(account)
    return out


def normalize_active_symbols(payload):
    """Convert current Deriv Options active_symbols response into app market rows.

    New API: underlying_symbol, underlying_symbol_name.
    Legacy API: symbol, display_name (retained only for compatibility).
    Never invent a tradable symbol or silently accept an unknown response schema.
    """
    if not isinstance(payload, dict) or not isinstance(payload.get('active_symbols'), list):
        raise BridgeError('Deriv markets response has an unexpected format. No market orders are allowed.')
    result = []
    seen = set()
    markets = payload['active_symbols']
    for item in markets:
        if not isinstance(item, dict):
            continue
        if item.get('exchange_is_open') in (0, False, '0') or item.get('is_trading_suspended') in (1, True, '1'):
            continue
        code = item.get('underlying_symbol') or item.get('symbol')
        if not isinstance(code, str) or not SYMBOL.fullmatch(code) or code in seen:
            continue
        seen.add(code)
        name = item.get('underlying_symbol_name') or item.get('display_name') or code
        if not isinstance(name, str):
            name = code
        # Display labels are untrusted source data; avoid excessive UI strings.
        result.append({'symbol': code, 'name': name[:120]})
        if len(result) >= 250:
            break
    recognized = any(isinstance(item, dict) and isinstance(item.get('underlying_symbol') or item.get('symbol'), str)
                     and SYMBOL.fullmatch(item.get('underlying_symbol') or item.get('symbol')) for item in markets)
    if markets and not result and not recognized:
        raise BridgeError('Deriv returned markets but their symbol field format is not recognized. Update MIKEIZU before trading.')
    return result


# Contract availability is account-, symbol-, and contract-type-dependent.
# This parser reads only broker-advertised duration ranges; it does not make
# speculative proposal requests or infer permissions from active_symbols.
DURATION_SECONDS = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}

def _duration_seconds(value):
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r'([1-9][0-9]{0,5})([smhd])', value.strip().lower())
    if not match:
        return None
    return int(match.group(1)) * DURATION_SECONDS[match.group(2)]


def normalize_contract_durations(payload):
    """Map Deriv contracts_for CALL/PUT offers to supported 1–15-minute expiries.

    No inferred duration if bounds are absent, malformed, or tick-based.
    Only barrier-free Rise/Fall offers match this app's proposal payload.
    The final proposal is still authoritative; metadata can change.
    """
    if not isinstance(payload, dict):
        raise BridgeError('Unexpected Deriv contracts_for response: not a JSON object')
    data = payload.get('contracts_for')
    if not isinstance(data, dict) or not isinstance(data.get('available'), list):
        raise BridgeError('Deriv contract availability response is incomplete; no order submitted')
    choices = {'UP': set(), 'DOWN': set()}
    types_found = set()
    for item in data['available']:
        if not isinstance(item, dict):
            continue
        typ = item.get('contract_type')
        if isinstance(typ, str):
            types_found.add(typ)
        if typ not in ('CALL','PUT'):
            continue
        # A barrier-dependent contract cannot use MIKEIZU's barrier-free payload.
        if str(item.get('barriers', 0)) not in ('0','0.0'):
            continue
        minimum = _duration_seconds(item.get('min_contract_duration'))
        maximum = _duration_seconds(item.get('max_contract_duration'))
        if minimum is None or maximum is None or minimum > maximum:
            continue
        side = 'UP' if typ == 'CALL' else 'DOWN'
        choices[side].update(n for n in range(1, 16) if minimum <= 60*n <= maximum)
    return {
        'UP': sorted(choices['UP']),
        'DOWN': sorted(choices['DOWN']),
        'contract_types': sorted(types_found),
        'note': ('Durations are based on the broker contract catalogue; a fresh price proposal '
                 'may still be declined because of trading hours, pricing, or other restrictions.'),
    }


class DerivTransport:
    def __init__(self, http=None, ws_factory=None):
        self.http = http or self._http
        self.ws_factory = ws_factory or self._websocket
        self.ws = None
        self.req_id = 0
        self.lock = threading.RLock()
        self.market_metadata = {}
        self.last_response_at = None

    @staticmethod
    def _http(method, path, app_id, token):
        _credentials(app_id,token)
        req = Request(API_ROOT + path, method=method, headers={
            'Authorization': 'Bearer ' + token,
            'Deriv-App-ID': app_id,
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        })
        try:
            with urlopen(req, timeout=14) as resp:
                return json.load(resp)
        except HTTPError as exc:
            # Never log or repeat API credentials. Deriv sometimes returns only a
            # non-JSON/generic 401 body, so give useful account-specific guidance.
            try:
                data = json.load(exc)
                errors = data.get('errors', []) if isinstance(data, dict) else []
                detail = next((e.get('message', '') for e in errors
                               if isinstance(e, dict) and isinstance(e.get('message'), str)), '')
            except (ValueError, TypeError, OSError):
                detail = ''
            # No raw response bytes or request URLs: they can contain sensitive data.
            if exc.code == 401:
                message = ('Deriv HTTP 401 — authentication rejected. Check your new '
                           'PAT-type App ID from developers.deriv.com and a matching, '
                           'unrevoked Personal Access Token (PAT) with trade permission. '
                           'Legacy App IDs and OAuth tokens will not work with PAT login.')
                # Only include specific non-sensitive standardized server reasons.
                if 'Deriv-App-ID header is required' in detail:
                    message += ' Deriv reports the App ID header is missing; verify the app ID.'
                raise BridgeError(message) from None
            if exc.code == 403:
                raise BridgeError('Deriv HTTP 403 — access denied. The PAT may lack trade permission or the Options account may not be authorized for API trading.') from None
            if exc.code == 429:
                raise BridgeError('Deriv HTTP 429 — rate limit reached. Stop repeated attempts and retry later.') from None
            raise BridgeError(f'Deriv API HTTP {exc.code} — request failed. Check your account status and API permissions.') from None
        except (URLError, TimeoutError, OSError):
            raise BridgeError('Cannot reach the Deriv REST API. Check internet access.') from None
        except (ValueError,TypeError,UnicodeError):
            raise BridgeError('Deriv REST response or request format is invalid; no broker operation completed') from None

    @staticmethod
    def _websocket(url):
        try:
            import websocket
        except ImportError:
            raise BridgeError('Install dependency: python -m pip install websocket-client') from None
        return websocket.create_connection(url, timeout=12, enable_multithread=True)

    def accounts(self, app_id, pat):
        _credentials(app_id,pat)
        return normalize_accounts(self.http('GET', '/trading/v1/options/accounts', app_id, pat))

    def connect(self, app_id, pat, account_id, mode):
        if mode not in ('demo','real'):
            raise BridgeError('Only demo/real accounts are supported')
        if not isinstance(account_id,str) or not ACCOUNT_ID.fullmatch(account_id):
            raise BridgeError('Invalid account ID')
        _credentials(app_id,pat)
        accounts = self.accounts(app_id, pat)
        if not any(a['account_id']==account_id and a['account_type']==mode for a in accounts):
            raise BridgeError('The selected account is not listed as a ' + mode + ' account')
        payload = self.http('POST', '/trading/v1/options/accounts/'+quote(account_id)+'/otp', app_id, pat)
        data=payload.get('data') if isinstance(payload,dict) else None
        url=data.get('url') if isinstance(data,dict) else None
        if not isinstance(url, str):
            raise BridgeError('Deriv did not return a WebSocket URL')
        check_otp_url(url, mode)
        with self.lock:
            self.close()
            try:
                self.ws = self.ws_factory(url)
            except Exception:
                raise BridgeError('Cannot connect to Deriv WebSocket. Check your account and network.') from None
        return next(a for a in accounts if a['account_id']==account_id and a['account_type']==mode)

    def close(self):
        with self.lock:
            sock, self.ws = self.ws, None
            if sock:
                try: sock.close()
                except Exception: pass

    def rpc(self, request, *, purchasing=False):
        with self.lock:
            if not self.ws:
                raise BridgeError('Broker not connected')
            self.req_id += 1
            req_id = self.req_id
            data = {**request, 'req_id': req_id}
            try:
                deadline = time.monotonic() + 15
                self.ws.send(json.dumps(data, separators=(',',':')))
                # Responses to other requests/subscriptions are ignored. The v2 connector
                # uses one-off RPC calls, so there should be no streaming interleaving.
                for _ in range(12):
                    remaining=deadline-time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError('Broker response deadline exceeded')
                    if callable(getattr(self.ws,'settimeout',None)):
                        self.ws.settimeout(min(12,remaining))
                    msg = json.loads(self.ws.recv())
                    if not isinstance(msg, dict):
                        raise ValueError('Malformed broker reply')
                    reply_id=msg.get('req_id')
                    if isinstance(reply_id,bool) or not isinstance(reply_id,int) or reply_id != req_id:
                        continue
                    if 'error' in msg and msg['error'] is not None:
                        err = msg['error']
                        # Do not reflect raw broker text, echo_req, OTPs, or URLs.
                        code = err.get('code', '') if isinstance(err, dict) else ''
                        if (not isinstance(err,dict) or not isinstance(code,str)
                                or not re.fullmatch(r'[A-Za-z0-9_]{1,80}',code)
                                or (purchasing and msg.get('buy'))):
                            raise ValueError('Ambiguous broker error response')
                        raise BrokerRejection(f'Deriv {code}: Request rejected; inspect account permissions and broker contract availability.')
                    self.last_response_at = time.time()
                    return msg
                raise TimeoutError('No matching Deriv reply')
            except BridgeError:
                raise
            except Exception:
                self.close()
                if purchasing:
                    raise UnknownExecution('BUY result unknown. Trading is blocked until contract reconciliation.') from None
                raise BridgeError('Deriv connection was interrupted; reconnect to continue.') from None

    def balance(self):
        result = self.rpc({'balance':1}).get('balance')
        if not isinstance(result, dict):
            raise BridgeError('Broker balance response is incomplete; trading is blocked')
        return result

    def portfolio(self):
        result = self.rpc({'portfolio':1}).get('portfolio')
        if not isinstance(result, dict) or not isinstance(result.get('contracts'), list):
            raise BridgeError('Broker portfolio response is incomplete; trading is blocked')
        return result

    def symbols(self):
        # Current Deriv API renamed symbol -> underlying_symbol and
        # display_name -> underlying_symbol_name. See the official API migration guide.
        payload = self.rpc({'active_symbols':'brief'})
        symbols = normalize_active_symbols(payload)
        permitted={item['symbol'] for item in symbols}
        self.market_metadata={}
        for item in payload['active_symbols']:
            if not isinstance(item,dict):continue
            code=item.get('underlying_symbol') or item.get('symbol')
            if not isinstance(code,str) or code not in permitted:continue
            kind=item.get('market')
            if code in self.market_metadata and self.market_metadata[code]['market']!=kind:
                self.market_metadata[code]={'market':None}
            elif code not in self.market_metadata:
                self.market_metadata[code]={'market':kind}
        return symbols

    def contracts_for(self, symbol):
        if not isinstance(symbol, str) or not SYMBOL.fullmatch(symbol):
            raise BridgeError('Invalid market symbol')
        return normalize_contract_durations(self.rpc({'contracts_for':symbol}))

    def candles(self, symbol, count=140, granularity=60):
        if not isinstance(symbol, str) or not SYMBOL.fullmatch(symbol):
            raise BridgeError('Invalid market symbol')
        if isinstance(granularity,bool) or not isinstance(granularity,int) or granularity not in (60,120,180,300,600,900,1800,3600,7200,14400,28800,86400):
            raise BridgeError('Invalid Deriv candle granularity')
        if isinstance(count,bool) or not isinstance(count,int) or not 1 <= count <= 2500:
            raise BridgeError('Invalid candle history count')
        result = self.rpc({'ticks_history':symbol,'end':'latest','style':'candles','granularity':granularity,'count':count})
        source = result.get('candles')
        if not isinstance(source, list):
            raise BridgeError('Broker candle history is missing; no signal may be generated')
        rows=[]
        for c in source:
            try:
                if not isinstance(c,dict) or any(isinstance(c.get(k),bool) for k in ('open','high','low','close','epoch')):
                    raise ValueError('Boolean or invalid candle')
                row={k:float(c[k]) for k in ('open','high','low','close')}
                epoch=float(c['epoch'])
                if not math.isfinite(epoch) or not epoch.is_integer():raise ValueError('Invalid epoch')
                row['time']=int(epoch)
                if (not all(math.isfinite(row[k]) and row[k]>0 for k in ('open','high','low','close'))
                        or row['high'] < max(row['open'], row['close'])
                        or row['low'] > min(row['open'], row['close'])
                        or row['time'] <= 0 or (rows and row['time'] <= rows[-1]['time'])):
                    raise ValueError('Invalid OHLC history')
                rows.append(row)
            except (ValueError, TypeError, KeyError, OverflowError):
                raise BridgeError('Broker candles are malformed or out of order; trading is blocked') from None
        return rows

    def proposal(self, symbol, side, stake, minutes, currency):
        return self.rpc({'proposal':1,'amount':stake,'basis':'stake',
                         'contract_type':'CALL' if side=='UP' else 'PUT',
                         'currency':currency,'duration':minutes,'duration_unit':'m',
                         'underlying_symbol':symbol}).get('proposal') or {}

    def buy(self, proposal_id, ask_price):
        return self.rpc({'buy':proposal_id,'price':ask_price}, purchasing=True).get('buy') or {}

    def contract(self, contract_id):
        return self.rpc({'proposal_open_contract':1, 'contract_id':contract_id}).get('proposal_open_contract') or {}


class BrokerController:
    """Single-user demo execution session; real accounts are strictly read-only."""
    def __init__(self, store, transport=None, allow_live=False, risk_engine=None):
        from risk_engine import RiskEngine
        self.db = store
        self.transport = transport or DerivTransport()
        self.risk = risk_engine or RiskEngine(Path(store.path).with_name('risk_control.db'))
        self.lock = threading.RLock()
        # Legacy opt-in is deliberately inert until production gates are implemented.
        self.allow_live = False
        self.mode = 'disconnected'
        self.connection_state = 'disconnected'
        self.account_id = ''
        self.currency = ''
        self.account_balance = None
        self.last_verified_at = None
        self.allowed_symbols = []
        self.quote = None
        self.live_armed_until = 0
        self.automation = False
        self.auto_symbol = ''
        self.auto_strategy = 'RSI'
        self.auto_stake = 1.0
        self.last_auto_candle = None
        self.last_message = 'Connect to your Deriv demo account to begin.'
        self.last_error = ''

    def status(self):
        with self.lock:
            connected = self.mode != 'disconnected'
            if isinstance(self.transport, DerivTransport):
                connected = connected and self.transport.ws is not None
            return {'mode':self.mode,'connected':connected,
                    'account_id':self.account_id,'currency':self.currency,
                    'balance':self.account_balance,'allow_live':False,
                    'armed':False,'live_execution_supported':False,
                    'connection_state':self.connection_state,
                    'last_broker_response_at':getattr(self.transport, 'last_response_at', None),
                    'last_verified_at':self.last_verified_at,
                    'connectivity_note':'Connected identifies the authenticated socket session, not a continuous heartbeat. Orders require fresh verified broker snapshots.',
                    'symbols':self.allowed_symbols,'automation':self.automation,
                    'message':self.last_message,'error':self.last_error,
                    'orders':self.db.orders(self.account_id, 50) if self.account_id else []}

    def list_accounts(self, app_id, pat):
        with self.lock:
            return self.transport.accounts(str(app_id).strip(),str(pat).strip())

    def connect(self, app_id, pat, account_id, mode):
        mode=str(mode)
        if mode not in ('demo', 'real'):
            raise BridgeError('Only verified demo or read-only real accounts are supported')
        with self.lock:
            self.disconnect()
            self.connection_state = 'connecting'
            try:
                expected_id = str(account_id).strip()
                account = self.transport.connect(str(app_id).strip(),str(pat).strip(),expected_id,mode)
                if (not isinstance(account, dict) or account.get('account_id') != expected_id
                        or account.get('account_type') != mode):
                    raise BridgeError('Broker account identity or mode mismatch; connection cancelled')
                # Bind identity only after both account catalogue and OTP validation.
                self.account_id = expected_id; self.mode = mode
                currency = account.get('currency')
                self.currency = currency if isinstance(currency, str) else ''
                self._read_balance()
                self.allowed_symbols=self.transport.symbols()
                positions=self._positions()  # Establish a complete broker snapshot on each connect.
                self.reconcile()
                self.connection_state = ('reconciliation_required' if positions or self.db.unresolved(self.account_id) else 'ready')
            except Exception:
                self.disconnect()
                raise
            # A valid authenticated account is still connected even if the broker
            # legitimately has no active symbols at this moment. Trades remain
            # blocked because every entry checks allowed_symbols membership.
            if self.allowed_symbols:
                self.last_message=f'Connected to Deriv {mode.upper()} account. {len(self.allowed_symbols)} markets available.'
            else:
                self.last_message=(f'Connected to Deriv {mode.upper()} account, but the broker reported '
                                   'zero active markets. Trading is disabled; refresh markets later.')
            if mode == 'real':
                self.last_message += ' READ-ONLY: live order execution is unavailable.'
            if self.connection_state == 'reconciliation_required':
                self.last_message += ' Unresolved journal orders block new purchases.'
            self.last_error=''
            return self.status()

    def refresh_markets(self):
        with self.lock:
            if self.mode == 'disconnected':
                raise BridgeError('Connect a Deriv account first')
            self.quote=None
            # A failed catalogue refresh must not leave stale permissions usable.
            self.allowed_symbols=[]
            try:latest=self.transport.symbols()
            except Exception:
                self.automation=False
                self.last_error='Market catalogue refresh failed; trading is blocked until a successful refresh.'
                raise
            self.allowed_symbols = latest
            if not latest or (self.auto_symbol and self.auto_symbol not in {s['symbol'] for s in latest}):
                self.automation = False  # fail closed if symbols disappeared
            self.last_message = (f'Market list updated: {len(latest)} active markets.'
                                 if latest else 'No active markets reported by Deriv; all trading remains disabled.')
            return self.status()

    def disconnect(self):
        with self.lock:
            self.transport.close()
            self.mode='disconnected';self.account_id='';self.quote=None
            self.connection_state='disconnected';self.currency=''
            self.live_armed_until=0;self.account_balance=None
            self.last_verified_at=None
            self.allowed_symbols=[];self.automation=False
            self.last_message='Disconnected. No broker orders can be placed.'

    def arm(self, phrase):
        raise BridgeError('Controlled live execution is unavailable; real accounts are read-only. Demo execution requires explicit demo controls.')

    def _read_balance(self):
        bal = self.transport.balance()
        if not isinstance(bal, dict):
            raise BridgeError('Broker balance response is invalid; trading is blocked')
        amount = _finite(bal.get('balance'), 'balance', minimum=0)
        currency = bal.get('currency')
        if not isinstance(currency, str) or not re.fullmatch(r'[A-Z0-9]{2,12}', currency):
            raise BridgeError('Broker currency is missing or invalid; trading is blocked')
        if self.currency and currency != self.currency:
            raise BridgeError('Broker account currency changed; reconnect before continuing')
        reported_id = bal.get('account_id') or bal.get('loginid')
        if reported_id is not None and str(reported_id) != self.account_id:
            raise BridgeError('Broker balance belongs to a different account; trading is blocked')
        self.account_balance = amount
        self.currency = currency
        self.risk.observe(self.account_id, self.mode, equity=amount)
        self.last_verified_at = time.time()
        return amount

    def _positions(self):
        port = self.transport.portfolio()
        if not isinstance(port, dict) or not isinstance(port.get('contracts'), list):
            raise BridgeError('Broker position information is missing; trading is blocked')
        if not all(isinstance(item, dict) for item in port['contracts']):
            raise BridgeError('Broker position information is invalid; trading is blocked')
        return port['contracts']

    def _market_kind(self, symbol):
        metadata = getattr(self.transport, 'market_metadata', {}).get(symbol, {})
        market = metadata.get('market')
        return 'synthetic' if market == 'synthetic_index' else ('forex' if market == 'forex' else 'unknown')

    def _precheck(self, stake, include_live=True, *, symbol='', automatic=False, nonce=None):
        if self.mode not in ('demo','real'):
            raise BridgeError('Connect a broker account first')
        if self.mode=='real':
            raise BridgeError('Real accounts are read-only; live order execution is unavailable')
        if not self.db.audit(self.account_id)['integrity']:
            raise BridgeError('Order journal integrity check failed; new trading is blocked')
        self.reconcile()  # fail closed on connectivity or uncertain outcomes
        unresolved=self.db.unresolved(self.account_id)
        if unresolved:
            raise BridgeError('An open or uncertain order exists. Reconcile it before new purchases.')
        self._read_balance()
        if stake > self.account_balance*.01 +1e-9:
            raise BridgeError('Stake exceeds 1% of broker-reported account balance')
        pnl,trades=self.db.today(self.account_id)
        if stake>50: raise BridgeError('Demo stake ceiling is 50 account-currency units')
        if pnl<=-100 or trades>=12: raise BridgeError('Demo daily loss/trade limit reached')
        positions = self._positions()
        if positions: raise BridgeError('Broker account has open positions. Close/settle before opening another.')
        from risk_engine import RiskError
        try:
            snapshot = dict(equity=self.account_balance, stake=stake, symbol=symbol,
                            positions=positions, orders=self.db.history(self.account_id),
                            automatic=automatic, market_kind=self._market_kind(symbol))
            if nonce is None:
                decision = self.risk.require(self.account_id, self.mode, **snapshot)
            else:
                decision = self.risk.reserve(nonce, self.account_id, self.mode, **snapshot)
                if not decision['allowed']:
                    raise RiskError('; '.join(decision['reasons']))
        except RiskError as exc:
            raise BridgeError('Risk control blocked order: ' + str(exc)) from None
        return decision

    def get_candles(self, symbol):
        with self.lock:
            if not isinstance(symbol,str) or symbol not in {s['symbol'] for s in self.allowed_symbols}:
                raise BridgeError('Choose an available Deriv market')
            return self.transport.candles(symbol)

    def available_durations(self, symbol):
        with self.lock:
            if self.mode not in ('demo', 'real'):
                raise BridgeError('Connect your Deriv account before checking available expiries')
            if not isinstance(symbol,str) or symbol not in {s['symbol'] for s in self.allowed_symbols}:
                raise BridgeError('Choose a market offered to your account')
            result = self.transport.contracts_for(symbol)
            # Never trust the client to provide fabricated choices.
            return {'symbol':symbol, 'mode':self.mode, **result}

    @staticmethod
    def _duration_rejection(symbol, side, minutes, offers):
        offered = offers.get(side, [])
        choices = ', '.join(str(n) for n in offered) if offered else 'none within 1–15 minutes'
        other = 'DOWN' if side == 'UP' else 'UP'
        return (f'Deriv does not offer {side} Rise/Fall with {minutes} minute(s) on {symbol} '
                f'for this account. Supported {side} expiries: {choices}. '
                f'Supported {other} expiries: {", ".join(map(str,offers.get(other, []))) or "none"}. '
                'Choose one of the offered durations or change the market. No order placed.')

    def new_quote(self, symbol, side, stake, minutes, *, internal=False, context=None):
        with self.lock:
            self.quote = None  # A failed refresh must not leave an older executable quote.
            if not isinstance(internal,bool):raise BridgeError('Automatic order flag must be a boolean')
            if self.mode=='real':
                raise BridgeError('Real accounts are read-only; live order execution is unavailable')
            stake=_positive(stake,.35,50,'Stake')
            if isinstance(minutes, bool):
                raise BridgeError('Expiry minutes must be an integer')
            try:
                numeric_minutes = float(minutes)
                if not math.isfinite(numeric_minutes) or not numeric_minutes.is_integer():
                    raise ValueError('Noninteger duration')
                minutes=int(numeric_minutes)
            except (ValueError, TypeError, OverflowError):
                raise BridgeError('Expiry minutes must be an integer') from None
            if not 1<=minutes<=15:raise BridgeError('Expiry minutes must be 1–15')
            if side not in ('UP','DOWN'):raise BridgeError('Invalid contract direction')
            if not isinstance(symbol,str) or symbol not in {s['symbol'] for s in self.allowed_symbols}:
                raise BridgeError('Choose an active Deriv market')
            offers = self.available_durations(symbol)
            if minutes not in offers[side]:
                raise BridgeError(self._duration_rejection(symbol,side,minutes,offers))
            decision = self._precheck(stake, symbol=symbol, automatic=internal)
            try:
                p=self.transport.proposal(symbol,side,stake,minutes,self.currency)
            except BridgeError as exc:
                if 'not offered for this duration' in str(exc).lower():
                    raise BridgeError(
                        f'Deriv declined {side} {minutes}-minute Rise/Fall on {symbol} despite its '
                        'contract catalogue. Availability can change or have additional restrictions. '
                        'Refresh supported expiries or choose another market. No order placed.'
                    ) from None
                raise
            if not isinstance(p, dict):
                raise BridgeError('Broker proposal is incomplete; no order placed')
            proposal_id=p.get('id')
            ask=_finite(p.get('ask_price'), 'proposal ask price', minimum=.01)
            if ask > 1000:
                raise BridgeError('Broker proposal ask price exceeds supported limit')
            payout = _finite(p.get('payout'), 'proposal payout', minimum=0)
            if not isinstance(proposal_id,str) or not proposal_id:
                raise BridgeError('Deriv did not return a proposal ID')
            if ask>stake*1.02:
                raise BridgeError('Broker quote exceeds stake tolerance; no order was placed')
            if payout <= ask:
                raise BridgeError('Broker payout does not exceed purchase cost; no order placed')
            audit_context = {}
            if context is not None:
                if not isinstance(context, dict):
                    raise BridgeError('Order context must be an object')
                for key in ('strategy', 'strategy_version', 'timeframe', 'signal_at', 'regime', 'rationale'):
                    value = context.get(key)
                    if isinstance(value, (str, int, float)) and not isinstance(value, bool):
                        if isinstance(value, float) and not math.isfinite(value):
                            continue
                        audit_context[key] = value[:500] if isinstance(value, str) else value
            self.quote={'token':uuid.uuid4().hex,'proposal_id':proposal_id,'ask_price':ask,
                        'symbol':symbol,'side':side,'stake':stake,'minutes':minutes,
                        'created':time.monotonic(),'mode':self.mode,'account_id':self.account_id,
                        'payout':payout,'longcode':str(p.get('longcode') or '')[:220],
                        'automatic':bool(internal),'context':audit_context,
                        'risk_decision':decision}
            return {k:self.quote[k] for k in ('token','symbol','side','stake','minutes','ask_price','payout','longcode','mode')}

    def buy_quote(self, token, *, internal=False):
        with self.lock:
            if not isinstance(internal,bool):raise BridgeError('Automatic order flag must be a boolean')
            q=self.quote
            if not q or q['token']!=token or self.mode!=q['mode'] or self.account_id!=q['account_id']:
                raise BridgeError('Missing, expired, or already consumed proposal')
            self.quote=None # consume before sending; never permit duplicate clicking
            if time.monotonic()-q['created']>12:
                raise BridgeError('Quote expired; request a new proposal')
            if self.mode=='real':
                raise BridgeError('Real accounts are read-only; live order execution is unavailable')
            # Revalidate final ask, capabilities and all risk controls immediately
            # before atomically reserving the nonce. Quotes are never permission.
            offers = self.available_durations(q['symbol'])
            if q['minutes'] not in offers[q['side']]:
                raise BridgeError(self._duration_rejection(q['symbol'],q['side'],q['minutes'],offers))
            q['risk_decision'] = self._precheck(max(q['stake'], q['ask_price']), symbol=q['symbol'],
                                              automatic=bool(internal or q.get('automatic')),
                                              nonce=q['token'])
            known_contract_id = None
            try:
                order_id = self.db.reserve(self.account_id,self.mode,q)
            except Exception:
                self.risk.resolve(q['token'], 'REJECTED')
                raise BridgeError('Unable to reserve durable order; no purchase submitted') from None
            purchase_attempted = False
            try:
                if time.monotonic()-q['created'] > 12:
                    raise BridgeError('Quote expired while validating risk; no purchase submitted')
                # A stop may have been persisted while the journal reservation
                # waited on disk. Recheck immediately before the send boundary.
                if (self.risk.global_status()['killed'] or
                        self.risk.status(self.account_id, self.mode)['killed']):
                    raise BridgeError('Emergency stop activated before dispatch; no purchase submitted')
                purchase_attempted = True
                result=self.transport.buy(q['proposal_id'],q['ask_price'])
                cid=result.get('contract_id') if isinstance(result, dict) else None
                if (isinstance(cid, bool) or not isinstance(cid, (str, int))
                        or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', str(cid))):
                    raise UnknownExecution('Broker did not return a valid contract ID. Check Deriv before further trading.')
                known_contract_id = str(cid)
                paid = _finite(result.get('buy_price'), 'purchase price', minimum=0)
                if paid <= 0 or paid > q['ask_price'] + 1e-9:
                    raise UnknownExecution('Broker purchase amount is invalid or exceeds the approved amount. Reconciliation is required.')
                self.db.update(order_id,'OPEN',str(cid),None)
                self.risk.resolve(q['token'], 'OPEN')
                self.connection_state = 'reconciliation_required'
                self.account_balance=None  # refresh after order when requested
                self.last_message=f'{self.mode.upper()} order #{order_id} purchased, contract {cid}'
                return {'order_id':order_id,'contract_id':str(cid),'mode':self.mode,
                        'buy_price':result.get('buy_price'),'message':self.last_message}
            except Exception as exc:
                # Only a correlated broker error proves rejection. Every other
                # failure after the send boundary may have spent money.
                rejected = not purchase_attempted or isinstance(exc, BrokerRejection)
                status = 'REJECTED' if rejected else 'UNCERTAIN'
                try:
                    self.db.update(order_id,status,known_contract_id,None)
                except Exception:
                    # An existing PENDING row remains an interlock after disk errors.
                    pass
                try:
                    self.risk.resolve(q['token'], status)
                except Exception:
                    # The durable APPROVED reservation also blocks further risk.
                    pass
                self.automation=False
                self.connection_state='reconciliation_required'
                if rejected:
                    self.last_error=str(exc)
                    raise
                self.last_error='BUY result unknown. No retry: reconcile the durable order and broker statement.'
                raise UnknownExecution(self.last_error) from None

    def reconcile(self):
        with self.lock:
            if self.mode=='disconnected':return
            # Verify BEFORE updates; a legitimate settlement cannot launder an
            # unaudited change to materialized order rows by replacing snapshots.
            if not self.db.audit(self.account_id)['integrity']:
                raise BridgeError('Order journal integrity check failed; reconciliation is blocked')
            for order in self.db.unresolved(self.account_id):
                if not order['contract_id']:
                    # Even if no position appears, it may have already expired.
                    # Hold the interlock until the user verifies in Deriv statement.
                    continue
                contract=self.transport.contract(order['contract_id'])
                if not isinstance(contract, dict):
                    raise BridgeError('Broker contract response is incomplete; reconciliation is blocked')
                reported_id=contract.get('contract_id')
                if reported_id is not None and str(reported_id)!=str(order['contract_id']):
                    raise BridgeError('Broker contract identity mismatch; reconciliation is blocked')
                status=str(contract.get('status') or '').lower()
                if contract.get('is_sold') in (1,True,'1') or status in ('sold','won','lost'):
                    if status and status not in ('sold','won','lost'):
                        raise BridgeError('Broker settlement state is inconsistent; reconciliation is blocked')
                    pnl = _finite(contract.get('profit'), 'settlement profit')
                    self.db.update(order['id'],'CLOSED',order['contract_id'],pnl)
                    self.risk.resolve(order['nonce'], 'CLOSED')
            self.connection_state = ('reconciliation_required' if self.db.unresolved(self.account_id) else 'ready')
            return self.db.orders(self.account_id,50)

    def broker_snapshot(self):
        with self.lock:
            if self.mode=='disconnected':raise BridgeError('Connect first')
            self.reconcile()
            self._read_balance()
            positions = self._positions()
            return {'balance':self.account_balance,'currency':self.currency,
                    'open_positions':positions, 'orders':self.db.orders(self.account_id,50)}

    def demo_auto_once(self, strategy_signal):
        """A caller supplies a completed-candle UP/DOWN signal. Only demo may auto-purchase."""
        with self.lock:
            if not self.automation or self.mode!='demo' or strategy_signal not in ('UP','DOWN'):
                return None
            q=self.new_quote(self.auto_symbol,strategy_signal,self.auto_stake,1,internal=True)
            return self.buy_quote(q['token'],internal=True)
