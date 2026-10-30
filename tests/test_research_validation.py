"""Deterministic research acceptance tests; no market or broker performance claims."""
import copy
import math
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from engine import backtest as indicator_backtest, rsi
from strategy_research import backtest
from market_data import sample_candles,StrategyError,resample,candles_valid
from research_analytics import performance_metrics, dataset_provenance
from strategy_selector import compare_all


def directional_rows(count=2000):
    # An artificial repeating 70% directional-win fixture, not a market dataset.
    rows=[]
    for i in range(count):
        close=1.003 if (i//2)%10<7 else .997
        rows.append({'time':1_700_000_000+i*300,'open':1.0,'high':1.004,'low':.996,'close':close})
    return rows


def setup_signal(rows,values,index,strategy,parameters=None):
    return 'UP'


class ResearchValidationTests(unittest.TestCase):
    def test_next_bar_entry_and_explicit_costs(self):
        rows=directional_rows(180)
        with patch('strategy_research.signal_at',side_effect=setup_signal):
            free=backtest(rows,'RSI','scalping','5m',expiry_bars=1,stake=1,
                          commission_per_trade=0,spread_bps=0,slippage_bps=0)
            cost=backtest(rows,'RSI','scalping','5m',expiry_bars=1,stake=1,
                          commission_per_trade=.03,spread_bps=1,slippage_bps=.5)
        first=cost['trades_detail'][0]
        self.assertGreater(first['entered_at'],first['signal_at'])
        self.assertGreater(first['entry'],first['entry_mid'])
        self.assertLess(first['exit'],first['exit_mid'])
        self.assertAlmostEqual(cost['overall']['trading_costs'],cost['overall']['trades']*.03,places=5)
        self.assertLess(cost['overall']['pnl'],free['overall']['pnl'])
        self.assertGreater(cost['break_even_win_rate_pct'],free['break_even_win_rate_pct'])

    def test_high_winrate_target_does_not_gate_valid_positive_expectancy(self):
        with patch('strategy_research.signal_at',side_effect=setup_signal):
            result=backtest(directional_rows(),'RSI','scalping','5m',expiry_bars=1,
                            stake=1,target_win_rate=95,spread_bps=0,slippage_bps=0)
        self.assertTrue(result['research_pass'])
        self.assertFalse(result['validation']['benchmark_met'])
        self.assertFalse(result['validation']['benchmark_is_promotion_gate'])
        self.assertFalse(result['validation']['execution_authorized'])
        self.assertFalse(result['validation']['demo_forward_verified'])

    def test_cost_stress_can_reject_apparently_profitable_holdout(self):
        rows=directional_rows()
        for row in rows:
            row['close']=1.0003 if row['close']>1 else .9997
        with patch('strategy_research.signal_at',side_effect=setup_signal):
            result=backtest(rows,'RSI','scalping','5m',expiry_bars=1,stake=1)
        self.assertGreater(result['test']['pnl'],0)
        self.assertTrue(result['walk_forward']['passed'])
        self.assertLess(result['robustness']['cost_stress_holdout']['pnl'],0)
        self.assertFalse(result['robustness']['passed'])
        self.assertFalse(result['research_pass'])

    def test_walk_forward_folds_cannot_touch_final_holdout(self):
        with patch('strategy_research.signal_at',side_effect=setup_signal):
            result=backtest(directional_rows(),'MACD','scalping','5m',expiry_bars=3,stake=1)
        boundary=result['validation']['holdout_start_at']
        self.assertEqual(len(result['walk_forward']['folds']),3)
        for fold in result['walk_forward']['folds']:
            self.assertLess(fold['train_end_at'],fold['validation_start_at'])
            self.assertLessEqual(fold['validation_end_at'],boundary)
            self.assertEqual(fold['embargo_bars'],3)
        for trade in result['trades_detail']:
            self.assertFalse(trade['entered_at']<boundary<=trade['exited_at'])

    def test_later_data_does_not_change_training_trades(self):
        rows=directional_rows(1000)
        altered=copy.deepcopy(rows)
        boundary=700
        for row in altered[boundary:]:
            row.update(open=2.0,high=2.01,low=1.99,close=2.005)
        with patch('strategy_research.signal_at',side_effect=setup_signal):
            a=backtest(rows,'MACD','scalping','5m',expiry_bars=2,stake=1)
            b=backtest(altered,'MACD','scalping','5m',expiry_bars=2,stake=1)
        self.assertEqual(a['train'],b['train'])
        self.assertEqual(a['walk_forward'],b['walk_forward'])

    def test_provenance_changes_with_data_or_settings(self):
        rows=sample_candles(160)
        a=backtest(rows,'MACD','scalping','5m',source='synthetic')
        b=backtest(rows,'MACD','scalping','5m',source='synthetic',commission_per_trade=.02)
        changed=copy.deepcopy(rows);changed[-1]['close']=changed[-1]['open']
        c=backtest(changed,'MACD','scalping','5m',source='synthetic')
        self.assertEqual(a['provenance']['dataset_sha256'],b['provenance']['dataset_sha256'])
        self.assertNotEqual(a['provenance']['configuration_sha256'],b['provenance']['configuration_sha256'])
        self.assertNotEqual(a['provenance']['dataset_sha256'],c['provenance']['dataset_sha256'])
        self.assertEqual(a['provenance']['result_kind'],'historical_simulation')

    def test_missing_holding_bars_are_skipped(self):
        rows=directional_rows(170)
        for row in rows[68:]:row['time']+=300
        with patch('strategy_research.signal_at',side_effect=setup_signal):
            result=backtest(rows,'MACD','scalping','5m',expiry_bars=3)
        self.assertGreater(result['skipped']['missing_bars_or_market_closures'],0)

    def test_bankrupt_training_does_not_starve_independently_funded_holdout(self):
        losing=directional_rows(600)
        winning=copy.deepcopy(losing)
        boundary=int(len(losing)*.7)
        for row in losing[:boundary]:row['close']=.997
        for row in winning[:boundary]:row['close']=1.003
        with patch('strategy_research.signal_at',side_effect=setup_signal):
            a=backtest(losing,'MACD','scalping','5m',expiry_bars=1,stake=100,
                       initial_balance=100,spread_bps=0,slippage_bps=0)
            b=backtest(winning,'MACD','scalping','5m',expiry_bars=1,stake=100,
                       initial_balance=100,spread_bps=0,slippage_bps=0)
        self.assertEqual(a['train']['ending_balance'],0)
        self.assertGreater(a['skipped']['insufficient_bankroll'],0)
        self.assertGreater(a['test']['trades'],0)
        self.assertEqual(a['test'],b['test'])
        self.assertEqual(a['capital_model']['combined_funded_capital'],200)
        self.assertEqual(a['overall']['starting_balance'],200)
        self.assertAlmostEqual(a['overall']['pnl'],a['train']['pnl']+a['test']['pnl'])
        self.assertAlmostEqual(a['overall']['roi_pct'],a['overall']['pnl']/200*100)

    def test_discarded_boundary_loss_cannot_change_holdout_admission(self):
        rows=directional_rows(120)
        # Confirmation index81 would enter82 and expire86, crossing boundary84.
        # The only in-sample outcome is therefore purged. A later holdout trade
        # must still receive its declared fresh capital, rather than its loss.
        def sparse(rows,values,index,strategy,parameters=None):
            return setup_signal(rows,values,index,strategy) if index in (81,87) else None
        with patch('strategy_research.signal_at',side_effect=sparse):
            report=backtest(rows,'MACD','scalping','5m',expiry_bars=5,stake=100,
                            initial_balance=100,spread_bps=0,slippage_bps=0)
        self.assertEqual(report['train']['trades'],0)
        self.assertEqual(report['train']['ending_balance'],100)
        self.assertEqual(report['test']['trades'],1)
        self.assertGreater(report['validation']['purged_boundary_trades'],0)
        self.assertEqual(report['trades_detail'][0]['partition'],'holdout')

    def test_weekly_and_monthly_calendar_bars_are_canonical(self):
        for frame,seconds in (('1w',604800),('1mo',2592000)):
            rows=sample_candles(120,seconds)
            for row in rows:
                stamp=datetime.fromtimestamp(row['time'],timezone.utc)
                self.assertEqual((stamp.hour,stamp.minute,stamp.second),(0,0,0))
                self.assertTrue(stamp.day==1 if frame=='1mo' else stamp.weekday()==0)
            report=backtest(rows,'MACD','position',frame)
            self.assertTrue(report['data_integrity']['calendar_alignment_required'])
            misaligned=copy.deepcopy(rows)
            for row in misaligned:row['time']+=86400
            with self.assertRaises(StrategyError):backtest(misaligned,'MACD','position',frame)

    def test_resampling_drops_partial_edges_and_uses_calendar_open(self):
        start=datetime(2024,1,15,tzinfo=timezone.utc)
        rows=[{'time':int((start+timedelta(days=i)).timestamp()),'open':1,'high':1.1,'low':.9,'close':1}
              for i in range(60)]
        months=resample(rows,'1mo')
        self.assertEqual([r['time'] for r in months],[int(datetime(2024,2,1,tzinfo=timezone.utc).timestamp())])
        weeks=resample(rows,'1w')
        self.assertTrue(weeks)
        self.assertTrue(all(datetime.fromtimestamp(r['time'],timezone.utc).weekday()==0 for r in weeks))

    def test_data_and_boolean_types_fail_with_clear_validation(self):
        rows=directional_rows(120)
        for settings in ({'payout':True},{'expiry_bars':True},{'profile':[]},{'strategy':{}},
                         {'instrument':{}},{'spread_bps':False}):
            arguments={'strategy':'MACD','profile':'scalping','frame':'5m',**settings}
            with self.subTest(settings=settings),self.assertRaises(StrategyError):backtest(rows,**arguments)
        for field,value in (('time',True),('time',1.5),('time',float('inf')),('time',10**30),('close',True)):
            bad=copy.deepcopy(rows);bad[0][field]=value
            with self.subTest(field=field,value=value),self.assertRaises(StrategyError):candles_valid(bad)

    def test_parameter_bounds_and_nan_fail_closed(self):
        rows=sample_candles(160)
        for settings in ({'commission_per_trade':float('nan')},{'expiry_bars':2.2},
                         {'parameters':{'rsi_period':0}},{'parameters':{'unknown':1}},
                         {'regime_filter':'false'}):
            with self.subTest(settings=settings),self.assertRaises(StrategyError):
                backtest(rows,'MACD','scalping','5m',**settings)

    def test_selector_weights_validated(self):
        with self.assertRaises(ValueError):
            compare_all(sample_candles(160),profile='scalping',timeframe='5m',ranking_weights={'expectancy':1})

    def test_shared_metrics_are_net_and_include_losses(self):
        trades=[{'pnl':8,'commission':1,'stake':10},{'pnl':-10,'commission':1,'stake':10},
                {'pnl':4,'commission':1,'stake':10},{'pnl':-2,'commission':1,'stake':10}]
        metrics=performance_metrics(trades,100)
        self.assertEqual(metrics['wins'],2)
        self.assertEqual(metrics['losses'],2)
        self.assertEqual(metrics['expected_value_per_trade'],0)
        self.assertEqual(metrics['profit_factor'],1)
        self.assertEqual(metrics['average_winning_trade'],6)
        self.assertEqual(metrics['average_losing_trade'],-6)
        self.assertEqual(metrics['trading_costs'],4)
        self.assertEqual(len(metrics['drawdown_curve']),5)
        self.assertEqual(metrics['longest_losing_streak'],1)

    def test_empty_metrics_do_not_invent_ratios(self):
        metrics=performance_metrics([],100)
        self.assertIsNone(metrics['profit_factor'])
        self.assertIsNone(metrics['expected_value_per_trade'])
        self.assertIsNone(metrics['risk_adjusted_return'])
        self.assertEqual(metrics['equity_curve'],[100])

    def test_legacy_indicator_uses_next_open(self):
        rows=directional_rows(90)
        with patch('engine.signal_at',return_value='UP'):
            report=indicator_backtest(rows,'RSI',duration=3,spread_bps=0,slippage_bps=0)
        self.assertEqual(report['trades'][0]['entry_index'],report['trades'][0]['index']+1)
        self.assertEqual(report['trades'][0]['entry'],rows[report['trades'][0]['entry_index']]['open'])
        self.assertEqual(report['trades'][0]['exit'],rows[report['trades'][0]['exit_index']]['close'])

    def test_flat_rsi_is_neutral(self):
        self.assertEqual(rsi([1.0]*30)[-1],50)


if __name__=='__main__':unittest.main()
