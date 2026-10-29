"""Durable virtual stop/target research ledger; never broker positions.

Signals queue at a reference close, then fill at the next completed bar open.
Explicit estimated costs, adverse stop-gap fills and stop-first OHLC ambiguity.
No historical bid/ask, financing or liquidity feed; simulated results only.
"""
from __future__ import annotations
import json, math, sqlite3, threading, time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

class PaperError(ValueError): pass

def number(value, name, positive=False):
    if isinstance(value, bool): raise PaperError('Invalid '+name)
    try: value=float(value)
    except (TypeError,ValueError,OverflowError): raise PaperError('Invalid '+name) from None
    if not math.isfinite(value) or (positive and value<=0): raise PaperError('Invalid '+name)
    return value

class PaperBook:
    VERSION='paper-next-open-v2'
    def __init__(self,path,*,risk_pct=.5,spread_bps=1.,slippage_bps=.5,commission_per_unit=0.):
        self.path=Path(path);self.lock=threading.RLock()
        self.risk_pct=number(risk_pct,'risk percentage',True)
        self.spread_bps=number(spread_bps,'spread');self.slippage_bps=number(slippage_bps,'slippage')
        self.commission=number(commission_per_unit,'commission')
        if self.risk_pct>1 or min(self.spread_bps,self.slippage_bps,self.commission)<0:
            raise PaperError('Paper risk cannot exceed 1%; costs cannot be negative')
        with self.db() as c:
            c.execute('''CREATE TABLE IF NOT EXISTS paper_positions(
               id INTEGER PRIMARY KEY AUTOINCREMENT, account_id TEXT NOT NULL,
               symbol TEXT NOT NULL, timeframe TEXT NOT NULL, strategy TEXT NOT NULL,
               side TEXT NOT NULL, entry REAL NOT NULL, stop REAL NOT NULL,
               target REAL NOT NULL, risk_amount REAL NOT NULL, status TEXT NOT NULL,
               pnl REAL, opened_candle INTEGER NOT NULL, closed_candle INTEGER,
               opened_at INTEGER NOT NULL, closed_at INTEGER)''')
            c.execute('CREATE INDEX IF NOT EXISTS paper_account ON paper_positions(account_id,status)')
            cols={r[1] for r in c.execute('PRAGMA table_info(paper_positions)')}
            for key,kind in {'quantity':'REAL','exit':'REAL','gross_pnl':'REAL','costs':'REAL NOT NULL DEFAULT 0',
                             'signal_candle':'INTEGER','signal_key':'TEXT','model':'TEXT','assumptions':'TEXT','detail':'TEXT'}.items():
                if key not in cols:c.execute(f'ALTER TABLE paper_positions ADD COLUMN {key} {kind}')
            c.execute('CREATE UNIQUE INDEX IF NOT EXISTS paper_signal ON paper_positions(account_id,symbol,timeframe,strategy,signal_key) WHERE signal_key IS NOT NULL')
            c.execute('''CREATE TABLE IF NOT EXISTS paper_accounts(account_id TEXT PRIMARY KEY,
                      peak_equity REAL NOT NULL DEFAULT 10000,halted INTEGER NOT NULL DEFAULT 0,
                      halt_reason TEXT NOT NULL DEFAULT '')''')
    @contextmanager
    def db(self):
        with self.lock:
            c=sqlite3.connect(self.path,timeout=10)
            try:
                c.row_factory=sqlite3.Row;c.execute('BEGIN IMMEDIATE')
                yield c;c.commit()
            except Exception:c.rollback();raise
            finally:c.close()
    @staticmethod
    def equity(c,account):
        return 10000+float(c.execute("SELECT COALESCE(SUM(pnl),0) FROM paper_positions WHERE account_id=? AND status='CLOSED'",(account,)).fetchone()[0])
    def positions(self,account):
        with self.db() as c:return [dict(r) for r in c.execute('SELECT * FROM paper_positions WHERE account_id=? ORDER BY id DESC LIMIT 75',(account,))]
    def balance(self,account):
        with self.db() as c:return round(self.equity(c,account),2)
    def cancel_pending(self,account,symbol=None,frame=None,reason='Strategy stopped before virtual entry'):
        sql="UPDATE paper_positions SET status='CANCELLED',detail=? WHERE account_id=? AND status='PENDING'"
        args=[str(reason)[:300],account]
        if symbol is not None:sql+=' AND symbol=?';args.append(symbol)
        if frame is not None:sql+=' AND timeframe=?';args.append(frame)
        with self.db() as c:c.execute(sql,args)
    def halt(self,account,reason='Emergency stop'):
        with self.db() as c:
            c.execute('INSERT OR IGNORE INTO paper_accounts(account_id) VALUES (?)',(account,))
            c.execute('UPDATE paper_accounts SET halted=1,halt_reason=? WHERE account_id=?',(str(reason)[:200],account))
            c.execute("UPDATE paper_positions SET status='CANCELLED',detail='Emergency stop before virtual entry' WHERE account_id=? AND status='PENDING'",(account,))
    def resume(self,account,confirmation):
        if confirmation!='RESUME DEMO TRADING':raise PaperError('Explicit resume confirmation required')
        with self.db() as c:c.execute("UPDATE paper_accounts SET halted=0,halt_reason='' WHERE account_id=?",(account,))
    def guard(self,c,account,risk,excluding=None):
        c.execute('INSERT OR IGNORE INTO paper_accounts(account_id) VALUES (?)',(account,))
        state=c.execute('SELECT * FROM paper_accounts WHERE account_id=?',(account,)).fetchone()
        if state['halted']:raise PaperError('Paper trading halted: '+state['halt_reason'])
        equity=self.equity(c,account);peak=max(equity,state['peak_equity'])
        c.execute('UPDATE paper_accounts SET peak_equity=? WHERE account_id=?',(peak,account))
        if equity<=0 or peak-equity>=peak*.1:raise PaperError('Paper equity/drawdown limit reached')
        active=[r for r in c.execute("SELECT id,risk_amount FROM paper_positions WHERE account_id=? AND status IN ('PENDING','OPEN')",(account,)) if r['id']!=excluding]
        if len(active)>=3:raise PaperError('Maximum three simultaneous paper positions')
        now=datetime.now(timezone.utc);day=int(now.replace(hour=0,minute=0,second=0,microsecond=0).timestamp());week=day-now.weekday()*86400
        daily=c.execute("SELECT COALESCE(SUM(pnl),0) FROM paper_positions WHERE account_id=? AND status='CLOSED' AND closed_at>=?",(account,day)).fetchone()[0]
        weekly=c.execute("SELECT COALESCE(SUM(pnl),0) FROM paper_positions WHERE account_id=? AND status='CLOSED' AND closed_at>=?",(account,week)).fetchone()[0]
        day_equity=equity-daily;week_equity=equity-weekly
        exposure=sum(r['risk_amount'] for r in active)+risk
        if -min(0,daily)+exposure>day_equity*.02+1e-9:raise PaperError('Paper daily loss/exposure budget exceeded')
        if -min(0,weekly)+exposure>week_equity*.05+1e-9:raise PaperError('Paper weekly loss/exposure budget exceeded')
        if risk>equity*self.risk_pct/100+1e-9:raise PaperError('Paper per-trade risk limit exceeded')
    def open(self,account,symbol,frame,strategy,signal,entry):
        if not all(isinstance(x,str) and x for x in (account,symbol,frame,strategy)):
            raise PaperError('Paper account, instrument and rule set required')
        stop=number(signal.get('stop'),'stop',True);entry=number(entry,'reference price',True);side=signal.get('side')
        stamp=number(signal.get('confirmed_at'),'signal time')
        if side not in ('UP','DOWN') or stamp<0 or stamp!=int(stamp):raise PaperError('Invalid paper signal')
        dist=entry-stop if side=='UP' else stop-entry
        if not 0<dist<entry*.25:raise PaperError('Invalid paper stop: no virtual position opened')
        target=entry+(2*dist if side=='UP' else -2*dist)
        if target<=0:raise PaperError('Invalid paper target')
        assumptions=json.dumps({'spread_bps':self.spread_bps,'slippage_bps':self.slippage_bps,
             'commission_per_unit_per_side':self.commission,'financing':'not modeled','fill':'next completed bar open'},sort_keys=True)
        with self.db() as c:
            if c.execute("SELECT id FROM paper_positions WHERE account_id=? AND symbol=? AND status IN ('OPEN','PENDING')",(account,symbol)).fetchone():return None
            if c.execute('SELECT id FROM paper_positions WHERE account_id=? AND symbol=? AND timeframe=? AND strategy=? AND signal_key=?',(account,symbol,frame,strategy,str(int(stamp)))).fetchone():return None
            risk=math.floor(self.equity(c,account)*self.risk_pct)/100
            if risk<1:raise PaperError('Virtual account equity too low')
            self.guard(c,account,risk)
            c.execute('''INSERT INTO paper_positions(account_id,symbol,timeframe,strategy,side,entry,stop,target,risk_amount,status,opened_candle,opened_at,signal_candle,signal_key,model,assumptions,detail)
                      VALUES (?,?,?,?,?,?,?,?,?,'PENDING',?,?,?,?,?,?,?)''',(account,symbol,frame,strategy,side,entry,stop,target,risk,int(stamp),int(time.time()),int(stamp),str(int(stamp)),self.VERSION,assumptions,'Queued virtual order; awaiting next completed candle. No broker order.'))
            return c.execute('SELECT last_insert_rowid()').fetchone()[0]
    def reconcile(self,account,symbol,frame,rows):
        bars=[];prior=None
        for source in rows:
            bar={k:number(source.get(k),k,k!='time') for k in ('time','open','high','low','close')}
            if bar['time']!=int(bar['time']) or (prior is not None and bar['time']<=prior):raise PaperError('Paper candle times must increase')
            if bar['high']<max(bar['open'],bar['close']) or bar['low']>min(bar['open'],bar['close']) or bar['low']>bar['high']:raise PaperError('Invalid paper OHLC candle')
            prior=bar['time'];bars.append(bar)
        with self.db() as c:
            positions=[dict(r) for r in c.execute("SELECT * FROM paper_positions WHERE account_id=? AND symbol=? AND timeframe=? AND status IN ('OPEN','PENDING')",(account,symbol,frame))]
            for p in positions:
                costs=json.loads(p['assumptions']) if p['assumptions'] else {'spread_bps':0,'slippage_bps':0,'commission_per_unit_per_side':0}
                rate=(costs['spread_bps']/2+costs['slippage_bps'])/10000;commission=costs['commission_per_unit_per_side']
                for bar in bars:
                    if bar['time']<=p['opened_candle']:continue
                    if p['status']=='PENDING':
                        try:self.guard(c,account,p['risk_amount'],p['id'])
                        except PaperError as exc:
                            c.execute("UPDATE paper_positions SET status='CANCELLED',detail=? WHERE id=?",(str(exc),p['id']));break
                        reference=bar['open'];entry=reference*(1+rate if p['side']=='UP' else 1-rate)
                        dist=entry-p['stop'] if p['side']=='UP' else p['stop']-entry
                        if not 0<dist<entry*.25:
                            c.execute("UPDATE paper_positions SET status='CANCELLED',detail='Next-open gap invalidates stop' WHERE id=?",(p['id'],));break
                        quantity=p['risk_amount']/(dist+p['stop']*rate+2*commission)
                        target=entry+(2*dist if p['side']=='UP' else -2*dist)
                        p.update(entry=entry,quantity=quantity,target=target,status='OPEN',opened_candle=int(bar['time']))
                        c.execute("UPDATE paper_positions SET entry=?,quantity=?,target=?,status='OPEN',opened_candle=?,detail='Virtual next-open fill; cost model applied' WHERE id=?",(entry,quantity,target,int(bar['time']),p['id']))
                    loss=bar['low']<=p['stop'] if p['side']=='UP' else bar['high']>=p['stop']
                    win=bar['high']>=p['target'] if p['side']=='UP' else bar['low']<=p['target']
                    if loss or win:
                        reference=(min(p['stop'],bar['open']) if p['side']=='UP' else max(p['stop'],bar['open'])) if loss else p['target']
                        price=reference*(1-rate if p['side']=='UP' else 1+rate)
                        quantity=p['quantity'] if p['quantity'] is not None else p['risk_amount']/abs(p['entry']-p['stop'])
                        net=((price-p['entry']) if p['side']=='UP' else (p['entry']-price))*quantity-2*commission*quantity
                        cost=abs(reference-price)*quantity+2*commission*quantity
                        if p['model']==self.VERSION:cost+=p['entry']*rate/(1+rate if p['side']=='UP' else 1-rate)*quantity
                        c.execute("UPDATE paper_positions SET status='CLOSED',pnl=?,gross_pnl=?,costs=?,exit=?,closed_candle=?,closed_at=?,detail=? WHERE id=?",(round(net,2),round(net+cost,2),round(cost,2),price,int(bar['time']),int(time.time()),'Virtual stop first / adverse gap fill' if loss else 'Virtual 2R target fill',p['id']))
                        c.execute('UPDATE paper_accounts SET peak_equity=MAX(peak_equity,?) WHERE account_id=?',(self.equity(c,account),account))
                        break
