"""Deterministic heuristic classifications, never broker verification."""
import math
import unittest
from market_regime import classify_regime


def rows_for(prices):
    return [{'time':1_700_000_000+i*300,'open':p,'high':p+.10,'low':p-.10,'close':p}
            for i,p in enumerate(prices)]


class RegimeTests(unittest.TestCase):
    def test_trend_continuation_eligible_in_uptrend(self):
        result=classify_regime(rows_for([100+i*.2 for i in range(80)]))
        self.assertEqual(result['regime'],'trending_up')
        self.assertIn('EMA_CROSS',result['eligible_strategies'])
        self.assertNotIn('BOLLINGER_REENTRY',result['eligible_strategies'])
        self.assertIsNone(result['confidence'])

    def test_range_suspends_continuation(self):
        result=classify_regime(rows_for([100+.2*math.sin(i) for i in range(80)]))
        self.assertEqual(result['regime'],'ranging')
        self.assertNotIn('EMA_CROSS',result['eligible_strategies'])

    def test_insufficient_and_invalid_data_blocks_entries(self):
        self.assertFalse(classify_regime([])['trading_allowed'])
        rows=rows_for([100]*80);rows[-1]['close']=float('nan')
        self.assertFalse(classify_regime(rows)['trading_allowed'])

    def test_required_calendar_outage_blocks_entries(self):
        result=classify_regime(rows_for([100+i*.2 for i in range(80)]),require_news=True)
        self.assertEqual(result['regime'],'uncertain')
        self.assertFalse(result['trading_allowed'])
        self.assertIn('calendar',result['reasons'][0])

    def test_verified_news_restriction_blocks_entries(self):
        result=classify_regime(rows_for([100+i*.2 for i in range(80)]),news_state='restricted')
        self.assertEqual(result['regime'],'news_driven_or_abnormal')
        self.assertFalse(result['trading_allowed'])

    def test_price_spike_is_abnormal_without_claiming_news_cause(self):
        rows=rows_for([100]*80);rows[-1]['high']=120
        result=classify_regime(rows)
        self.assertEqual(result['regime'],'news_driven_or_abnormal')
        self.assertIn('cause unknown',result['reasons'][0])

    def test_stale_or_future_data_blocks_entries(self):
        rows=rows_for([100+i*.2 for i in range(80)])
        for now in (rows[-1]['time']+3600,rows[-1]['time']-1):
            self.assertFalse(classify_regime(rows,now=now,max_age_seconds=600)['trading_allowed'])

    def test_high_and_low_volatility_suspend_new_entries(self):
        rows=rows_for([100]*80)
        for row in rows:row.update(high=105,low=95)
        self.assertEqual(classify_regime(rows)['regime'],'high_volatility')
        for row in rows:row.update(high=100.001,low=99.999)
        self.assertEqual(classify_regime(rows)['regime'],'low_volatility')

    def test_invalid_news_and_freshness_types_fail_clearly(self):
        rows=rows_for([100]*80)
        for options in ({'require_news':'false'},{'news_state':'unknown'},
                        {'max_age_seconds':True},{'max_age_seconds':600,'now':float('nan')}):
            with self.subTest(options=options),self.assertRaises(ValueError):classify_regime(rows,**options)

    def test_configuration_validation(self):
        for config in ({'lookback':2},{'unknown':1},{'high_volatility_pct':float('nan')},
                       {'range_efficiency':.8,'trend_efficiency':.5},[1],True,{'lookback':True}):
            with self.subTest(config=config),self.assertRaises(ValueError):classify_regime([],thresholds=config)


if __name__=='__main__':unittest.main()
