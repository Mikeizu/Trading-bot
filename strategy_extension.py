"""Broker-backed strategy monitor + DEMO-only optional automated Rise/Fall orders.

Independent of legacy indicator robot; neither runs concurrently. Active rules
are kept in RAM. Signals persist to a local SQLite audit journal, not credentials.
"""
from __future__ import annotations
from datetime import datetime,timezone
from contextlib import contextmanager
import json,sqlite3,threading,time,math,hashlib
from pathlib import Path
from naked_strategies import TIMEFRAMES, PROFILES,STRATEGIES,StrategyError,backtest,candles_valid,confirmed_signal,resample,sample_candles,validate_parameters,STRATEGY_VERSION
from deriv_bridge import BridgeError
from paper_engine import PaperBook
from strategy_selector import compare_all
from market_regime import classify_regime

GRANULARITIES={'1m':60,'5m':300,'15m':900,'1h':3600,'4h':14400,'1d':86400,'1w':86400,'1mo':86400}

def _request_object(value):
    if not isinstance(value,dict):raise StrategyError('Strategy request must be a JSON object')
    return value

def _frame(value):
    if not isinstance(value,str) or value not in TIMEFRAMES:raise StrategyError('Invalid timeframe')
    return value

def _limit(value):
    if isinstance(value,bool) or not isinstance(value,int) or not 1<=value<=10000:
        raise StrategyError('Event limit must be an integer from 1 to 10000')
    return value

class SignalBook:
    def __init__(self,path):
        self.path=Path(path)
        self.lock=threading.RLock()
        with self._connect() as c:
            c.execute('''CREATE TABLE IF NOT EXISTS strategy_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, account_id TEXT NOT NULL,
                mode TEXT NOT NULL, symbol TEXT NOT NULL, timeframe TEXT NOT NULL,
                strategy TEXT NOT NULL, confirmed_at INTEGER NOT NULL, side TEXT NOT NULL,
                action TEXT NOT NULL, explanation TEXT NOT NULL, detail TEXT NOT NULL,
                event_at INTEGER NOT NULL,
                UNIQUE (account_id,symbol,timeframe,strategy,confirmed_at))''')
            columns={r[1] for r in c.execute('PRAGMA table_info(strategy_events)')}
            for key,kind in {'strategy_version':'TEXT','regime':'TEXT','data_hash':'TEXT','evidence':'TEXT'}.items():
                if key not in columns:c.execute(f'ALTER TABLE strategy_events ADD COLUMN {key} {kind}')
            c.execute('''CREATE TABLE IF NOT EXISTS strategy_event_history(
                id INTEGER PRIMARY KEY AUTOINCREMENT,event_id INTEGER NOT NULL,
                account_id TEXT NOT NULL,action TEXT NOT NULL,detail TEXT NOT NULL,event_at INTEGER NOT NULL)''')
    @contextmanager
    def _connect(self):
        c=sqlite3.connect(self.path,timeout=10)
        try:
            yield c;c.commit()
        except Exception:c.rollback();raise
        finally:c.close()
    def record(self,acct,mode,symbol,tf,strategy,signal,action,detail):
        if (not all(isinstance(x,str) and x for x in (acct,symbol,strategy,action))
                or mode not in ('demo','real') or not isinstance(signal,dict)):
            raise StrategyError('A valid broker signal identity is required')
        _frame(tf)
        stamp=signal.get('confirmed_at')
        if (isinstance(stamp,bool) or not isinstance(stamp,(int,float)) or not math.isfinite(stamp)
                or not 0<=stamp<=253402300799 or stamp!=int(stamp) or signal.get('side') not in ('UP','DOWN')
                or not isinstance(signal.get('explanation'),str) or not signal['explanation']):
            raise StrategyError('Signal time, direction and explanation are required')
        if not isinstance(signal.get('evidence',{}),dict):raise StrategyError('Signal evidence must be an object')
        with self.lock,self._connect() as c:
            cur=c.execute('''INSERT OR IGNORE INTO strategy_events
                (account_id,mode,symbol,timeframe,strategy,confirmed_at,side,action,explanation,detail,event_at,strategy_version,regime,data_hash,evidence)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(acct,mode,symbol,tf,strategy,
                signal['confirmed_at'],signal['side'],action,signal['explanation'],detail,int(time.time()),
                signal.get('strategy_version',STRATEGY_VERSION),signal.get('regime'),signal.get('data_hash'),
                json.dumps(signal.get('evidence',{}),allow_nan=False,sort_keys=True)))
            inserted=cur.rowcount==1
            if inserted:
                c.execute('INSERT INTO strategy_event_history(event_id,account_id,action,detail,event_at) VALUES (?,?,?,?,?)',
                          (cur.lastrowid,acct,action,str(detail)[:1200],int(time.time())))
            return inserted
    def outcome(self,acct,symbol,tf,strategy,confirmed_at,action,detail):
        with self.lock,self._connect() as c:
            c.execute('''UPDATE strategy_events SET action=?,detail=? WHERE account_id=? AND symbol=? AND timeframe=? AND strategy=? AND confirmed_at=?''',
                      (action,str(detail)[:1200],acct,symbol,tf,strategy,confirmed_at))
            row=c.execute('SELECT id FROM strategy_events WHERE account_id=? AND symbol=? AND timeframe=? AND strategy=? AND confirmed_at=?',
                          (acct,symbol,tf,strategy,confirmed_at)).fetchone()
            if row:
                c.execute('INSERT INTO strategy_event_history(event_id,account_id,action,detail,event_at) VALUES (?,?,?,?,?)',
                          (row[0],acct,action,str(detail)[:1200],int(time.time())))
    def recent(self,account_id,limit=75):
        _limit(limit)
        with self.lock,self._connect() as c:
            c.row_factory=sqlite3.Row
            return [dict(x) for x in c.execute('SELECT * FROM strategy_events WHERE account_id=? ORDER BY id DESC LIMIT ?', (account_id,limit))]
    def history(self,account_id,limit=250):
        _limit(limit)
        with self.lock,self._connect() as c:
            c.row_factory=sqlite3.Row
            return [dict(x) for x in c.execute('SELECT * FROM strategy_event_history WHERE account_id=? ORDER BY id DESC LIMIT ?', (account_id,limit))]

class StrategySupervisor:
    def __init__(self,broker,db_path):
        self.broker=broker
        self.book=SignalBook(db_path)
        self.paper=PaperBook(Path(db_path).with_name("naked_paper.db"))
        self.lock=threading.RLock()
        self.active=False
        self.strategy='kangaroo';self.profile='scalping';self.frame='5m'
        self.symbol='';self.action='monitor';self.stake=1;self.expiry_minutes=3
        self.last_candle=None;self.account_id='';self.last_note='Stopped'
        self.last_error='';self.last_check=None
        self.best_selection=None;self.auto_selected=False;self.min_demo_payout=None
        self.parameters=validate_parameters();self.regime_thresholds=None
        self.last_regime=None;self.last_calendar=None;self.last_explanation=None;self.account_mode=''

    def _execution_enabled(self):
        """A persisted application/account kill also gates virtual new entries."""
        risk=getattr(self.broker,'risk',None)
        if risk is None or not callable(getattr(risk,'status',None)):
            raise BridgeError('Persistent risk controls are unavailable; automatic entries are blocked')
        state=risk.status(self.broker.account_id,self.broker.mode)
        if (not isinstance(state,dict) or not isinstance(state.get('global'),dict)
                or not isinstance(state.get('killed'),bool)
                or not isinstance(state['global'].get('killed'),bool)):
            raise BridgeError('Persistent risk status is incomplete; automatic entries are blocked')
        if state.get('killed') or state.get('global',{}).get('killed'):
            raise BridgeError('Emergency stop is active; explicitly resume in Risk Control Center before starting new entries')

    def stop(self,reason='Stopped by user'):
        with self.lock:
            self.active=False;self.last_note=reason
            if self.account_id:
                self.paper.cancel_pending(self.account_id,self.symbol,self.frame,reason)
        return self.status()

    def _calendar_status(self,symbol):
        risk=getattr(self.broker,'risk',None)
        if risk is None or not hasattr(risk,'calendar_status'):
            return {'allowed':False,'required':True,'fresh':False,
                    'reasons':['Calendar risk control unavailable; automatic entries blocked']}
        kind=self.broker._market_kind(symbol) if hasattr(self.broker,'_market_kind') else 'unknown'
        return risk.calendar_status(self.broker.account_id,self.broker.mode,symbol,kind)

    def status(self):
        # All identity-linked records must describe one broker session snapshot.
        # stop() releases self.lock before requesting this snapshot, so it can
        # still interrupt a quote while the network call holds broker.lock.
        with self.broker.lock,self.lock:
            return {'active':self.active,'strategy':self.strategy,'profile':self.profile,
              'frame':self.frame,'symbol':self.symbol,'action':self.action,
              'account_id':self.account_id,'stake':self.stake,'expiry_minutes':self.expiry_minutes,
              'last_candle':self.last_candle,'last_check':self.last_check,
              'auto_selected':self.auto_selected,
              'strategy_version':STRATEGY_VERSION,'parameters':self.parameters,
              'regime':self.last_regime,'calendar':self.last_calendar,'explanation':self.last_explanation,
              'paper_model':self.paper.VERSION,
              'best_selection':({k:self.best_selection[k] for k in ('winner','qualified','source','symbol','timeframe','created_at')}
                   if self.best_selection else None),
              'message':self.last_note,'error':self.last_error,
              'events':self.book.recent(self.broker.account_id) if self.broker.account_id else [],
              'event_history':self.book.history(self.broker.account_id) if self.broker.account_id else [],
              'paper_balance':self.paper.balance(self.broker.account_id) if self.broker.account_id else None,
              'paper_positions':self.paper.positions(self.broker.account_id) if self.broker.account_id else []}

    def configure(self,obj,*,validated_best=False):
        _request_object(obj)
        # Consistent broker -> supervisor lock order (also used by HTTP kill).
        with self.broker.lock,self.lock:
            if self.active:raise BridgeError('Stop the current strategy monitor before switching rules')
            if self.broker.mode not in ('demo','real'):
                raise BridgeError('Connect to your Deriv broker account first')
            strat=obj.get('strategy');profile=obj.get('profile');frame=obj.get('timeframe')
            sym=obj.get('symbol');action=obj.get('action','monitor')
            if not isinstance(strat,str) or strat not in STRATEGIES:raise StrategyError('Unknown Naked Forex strategy')
            if not isinstance(profile,str) or profile not in PROFILES or not isinstance(frame,str) or frame not in PROFILES[profile]['timeframes']:
                raise StrategyError('Timeframe does not match the trading style')
            if not isinstance(sym,str):raise StrategyError('Market symbol must be text')
            if sym not in {s['symbol'] for s in self.broker.allowed_symbols}:
                raise BridgeError('Choose an available Deriv market from the Broker tab')
            if action not in ('monitor','paper_trade','demo_trade'):
                raise StrategyError('Choose monitor, virtual paper position, or demo option')
            if action!='monitor':self._execution_enabled()
            parameters=validate_parameters(obj.get('parameters'))
            thresholds=obj.get('regime_thresholds')
            classify_regime([],thresholds=thresholds)  # validate before activation
            try:stake=float(obj.get('stake',1));horizon=float(obj.get('expiry_minutes',3));expiration=int(horizon)
            except (TypeError,ValueError,OverflowError):raise StrategyError('Invalid stake/expiry') from None
            if (isinstance(obj.get('stake'),bool) or isinstance(obj.get('expiry_minutes'),bool)
                  or not math.isfinite(stake) or horizon!=expiration or not .35<=stake<=5 or not 1<=expiration<=15):
                raise StrategyError('Demo robot stake must be $0.35–$5 and expiry 1–15 minutes')
            if action=='demo_trade':
                if self.broker.mode!='demo':raise BridgeError('Only a Deriv DEMO account may execute automated orders')
                if frame not in ('1m','5m','15m'):
                    raise BridgeError('Automatic Deriv Rise/Fall orders are limited to 1m/5m/15m signal charts; longer-term signals are monitor-only')
                if self.broker.automation:raise BridgeError('Stop the existing Deriv indicator robot before starting the Naked Forex robot')
                durations=self.broker.available_durations(sym)
                requested=expiration
                if requested not in durations['UP'] or requested not in durations['DOWN']:
                    raise BridgeError('The selected market does not offer both Rise and Fall contracts '
                                      f'at {requested} minutes. Available UP: {durations["UP"]}; '
                                      f'DOWN: {durations["DOWN"]}. Choose a supported expiry or market. '
                                      'No automated orders started.')
            self.strategy=strat;self.profile=profile;self.frame=frame;self.symbol=sym
            self.action=action;self.stake=stake;self.expiry_minutes=expiration
            self.account_id=self.broker.account_id;self.account_mode=self.broker.mode;self.last_candle=None
            self.parameters=parameters;self.regime_thresholds=thresholds
            self.last_regime=None;self.last_calendar=None;self.last_explanation=None
            self.auto_selected=validated_best
            self.min_demo_payout=(float(obj['_min_net_payout']) if validated_best else None)
            self.active=True;self.last_error=''
            self.last_note=('DEMO auto-order mode armed; purchases require confirmed closed candles and broker risk checks.'
                if action=='demo_trade' else ('PAPER position robot running; no broker orders.' if action=='paper_trade' else 'Live market MONITOR running: signals logged, no broker orders.'))
            return self.status()

    def read_closed(self,symbol,frame,*,research=False):
        """Read authentic Deriv candles; NEVER include a bar still forming.
        W/M are locally aggregated from daily UTC bars. We do not fabricate
        unsupported native weekly/monthly candle intervals.
        """
        _frame(frame)
        if not isinstance(research,bool):raise StrategyError('research must be a boolean')
        gran=GRANULARITIES[frame]
        # Match the adapter's supported single-request history bound. Longer
        # monthly research can legitimately need more data than this provides;
        # report insufficiency instead of inventing history or unsupported paging.
        count=2500 if research or frame in ('1w','1mo') else 600
        rows=self.broker.transport.candles(symbol,count=count,granularity=gran)
        rows=candles_valid(rows)
        now=int(time.time())
        rows=[c for c in rows if c['time']+gran <=now]
        if frame in ('1w','1mo'):
            rows=resample(rows,frame)
            if rows:
                last_dt=datetime.fromtimestamp(rows[-1]['time'],timezone.utc)
                this=datetime.fromtimestamp(now,timezone.utc)
                incomplete=(last_dt.year,last_dt.month)==(this.year,this.month) if frame=='1mo' else last_dt.isocalendar()[:2]==this.isocalendar()[:2]
                if incomplete:rows=rows[:-1]
        return rows

    def sample(self,frame):
        _frame(frame)
        base=TIMEFRAMES[frame]
        if frame in ('1w','1mo'):
            # Simulated WEEKLY/MONTHLY bars, not a resampling of broker data.
            return sample_candles(count=280,granularity=base)
        return sample_candles(count=1400,granularity=base)

    def _history(self,obj):
        """One immutable source used for ALL competing patterns in a scan."""
        _request_object(obj)
        src=obj.get('source','synthetic');frame=obj.get('timeframe','5m')
        _frame(frame)
        if src=='synthetic':rows=self.sample(frame)
        elif src=='csv':rows=candles_valid(obj.get('candles'))
        elif src=='deriv':
            with self.broker.lock:
                if self.broker.mode=='disconnected':
                    raise BridgeError('Connect to Deriv before fetching authentic broker candles')
                symbol=obj.get('symbol')
                if not isinstance(symbol,str) or symbol not in {s['symbol'] for s in self.broker.allowed_symbols}:
                    raise BridgeError('Choose a market listed by Deriv')
                rows=self.read_closed(symbol,frame,research=True)
        else:raise StrategyError('Unknown historical source')
        return rows,src,frame

    @staticmethod
    def _source_label(src):
        return {'synthetic':'Synthetic sample — no broker market history',
                'deriv':'Official Deriv historical candles',
                'csv':'User-provided CSV'}[src]

    def research(self,obj):
        rows,src,frame=self._history(obj)
        report=backtest(rows,obj.get('strategy','kangaroo'),obj.get('profile','scalping'),frame,
            payout=obj.get('payout',.8),stake=obj.get('stake',1),
            expiry_bars=obj.get('expiry_bars',3),target_win_rate=obj.get('target_win_rate',65),
            **self._research_options(obj,src))
        report['source']=self._source_label(src)
        report['warning']='Research only. Assumed payout is not a broker quotation. Results cannot validate multi-day forex/CFD stop-loss strategies.'
        return report

    @staticmethod
    def _research_options(obj,src):
        return {'commission_per_trade':obj.get('commission_per_trade',0),
                'spread_bps':obj.get('spread_bps',1),'slippage_bps':obj.get('slippage_bps',.5),
                'parameters':obj.get('parameters'),'regime_filter':obj.get('regime_filter',False),
                'source':src,'instrument':obj.get('symbol') or obj.get('instrument'),
                'initial_balance':obj.get('initial_balance',1000.)}

    def scan_all(self,obj):
        """Select using training data ONLY; retain successful Deriv-only selection.

        Running again against the SAME held-out interval is not fresh validation.
        Scans never submit orders or change a running trading strategy.
        """
        _request_object(obj)
        classify_regime([],thresholds=obj.get('regime_thresholds'))
        with self.broker.lock:
            source_identity=(self.broker.account_id,self.broker.mode)
            rows,src,frame=self._history(obj)
        # Preserve raw inputs for the backtest's strict validator; int() here
        # used to silently turn a requested 1.5-bar horizon into one bar.
        payout=obj.get('payout',.8);stake=obj.get('stake',1)
        expiry_bars=obj.get('expiry_bars',3);target=obj.get('target_win_rate',65)
        compared=compare_all(rows,profile=obj.get('profile','scalping'),timeframe=frame,
                             payout=payout,stake=stake,expiry_bars=expiry_bars,
                             target_win_rate=target,ranking_weights=obj.get('ranking_weights'),
                             **self._research_options(obj,src))
        payout=float(payout);stake=float(stake);expiry_bars=int(expiry_bars);target=float(target)
        compared.update({'source':self._source_label(src),'source_kind':src,
                'symbol':obj.get('symbol') if src=='deriv' else None,
                'profile':obj.get('profile','scalping'),'timeframe':frame,
                'bars':len(rows),'assumed_payout_pct':round(100*payout,2),
                'expiry_bars':expiry_bars,'target_win_rate_pct':target})
        # A synthetic/CSV ranking is for study, never an authorization to
        # automatically submit broker DEMO trades.
        with self.broker.lock,self.lock:
            linked=(src=='deriv' and self.broker.mode in ('demo','real') and
                    (self.broker.account_id,self.broker.mode)==source_identity)
            # Require a current completed broker bar; an old CSV cannot masquerade as this.
            if linked:
                max_lag=max(3600,3*TIMEFRAMES[frame])
                is_fresh=bool(rows and 0<=int(time.time())-rows[-1]['time']<=max_lag)
            else:is_fresh=False
            deployable=bool(linked and is_fresh and compared['qualified'])
            compared['auto_eligible']=deployable
            compared['deployment_note']=(
                'Eligible for explicit one-click auto-selection in MONITOR/PAPER mode; Deriv DEMO option execution also requires an available short timeframe and a demo account.'
                if deployable else
                'NOT ARMED. Requires a qualified train/holdout result on fresh authentic Deriv history from the connected account. Synthetic/CSV results cannot authorize automatic deployment.')
            self.best_selection={
                'winner':compared['winner'] if deployable else None,
                'qualified':deployable,'source':src,'symbol':obj.get('symbol') if src=='deriv' else None,
                'profile':obj.get('profile','scalping'),'timeframe':frame,
                'account_id':self.broker.account_id if linked else None,
                'mode':self.broker.mode if linked else None,
                'created_at':int(time.time()),'assumed_payout':payout,
                'expiry_bars':expiry_bars,
                'parameters':validate_parameters(obj.get('parameters')),
                'regime_thresholds':obj.get('regime_thresholds'),
                'research_options':self._research_options(obj,src),
                'last_market_time':rows[-1]['time'] if rows else None}
        return compared

    def activate_best(self,obj):
        """Start the server-selected pattern. Client cannot supply or forge winner."""
        _request_object(obj)
        with self.broker.lock,self.lock:
            selection=self.best_selection
            if self.active:raise BridgeError('Stop the current strategy before starting the selected best')
            if not selection or not selection['qualified'] or not selection['winner']:
                raise BridgeError('No validated broker-data strategy. Run Compare All and check the holdout result.')
            age=int(time.time())-selection['created_at']
            if not 0<=age<=3600:
                raise BridgeError('Comparison is over one hour old. Run the scan again before activation.')
            if (self.broker.mode=='disconnected' or self.broker.account_id!=selection['account_id']
                  or self.broker.mode!=selection['mode']):
                raise BridgeError('Broker account changed since comparison. Scan again.')
            if selection['source']!='deriv':
                raise BridgeError('Synthetic/CSV research cannot deploy a broker-connected strategy.')
            action=obj.get('action','monitor')
            if action not in ('monitor','paper_trade','demo_trade'):
                raise StrategyError('Invalid automatic action')
            if action=='demo_trade':
                expected_minutes=TIMEFRAMES[selection['timeframe']]/60*selection['expiry_bars']
                try:
                    requested=float(obj.get('expiry_minutes',3))
                    if isinstance(obj.get('expiry_minutes'),bool) or not math.isfinite(requested) or not requested.is_integer():
                        raise ValueError()
                except (ValueError,TypeError,OverflowError):raise StrategyError('Demo expiry must be a finite integer') from None
                if (expected_minutes>15 or expected_minutes<1 or
                    expected_minutes!=requested):
                    raise BridgeError(
                        f'Demo expiry must equal tested bar horizon: {expected_minutes:g} minutes. '
                        'Only 1–15 minute Deriv contracts are supported; choose shorter bars or another timeframe, rescan, then match contract expiry.')
            # Build from server-side validated winner; never trust client strategy or asset.
            options={'strategy':selection['winner'],'profile':selection['profile'],
              'timeframe':selection['timeframe'],'symbol':selection['symbol'],
              'action':action,'stake':obj.get('stake',1),
              'expiry_minutes':obj.get('expiry_minutes',3),
              'parameters':selection.get('parameters'),
              'regime_thresholds':selection.get('regime_thresholds'),
              '_min_net_payout':selection['assumed_payout']}
            return self.configure(options,validated_best=True)

    def tick(self):
        with self.lock:
            if not self.active:return
            st,profile,frame,sym,action,acct,stake,exp=(self.strategy,self.profile,self.frame,self.symbol,
                                        self.action,self.account_id,self.stake,self.expiry_minutes)
            mode=self.account_mode;parameters=dict(self.parameters);thresholds=self.regime_thresholds
        try:
            with self.broker.lock:
                if self.broker.mode=='disconnected' or self.broker.account_id!=acct or self.broker.mode!=mode:
                    raise BridgeError('Account changed/disconnected. Strategy stopped to protect session')
                if action=='demo_trade' and self.broker.mode!='demo':
                    raise BridgeError('Demo bot cannot run on a real account')
                if action!='monitor':self._execution_enabled()
                rows=self.read_closed(sym,frame)
                calendar=self._calendar_status(sym)
            age=int(time.time())-rows[-1]['time'] if rows else None
            fresh=bool(rows and age is not None and 0<=age<=max(3*TIMEFRAMES[frame],180))
            with self.lock:self.last_calendar=calendar
            if action=='paper_trade' and rows:
                if not calendar['allowed'] or not fresh:
                    self.paper.cancel_pending(acct,sym,frame,'Calendar restricted or market data stale before virtual entry')
                self.paper.reconcile(acct,sym,frame,rows)
            if len(rows)<70:
                with self.lock:self.last_note=f'Need at least 70 completed {frame} candles (have {len(rows)}); no order.'
                return
            regime=classify_regime(rows,thresholds=thresholds,
                  max_age_seconds=max(3*TIMEFRAMES[frame],180),
                  news_state=('restricted' if calendar.get('fresh') and not calendar['allowed'] else
                              'fresh' if calendar.get('fresh') else 'unavailable'),
                  require_news=action!='monitor' and calendar.get('required',True))
            with self.lock:self.last_regime=regime
            if not fresh:
                with self.lock:self.last_note='Stale or future-dated market candles; no new signal or entry.'
                return
            latest=rows[-1]['time']
            with self.lock:
                if not self.active or self.last_candle==latest:return
                self.last_candle=latest;self.last_check=int(time.time())
            sig=confirmed_signal(rows,st,parameters=parameters)
            if not sig:
                with self.lock:self.last_note=f'Checked {frame} close; no {STRATEGIES[st]["name"]} confirmation.'
                return
            if sig.get('confirmed_at')!=latest:
                raise BridgeError('Signal is not linked to the latest completed candle; no order')
            evidence={'source':'deriv','instrument':sym,'timeframe':frame,'first_bar':rows[0]['time'],
                'last_bar':latest,'bars':len(rows),'parameters':parameters,
                'strategy_version':STRATEGY_VERSION,'regime':regime,'calendar':calendar}
            sig={**sig,'strategy_version':STRATEGY_VERSION,'regime':regime['regime'],
                 'data_hash':hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest(),
                 'evidence':evidence}
            with self.lock:self.last_explanation={**sig,'execution_status':'awaiting_validation'}
            # Signal persistence before order, even if the order is later declined.
            # Never submit again for same event after restart: unique DB constraint.
            inserted=self.book.record(acct,mode,sym,frame,st,sig,'SIGNAL','Confirmed candle signal; not an order or fill')
            if not inserted:return
            if action=='monitor':
                self.book.outcome(acct,sym,frame,st,latest,'SIGNAL_ONLY','Monitoring only; no order submitted')
                with self.lock:self.last_note=f'{sig["side"]} signal confirmed on {sym} {frame}; monitor-only, NO ORDER.'
                return
            if not calendar['allowed']:
                note='New entry blocked by economic-calendar controls: '+'; '.join(calendar['reasons'])
                self.book.outcome(acct,sym,frame,st,latest,'BLOCKED_CALENDAR',note)
                with self.lock:
                    self.last_note=note;self.last_explanation['execution_status']='blocked_calendar'
                return
            if not regime['trading_allowed'] or st not in regime['eligible_strategies']:
                note='New entry blocked by regime rules: '+'; '.join(regime['reasons'])
                self.book.outcome(acct,sym,frame,st,latest,'BLOCKED_REGIME',note)
                with self.lock:
                    self.last_note=note;self.last_explanation['execution_status']='blocked_regime'
                return
            if action=='paper_trade':
                with self.broker.lock,self.lock:
                    self._execution_enabled()
                    if not self.active or self.broker.account_id!=acct or self.broker.mode!=mode:
                        raise BridgeError('Account changed; virtual entry cancelled')
                    paper_id=self.paper.open(acct,sym,frame,st,sig,rows[-1]['close'])
                self.book.outcome(acct,sym,frame,st,latest,'PAPER_PENDING' if paper_id else 'PAPER_DUPLICATE',
                         f'Virtual order {paper_id}; next completed candle open required' if paper_id else 'Existing virtual position; skipped')
                with self.lock:self.last_note=(f'PAPER order #{paper_id} queued on {sym} {frame}; waits for next candle open. No broker order.' if paper_id else 'Existing virtual position; duplicate skipped.')
                return
            with self.broker.lock:
                if not self.active or self.broker.mode!='demo' or self.broker.account_id!=acct:
                    raise BridgeError('Trading session changed; order cancelled')
                # Deny if any legacy or supervisor bot is in a conflicting state.
                if self.broker.automation:raise BridgeError('Legacy demo robot is running; strategy order blocked')
                # new_quote / buy_quote re-check broker account, portfolio, journal, risk caps.
                q=self.broker.new_quote(sym,sig['side'],stake,exp,internal=True,
                    context={'strategy':st,'strategy_version':STRATEGY_VERSION,'timeframe':frame,
                             'signal_at':latest,'regime':regime['regime'],'rationale':sig['explanation']})
                if self.auto_selected and self.min_demo_payout is not None:
                    try:
                        gross=float(q['payout']); paid=float(q['ask_price'])
                        net_ratio=(gross-paid)/paid
                        valid=math.isfinite(net_ratio) and net_ratio>=self.min_demo_payout-1e-8
                    except (TypeError,ValueError,ZeroDivisionError):valid=False
                    if not valid:
                        self.broker.quote=None
                        raise BridgeError('Actual Deriv demo proposal payout is lower than research assumption or missing. No order placed; strategy stopped.')
                with self.lock:
                    if not self.active:
                        self.broker.quote=None
                        raise BridgeError('Strategy stopped before purchase; no order submitted')
                self.broker.buy_quote(q['token'],internal=True)
            self.book.outcome(acct,sym,frame,st,latest,'BROKER_ACCEPTED','Demo broker accepted purchase; inspect durable order/settlement journal')
            with self.lock:self.last_note=f'Deriv DEMO order sent: {sig["side"]} on {sym}; inspect broker journal.'
        except Exception as exc:
            # Fail closed on ANY broker error, unknown execution or timeout; no retry.
            with self.lock:
                self.active=False
                self.last_error=str(exc)[:220]
                self.last_note='Strategy stopped. Inspect Deriv broker journal and verify account.'
            if 'sig' in locals() and sig and 'latest' in locals():
                try:
                    self.book.outcome(acct,sym,frame,st,latest,'BLOCKED_OR_UNCERTAIN',
                                      'Execution failed or uncertain; inspect broker order journal. '+str(exc)[:200])
                except Exception:
                    with self.lock:self.last_note='Strategy stopped; signal audit unavailable. Inspect persistent broker order journal.'

    def loop(self,stop_event):
        while not stop_event.wait(25):
            if self.active:self.tick()
