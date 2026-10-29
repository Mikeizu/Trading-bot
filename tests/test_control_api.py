"""HTTP integration and durable audit checks; no broker network operations."""
import http.client
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer

import deriv_server as app
from deriv_bridge import BrokerController, BridgeError
from strategy_extension import StrategySupervisor
from test_deriv import FakeTransport


class ControlApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.journal=app.Journal(self.root/'orders.db')
        self.transport=FakeTransport()
        self.broker=BrokerController(self.journal,self.transport)
        self.supervisor=StrategySupervisor(self.broker,self.root/'signals.db')
        self.patches=[patch.object(app,'journal',self.journal),patch.object(app,'broker',self.broker),
            patch.object(app,'strategy_supervisor',self.supervisor),
            patch.object(app.simulator,'DB_FILE',self.root/'simulator.db')]
        for p in self.patches:p.start()
        app.simulator.BOT_ACTIVE=False
        app.simulator.db_initialize()
        self.httpd=ThreadingHTTPServer(('127.0.0.1',0),app.API)
        self.thread=threading.Thread(target=self.httpd.serve_forever,daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown();self.httpd.server_close();self.thread.join(timeout=2)
        for p in reversed(self.patches):p.stop()
        app.simulator.BOT_ACTIVE=False
        self.tmp.cleanup()

    def request(self,path,payload=None,headers=None):
        client=http.client.HTTPConnection('127.0.0.1',self.httpd.server_port,timeout=5)
        try:
            body=json.dumps(payload) if payload is not None else None
            opts={'Content-Type':'application/json',**(headers or {})}
            client.request('POST' if payload is not None else 'GET',path,body,opts)
            response=client.getresponse();data=response.read()
            return response.status,json.loads(data),dict(response.getheaders())
        finally:client.close()

    def connect(self):
        return self.request('/api/deriv/connect',{'app_id':'test-app','token':'demo-test-token',
            'account_id':'DOT90000001','mode':'demo'})

    def test_health_and_capabilities_disclose_limits(self):
        status,body,headers=self.request('/api/system/health')
        self.assertEqual(status,200);self.assertFalse(body['broker']['connected'])
        self.assertFalse(body['live_execution'])
        self.assertIn("script-src 'self'",headers['Content-Security-Policy'])
        _,caps,_=self.request('/api/capabilities')
        self.assertIn('disabled',caps['modes']['live'])
        self.assertIn('not implemented',caps['modes']['mt5'])

    def test_rebinding_cross_origin_and_wrong_content_type_blocked(self):
        self.assertEqual(self.request('/api/risk/status',headers={'Host':'attacker.invalid'})[0],403)
        self.assertEqual(self.request('/api/risk/kill',{},headers={'Origin':'https://attacker.invalid'})[0],403)
        self.assertEqual(self.request('/api/risk/kill',{},headers={'Content-Type':'text/plain'})[0],415)
        self.assertFalse(self.broker.risk.global_status()['killed'])

    def test_disconnected_global_stop_survives_recreation_and_account_change(self):
        status,state,_=self.request('/api/risk/kill',{'reason':'test operator emergency'})
        self.assertEqual(status,200);self.assertTrue(state['halted'])
        self.assertEqual(self.connect()[0],200)
        with self.assertRaises(BridgeError):self.broker.new_quote('R_100','UP',1,2)
        recreated=BrokerController(self.journal,FakeTransport())
        self.assertTrue(recreated.risk.global_status()['killed'])
        self.assertEqual(self.request('/api/robot',{'active':True})[0],400)

    def test_resume_requires_phrase_and_never_starts_automation(self):
        self.request('/api/risk/kill',{})
        self.assertEqual(self.request('/api/risk/resume',{'confirmation':'yes'})[0],400)
        code,state,_=self.request('/api/risk/resume',{'confirmation':'RESUME DEMO TRADING'})
        self.assertEqual(code,200);self.assertFalse(state['halted'])
        self.assertFalse(self.broker.automation);self.assertFalse(self.supervisor.active)
        self.assertFalse(app.simulator.BOT_ACTIVE)

    def test_risk_configuration_is_bounded_and_account_scoped(self):
        self.assertEqual(self.request('/api/risk/config',{'risk_per_trade_pct':.25})[0],400)
        self.assertEqual(self.connect()[0],200)
        self.assertEqual(self.request('/api/risk/config',{'risk_per_trade_pct':99})[0],400)
        self.assertEqual(self.request('/api/risk/config',{'risk_per_trade_pct':float('nan')})[0],400)
        code,state,_=self.request('/api/risk/config',{'risk_per_trade_pct':.25})
        self.assertEqual(code,200);self.assertEqual(state['limits']['risk_per_trade_pct'],.25)

    def test_calendar_contract_and_freshness(self):
        self.connect();now=time.time()
        payload={'events':[],'updated_at':now,'valid_until':now+3600,'source':'test fixture only'}
        code,state,_=self.request('/api/risk/calendar',payload)
        self.assertEqual(code,200);self.assertTrue(state['risk']['calendar']['fresh'])
        self.assertEqual(state['risk']['calendar']['event_count'],0)
        self.assertEqual(self.request('/api/risk/calendar',{**payload,'source':''})[0],400)

    def test_kill_keeps_orders_and_cancels_pending_paper(self):
        self.connect()
        self.supervisor.paper.open(self.broker.account_id,'R_100','1m','kangaroo',
            {'side':'UP','stop':99,'confirmed_at':1000},100)
        quote=self.broker.new_quote('R_100','UP',1,2)
        self.broker.buy_quote(quote['token'])
        code,state,_=self.request('/api/risk/kill',{})
        self.assertEqual(code,200);self.assertTrue(state['halted'])
        self.assertEqual(self.journal.orders(self.broker.account_id)[0]['status'],'OPEN')
        self.assertEqual(self.supervisor.paper.positions(self.broker.account_id)[0]['status'],'CANCELLED')
        _,audit,_=self.request('/api/audit')
        self.assertTrue(audit['integrity']);self.assertEqual(len(audit['events']),2)
        self.assertNotIn('demo-test-token',json.dumps(audit))


class JournalRecoveryTests(unittest.TestCase):
    def test_durable_context_state_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'orders.db';book=app.Journal(path)
            q={'token':'once','symbol':'R_100','side':'UP','stake':1.,'ask_price':1.,'minutes':2,
                'context':{'strategy':'kangaroo','strategy_version':'test-v1','token':'must not persist'}}
            order=book.reserve('demo1','demo',q)
            book.update(order,'OPEN','123',None)
            restored=app.Journal(path)
            self.assertEqual(restored.history('demo1')[0]['status'],'OPEN')
            self.assertEqual(json.loads(restored.history('demo1')[0]['context_json']),
                {'strategy':'kangaroo','strategy_version':'test-v1'})
            with self.assertRaises(ValueError):restored.update(order,'REJECTED')
            self.assertTrue(restored.audit()['integrity'])
            with sqlite3.connect(path) as c:c.execute("UPDATE order_audit SET event_json='{}' WHERE id=1")
            self.assertFalse(restored.audit()['integrity'])

    def test_schema_upgrade_preserves_legacy_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'orders.db'
            with sqlite3.connect(path) as c:
                c.execute('''CREATE TABLE orders(id INTEGER PRIMARY KEY,nonce TEXT UNIQUE NOT NULL,
                    account_id TEXT NOT NULL,mode TEXT NOT NULL,symbol TEXT NOT NULL,direction TEXT NOT NULL,
                    stake REAL NOT NULL,ask_price REAL NOT NULL,expiry_minutes INTEGER NOT NULL,
                    contract_id TEXT,status TEXT NOT NULL,pnl REAL,opened_at INTEGER NOT NULL,updated_at INTEGER NOT NULL)''')
                c.execute("INSERT INTO orders VALUES(1,'legacy','demo1','demo','R_100','UP',1,1,2,NULL,'PENDING',NULL,1000,1000)")
            book=app.Journal(path)
            self.assertEqual(book.unresolved('demo1')[0]['nonce'],'legacy')
            self.assertEqual(book.history('demo1')[0]['context_json'],'{}')
            self.assertTrue(book.audit()['integrity'])
            with sqlite3.connect(path) as c:c.execute('UPDATE orders SET stake=0.01 WHERE id=1')
            self.assertFalse(book.audit()['integrity'])


if __name__=='__main__':unittest.main()
