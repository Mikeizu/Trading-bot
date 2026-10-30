"""Function-level regression evidence for the full control audit.

All broker replies are deterministic local doubles. No external broker request,
market-performance claim, or real/demo purchase is made by this module.
"""
import copy
import io
import json
import math
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from deriv_bridge import (BridgeError, BrokerController, BrokerRejection,
                          DerivTransport, UnknownExecution, check_otp_url,
                          normalize_accounts)
from deriv_server import Journal
from engine import backtest as indicator_backtest, ema, indicators, rsi, signal_at, sma
from market_regime import classify_regime
from market_data import StrategyError, candles_valid, sample_candles
from research_analytics import performance_metrics, wilson_interval
from test_deriv import FakeTransport


def candles(count=90):
    return [{'time':1_700_000_000+i*60,'open':100.,'high':102.,'low':99.,'close':100.}
            for i in range(count)]


class TransportFunctionAudit(unittest.TestCase):
    def test_credentials_are_rejected_before_http_without_reflection(self):
        for app,token in [('bad\napp','unit-token'),('test-app',''),
                          ('test-app','unit-token\r\nInjected: value'),
                          ('test-app',True),('test-app','é')]:
            transport=DerivTransport(http=lambda *args:self.fail('Invalid headers reached HTTP'))
            with self.subTest(app=app,token_type=type(token).__name__),self.assertRaises(BridgeError) as error:
                transport.accounts(app,token)
            self.assertNotIn('Injected',str(error.exception))

    def test_accounts_schema_rejects_scalar_and_conflicting_identity(self):
        for payload in (None,[],{'data':{'accounts':{}}},
                        {'data':[{'account_id':'DEMO123','account_type':'demo'},
                                 {'account_id':'DEMO123','account_type':'real'}]}):
            with self.subTest(payload=payload),self.assertRaises(BridgeError):normalize_accounts(payload)
        same={'account_id':'DEMO123','account_type':'demo','currency':'USD'}
        self.assertEqual(len(normalize_accounts({'data':[same,same]})),1)

    def test_malformed_otp_payload_never_opens_a_websocket(self):
        accounts={'data':[{'account_id':'DEMO123','account_type':'demo','currency':'USD'}]}
        for otp in (None,[],{'data':[]},{'data':{'url':123}},
                    {'data':{'url':'wss://api.derivws.com/trading/v1/options/ws/real?otp=unit'}}):
            transport=DerivTransport(http=lambda method,*args:accounts if method=='GET' else otp,
                                     ws_factory=lambda url:self.fail('Malformed OTP opened a socket'))
            with self.subTest(otp=otp),self.assertRaises(BridgeError):
                transport.connect('test-app','unit-token','DEMO123','demo')

    def test_invalid_otp_syntax_uses_credential_safe_bridge_error(self):
        for url in ('wss://[broken',None,42,
                    'wss://api.derivws.com/trading/v1/options/ws/demo?otp=unit#fragment'):
            with self.subTest(url=url),self.assertRaises(BridgeError):check_otp_url(url,'demo')

    def test_rest_malformed_json_has_safe_error(self):
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self):return b'{"token":"private-unit-token"'
        with patch('deriv_bridge.urlopen',return_value=Response()):
            with self.assertRaises(BridgeError) as error:
                DerivTransport._http('GET','/trading/v1/options/accounts','test-app','private-unit-token')
        self.assertNotIn('private-unit-token',str(error.exception))

    def test_history_request_rejects_bool_fractional_and_invalid_granularity(self):
        transport=DerivTransport()
        for count in (True,1.5,'140',0,2501):
            with self.subTest(count=count),patch.object(transport,'rpc') as call,self.assertRaises(BridgeError):
                transport.candles('R_100',count=count)
            call.assert_not_called()
        for granularity in (True,60.0,61,'60'):
            with self.subTest(granularity=granularity),patch.object(transport,'rpc') as call,self.assertRaises(BridgeError):
                transport.candles('R_100',granularity=granularity)
            call.assert_not_called()

    def test_history_reply_does_not_coerce_boolean_prices_or_fractional_epoch(self):
        base={'epoch':1000,'open':100,'high':102,'low':99,'close':101}
        invalid=[{**base,key:True} for key in base]
        invalid += [{**base,'epoch':1000.5},{**base,'epoch':'1000.5'},None]
        for row in invalid:
            transport=DerivTransport()
            with self.subTest(row=row),patch.object(transport,'rpc',return_value={'candles':[row]}),self.assertRaises(BridgeError):
                transport.candles('R_100')
        transport=DerivTransport()
        with patch.object(transport,'rpc',return_value={'candles':[base]}):
            self.assertEqual(transport.candles('R_100')[0]['time'],1000)

    def test_boolean_response_id_cannot_match_integer_request(self):
        class Socket:
            def __init__(self):self.reads=0;self.timeouts=[]
            def send(self,raw):self.request=json.loads(raw)
            def settimeout(self,value):self.timeouts.append(value)
            def recv(self):
                self.reads+=1
                return json.dumps({'req_id':True if self.reads==1 else self.request['req_id'],
                                   'value':'ignored' if self.reads==1 else 'matched'})
            def close(self):pass
        transport=DerivTransport();transport.ws=Socket()
        result=transport.rpc({'ping':1})
        self.assertEqual(result['value'],'matched')
        self.assertEqual(transport.ws.reads,2)
        self.assertTrue(all(0<t<=12 for t in transport.ws.timeouts))

    def test_ambiguous_purchase_error_is_unknown_not_known_rejection(self):
        for payload in ({'error':{}},{'error':'private-token'},
                        {'error':{'code':'InvalidToken'},'buy':{'contract_id':10}}):
            class Socket:
                def send(self,raw):self.request=json.loads(raw)
                def recv(self):return json.dumps({'req_id':self.request['req_id'],**payload})
                def close(self):pass
            transport=DerivTransport();transport.ws=Socket()
            with self.subTest(payload=payload),self.assertRaises(UnknownExecution):
                transport.rpc({'buy':'proposal','price':1},purchasing=True)

    def test_conflicting_symbol_metadata_cannot_grant_news_exemption(self):
        transport=DerivTransport()
        payload={'active_symbols':[{'symbol':'R_100','market':'synthetic_index'},
                                   {'symbol':'R_100','market':'forex'}]}
        with patch.object(transport,'rpc',return_value=payload):symbols=transport.symbols()
        self.assertEqual(len(symbols),1)
        self.assertIsNone(transport.market_metadata['R_100']['market'])


class ControllerRecoveryFunctionAudit(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.journal=Journal(Path(self.folder.name)/'orders.db')
        self.transport=FakeTransport();self.broker=BrokerController(self.journal,self.transport)
        self.broker.connect('test-app','demo-test-token','DOT90000001','demo')

    def test_failed_refresh_removes_stale_quote_permissions_and_automation(self):
        quote=self.broker.new_quote('R_100','UP',1,2);self.broker.automation=True
        with patch.object(self.transport,'symbols',side_effect=BridgeError('Catalogue offline')):
            with self.assertRaises(BridgeError):self.broker.refresh_markets()
        self.assertFalse(self.broker.allowed_symbols)
        self.assertIsNone(self.broker.quote);self.assertFalse(self.broker.automation)
        with self.assertRaises(BridgeError):self.broker.buy_quote(quote['token'])
        self.assertEqual(self.transport.buy_count,0)

    def test_reconciliation_cannot_launder_tampered_materialized_order(self):
        quote=self.broker.new_quote('R_100','UP',1,2);self.broker.buy_quote(quote['token'])
        with sqlite3.connect(self.journal.path) as connection:
            connection.execute('UPDATE orders SET stake=0.01')
        self.transport.contract_sold=True
        with self.assertRaisesRegex(BridgeError,'integrity'):self.broker.reconcile()
        self.assertFalse(self.journal.audit()['integrity'])
        self.assertEqual(self.journal.history('DOT90000001')[0]['status'],'OPEN')

    def test_open_contract_identity_mismatch_blocks_reconciliation(self):
        quote=self.broker.new_quote('R_100','UP',1,2);self.broker.buy_quote(quote['token'])
        with patch.object(self.transport,'contract',return_value={'status':'open','contract_id':'wrong'}):
            with self.assertRaisesRegex(BridgeError,'identity mismatch'):self.broker.reconcile()
        self.assertEqual(self.journal.history('DOT90000001')[0]['status'],'OPEN')

    def test_contradictory_sold_flag_and_open_status_cannot_settle(self):
        quote=self.broker.new_quote('R_100','UP',1,2);self.broker.buy_quote(quote['token'])
        with patch.object(self.transport,'contract',return_value={'status':'open','is_sold':1,'profit':.8}):
            with self.assertRaisesRegex(BridgeError,'inconsistent'):self.broker.reconcile()
        self.assertEqual(self.journal.history('DOT90000001')[0]['status'],'OPEN')


class IndicatorFunctionAudit(unittest.TestCase):
    def test_all_indicator_periods_reject_nonpositive_fractional_boolean_and_nonfinite(self):
        for indicator in (sma,ema,rsi):
            for period in (True,0,-1,1.5,float('nan'),float('inf'),'3'):
                with self.subTest(indicator=indicator.__name__,period=period),self.assertRaises(ValueError):
                    indicator([1,2,3],period)

    def test_indicators_reject_nonfinite_boolean_and_extreme_series(self):
        for indicator in (sma,ema,rsi):
            for value in (True,float('nan'),float('inf'),1e308):
                with self.subTest(indicator=indicator.__name__,value=value),self.assertRaises(ValueError):
                    indicator([1,value,3],2)
        interpolated=ema([None,2,None,4],2)
        self.assertEqual(interpolated[:3],[None,2.,None])
        self.assertAlmostEqual(interpolated[-1],10/3)
        self.assertEqual(rsi([2]*20)[-1],50.)

    def test_bollinger_flat_close_does_not_use_asymmetric_wick_mean(self):
        rows=candles();values=indicators(rows)
        self.assertEqual(values['bb_upper'][-1],100.)
        self.assertEqual(values['bb_lower'][-1],100.)
        self.assertIsNone(signal_at(rows,values,len(rows)-1,'BOLLINGER'))

    def test_signal_rejects_invalid_index_strategy_and_wrong_length_values(self):
        rows=candles();values=indicators(rows)
        for index in (-1,True,len(rows),1.5):
            with self.subTest(index=index),self.assertRaises(ValueError):signal_at(rows,values,index,'RSI')
        with self.assertRaises(ValueError):signal_at(rows,values,40,None)
        with self.assertRaises(ValueError):signal_at(rows,{'rsi':[50]},40,'RSI')

    def test_indicator_backtest_skips_holding_gaps_instead_of_extending_expiry(self):
        rows=candles(100)
        for row in rows[37:]:row['time']+=60
        with patch('engine.signal_at',return_value='UP'):
            report=indicator_backtest(rows,'RSI',stake=1,duration=3)
        self.assertGreater(report['data_integrity']['missing_holding_bars_skipped'],0)
        for trade in report['trades']:
            self.assertEqual(trade['exited_at']-trade['entered_at'],180)
        self.assertEqual(report['data_integrity']['inferred_bar_interval_seconds'],60)

    def test_canonical_candles_reject_overflow_and_silent_time_truncation(self):
        for change in ({'time':1.5},{'time':True},{'open':True},{'close':1e308},{'low':1e-200}):
            bad={**candles(1)[0],**change}
            with self.subTest(change=change),self.assertRaises(StrategyError):candles_valid([bad])


class AnalyticsFunctionAudit(unittest.TestCase):
    def test_auxiliary_metrics_cannot_hide_invalid_cost_or_duration(self):
        for field in ('commission','stake','holding_seconds'):
            for value in (True,-1,float('nan'),float('inf')):
                with self.subTest(field=field,value=value),self.assertRaises(ValueError):
                    performance_metrics([{'pnl':1,field:value}])

    def test_balance_and_period_are_deliberately_validated(self):
        for balance in (True,0,-1,float('nan'),float('inf')):
            with self.subTest(balance=balance),self.assertRaises(ValueError):performance_metrics([],balance)
        for period in (True,0,-1,float('nan'),float('inf')):
            with self.subTest(period=period),self.assertRaises(ValueError):
                performance_metrics([{'pnl':1}],period_seconds=period)

    def test_valid_metrics_and_undefined_ratios_are_json_serializable(self):
        for trades in ([],[{'pnl':1,'commission':0,'stake':1,'holding_seconds':60}],
                       [{'pnl':-1,'commission':.1,'stake':1,'holding_seconds':60},{'pnl':1}]):
            report=performance_metrics(trades,period_seconds=120)
            json.dumps(report,allow_nan=False)
            self.assertEqual(report['trades'],report['wins']+report['losses']+report['breakeven_trades'])
        self.assertEqual(wilson_interval(0,0),(None,None))

    def test_regime_invalid_candles_fail_closed_without_numerical_overflow(self):
        for change in ({'open':True},{'high':1e308},{'time':True},{'time':1.5}):
            rows=candles();rows[-1].update(change)
            with self.subTest(change=change):
                report=classify_regime(rows)
                self.assertFalse(report['trading_allowed'])
                self.assertEqual(report['regime'],'uncertain')
                json.dumps(report,allow_nan=False)


if __name__=='__main__':unittest.main()
