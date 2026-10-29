"""MIKEIZU v4 local server: v1 simulator + opt-in official Deriv broker bridge.

Never expose on a public interface. Startup binds only to localhost.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import sqlite3
import threading
import time
import traceback
import webbrowser
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
import server as simulator
from deriv_bridge import BrokerController, BridgeError, UnknownExecution
from engine import indicators,signal_at
from naked_strategies import StrategyError, STRATEGIES,PROFILES
from strategy_extension import StrategySupervisor
from risk_engine import RiskError

ROOT=Path(__file__).resolve().parent
DATA_DIR=Path(os.environ.get('MIKEIZU_DATA_DIR',str(ROOT))).expanduser().resolve()
DATA_DIR.mkdir(parents=True,exist_ok=True)
BROKER_DB=DATA_DIR/'deriv_order_journal.db'


class Journal:
    def __init__(self,path=None):
        self.path=Path(path) if path else BROKER_DB
        self.lock=threading.RLock()
        with self.db() as c:
            c.execute('''CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nonce TEXT NOT NULL UNIQUE,
                account_id TEXT NOT NULL,
                mode TEXT NOT NULL,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                stake REAL NOT NULL,
                ask_price REAL NOT NULL,
                expiry_minutes INTEGER NOT NULL,
                contract_id TEXT,
                status TEXT NOT NULL,
                pnl REAL,
                opened_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )''')
            c.execute('CREATE INDEX IF NOT EXISTS ix_broker_orders ON orders(account_id,status)')
            columns={r[1] for r in c.execute('PRAGMA table_info(orders)')}
            if 'context_json' not in columns:
                c.execute("ALTER TABLE orders ADD COLUMN context_json TEXT NOT NULL DEFAULT '{}'")
            c.execute('''CREATE TABLE IF NOT EXISTS order_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT, event_json TEXT NOT NULL,
                previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL)''')
            c.execute('CREATE TABLE IF NOT EXISTS journal_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
            if not c.execute("SELECT 1 FROM journal_meta WHERE key='snapshot_baseline'").fetchone():
                for row in c.execute('SELECT * FROM orders ORDER BY id').fetchall():
                    self._audit(c,{'event':'LEGACY_BASELINE','order_id':row['id'],
                        'account_id':row['account_id'],'mode':row['mode'],'time':int(time.time()),
                        'note':'Imported legacy state; pre-migration provenance is unverified'})
                c.execute("INSERT INTO journal_meta VALUES('snapshot_baseline','1')")
            c.execute('PRAGMA user_version=3')

    from contextlib import contextmanager
    @contextmanager
    def db(self):
        with self.lock:
            conn=sqlite3.connect(self.path,timeout=10)
            try:
                conn.row_factory=sqlite3.Row
                conn.execute('PRAGMA busy_timeout=10000')
                conn.execute('PRAGMA journal_mode=WAL')
                conn.execute('PRAGMA synchronous=FULL')
                yield conn
                conn.commit()
            except Exception:
                conn.rollback();raise
            finally:conn.close()

    def reserve(self,account_id,mode,q):
        now=int(time.time())
        with self.db() as c:
            # Context is a fixed allowlist of research metadata, never credentials.
            context={k:q.get('context',{}).get(k) for k in
                ('strategy','strategy_version','timeframe','signal_at','regime','rationale','data_hash')
                if k in q.get('context',{})}
            context_json=json.dumps(context,sort_keys=True,allow_nan=False)
            if len(context_json)>8192:raise ValueError('Order context exceeds limit')
            cur=c.execute('INSERT INTO orders (nonce,account_id,mode,symbol,direction,stake,ask_price,expiry_minutes,status,opened_at,updated_at,context_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                (q['token'],account_id,mode,q['symbol'],q['side'],q['stake'],q['ask_price'],q['minutes'],'PENDING',now,now,context_json))
            order_id=cur.lastrowid
            self._audit(c,{'event':'ORDER_RESERVED','order_id':order_id,'account_id':account_id,
                'mode':mode,'symbol':q['symbol'],'stake':q['stake'],'context':context,'time':now})
            return order_id

    def update(self,order_id,status,contract_id=None,pnl=None):
        with self.db() as c:
            row=c.execute('SELECT account_id,mode,status FROM orders WHERE id=?',(order_id,)).fetchone()
            if row is None:raise ValueError('Order not found')
            allowed={'PENDING':{'OPEN','UNCERTAIN','REJECTED'},'OPEN':{'OPEN','CLOSED','UNCERTAIN'},
                'UNCERTAIN':{'UNCERTAIN','OPEN','CLOSED'},'CLOSED':{'CLOSED'},'REJECTED':{'REJECTED'}}
            if status not in allowed.get(row['status'],set()):raise ValueError('Invalid order state transition')
            if status=='CLOSED' and (pnl is None or not simulator.math.isfinite(float(pnl))):
                raise ValueError('Settlement requires finite broker P&L')
            c.execute('UPDATE orders SET status=?,contract_id=?,pnl=?,updated_at=? WHERE id=?',
                      (status,contract_id,pnl,int(time.time()),order_id))
            self._audit(c,{'event':'ORDER_'+status,'order_id':order_id,'account_id':row['account_id'],
                'mode':row['mode'],'previous_status':row['status'],'contract_id':contract_id,
                'pnl':pnl,'time':int(time.time())})

    @staticmethod
    def _audit(c,event):
        if event.get('order_id') is not None:
            snapshot=c.execute('SELECT * FROM orders WHERE id=?',(event['order_id'],)).fetchone()
            event={**event,'order_snapshot':dict(snapshot)}
        previous=c.execute('SELECT event_hash FROM order_audit ORDER BY id DESC LIMIT 1').fetchone()
        previous=previous[0] if previous else '0'*64
        encoded=json.dumps(event,sort_keys=True,separators=(',',':'),allow_nan=False)
        digest=hashlib.sha256((previous+encoded).encode()).hexdigest()
        c.execute('INSERT INTO order_audit(event_json,previous_hash,event_hash) VALUES(?,?,?)',(encoded,previous,digest))

    def audit(self,account_id=None,limit=200):
        with self.db() as c:
            chain=list(c.execute('SELECT * FROM order_audit ORDER BY id'))
            actual={row['id']:dict(row) for row in c.execute('SELECT * FROM orders ORDER BY id')}
        previous='0'*64;valid=True;events=[];snapshots={}
        for row in chain:
            digest=hashlib.sha256((previous+row['event_json']).encode()).hexdigest()
            valid=valid and row['previous_hash']==previous and row['event_hash']==digest
            previous=row['event_hash']
            try:event=json.loads(row['event_json'])
            except (ValueError,TypeError):
                valid=False;continue
            if not isinstance(event,dict):
                valid=False;continue
            if event.get('order_snapshot'):
                snapshots[event.get('order_id')]=event['order_snapshot']
            if account_id is None or event.get('account_id')==account_id:
                events.append({'id':row['id'],**event,'event_hash':row['event_hash']})
        valid=valid and snapshots==actual
        return {'events':events[-limit:][::-1],'integrity':valid,'count':len(events),
            'note':'Local hash chain detects edits; it is not externally anchored and cannot prove an untampered database.'}

    def history(self,account_id):
        with self.db() as c:
            return [dict(r) for r in c.execute('SELECT * FROM orders WHERE account_id=? ORDER BY id',(account_id,))]

    def orders(self,account_id,limit=50):
        if not account_id:return []
        with self.db() as c:
            return [dict(r) for r in c.execute('SELECT * FROM orders WHERE account_id=? ORDER BY id DESC LIMIT ?', (account_id,limit))]

    def unresolved(self,account_id):
        with self.db() as c:
            return [dict(r) for r in c.execute("SELECT * FROM orders WHERE account_id=? AND status IN ('OPEN','PENDING','UNCERTAIN')",(account_id,))]

    def today(self,account_id):
        midnight=int(datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0).timestamp())
        with self.db() as c:
            row=c.execute('SELECT COALESCE(SUM(CASE WHEN status="CLOSED" THEN pnl ELSE 0 END),0) AS pnl,COUNT(*) AS trades FROM orders WHERE account_id=? AND opened_at>=? AND status!="REJECTED"',(account_id,midnight)).fetchone()
            return float(row['pnl']),int(row['trades'])

journal=Journal()
broker=BrokerController(journal)
strategy_supervisor=StrategySupervisor(broker,DATA_DIR/'naked_signals.db')
STARTED_AT=time.time()
WORKERS={}


def entry_guard():
    if broker.risk.global_status()['killed']:
        raise ValueError('Application emergency stop is active. Explicitly resume in Risk Control Center.')


simulator.ENTRY_GUARD=entry_guard


def risk_status():
    with broker.lock:
        connected=broker.status()['connected']
        has_identity=broker.mode in ('demo','real') and bool(broker.account_id)
        result=broker.risk.status(broker.account_id,broker.mode) if has_identity else {'global':broker.risk.global_status()}
        global_state=result.get('global',{})
        return {'account_id':broker.account_id,'mode':broker.mode,'connected':connected,
                'risk':result,'limits':result.get('config',{}),'state':result,
                'halted':bool(result.get('killed') or global_state.get('killed')),
                'halt_reason':global_state.get('kill_reason') or result.get('kill_reason','')}


def emergency_stop(reason='Emergency stop requested by user'):
    # Persist the interlock before waiting for a currently executing broker RPC.
    # Already-submitted purchases may still fill; this never claims to close them.
    broker.risk.kill_all(reason)
    with broker.lock:
        broker.automation=False
        broker.quote=None
        broker.last_message='Emergency stop: new orders halted. Existing contracts remain open until expiry.'
        strategy_supervisor.stop('Application emergency stop active')
        if broker.account_id:
            strategy_supervisor.paper.halt(broker.account_id,'Application emergency stop')
    with simulator.LOCK:
        simulator.BOT_ACTIVE=False
        simulator.BOT_MESSAGE='Application emergency stop active; no new synthetic trades.'
    return risk_status()


def capabilities():
    return {'version':'5.0','deployment':'private localhost; no remote multi-user authentication',
        'modes':{'research':'available; simulation with disclosed assumptions',
                 'monitor':'available with authentic broker candles; requires connection',
                 'paper':'virtual ledger, separate from broker balances',
                 'broker_demo':'implemented; explicit authorization and risk approval required; not verified against a real account here',
                 'live':'disabled in code; no activation mechanism',
                 'mt5':'not implemented'},
        'strategies':list(STRATEGIES),'broker_products':['Deriv barrier-free Rise/Fall, broker-advertised 1–15 minute durations'],
        'news':'user-supplied licensed calendar coverage; automatic entries fail closed when required coverage is missing or stale',
        'limitations':['No guaranteed returns or calibrated AI prediction model',
            'No MT5 forex/CFD execution, margin model, broker emergency close, or automated news provider',
            'Backtests do not reproduce actual contract pricing or all venue execution effects',
            'Local audit hash chains require external anchoring for independent tamper proof',
            'Real broker demo verification and jurisdiction review remain outstanding']}


class API(simulator.API):
    server_version='MIKEIZUTradeLab/5.0'
    def check_host(self):
        # DNS rebinding protection. Only loopback host names and the exact server port.
        host=self.headers.get('Host','')
        port=str(self.server.server_port)
        if host not in (f'127.0.0.1:{port}',f'localhost:{port}'):
            self.error_json('Open this app using its localhost address only',403)
            return False
        return True

    def check_origin(self):
        origin=self.headers.get('Origin')
        port=str(self.server.server_port)
        if origin and origin not in (f'http://127.0.0.1:{port}',f'http://localhost:{port}'):
            self.error_json('Cross-site requests are blocked',403)
            return False
        return True

    def do_strategy_POST(self,path):
        try:
            n=int(self.headers.get('Content-Length','0'))
            if not 0<=n<=1300000:return self.error_json('Payload exceeds 1.3 MB',413)
            if self.headers.get('Content-Type','').split(';')[0].strip()!='application/json':
                return self.error_json('JSON Content-Type required',415)
            obj=json.loads(self.rfile.read(n) or b'{}')
            if not isinstance(obj,dict):raise StrategyError('JSON object expected')
            if path=='/api/strategy/backtest':return self.send_json(strategy_supervisor.research(obj))
            if path=='/api/strategy/scan-all':return self.send_json(strategy_supervisor.scan_all(obj))
            if path=='/api/strategy/start-best':return self.send_json(strategy_supervisor.activate_best(obj))
            if path=='/api/strategy/start':return self.send_json(strategy_supervisor.configure(obj))
            if path=='/api/strategy/stop':return self.send_json(strategy_supervisor.stop())
            return self.error_json('Unknown strategy endpoint',404)
        except (StrategyError,BridgeError,ValueError,TypeError,json.JSONDecodeError) as exc:
            return self.error_json(str(exc),400)
        except Exception:
            return self.error_json('Strategy engine request failed; no order placed.',502)

    def do_GET(self):
        if not self.check_host():return
        route=urlparse(self.path).path
        try:
            if route=='/api/risk/status':return self.send_json(risk_status())
            if route=='/api/capabilities':return self.send_json(capabilities())
            if route=='/api/audit':
                orders=journal.audit()
                risk_events=broker.risk.audit()
                risk_integrity=broker.risk.verify_audit()
                return self.send_json({'events':orders['events'],'risk_events':risk_events,
                    'integrity':orders['integrity'] and risk_integrity['valid'],
                    'orders':orders,'risk_integrity':risk_integrity,
                    'scope':'local order and risk records; credentials are never included'})
            if route=='/api/system/health':
                state=broker.status()
                return self.send_json({'ok':True,'version':'5.0','uptime_seconds':round(time.time()-STARTED_AT),
                    'broker':{'connected':state['connected'],'mode':state['mode'],
                        'message':state['message'],'error':state['error']},
                    'workers':{name:worker.is_alive() for name,worker in WORKERS.items()},
                    'risk':risk_status(),'live_execution':False,
                    'audit_integrity':journal.audit(limit=1)['integrity'] and broker.risk.verify_audit()['valid']})
        except (RiskError,ValueError):return self.error_json('Risk state unavailable; new orders remain blocked',503)
        if route=='/api/strategy/catalog':return self.send_json({'strategies':STRATEGIES,'profiles':PROFILES})
        if route=='/api/strategy/status':return self.send_json(strategy_supervisor.status())
        if route=='/api/deriv/status':return self.send_json(broker.status())
        if route=='/api/deriv/health':return self.send_json({'ok':True,'mode':broker.mode,'live_enabled':broker.allow_live})
        return super().do_GET()

    def do_POST(self):
        if not self.check_host() or not self.check_origin():return
        path=urlparse(self.path).path
        if path.startswith('/api/risk/'):
            return self.do_risk_POST(path)
        if path.startswith('/api/strategy/'):
            return self.do_strategy_POST(path)
        if not path.startswith('/api/deriv/'):
            return super().do_POST()
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<=length<=65536:return self.error_json('Invalid payload size',413)
            if self.headers.get('Content-Type','').split(';')[0].strip()!='application/json':
                return self.error_json('JSON Content-Type required',415)
            obj=json.loads(self.rfile.read(length) or b'{}')
            if not isinstance(obj,dict):raise BridgeError('Expected JSON object')
            if path=='/api/deriv/accounts':
                return self.send_json({'accounts':broker.list_accounts(obj.get('app_id',''),obj.get('token',''))})
            if path=='/api/deriv/connect':
                return self.send_json(broker.connect(obj.get('app_id',''),obj.get('token',''),obj.get('account_id',''),obj.get('mode','demo')))
            if path=='/api/deriv/disconnect':
                strategy_supervisor.stop('Broker disconnected')
                broker.disconnect();return self.send_json(broker.status())
            if path=='/api/deriv/arm':return self.send_json(broker.arm(obj.get('phrase','')))
            if path=='/api/deriv/durations':
                return self.send_json(broker.available_durations(obj.get('symbol','')))
            if path=='/api/deriv/quote':
                return self.send_json(broker.new_quote(obj.get('symbol',''),obj.get('side',''),obj.get('stake'),obj.get('minutes',2)))
            if path=='/api/deriv/buy':
                return self.send_json(broker.buy_quote(obj.get('token','')))
            if path=='/api/deriv/snapshot':return self.send_json(broker.broker_snapshot())
            if path=='/api/deriv/markets':return self.send_json(broker.refresh_markets())
            if path=='/api/deriv/candles':
                return self.send_json({'candles':broker.get_candles(obj.get('symbol',''))})
            if path=='/api/deriv/automation':
                enabled=obj.get('active')
                if not isinstance(enabled,bool):raise BridgeError('active must be a boolean')
                with broker.lock:
                    if enabled:
                        entry_guard()
                        if strategy_supervisor.active and strategy_supervisor.action=='demo_trade':
                            raise BridgeError('Stop the Naked Forex demo robot before starting the indicator robot')
                        if broker.mode!='demo':raise BridgeError('Robot can only trade a Deriv DEMO account')
                        symbol=obj.get('symbol')
                        if symbol not in {s['symbol'] for s in broker.allowed_symbols}:
                            raise BridgeError('Select an available market')
                        strategy=obj.get('strategy')
                        if strategy not in simulator.STRATEGIES:raise BridgeError('Unknown strategy')
                        stake=float(obj.get('stake',1))
                        if not .35<=stake<=5:raise BridgeError('Demo robot stake must be $0.35–$5')
                        durations=broker.available_durations(symbol)
                        if 1 not in durations['UP'] or 1 not in durations['DOWN']:
                            raise BridgeError('The legacy demo robot requires both UP and DOWN 1-minute Rise/Fall contracts. This market does not offer them; choose another market or use monitor mode.')
                        broker.auto_symbol=symbol;broker.auto_strategy=strategy;broker.auto_stake=stake
                        broker.last_auto_candle=None
                        broker.automation=True
                        broker.last_message='Broker demo robot started; checks completed one-minute candles.'
                    else:
                        broker.automation=False
                        broker.last_message='Broker demo robot stopped; existing orders still expire normally.'
                return self.send_json(broker.status())
            return self.error_json('Unknown Deriv endpoint',404)
        except (BridgeError,ValueError,TypeError,json.JSONDecodeError) as exc:
            return self.error_json(str(exc),400)
        except Exception:
            # Do NOT print traceback: network exception URLs can contain one-time OTP.
            return self.error_json('Broker operation failed. Check connection and log in again.',502)

    def do_risk_POST(self,path):
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<=length<=1_000_000:return self.error_json('Invalid payload size',413)
            if self.headers.get('Content-Type','').split(';')[0].strip()!='application/json':
                return self.error_json('JSON Content-Type required',415)
            def invalid_constant(value):raise ValueError('Non-finite JSON numbers are prohibited')
            obj=json.loads(self.rfile.read(length) or b'{}',parse_constant=invalid_constant)
            if not isinstance(obj,dict):raise ValueError('Expected JSON object')
            if path=='/api/risk/kill':
                return self.send_json(emergency_stop(str(obj.get('reason','Emergency stop requested by user'))[:240]))
            with broker.lock:
                if path in ('/api/risk/resume','/api/risk/reset'):
                    if broker.mode=='real':raise RiskError('Real-money execution is disabled')
                    phrase=obj.get('confirmation','')
                    # Resume never resets period baselines, losses, drawdown, or audit history.
                    broker.risk.resume_all(phrase)
                    if broker.account_id:
                        broker.risk.resume(broker.account_id,broker.mode,phrase)
                        strategy_supervisor.paper.resume(broker.account_id,phrase)
                    return self.send_json(risk_status())
                if broker.mode not in ('demo','real'):raise RiskError('Connect an account before changing its risk configuration')
                if broker.automation or strategy_supervisor.active:
                    raise RiskError('Stop automation before changing risk controls or calendar coverage')
                if path=='/api/risk/config':
                    if journal.unresolved(broker.account_id):raise RiskError('Resolve outstanding broker orders before changing risk limits')
                    broker.risk.configure(broker.account_id,broker.mode,obj)
                elif path=='/api/risk/calendar':
                    broker.risk.set_calendar(broker.account_id,broker.mode,obj.get('events'),
                        obj.get('updated_at'),obj.get('valid_until'),obj.get('source'))
                else:return self.error_json('Unknown risk endpoint',404)
                return self.send_json(risk_status())
        except (RiskError,ValueError,TypeError,json.JSONDecodeError,UnicodeDecodeError) as exc:
            return self.error_json(str(exc),400)
        except Exception:
            return self.error_json('Risk-control operation failed; verify local database access',503)


def auto_loop(stop):
    """Low-frequency demo-only indicator robot; stop on errors and never retry buys."""
    while not stop.wait(20):
        with broker.lock:
            if broker.mode!='demo' or not broker.automation:continue
            try:
                candles=broker.get_candles(broker.auto_symbol)
                # Only fully completed minute bars; the latest one may be incomplete.
                cutoff=(int(time.time())//60)*60
                done=[c for c in candles if c['time'] < cutoff]
                if len(done)<55:continue
                epoch=done[-1]['time']
                if broker.last_auto_candle==epoch:continue
                broker.last_auto_candle=epoch
                sig=signal_at(done,indicators(done),len(done)-1,broker.auto_strategy)
                if sig:
                    broker.reconcile()
                    outstanding=journal.unresolved(broker.account_id)
                    if any(r['status'] in ('UNCERTAIN','PENDING') for r in outstanding):
                        raise BridgeError('Uncertain trade requires investigation before automation continues')
                    if outstanding or (broker.transport.portfolio().get('contracts') or []):
                        continue  # wait for existing contract to settle before next demo signal
                    broker.demo_auto_once(sig)
                    broker.last_message=f'Broker DEMO {sig} signal submitted for {broker.auto_symbol}.'
            except Exception:
                broker.automation=False
                broker.last_error='Demo robot stopped after broker error. Inspect orders and reconnect if necessary.'
                broker.last_message=broker.last_error


def main():
    parser=argparse.ArgumentParser(description='MIKEIZU TradeLab PRO v2 Deriv Edition — private localhost only')
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--no-browser',action='store_true')
    args=parser.parse_args()
    simulator.db_initialize()
    stop=threading.Event()
    for name,target in (('synthetic',simulator.market_loop),('indicator',auto_loop),('strategy',strategy_supervisor.loop)):
        worker=threading.Thread(target=target,args=(stop,),daemon=True,name=name)
        WORKERS[name]=worker;worker.start()
    server=ThreadingHTTPServer(('127.0.0.1',args.port),API)
    print(f'\nMIKEIZU TradeLab PRO v5.0: http://127.0.0.1:{args.port}')
    print('Deriv PAT/OTP adapter. Live execution disabled. Broker demo integration requires account verification.')
    print('Do not expose this port to the internet.\n')
    if not args.no_browser:
        threading.Timer(1.0,lambda:webbrowser.open(f'http://127.0.0.1:{args.port}')).start()
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:
        strategy_supervisor.stop('Application closed')
        broker.disconnect();stop.set();server.server_close()

if __name__=='__main__':main()
