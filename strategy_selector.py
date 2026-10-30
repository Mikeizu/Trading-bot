"""Transparent training-only strategy ranking, followed by ONE holdout check.

The 65% benchmark is informational. A simulated research pass never authorizes a
live order or substitutes for independent demo-forward evidence. Repeated scans
of the same holdout are not new evidence.
"""
from __future__ import annotations
import math
from market_data import candles_valid,StrategyError
from indicator_strategies import STRATEGIES,validate_parameters
from strategy_research import backtest
from market_regime import classify_regime
from research_analytics import dataset_provenance

DEFAULT_WEIGHTS = {'confidence_edge':.35,'expectancy':.25,'profit_factor':.10,
                   'risk_adjusted_return':.10,'drawdown':.15,'walk_forward':.05}


def compare_all(rows, *, profile, timeframe, payout=.8, stake=1,
                expiry_bars=3, target_win_rate=65, commission_per_trade=0.0,
                spread_bps=1.0,slippage_bps=.5,initial_balance=1000.0,parameters=None,
                regime_filter=False,regime_thresholds=None,source='unspecified',instrument=None,ranking_weights=None,parameters_by_strategy=None):
    if ranking_weights is not None and not isinstance(ranking_weights,dict):
        raise ValueError('Ranking weights must be an object')
    weights={**DEFAULT_WEIGHTS,**(ranking_weights or {})}
    if ranking_weights and set(ranking_weights)-set(DEFAULT_WEIGHTS):
        raise ValueError('Unknown ranking weight')
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not 0<=v<=1 for v in weights.values()) or abs(sum(weights.values())-1)>1e-6:
        raise ValueError('Ranking weights must be finite, nonnegative and sum to one')
    if parameters not in (None,{}):
        raise StrategyError('Compare All uses each strategy defaults; use parameters_by_strategy for explicit overrides')
    if parameters_by_strategy is None:parameters_by_strategy={}
    if not isinstance(parameters_by_strategy,dict) or set(parameters_by_strategy)-set(STRATEGIES):
        raise StrategyError('Parameters by strategy must map known strategy IDs to parameter objects')
    try:configured={strategy:validate_parameters(strategy,parameters_by_strategy.get(strategy)) for strategy in STRATEGIES}
    except ValueError as exc:raise StrategyError(str(exc)) from None
    rows=candles_valid(rows)
    regime=classify_regime(rows,thresholds=regime_thresholds)
    reports=[]
    for strategy in STRATEGIES:
        report=backtest(rows,strategy,profile,timeframe,payout=payout,
                        stake=stake,expiry_bars=expiry_bars,target_win_rate=target_win_rate,
                        commission_per_trade=commission_per_trade,spread_bps=spread_bps,
                        slippage_bps=slippage_bps,initial_balance=initial_balance,
                        parameters=configured[strategy],regime_filter=regime_filter,regime_thresholds=regime_thresholds,source=source,instrument=instrument)
        train=report['train'];hold=report['test'];count=train['trades']
        lower=train['wilson_lower_95_pct'];breakeven=report['break_even_win_rate_pct']
        expectancy=round(train['pnl']/(float(stake)*count)*100,6) if count else None
        compatible=strategy in regime['eligible_strategies']
        walk=report.get('walk_forward')
        folds=walk.get('folds') if isinstance(walk,dict) else None
        complete_folds=isinstance(folds,list) and len(folds)==3 and all(isinstance(f,dict) and isinstance(f.get('passed'),bool) for f in folds)
        fold_passes=sum(f['passed'] for f in folds) if complete_folds else 0
        walk_evidence=bool(complete_folds and isinstance(walk.get('passes'),int)
                           and not isinstance(walk.get('passes'),bool) and walk['passes']==fold_passes)
        walk_passed=bool(walk_evidence and walk.get('passed') is True and fold_passes>=2)
        # No holdout metric participates in training eligibility or score.
        eligible=bool(count>=30 and train['pnl']>0 and lower is not None and lower>breakeven
                      and train['max_drawdown_pct']<=10 and walk_passed)
        factor=train.get('profit_factor');risk_adjusted=train.get('risk_adjusted_return')
        components={
            'confidence_edge':lower-breakeven if lower is not None else 0,
            'expectancy':expectancy or 0,
            'profit_factor':max(-10,min(10,((factor or 1)-1)*10)),
            'risk_adjusted_return':max(-10,min(10,(risk_adjusted or 0)*2)),
            'drawdown':-train['max_drawdown_pct'],
            'walk_forward':10*fold_passes/len(folds) if walk_evidence else 0,
        }
        score=round(sum(weights[k]*v for k,v in components.items()),6) if eligible else None
        reports.append({'strategy':strategy,'name':STRATEGIES[strategy]['name'],
                        'train':train,'holdout':hold,'training_eligible':eligible,
                        'training_score':score,'score_components':components,'parameters':configured[strategy],
                        'strategy_version':STRATEGIES[strategy].get('version'),'family':STRATEGIES[strategy]['family'],
                        'training_expectancy_pct_of_stake':expectancy,
                        'regime_compatible':compatible,'walk_forward':walk,
                        'training_walk_forward_evidence_complete':walk_evidence,
                        'holdout_pass':report['research_pass'],'assessment':report['assessment']})
    reports.sort(key=lambda x:(x['training_score'] is not None,
                  x['training_score'] if x['training_score'] is not None else -math.inf,
                  x['train']['trades'],x['strategy']),reverse=True)
    for idx,row in enumerate(reports,1):row['rank']=idx
    candidate=next((r for r in reports if r['training_eligible']),None)
    qualified=bool(candidate and candidate['holdout_pass'] and (not regime_filter or candidate['regime_compatible']))
    winner=candidate['strategy'] if qualified else None
    if not candidate:
        verdict=('NO VALIDATED STRATEGY: none has sufficient training samples, positive net expectancy, '
                 'a lower confidence bound above assumed break-even, acceptable drawdown and training walk-forward evidence.')
    elif candidate['holdout_pass'] and regime_filter and not candidate['regime_compatible']:
        verdict=(f"TRAINING WINNER {candidate['name']} is unsuitable for the current heuristic regime. "
                 'NO VALIDATED STRATEGY for current entries; no runner-up substituted.')
    elif not qualified:
        verdict=(f"TRAINING WINNER {candidate['name']} DID NOT PASS ITS HOLDOUT CHECK. "
                 'NO VALIDATED STRATEGY. Do not substitute a runner-up using holdout scores; collect fresh unseen data.')
    else:
        verdict=(f"TRAINING WINNER {candidate['name']} passed predefined simulation research gates. "
                 'Independent demo-forward testing, parameter stability and execution validation remain required. No live authorization.')
    configuration={'profile':profile,'timeframe':timeframe,'payout':payout,'stake':stake,
                   'expiry_bars':expiry_bars,'target_win_rate':target_win_rate,'ranking_weights':weights,
                   'commission_per_trade':commission_per_trade,'spread_bps':spread_bps,
                   'slippage_bps':slippage_bps,'parameters_by_strategy':configured,'regime_filter':regime_filter,'regime_thresholds':regime_thresholds}
    return {'strategies_tested':len(reports),'ranked':reports,'training_candidate':candidate['strategy'] if candidate else None,
            'winner':winner,'winner_parameters':configured[winner] if winner else None,'qualified':qualified,'verdict':verdict,
            'selection_method':'Train-only weighted confidence edge, net expectancy, profit factor, unannualized risk-adjusted return, drawdown and purged walk-forward score; one final 30% holdout check.',
            'ranking_weights':weights,'market_regime':regime,
            'provenance':dataset_provenance(rows,source=source,instrument=instrument,timeframe=timeframe,configuration=configuration),
            'target_is_promotion_gate':False,'demo_forward_verified':False,'execution_authorized':False,
            'warning':'Assumed option payouts, spread and slippage are not authenticated Deriv quotes or CFD fills. Repeated use of a holdout creates selection bias. Rankings do not authorize trades or guarantee profits.'}
