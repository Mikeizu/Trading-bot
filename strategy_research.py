"""Causal indicator-strategy research with transparent fixed-expiry assumptions.

Training, final holdout and validation folds use independent funding. Signals
are known only after their source bar closes and fill at the next bar open.
This module is not a broker fill simulator, predictive AI or proof of accuracy.
"""
from __future__ import annotations
from datetime import datetime,timezone
import math
from market_data import TIMEFRAMES,PROFILES,StrategyError,candles_valid
from indicator_strategies import STRATEGIES,validate_parameters,warmup_bars
from engine import indicators,signal_at
from market_regime import classify_regime
from research_analytics import performance_metrics,dataset_provenance
STRATEGY_VERSION='indicator-research-3.0.0'


def _validated_parameters(strategy,parameters):
    try:return validate_parameters(strategy,parameters)
    except ValueError as exc:raise StrategyError(str(exc)) from None


def latest_signal(rows,strategy,parameters=None,*,values=None):
    rows=candles_valid(rows)
    rules=_validated_parameters(strategy,parameters)
    if values is None:values=indicators(rows,parameters=rules)
    if not rows:return None
    side=signal_at(rows,values,len(rows)-1,strategy,parameters=rules)
    if side is None:return None
    evidence=dataset_provenance(rows,configuration={'strategy':strategy,'parameters':rules})
    return {'side':side,'strategy':strategy,'strategy_version':STRATEGIES[strategy].get('version',STRATEGY_VERSION),
            'confirmed_at':rows[-1]['time'],'explanation':STRATEGIES[strategy]['rules'],
            'data_window_sha256':evidence['dataset_sha256'],'parameters':rules,
            'execution_status':'research_signal_only'}


def _bar_end(epoch,frame):
    if frame=='1mo':
        d=datetime.fromtimestamp(epoch,timezone.utc)
        return int(datetime(d.year+(d.month==12),1 if d.month==12 else d.month+1,1,tzinfo=timezone.utc).timestamp())
    return epoch+TIMEFRAMES[frame]


def _simulate_partition(rows,start,end,*,strategy,rules,values,frame,stake,payout,expiry_bars,
                        initial_balance,commission_per_trade,price_cost,regime_filter,regime_thresholds,
                        instrument,partition):
    """One funded causal experiment; a closing-bar signal fills next open.

    Boundary crossing candidates are rejected before capital or occupancy change.
    A settled outcome may fund only an entry after the corresponding bar closes.
    """
    warmup=warmup_bars(strategy,rules)
    trades=[];balance=initial_balance;next_allowed=max(warmup-1,start-1)
    skipped={'insufficient_bankroll':0,'missing_bars_or_market_closures':0,
             'regime_filter':0,'boundary_crossing':0,'warmup_bars':max(0,min(end,warmup-1)-start)}
    boundary_at=rows[end]['time'] if end<len(rows) else None
    for i in range(max(warmup-1,start-1),min(len(rows)-expiry_bars,end-1)):
        if i<next_allowed:continue
        side=signal_at(rows,values,i,strategy,parameters=rules)
        if side is None:continue
        if side not in ('UP','DOWN'):raise StrategyError('Indicator returned an invalid signal direction')
        enter=i+1;exit_idx=enter+expiry_bars-1
        if exit_idx>=end:
            skipped['boundary_crossing']+=1;continue
        end_time=_bar_end(rows[exit_idx]['time'],frame)
        if boundary_at is not None and end_time>=boundary_at:
            skipped['boundary_crossing']+=1;continue
        if any(rows[j+1]['time']!=_bar_end(rows[j]['time'],frame) for j in range(i,exit_idx)):
            skipped['missing_bars_or_market_closures']+=1;continue
        regime=classify_regime(rows[max(0,i-500):i+1],thresholds=regime_thresholds)
        if regime_filter and strategy not in regime['eligible_strategies']:
            skipped['regime_filter']+=1;continue
        if balance<stake+commission_per_trade:
            skipped['insufficient_bankroll']+=1;continue
        direction=1 if side=='UP' else -1
        entry_mid=rows[enter]['open'];exit_mid=rows[exit_idx]['close']
        entry_price=entry_mid*(1+direction*price_cost)
        exit_price=exit_mid*(1-direction*price_cost)
        contract_win=(exit_price-entry_price)*direction>0
        gross=stake*payout if contract_win else -stake
        pnl=round(gross-commission_per_trade,6);balance+=pnl
        atr_series=values.get('atr',[])
        atr_value=atr_series[i] if len(atr_series)>i else None
        invalidation=entry_mid-direction*atr_value if atr_value is not None else None
        trades.append({'signal_at':rows[i]['time'],'entered_at':rows[enter]['time'],
            'exited_at':end_time,'side':side,'strategy':strategy,'strategy_version':STRATEGIES[strategy]['version'],
            'research_model_version':STRATEGY_VERSION,
            'entry':entry_price,'exit':exit_price,'entry_mid':entry_mid,'exit_mid':exit_mid,'stake':stake,
            'gross_pnl':round(gross,6),'commission':commission_per_trade,'pnl':pnl,
            'win':pnl>0,'contract_win':contract_win,'balance':round(balance,6),
            'holding_seconds':end_time-rows[enter]['time'],'regime':regime['regime'],
            'timeframe':frame,'instrument':instrument,'explanation':STRATEGIES[strategy]['rules'],
            'invalidation':invalidation,'invalidation_used_by_model':False,
            'result_kind':'historical_simulation','partition':partition})
        next_allowed=exit_idx
    return trades,skipped


def _walk_forward(rows,split_bar,expiry_bars,initial_balance,simulate):
    """Fixed-parameter, independently funded validation BEFORE final holdout."""
    first=max(67,int(split_bar*.4))
    step=max(1,(split_bar-first)//3)
    folds=[]
    for number in range(3):
        train_end=first+number*step
        end=min(split_bar,first+(number+1)*step)
        begin=train_end+expiry_bars
        if begin>=end:continue
        start_at=rows[begin]['time'];end_at=rows[end]['time']
        selected,skipped=simulate(begin,end,'walk_forward_'+str(number+1))
        metrics=performance_metrics(selected,initial_balance,period_seconds=end_at-start_at)
        passed=bool(metrics['trades']>=10 and metrics['pnl']>0 and metrics['max_drawdown_pct']<=10)
        folds.append({'fold':number+1,'train_start_at':rows[0]['time'],
                      'train_end_at':rows[train_end]['time'],
                      'validation_start_at':start_at,'validation_end_at':end_at,
                      'train_dataset_sha256':dataset_provenance(rows[:train_end])['dataset_sha256'],
                      'validation_dataset_sha256':dataset_provenance(rows[begin:end])['dataset_sha256'],
                      'embargo_bars':expiry_bars,'initial_balance':initial_balance,
                      'metrics':metrics,'passed':passed,'skipped':skipped})
    passes=sum(f['passed'] for f in folds)
    return {'folds':folds,'passes':passes,'passed':len(folds)==3 and passes>=2,
            'method':'Three fixed-parameter expanding training/validation folds inside the first 70%; independently funded validation; holding-period embargo; crossing positions purged before capital mutation. Final 30% holdout untouched by folds.',
            'minimum_trades_per_fold':10,'required_positive_folds':2,
            'limitation':'Parameter stability across alternate configurations and independent demo-forward results remain unverified.'}


def backtest(rows,strategy,profile,frame,payout=.8,stake=5,expiry_bars=3,target_win_rate=65,
             *,commission_per_trade=0.0,spread_bps=1.0,slippage_bps=.5,initial_balance=1000.0,
             parameters=None,regime_filter=False,regime_thresholds=None,source='unspecified',instrument=None):
    """Next-bar-open theoretical fixed-expiry options research, with explicit costs.

    This is NOT a broker execution simulator or a stop-loss CFD backtest. Prices
    are shifted adversely by assumed spread and slippage; commission is deducted
    from each contract result. No real payout, latency, financing or liquidity is
    invented. Win-rate target is a research annotation, never a promotion gate.
    """
    if not isinstance(strategy,str) or strategy not in STRATEGIES:raise StrategyError('Unknown indicator strategy')
    if not isinstance(profile,str) or not isinstance(frame,str) or profile not in PROFILES or frame not in PROFILES[profile]['timeframes']:
        raise StrategyError('Timeframe is not valid for selected trading style')
    if any(isinstance(value,bool) for value in (payout,stake,expiry_bars,target_win_rate,commission_per_trade,spread_bps,slippage_bps,initial_balance)):
        raise StrategyError('Boolean values are not numeric research settings')
    try:
        payout=float(payout);stake=float(stake);target_win_rate=float(target_win_rate)
        horizon=float(expiry_bars)
        commission_per_trade=float(commission_per_trade);spread_bps=float(spread_bps)
        slippage_bps=float(slippage_bps);initial_balance=float(initial_balance)
    except (ValueError,TypeError,OverflowError) as exc:
        raise StrategyError('Research settings must be finite numbers') from exc
    values=(payout,stake,target_win_rate,horizon,commission_per_trade,spread_bps,slippage_bps,initial_balance)
    if not all(math.isfinite(v) for v in values):raise StrategyError('Research settings must be finite numbers')
    if not(.20<=payout<=1.5 and .35<=stake<=100 and 1<=horizon<=20 and horizon==int(horizon) and 40<=target_win_rate<=95):
        raise StrategyError('Payout, stake, horizon or benchmark outside safe limits')
    if not(0<=commission_per_trade<=stake and 0<=spread_bps<=100 and 0<=slippage_bps<=100 and 100<=initial_balance<=1_000_000_000):
        raise StrategyError('Costs or initial balance outside allowed research limits')
    if not isinstance(regime_filter,bool):raise StrategyError('Regime filter must be true or false')
    if not isinstance(source,str) or len(source)>200 or (instrument is not None and (not isinstance(instrument,str) or len(instrument)>100)):
        raise StrategyError('Source and instrument must be short text labels')
    classify_regime([],thresholds=regime_thresholds)
    expiry_bars=int(horizon);rules=_validated_parameters(strategy,parameters)
    rows=candles_valid(rows)
    if len(rows)<100:raise StrategyError('At least 100 completed candles are needed')
    if frame in ('1w','1mo'):
        for row in rows:
            stamp=datetime.fromtimestamp(row['time'],timezone.utc)
            aligned=(stamp.day==1 if frame=='1mo' else stamp.weekday()==0)
            if not aligned or any((stamp.hour,stamp.minute,stamp.second)):
                raise StrategyError('Weekly/monthly bars must start at their UTC calendar boundary; resample daily history first')
    split_bar=int(len(rows)*.7);split_at=rows[split_bar]['time']
    end_at=_bar_end(rows[-1]['time'],frame)
    price_cost=(spread_bps/2+slippage_bps)/10000
    values=indicators(rows,parameters=rules)
    def simulate(start,end,partition):
        return _simulate_partition(rows,start,end,strategy=strategy,rules=rules,values=values,frame=frame,
            stake=stake,payout=payout,expiry_bars=expiry_bars,initial_balance=initial_balance,
            commission_per_trade=commission_per_trade,price_cost=price_cost,
            regime_filter=regime_filter,regime_thresholds=regime_thresholds,instrument=instrument,partition=partition)
    train,train_skipped=simulate(0,split_bar,'train')
    test,test_skipped=simulate(split_bar,len(rows),'holdout')
    trades=train+test
    # Each split has its OWN funded allocation. Combined ROI uses both capital
    # allocations, rather than silently resetting cash and overstating returns.
    combined_capital=2*initial_balance
    metrics=performance_metrics(trades,combined_capital,period_seconds=end_at-rows[0]['time'])
    a=performance_metrics(train,initial_balance,period_seconds=split_at-rows[0]['time'])
    b=performance_metrics(test,initial_balance,period_seconds=end_at-split_at)
    walk=_walk_forward(rows,split_bar,expiry_bars,initial_balance,simulate)
    skipped={key:train_skipped[key]+test_skipped[key] for key in train_skipped}
    breakeven=100*(1+commission_per_trade/stake)/(payout+1)
    criteria={'minimum_train_trades':30,'minimum_holdout_trades':30,'maximum_drawdown_pct':10,
              'positive_net_expectancy_required':True,'wilson_lower_above_break_even_required':True,
              'training_walk_forward_required':True}
    stress=[]
    stress_price_cost=price_cost*2
    for trade in test:
        direction=1 if trade['side']=='UP' else -1
        stressed_entry=trade['entry_mid']*(1+direction*stress_price_cost)
        stressed_exit=trade['exit_mid']*(1-direction*stress_price_cost)
        won=(stressed_exit-stressed_entry)*direction>0
        stressed_commission=commission_per_trade*1.5
        stress.append({**trade,'pnl':round((stake*payout if won else -stake)-stressed_commission,6),
                       'commission':stressed_commission})
    stressed=performance_metrics(stress,initial_balance,period_seconds=end_at-split_at)
    stress_pass=bool(stressed['trades'] and stressed['pnl']>0 and stressed['max_drawdown_pct']<=10)
    criteria['positive_cost_stress_holdout_required']=True
    enough=a['trades']>=30 and b['trades']>=30
    qualified=bool(enough and a['pnl']>0 and b['pnl']>0 and b['wilson_lower_95_pct']>breakeven
                   and max(a['max_drawdown_pct'],b['max_drawdown_pct'])<=10 and walk['passed'] and stress_pass)
    reason=('Meets predefined simulation research gates; independent demo-forward validation is still required. This is NOT proof of future returns.' if qualified else
            'NOT VALIDATED: requires >=30 trades in both chronological splits, positive net expectancy after assumed costs, '
            'held-out 95% lower win-rate bound above fee-adjusted break-even, <=10% drawdown, and >=2 sufficient positive training walk-forward folds plus positive doubled-friction holdout. '
            'The win-rate research benchmark does not authorize trading.')
    costs={'commission_per_trade':commission_per_trade,'spread_bps':spread_bps,'slippage_bps':slippage_bps,
           'model':'Adverse half-spread plus slippage on entry and exit; fixed commission per settled contract.',
           'assumptions_verified_with_broker':False,
           'unmodeled':['Actual broker bid/ask and contract payout','latency','partial fills','rejections','liquidity','swap/financing']}
    config={'strategy':strategy,'strategy_version':STRATEGIES[strategy]['version'],
            'research_model_version':STRATEGY_VERSION,'rules_origin':'Independently defined technical indicator rules; not proprietary Qumatix algorithms',
            'profile':profile,'frame':frame,'payout':payout,'stake':stake,
            'expiry_bars':expiry_bars,'initial_balance_per_split':initial_balance,'combined_funded_capital':combined_capital,'costs':costs,
            'parameters':rules,'regime_filter':regime_filter,'regime_thresholds':regime_thresholds,'target_win_rate':target_win_rate}
    by_regime={key:performance_metrics([t for t in trades if t['regime']==key],combined_capital)
               for key in sorted({t['regime'] for t in trades})}
    return {'strategy':strategy,'strategy_version':STRATEGIES[strategy]['version'],
            'research_model_version':STRATEGY_VERSION,'indicator_version':STRATEGIES[strategy]['version'],
            'parameters':rules,'warmup_bars':warmup_bars(strategy,rules),'profile':profile,'timeframe':frame,'bars':len(rows),
            'model':'Hypothetical cost-adjusted fixed-expiry Rise/Fall, not a Deriv contract or CFD execution backtest',
            'assumed_payout_pct':round(100*payout,1),'break_even_win_rate_pct':round(breakeven,4),
            'target_win_rate_pct':target_win_rate,'train':a,'test':b,'overall':metrics,
            'capital_model':{'initial_balance_per_split':initial_balance,'combined_funded_capital':combined_capital,
                             'description':'Train and holdout are independently funded experiments. Combined equity/ROI uses both allocations; no training profit or loss changes holdout buying power.'},
            'research_pass':qualified,'assessment':reason,'walk_forward':walk,
            'robustness':{'cost_stress_holdout':stressed,'passed':stress_pass,
                          'assumptions':'Reprice the same holdout signals at double spread/slippage and 1.5x commission. Not a new independent dataset or a liquidity simulation.'},
            'validation':{'benchmark_met':bool(b['win_rate_pct'] is not None and b['win_rate_pct']>=target_win_rate),
                          'benchmark_is_promotion_gate':False,'criteria':criteria,
                          'train_end_at':split_at,'holdout_start_at':split_at,'holdout_end_at':end_at,
                          'train_dataset_sha256':dataset_provenance(rows[:split_bar])['dataset_sha256'],
                          'holdout_dataset_sha256':dataset_provenance(rows[split_bar:])['dataset_sha256'],
                          'split_policy':'Independently funded chronological experiments; boundary-crossing trades discarded before any balance or occupancy mutation.',
                          'feature_warmup':'Earlier completed bars may inform indicators; trade outcomes remain within their own experiment.',
                          'purged_boundary_trades':skipped['boundary_crossing'],'demo_forward_verified':False,
                          'parameter_stability_verified':False,'execution_authorized':False},
            'costs':costs,'provenance':dataset_provenance(rows,source=source,instrument=instrument,timeframe=frame,configuration=config),
            'market_regime':classify_regime(rows,thresholds=regime_thresholds),
            'data_integrity':{'candle_time_semantics':'UTC bar-open epochs; modeled exit at calendar bar end.',
                              'contiguous_holding_bars_required':True,'calendar_alignment_required':frame in ('1w','1mo'),
                              'missing_sessions_fabricated':False},
            'performance_breakdown':{'by_regime':by_regime,'by_timeframe':{frame:metrics},
                                     'by_instrument':{instrument or 'unspecified':metrics}},
            'skipped':skipped,
            'trades_detail':trades,'last_signal':latest_signal(rows,strategy,rules,values=values)}
