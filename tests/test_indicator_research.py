"""Indicator research contracts; artificial OHLC is never broker evidence."""
import copy
import json
import unittest
from unittest.mock import patch

from market_data import StrategyError,sample_candles
from indicator_strategies import STRATEGIES,validate_parameters,warmup_bars
from strategy_research import backtest
from strategy_selector import compare_all


class IndicatorResearchTests(unittest.TestCase):
    def setUp(self):
        self.rows=sample_candles(450,300)

    def test_entire_catalog_has_finite_honest_research_reports(self):
        self.assertGreaterEqual(len(STRATEGIES),18)
        for strategy in STRATEGIES:
            with self.subTest(strategy=strategy):
                report=backtest(self.rows,strategy,'scalping','5m',source='synthetic fixture')
                json.dumps(report,allow_nan=False)
                self.assertEqual(report['strategy'],strategy)
                self.assertEqual(report['parameters'],validate_parameters(strategy))
                self.assertEqual(report['overall']['trades'],report['train']['trades']+report['test']['trades'])
                self.assertFalse(report['validation']['execution_authorized'])
                self.assertFalse(report['validation']['demo_forward_verified'])
                self.assertEqual(report['provenance']['source'],'synthetic fixture')

    def test_catalog_research_has_no_removed_strategy_identifiers(self):
        removed={'kangaroo','shadow','belt','wammie','moolah','last_kiss','trendy_kangaroo'}
        self.assertFalse(removed.intersection(STRATEGIES))
        report=compare_all(self.rows,profile='scalping',timeframe='5m')
        self.assertEqual(report['strategies_tested'],len(STRATEGIES))
        self.assertEqual({row['strategy'] for row in report['ranked']},set(STRATEGIES))
        self.assertFalse(report['execution_authorized'])
        self.assertFalse(report['target_is_promotion_gate'])

    def test_comparison_retains_every_strategy_configuration(self):
        report=compare_all(self.rows,profile='scalping',timeframe='5m')
        configured=report['provenance']['configuration']['parameters_by_strategy']
        for row in report['ranked']:
            self.assertEqual(row['parameters'],validate_parameters(row['strategy']))
            self.assertEqual(configured[row['strategy']],row['parameters'])
            self.assertEqual(row['family'],STRATEGIES[row['strategy']]['family'])

    def test_comparison_rejects_ambiguous_global_override(self):
        with self.assertRaisesRegex(StrategyError,'parameters_by_strategy'):
            compare_all(self.rows,profile='scalping',timeframe='5m',parameters={'period':14})
        with self.assertRaises(StrategyError):
            compare_all(self.rows,profile='scalping',timeframe='5m',parameters_by_strategy={'REMOVED':{}})

    def test_comparison_winner_parameters_come_from_selected_server_report(self):
        def report(rows,strategy,*args,**kwargs):
            good=strategy=='RSI'
            train={'trades':60,'pnl':100 if good else -100,'wilson_lower_95_pct':70 if good else 20,
                   'max_drawdown_pct':1,'profit_factor':3,'risk_adjusted_return':2}
            return {'train':train,'test':train,'break_even_win_rate_pct':55.56,'research_pass':good,
                    'assessment':'fictional deterministic ranking fixture',
                    'walk_forward':{'passed':True,'passes':3,'folds':[{'passed':True} for _ in range(3)]}}
        with patch('strategy_selector.backtest',side_effect=report):
            compared=compare_all(self.rows,profile='scalping',timeframe='5m')
        self.assertEqual(compared['winner'],'RSI')
        self.assertEqual(compared['winner_parameters'],validate_parameters('RSI'))
        self.assertFalse(compared['execution_authorized'])

    def test_missing_or_inconsistent_walk_forward_cannot_qualify_a_winner(self):
        metrics={'trades':100,'pnl':100,'wilson_lower_95_pct':75,'max_drawdown_pct':1,
                 'profit_factor':4,'risk_adjusted_return':2}
        for walk in (None,{'passed':True},
                     {'passed':True,'passes':3,'folds':[{'passed':False} for _ in range(3)]}):
            report={'train':metrics,'test':metrics,'break_even_win_rate_pct':55.56,
                    'research_pass':True,'assessment':'fault injection; not market evidence'}
            if walk is not None:report['walk_forward']=walk
            with self.subTest(walk=walk),patch('strategy_selector.backtest',return_value=report):
                compared=compare_all(self.rows,profile='scalping',timeframe='5m')
            self.assertFalse(compared['qualified'])
            self.assertIsNone(compared['winner'])
            self.assertTrue(all(not r['training_eligible'] for r in compared['ranked']))

    def test_configured_warmup_and_version_are_reported_and_enforced(self):
        parameters={'ema_slow_period':150}
        required=warmup_bars('EMA_CROSS',parameters)
        with patch('strategy_research.signal_at',return_value='UP'):
            report=backtest(self.rows,'EMA_CROSS','scalping','5m',parameters=parameters)
        self.assertEqual(report['warmup_bars'],required)
        self.assertTrue(report['trades_detail'])
        self.assertTrue(all(t['signal_at']>=self.rows[required-1]['time'] for t in report['trades_detail']))
        self.assertEqual(report['strategy_version'],STRATEGIES['EMA_CROSS']['version'])
        self.assertEqual(report['provenance']['strategy_version'],STRATEGIES['EMA_CROSS']['version'])
        self.assertEqual(report['provenance']['configuration']['research_model_version'],report['research_model_version'])
        self.assertTrue(all(t['strategy_version']==report['strategy_version'] for t in report['trades_detail']))

    def test_threshold_change_is_recorded_in_research_provenance(self):
        a=backtest(self.rows,'RSI','scalping','5m',regime_filter=True)
        thresholds={'trend_efficiency':.45}
        b=backtest(self.rows,'RSI','scalping','5m',regime_filter=True,regime_thresholds=thresholds)
        self.assertNotEqual(a['provenance']['configuration_sha256'],b['provenance']['configuration_sha256'])
        self.assertEqual(b['provenance']['configuration']['regime_thresholds'],thresholds)

    def test_invalid_regime_thresholds_fail_even_without_trade_signals(self):
        with self.assertRaises(ValueError):
            backtest(self.rows,'RSI','scalping','5m',regime_thresholds={'unknown':1})
        with self.assertRaises(ValueError):
            compare_all(self.rows,profile='scalping',timeframe='5m',regime_thresholds={'lookback':1})

    def test_independent_holdout_cash_and_complete_provenance_remain(self):
        rows=copy.deepcopy(self.rows)
        with patch('strategy_research.signal_at',return_value='UP'):
            report=backtest(rows,'RSI','scalping','5m',stake=1,initial_balance=300)
        self.assertEqual(report['capital_model']['combined_funded_capital'],600)
        self.assertEqual(report['overall']['starting_balance'],600)
        self.assertEqual(report['train']['starting_balance'],300)
        self.assertEqual(report['test']['starting_balance'],300)
        self.assertAlmostEqual(report['overall']['pnl'],report['train']['pnl']+report['test']['pnl'])
        self.assertEqual(len(report['validation']['train_dataset_sha256']),64)
        self.assertEqual(len(report['validation']['holdout_dataset_sha256']),64)

    def test_no_order_overlaps_or_fills_before_closed_signal(self):
        with patch('strategy_research.signal_at',return_value='UP'):
            report=backtest(self.rows,'RSI','scalping','5m',expiry_bars=3)
        for partition in ('train','holdout'):
            trades=[x for x in report['trades_detail'] if x['partition']==partition]
            for trade in trades:
                self.assertGreater(trade['entered_at'],trade['signal_at'])
                self.assertFalse(trade['invalidation_used_by_model'])
            for before,after in zip(trades,trades[1:]):
                self.assertLessEqual(before['exited_at'],after['entered_at'])


if __name__=='__main__':unittest.main()
