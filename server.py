"""Private local Python web server for MIKEIZU TradeLab PRO.

No external libraries, external network calls or broker account credentials.
Run: python server.py
"""
from __future__ import annotations
import argparse, csv, io, json, math, os, random, sqlite3, threading, time, traceback, webbrowser
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from engine import indicators, signal_at, backtest

ROOT = Path(__file__).resolve().parent
STATIC = ROOT/'static'
DATA_DIR = Path(os.environ.get('MIKEIZU_DATA_DIR',str(ROOT))).expanduser().resolve()
DATA_DIR.mkdir(parents=True,exist_ok=True)
DB_FILE = DATA_DIR/'tradelab.db'
ASSETS = {'EUR/USD':1.085, 'GBP/USD':1.273, 'USD/JPY':148.2, 'XAU/USD':2674., 'BTC/USD':67400., 'CUSTOM':1.}
STRATEGIES = ('RSI','MACD','CCI','SMA','BOLLINGER','STOCHASTIC')
DEFAULT = {'balance':10000.,'asset':'EUR/USD','strategy':'RSI','stake':20.,'duration':3,'payout':0.8,
           'stop_loss':200., 'take_profit':350., 'max_stake_pct':.5,'trade_limit':40,
           'watchlist':['EUR/USD','GBP/USD','XAU/USD','BTC/USD']}
TICK_SECONDS = 4
LOCK = threading.RLock()
BOT_ACTIVE = False
BOT_MESSAGE = 'Robot is stopped. Demo account only.'
LAST_TICK = None
ENTRY_GUARD = None  # The unified server supplies the persistent emergency interlock.


def reject_json_constant(value):
    raise ValueError('Non-finite JSON numbers are prohibited')


@contextmanager
def conn():
    c = sqlite3.connect(DB_FILE, timeout=20)
    try:
        c.row_factory = sqlite3.Row
        c.execute('PRAGMA busy_timeout=20000')
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def db_initialize():
    with LOCK:
        with conn() as c:
            c.execute('PRAGMA journal_mode=WAL')
            c.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
            c.execute('CREATE TABLE IF NOT EXISTS candles (asset TEXT NOT NULL, tick INTEGER NOT NULL, time INTEGER NOT NULL, open REAL NOT NULL, high REAL NOT NULL, low REAL NOT NULL, close REAL NOT NULL, PRIMARY KEY(asset,tick))')
            c.execute('CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY AUTOINCREMENT, asset TEXT NOT NULL, side TEXT NOT NULL, stake REAL NOT NULL, entry REAL NOT NULL, exit REAL, opened_tick INTEGER NOT NULL, expiry_tick INTEGER NOT NULL, strategy TEXT NOT NULL, status TEXT NOT NULL, pnl REAL NOT NULL DEFAULT 0, opened_at INTEGER NOT NULL, settled_at INTEGER)')
            c.execute('CREATE INDEX IF NOT EXISTS ix_trades_time ON trades(opened_at)')
            for key,val in DEFAULT.items():
                c.execute('INSERT OR IGNORE INTO settings(key,value) VALUES (?,?)',(key,json.dumps(val)))
            columns={r[1] for r in c.execute('PRAGMA table_info(trades)')}
            if 'payout' not in columns:c.execute('ALTER TABLE trades ADD COLUMN payout REAL')
            if 'payout_source' not in columns:c.execute('ALTER TABLE trades ADD COLUMN payout_source TEXT')
            # Legacy files did not record entry terms. Preserve the migration
            # assumption explicitly; future settings must never rewrite a trade.
            c.execute("UPDATE trades SET payout=?,payout_source='legacy_setting_at_migration' WHERE payout IS NULL",
                      (get_settings(c)['payout'],))
            count = c.execute('SELECT COUNT(*) AS n FROM candles').fetchone()['n']
            if not count:
                start = int(time.time()) - 360*60
                for k,(asset,price) in enumerate(ASSETS.items()):
                    if asset == 'CUSTOM': continue
                    rnd = random.Random(933+k*187)
                    val = price
                    vol = .00085 if price < 2 else (.00045 if price < 1000 else .00165)
                    records = []
                    for tick in range(360):
                        prior = val
                        trend = math.sin(tick/24+k) * vol*.30
                        val = max(price*.01, prior * (1+rnd.gauss(0,vol)+trend))
                        wick = abs(rnd.gauss(0, vol*.3))
                        high = max(prior,val)*(1+wick)
                        low = min(prior,val)*(1-wick)
                        records.append((asset,tick,start+tick*60,prior,high,low,val))
                    c.executemany('INSERT INTO candles VALUES(?,?,?,?,?,?,?)',records)


def get_settings(c):
    return {r['key']:json.loads(r['value']) for r in c.execute('SELECT key,value FROM settings')}


def set_settings(c, obj):
    c.executemany('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',[(k,json.dumps(v)) for k,v in obj.items()])


def candles_for(c, asset, limit=260):
    return [dict(x) for x in reversed(c.execute('SELECT * FROM (SELECT asset,tick,time,open,high,low,close FROM candles WHERE asset=? ORDER BY tick DESC LIMIT ?) ORDER BY tick DESC',(asset,limit)).fetchall())]


def today_stats(c):
    day = int(datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0).timestamp())
    rows = c.execute('SELECT * FROM trades ORDER BY id DESC').fetchall()
    settled_today = [r for r in rows if r['status'] != 'OPEN' and (r['settled_at'] or 0) >= day]
    pnl = round(sum(r['pnl'] for r in settled_today),2)
    return {'total_trades':len([r for r in rows if r['status'] != 'OPEN']), 'open_trades':len([r for r in rows if r['status']=='OPEN']),
            'daily_pnl':pnl, 'daily_trades':len(settled_today), 'wins_today':len([r for r in settled_today if r['status']=='WIN']),
            'win_rate_today':round(len([r for r in settled_today if r['status']=='WIN'])/len(settled_today)*100,1) if settled_today else 0,
            'net_pnl':round(sum(r['pnl'] for r in rows if r['status'] != 'OPEN'),2)}


def market_advance():
    global BOT_MESSAGE, LAST_TICK, BOT_ACTIVE
    with LOCK:
        with conn() as c:
            s = get_settings(c)
            asset = s['asset']
            if asset=='CUSTOM':
                BOT_ACTIVE=False
                BOT_MESSAGE='Imported candles are historical research data. Synthetic extension is disabled.'
                raise ValueError(BOT_MESSAGE)
            latest = c.execute('SELECT * FROM candles WHERE asset=? ORDER BY tick DESC LIMIT 1',(asset,)).fetchone()
            if latest is None:
                BOT_ACTIVE = False; BOT_MESSAGE = 'No price history for this asset.'; return
            tick = latest['tick']+1
            # Enter at the next generated bar's open using only candles already
            # closed. Do not decide after seeing that same bar's closing price.
            price = float(latest['close'])
            if BOT_ACTIVE:
                if ENTRY_GUARD is not None:ENTRY_GUARD()
                stats=today_stats(c)
                blocked=None
                if stats['daily_pnl'] <= -s['stop_loss'] or stats['daily_pnl'] >= s['take_profit']:
                    blocked='daily profit/loss limit reached'
                elif stats['daily_trades']+stats['open_trades']>=s['trade_limit']:
                    blocked='daily trade count limit reached'
                elif s['stake']>s['balance'] or s['stake']>s['balance']*s['max_stake_pct']/100:
                    blocked='stake exceeds balance or maximum risk setting'
                elif -min(0,stats['daily_pnl'])+s['stake']>s['stop_loss']:
                    blocked='stake would exceed remaining daily loss budget'
                if blocked:
                    BOT_ACTIVE=False;BOT_MESSAGE='Robot stopped: '+blocked+'.'
                elif not stats['open_trades']:
                    candles=candles_for(c,asset,150)
                    sig=signal_at(candles,indicators(candles),len(candles)-1,s['strategy'])
                    if sig:
                        c.execute('''INSERT INTO trades(asset,side,stake,entry,opened_tick,expiry_tick,
                            strategy,status,opened_at,payout,payout_source) VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
                            (asset,sig,s['stake'],price,tick,tick+s['duration']-1,s['strategy'],'OPEN',
                             int(time.time()),s['payout'],'at_entry'))
                        s['balance']=round(s['balance']-s['stake'],2)
                        set_settings(c,{'balance':s['balance']})
                        BOT_MESSAGE=f'Synthetic {sig} trade opened on {asset} at next-bar open {price:.5f}.'
            rnd = random.Random(f"{asset}:{tick}:MIKEIZU")
            recent = candles_for(c,asset,60)
            scale = (max(x['high'] for x in recent) - min(x['low'] for x in recent))/max(latest['close'],1e-9)
            vol = max(.00015, min(.004,scale/12))
            prior_move = (recent[-1]['close']-recent[-6]['close'])/max(price,1e-9) if len(recent)>5 else 0
            movement = rnd.gauss(0,vol) + max(-vol*.4,min(vol*.4,prior_move*.12))
            closing = max(.000001,price*(1+movement))
            high = max(price,closing)*(1+abs(rnd.gauss(0,vol*.3)))
            low = min(price,closing)*(1-abs(rnd.gauss(0,vol*.3)))
            c.execute('INSERT INTO candles VALUES(?,?,?,?,?,?,?)',(asset,tick,latest['time']+60,price,high,low,closing))
            # Settle existing trades once their expiry bar has finished.
            for t in c.execute("SELECT * FROM trades WHERE status='OPEN' AND asset=? AND expiry_tick<=?",(asset,tick)).fetchall():
                won = (closing>t['entry'] if t['side']=='UP' else closing<t['entry'])
                pnl = round(t['stake']*t['payout'] if won else -t['stake'],2)
                if won: set_settings(c,{'balance':round(s['balance']+t['stake']+pnl,2)}); s['balance'] = round(s['balance']+t['stake']+pnl,2)
                c.execute('UPDATE trades SET exit=?,status=?,pnl=?,settled_at=? WHERE id=?',(closing,'WIN' if won else 'LOSS',pnl,int(time.time()),t['id']))
                BOT_MESSAGE = f"Demo trade #{t['id']} settled: {'WIN' if won else 'LOSS'} (${pnl:+.2f})"
            LAST_TICK = int(time.time())


def market_loop(stop_event):
    global BOT_MESSAGE, BOT_ACTIVE
    while not stop_event.wait(TICK_SECONDS):
        if BOT_ACTIVE:
            try: market_advance()
            except Exception as exc:
                BOT_ACTIVE=False; BOT_MESSAGE='Bot stopped due to internal error: '+str(exc)[:100]


def normalize_update(src):
    if not isinstance(src,dict):raise ValueError('Settings must be an object')
    out={}
    for name in ('asset','strategy','stake','duration','payout','stop_loss','take_profit','max_stake_pct','trade_limit'):
        if name not in src:continue
        val = src[name]
        if isinstance(val,bool):raise ValueError('Invalid '+name)
        if name == 'asset':
            if not isinstance(val,str) or val not in ASSETS: raise ValueError('Unknown asset')
        elif name == 'strategy':
            if not isinstance(val,str) or val not in STRATEGIES: raise ValueError('Unsupported strategy')
        elif name in ('duration','trade_limit'):
            try:
                numeric=float(val)
                if not math.isfinite(numeric) or not numeric.is_integer():raise ValueError()
                val=int(numeric)
            except (ValueError,TypeError,OverflowError):raise ValueError('Invalid '+name) from None
            if not 1 <= val <= (20 if name=='duration' else 1000): raise ValueError('Invalid '+name)
        else:
            try:val=float(val)
            except (ValueError,TypeError,OverflowError):raise ValueError('Invalid '+name) from None
            if not math.isfinite(val): raise ValueError('Invalid numeric value')
            ranges={'stake':(1,100000),'payout':(.1,1),'stop_loss':(1,100000),'take_profit':(1,100000),'max_stake_pct':(.1,5)}
            if not ranges[name][0] <= val <= ranges[name][1]: raise ValueError('Invalid '+name)
        out[name]=val
    return out


def import_csv(content):
    if len(content)>2_000_000: raise ValueError('CSV exceeds 2 MB limit')
    try: data=content.decode('utf-8-sig')
    except UnicodeDecodeError: raise ValueError('CSV must use UTF-8')
    reader=csv.DictReader(io.StringIO(data))
    if not reader.fieldnames: raise ValueError('CSV is empty')
    headings={h.strip().lower():h for h in reader.fieldnames}
    if len(headings)!=len(reader.fieldnames) or '' in headings:raise ValueError('CSV column names must be unique and nonempty')
    if not all(k in headings for k in ('open','high','low','close')):
        raise ValueError('CSV needs columns open, high, low, close (optional time)')
    rows=[];epochs=[]
    time_key=next((headings[k] for k in ('time','timestamp','epoch','date','datetime') if k in headings),None)
    for i,r in enumerate(reader):
        if i >= 10000: raise ValueError('Maximum 10,000 CSV rows')
        try:
            if None in r:raise ValueError()
            o,h,l,cl = (float(r[headings[k]]) for k in ('open','high','low','close'))
            if any(not math.isfinite(x) or x<=0 for x in (o,h,l,cl)) or h < max(o,cl) or l > min(o,cl) or l>h:
                raise ValueError()
        except (ValueError,TypeError): raise ValueError(f'Invalid OHLC values in CSV row {i+2}')
        rows.append((o,h,l,cl))
        if time_key:
            try:
                raw=(r[time_key] or '').strip()
                try:
                    epoch=float(raw)
                    if not math.isfinite(epoch) or not epoch.is_integer():raise ValueError()
                    stamp=int(epoch)
                except ValueError:
                    dt=datetime.fromisoformat(raw.replace('Z','+00:00'))
                    if dt.tzinfo is None:raise ValueError()
                    stamp=int(dt.timestamp())
                if stamp<=0 or (epochs and stamp<=epochs[-1]):raise ValueError()
            except (ValueError,TypeError,OverflowError):raise ValueError(f'Invalid or unordered timestamp in CSV row {i+2}') from None
            epochs.append(stamp)
    if len(rows)<60:raise ValueError('Import needs at least 60 OHLC rows')
    start=int(time.time())-len(rows)*60
    if not epochs:epochs=[start+i*60 for i in range(len(rows))]
    # Share the research validator's supported numeric/data bounds before
    # committing history; rejected data must not poison the running workspace.
    from naked_strategies import candles_valid
    candles_valid([{'time':epoch,'open':r[0],'high':r[1],'low':r[2],'close':r[3]} for epoch,r in zip(epochs,rows)])
    with LOCK:
        with conn() as c:
            if BOT_ACTIVE: raise ValueError('Stop robot before importing new data')
            if c.execute("SELECT 1 FROM trades WHERE status='OPEN' LIMIT 1").fetchone():
                raise ValueError('Settle open synthetic trades before replacing or switching history')
            c.execute('DELETE FROM candles WHERE asset=?',('CUSTOM',))
            c.executemany('INSERT INTO candles VALUES(?,?,?,?,?,?,?)',
                          [('CUSTOM',i,epochs[i],*row) for i,row in enumerate(rows)])
            set_settings(c,{'asset':'CUSTOM','custom_time_origin':'provided' if time_key else 'inferred_one_minute_intervals'})
    return len(rows)


class API(BaseHTTPRequestHandler):
    server_version='MIKEIZUTradeLab/1.0'
    def end_headers(self):
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('X-Frame-Options','DENY')
        self.send_header('Cross-Origin-Resource-Policy','same-origin')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; object-src 'none'")
        super().end_headers()
    def log_message(self,fmt,*args):
        print('[%s] %s'%(self.log_date_time_string(),fmt%args))
    def send_json(self,data,status=200):
        body=json.dumps(data,allow_nan=False,separators=(',',':')).encode()
        self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def error_json(self,error,status=400):self.send_json({'error':str(error)},status)
    def do_GET(self):
        path=urlparse(self.path).path
        if not path.startswith('/api/'):
            return self.serve_static(path)
        try:
            with LOCK:
                with conn() as c:
                    s=get_settings(c); asset=s['asset']
                    if path=='/api/bootstrap':
                        recent=candles_for(c,asset,200)
                        market={}
                        for item in ASSETS:
                            last=c.execute('SELECT close FROM candles WHERE asset=? ORDER BY tick DESC LIMIT 1',(item,)).fetchone()
                            market[item]=last['close'] if last else None
                        data={'settings':s,'assets':market,'strategies':STRATEGIES,'candles':recent,
                              'indicators':indicators(recent),'stats':today_stats(c),
                              'trades':[dict(x) for x in c.execute('SELECT * FROM trades ORDER BY id DESC LIMIT 150')],
                              'robot':{'active':BOT_ACTIVE,'message':BOT_MESSAGE,'tick_seconds':TICK_SECONDS,'last_tick':LAST_TICK},
                              'disclaimer':'Demo prices are synthetic. Not live, not connected to Quotex or any broker.'}
                        return self.send_json(data)
                    if path=='/api/health':return self.send_json({'ok':True,'mode':'OFFLINE_DEMO'})
                    if path=='/api/export':
                        return self.export_trades(c)
            return self.error_json('Unknown API endpoint',404)
        except Exception as ex: return self.error_json(ex,500)
    def export_trades(self,c):
        out=io.StringIO();writer=csv.writer(out)
        cols=['id','asset','side','stake','entry','exit','opened_tick','expiry_tick','strategy','status','pnl','opened_at','settled_at','payout','payout_source']
        writer.writerow(cols)
        for r in c.execute('SELECT * FROM trades ORDER BY id'):
            writer.writerow([r[k] for k in cols])
        content=out.getvalue().encode()
        self.send_response(200);self.send_header('Content-Type','text/csv; charset=utf-8')
        self.send_header('Content-Disposition','attachment; filename="mikeizu-demo-trades.csv"')
        self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content)
    def serve_static(self,path):
        filename = {'/':'index.html'}.get(path,path.lstrip('/'))
        filepath = (STATIC/filename).resolve()
        if not filepath.is_relative_to(STATIC.resolve()) or not filepath.is_file():
            self.send_error(404);return
        mime={'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8','.json':'application/json','.webmanifest':'application/manifest+json','.svg':'image/svg+xml','.png':'image/png'}
        blob=filepath.read_bytes()
        self.send_response(200);self.send_header('Content-Type',mime.get(filepath.suffix,'application/octet-stream'))
        self.send_header('Content-Length',str(len(blob)));self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(blob)
    def do_POST(self):
        global BOT_ACTIVE, BOT_MESSAGE
        path=urlparse(self.path).path
        try:
            length=int(self.headers.get('Content-Length','0'))
            if length < 0 or length>2_100_000: return self.error_json('Request too large',413)
            payload=self.rfile.read(length)
            if path=='/api/import':
                num=import_csv(payload)
                return self.send_json({'ok':True,'imported':num})
            if self.headers.get('Content-Type','').split(';')[0].strip()!='application/json':
                return self.error_json('JSON Content-Type required',415)
            try: obj=json.loads(payload.decode('utf-8'),parse_constant=reject_json_constant) if payload else {}
            except (json.JSONDecodeError,UnicodeDecodeError): return self.error_json('Invalid JSON request')
            if not isinstance(obj,dict): return self.error_json('JSON must be an object')
            if path=='/api/settings':
                with LOCK:
                    if BOT_ACTIVE: raise ValueError('Stop the robot before changing strategy settings')
                    update=normalize_update(obj)
                    with conn() as c:
                        if 'asset' in update and update['asset'] != get_settings(c)['asset'] and c.execute("SELECT COUNT(*) FROM trades WHERE status='OPEN'").fetchone()[0]:
                            raise ValueError('Settle open demo trades before switching assets')
                        if update.get('asset')=='CUSTOM' and not candles_for(c,'CUSTOM',1): raise ValueError('Import custom candles first')
                        set_settings(c,update)
                return self.send_json({'ok':True,'updated':update})
            if path=='/api/robot':
                requested=obj.get('active')
                if not isinstance(requested,bool):raise ValueError('active must be a boolean')
                with LOCK:
                    if requested:
                        if ENTRY_GUARD is not None:ENTRY_GUARD()
                        with conn() as c:
                            s=get_settings(c)
                            if s['asset']=='CUSTOM':raise ValueError('Imported history supports research only; synthetic extension is disabled')
                            if not candles_for(c,s['asset'],60): raise ValueError('No market history to trade')
                            if s['stake'] > s['balance']*s['max_stake_pct']/100: raise ValueError('Stake exceeds your per-trade risk limit')
                        BOT_ACTIVE=True;BOT_MESSAGE='Demo robot started. Waiting for indicator signals.'
                    else:BOT_ACTIVE=False;BOT_MESSAGE='Robot stopped. Existing demo trades will settle on next manual advance.'
                return self.send_json({'ok':True,'active':BOT_ACTIVE,'message':BOT_MESSAGE})
            if path=='/api/advance':
                if BOT_ACTIVE: raise ValueError('Stop the robot before manually advancing candles')
                market_advance()
                return self.send_json({'ok':True,'message':'Advanced one synthetic bar.'})
            if path=='/api/backtest':
                with LOCK:
                    with conn() as c:
                        s=get_settings(c)
                        asset=obj.get('asset',s['asset']); strategy=obj.get('strategy',s['strategy'])
                        stake=obj.get('stake',s['stake']);duration=obj.get('duration',s['duration'])
                        if not isinstance(asset,str) or not isinstance(strategy,str) or asset not in ASSETS or strategy not in STRATEGIES: raise ValueError('Invalid asset or strategy')
                        candles=candles_for(c,asset,10000)
                        result=backtest(candles,strategy,stake,duration,s['payout'])
                        return self.send_json(result)
            if path=='/api/reset':
                with LOCK:
                    if BOT_ACTIVE: raise ValueError('Stop the robot first')
                    with conn() as c:
                        c.execute('DELETE FROM trades')
                        set_settings(c,{'balance':10000.0})
                BOT_MESSAGE='Demo balance and trade history reset.'
                return self.send_json({'ok':True})
            return self.error_json('Unknown API endpoint',404)
        except (ValueError,TypeError,OverflowError) as exc:return self.error_json(exc,400)
        except Exception as exc:
            traceback.print_exc()
            return self.error_json('Internal error: '+str(exc),500)


def main():
    parser=argparse.ArgumentParser(description='MIKEIZU private offline demo trading app')
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--no-browser',action='store_true')
    args=parser.parse_args()
    db_initialize()
    stop=threading.Event()
    worker=threading.Thread(target=market_loop,args=(stop,),daemon=True);worker.start()
    server=ThreadingHTTPServer(('127.0.0.1',args.port),API)
    print(f'\nMIKEIZU TradeLab PRO running at http://127.0.0.1:{args.port}\nNo live broker integration. All trading is demo and synthetic.\n')
    if not args.no_browser:threading.Timer(1.0,lambda:webbrowser.open(f'http://127.0.0.1:{args.port}')).start()
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:stop.set();server.server_close()


if __name__=='__main__':main()
