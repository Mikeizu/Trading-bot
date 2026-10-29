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

MIN_PRICE=1e-100
MAX_NUMBER=1e100
MAX_EPOCH=253402300799
FRAME_SECONDS={'1m':60,'5m':300,'15m':900,'1h':3600,'4h':14400,'1d':86400,'1w':604800}

def number(value, name, positive=False):
    if isinstance(value, bool): raise PaperError('Invalid '+name)
    try: value=float(value)
    except (TypeError,ValueError,OverflowError): raise PaperError('Invalid '+name) from None
    if not math.isfinite(value) or abs(value)>MAX_NUMBER or (positive and value<MIN_PRICE): raise PaperError('Invalid '+name)
    return value

def identity(value,name):
    if not isinstance(value,str) or not value.strip() or len(value)>128:
        raise PaperError('Invalid '+name)
    return value

def epoch(value,name):
    value=number(value,name)
    if not 0<=value<=MAX_EPOCH or not value.is_integer():raise PaperError('Invalid '+name)
    return int(value)

def next_bar(stamp,frame):
    if frame in FRAME_SECONDS:
        result=stamp+FRAME_SECONDS[frame]
        if result>MAX_EPOCH:raise PaperError('Paper candle time exceeds supported calendar')
        return result
    if frame=='1mo':
        try:dt=datetime.fromtimestamp(stamp,timezone.utc)
        except (OverflowError,OSError,ValueError):raise PaperError('Paper candle time exceeds supported calendar') from None
        if dt.day!=1 or any((dt.hour,dt.minute,dt.second)):raise PaperError('Monthly paper candles require UTC month boundaries')
        if dt.year==9999 and dt.month==12:raise PaperError('Paper candle time exceeds supported calendar')
        try:return int(datetime(dt.year+(dt.month==12),1 if dt.month==12 else dt.month+1,1,tzinfo=timezone.utc).timestamp())
        except (OverflowError,OSError,ValueError):raise PaperError('Paper candle time exceeds supported calendar') from None
    raise PaperError('Unsupported paper timeframe')

class PaperBook:
    VERSION='paper-next-open-v3'
    def __init__(self,path,*,risk_pct=.5,spread_bps=1.,slippage_bps=.5,commission_per_unit=0.):
        self.path=Path(path);self.lock=threading.RLock()
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.risk_pct=number(risk_pct,'risk percentage',True)
        self.spread_bps=number(spread_bps,'spread');self.slippage_bps=number(slippage_bps,'slippage')
        self.commission=number(commission_per_unit,'commission')
        if self.risk_pct>1 or min(self.spread_bps,self.slippage_bps,self.commission)<0:
            raise PaperError('Paper risk cannot exceed 1%; costs cannot be negative')
        if max(self.spread_bps,self.slippage_bps)>100 or self.commission>1_000_000:
            raise PaperError('Paper spread/slippage cannot exceed 100 basis points; commission exceeds supported range')
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
                             'signal_candle':'INTEGER','signal_key':'TEXT','model':'TEXT','assumptions':'TEXT','detail':'TEXT','last_checked_candle':'INTEGER'}.items():
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
        values=[number(r[0],'settled paper P&L') for r in c.execute("SELECT pnl FROM paper_positions WHERE account_id=? AND status='CLOSED'",(account,))]
        return number(10000+math.fsum(values),'paper equity')
    def positions(self,account):
        identity(account,'paper account')
        with self.db() as c:return [dict(r) for r in c.execute('SELECT * FROM paper_positions WHERE account_id=? ORDER BY id DESC LIMIT 75',(account,))]
    def balance(self,account):
        identity(account,'paper account')
        with self.db() as c:return round(self.equity(c,account),2)
    def cancel_pending(self,account,symbol=None,frame=None,reason='Strategy stopped before virtual entry'):
        identity(account,'paper account')
        if symbol is not None:identity(symbol,'paper symbol')
        if frame is not None:identity(frame,'paper timeframe')
        sql="UPDATE paper_positions SET status='CANCELLED',detail=? WHERE account_id=? AND status='PENDING'"
        args=[str(reason)[:300],account]
        if symbol is not None:sql+=' AND symbol=?';args.append(symbol)
        if frame is not None:sql+=' AND timeframe=?';args.append(frame)
        with self.db() as c:c.execute(sql,args)
    def halt(self,account,reason='Emergency stop'):
        identity(account,'paper account')
        with self.db() as c:
            c.execute('INSERT OR IGNORE INTO paper_accounts(account_id) VALUES (?)',(account,))
            c.execute('UPDATE paper_accounts SET halted=1,halt_reason=? WHERE account_id=?',(str(reason)[:200],account))
            c.execute("UPDATE paper_positions SET status='CANCELLED',detail='Emergency stop before virtual entry' WHERE account_id=? AND status='PENDING'",(account,))
    def resume(self,account,confirmation):
        identity(account,'paper account')
        if confirmation!='RESUME DEMO TRADING':raise PaperError('Explicit resume confirmation required')
        with self.db() as c:c.execute("UPDATE paper_accounts SET halted=0,halt_reason='' WHERE account_id=?",(account,))
    def guard(self,c,account,risk,excluding=None):
        c.execute('INSERT OR IGNORE INTO paper_accounts(account_id) VALUES (?)',(account,))
        state=c.execute('SELECT * FROM paper_accounts WHERE account_id=?',(account,)).fetchone()
        if state['halted']:raise PaperError('Paper trading halted: '+state['halt_reason'])
        risk=number(risk,'paper risk',True)
        equity=self.equity(c,account);peak=max(equity,number(state['peak_equity'],'paper peak equity',True))
        c.execute('UPDATE paper_accounts SET peak_equity=? WHERE account_id=?',(peak,account))
        if equity<=0 or peak-equity>=peak*.1:raise PaperError('Paper equity/drawdown limit reached')
        active=[r for r in c.execute("SELECT id,risk_amount FROM paper_positions WHERE account_id=? AND status IN ('PENDING','OPEN')",(account,)) if r['id']!=excluding]
        if len(active)>=3:raise PaperError('Maximum three simultaneous paper positions')
        now=datetime.now(timezone.utc);day=int(now.replace(hour=0,minute=0,second=0,microsecond=0).timestamp());week=day-now.weekday()*86400
        daily=c.execute("SELECT COALESCE(SUM(pnl),0) FROM paper_positions WHERE account_id=? AND status='CLOSED' AND closed_at>=?",(account,day)).fetchone()[0]
        weekly=c.execute("SELECT COALESCE(SUM(pnl),0) FROM paper_positions WHERE account_id=? AND status='CLOSED' AND closed_at>=?",(account,week)).fetchone()[0]
        day_equity=equity-daily;week_equity=equity-weekly
        exposure=math.fsum(number(r['risk_amount'],'reserved paper risk',True) for r in active)+risk
        if -min(0,daily)+exposure>day_equity*.02+1e-9:raise PaperError('Paper daily loss/exposure budget exceeded')
        if -min(0,weekly)+exposure>week_equity*.05+1e-9:raise PaperError('Paper weekly loss/exposure budget exceeded')
        if risk>equity*self.risk_pct/100+1e-9:raise PaperError('Paper per-trade risk limit exceeded')
    def open(self,account,symbol,frame,strategy,signal,entry):
        for name,value in (('paper account',account),('paper instrument',symbol),('paper timeframe',frame),('paper strategy',strategy)):
            identity(value,name)
        if not isinstance(signal,dict):raise PaperError('Paper signal must be an object')
        stop=number(signal.get('stop'),'stop',True);entry=number(entry,'reference price',True);side=signal.get('side')
        stamp=epoch(signal.get('confirmed_at'),'signal time')
        next_bar(stamp,frame)
        if side not in ('UP','DOWN'):raise PaperError('Invalid paper signal')
        dist=entry-stop if side=='UP' else stop-entry
        if not 0<dist<entry*.25:raise PaperError('Invalid paper stop: no virtual position opened')
        target=entry+(2*dist if side=='UP' else -2*dist)
        number(target,'paper target',True)
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
        for name,value in (('paper account',account),('paper instrument',symbol),('paper timeframe',frame)):
            identity(value,name)
        if frame not in FRAME_SECONDS and frame!='1mo':raise PaperError('Unsupported paper timeframe')
        if not isinstance(rows,list) or len(rows)>10000:raise PaperError('Paper candles must be a list of at most 10000 rows')
        bars=[];prior=None
        for source in rows:
            if not isinstance(source,dict):raise PaperError('Paper candle must be an object')
            bar={k:number(source.get(k),k,k!='time') for k in ('time','open','high','low','close')}
            bar['time']=epoch(bar['time'],'paper candle time')
            if prior is not None and bar['time']<=prior:raise PaperError('Paper candle times must increase')
            if frame=='1mo':next_bar(bar['time'],frame)
            if bar['high']<max(bar['open'],bar['close']) or bar['low']>min(bar['open'],bar['close']) or bar['low']>bar['high']:raise PaperError('Invalid paper OHLC candle')
            prior=bar['time'];bars.append(bar)
        with self.db() as c:
            positions=[dict(r) for r in c.execute("SELECT * FROM paper_positions WHERE account_id=? AND symbol=? AND timeframe=? AND status IN ('OPEN','PENDING')",(account,symbol,frame))]
            for p in positions:
                try:costs=json.loads(p['assumptions']) if p['assumptions'] else {'spread_bps':0,'slippage_bps':0,'commission_per_unit_per_side':0}
                except (TypeError,ValueError):raise PaperError('Persisted paper costs are invalid') from None
                if not isinstance(costs,dict):raise PaperError('Persisted paper costs are invalid')
                try:
                    spread=number(costs['spread_bps'],'persisted spread');slippage=number(costs['slippage_bps'],'persisted slippage')
                    commission=number(costs['commission_per_unit_per_side'],'persisted commission')
                except KeyError:raise PaperError('Persisted paper costs are incomplete') from None
                if not 0<=spread<=100 or not 0<=slippage<=100 or not 0<=commission<=1_000_000:
                    raise PaperError('Persisted paper costs exceed supported range')
                if p['side'] not in ('UP','DOWN'):raise PaperError('Persisted paper direction is invalid')
                for key in ('entry','stop','target','risk_amount'):number(p[key],'persisted '+key,True)
                if not (p['stop']<p['entry']<p['target'] if p['side']=='UP' else p['target']<p['entry']<p['stop']):
                    raise PaperError('Persisted paper stop/target boundaries are invalid')
                if p['model'] not in (None,'paper-next-open-v2',self.VERSION):raise PaperError('Unknown persisted paper execution model')
                if p['quantity'] is not None:number(p['quantity'],'persisted paper quantity',True)
                rate=(spread/2+slippage)/10000
                last_checked=epoch(p['last_checked_candle'] if p['last_checked_candle'] is not None else p['opened_candle'],'last checked paper candle')
                for bar in bars:
                    if bar['time']<=last_checked:continue
                    if p['status']=='PENDING':
                        if bar['time']!=next_bar(epoch(p['opened_candle'],'pending signal time'),frame):
                            c.execute("UPDATE paper_positions SET status='CANCELLED',detail='Missing next candle; a later bar cannot prove the next-open fill' WHERE id=?",(p['id'],));break
                        try:self.guard(c,account,p['risk_amount'],p['id'])
                        except PaperError as exc:
                            c.execute("UPDATE paper_positions SET status='CANCELLED',detail=? WHERE id=?",(str(exc),p['id']));break
                        reference=bar['open'];entry=reference*(1+rate if p['side']=='UP' else 1-rate)
                        dist=entry-p['stop'] if p['side']=='UP' else p['stop']-entry
                        if not 0<dist<entry*.25:
                            c.execute("UPDATE paper_positions SET status='CANCELLED',detail='Next-open gap invalidates stop' WHERE id=?",(p['id'],));break
                        quantity=p['risk_amount']/(dist+p['stop']*rate+2*commission)
                        target=entry+(2*dist if p['side']=='UP' else -2*dist)
                        number(quantity,'paper position quantity',True);number(target,'paper target',True)
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
                        if p['model'] in ('paper-next-open-v2',self.VERSION):cost+=p['entry']*rate/(1+rate if p['side']=='UP' else 1-rate)*quantity
                        number(net,'settled paper P&L');number(cost,'settled paper costs')
                        c.execute("UPDATE paper_positions SET status='CLOSED',pnl=?,gross_pnl=?,costs=?,exit=?,closed_candle=?,closed_at=?,detail=? WHERE id=?",(round(net,2),round(net+cost,2),round(cost,2),price,int(bar['time']),int(time.time()),'Virtual stop first / adverse gap fill' if loss else 'Virtual 2R target fill',p['id']))
                        c.execute('UPDATE paper_accounts SET peak_equity=MAX(peak_equity,?) WHERE account_id=?',(self.equity(c,account),account))
                        break
                    last_checked=bar['time']
                    c.execute('UPDATE paper_positions SET last_checked_candle=? WHERE id=?',(last_checked,p['id']))
