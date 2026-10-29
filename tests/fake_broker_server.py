"""TEST ONLY: real HTTP/UI handlers with a deterministic, offline broker double.

Never use this helper as an application launcher. It requires isolated data,
does not contact Deriv, and exposes __test__ fault controls on loopback only.
All balances, candles, symbols, quotations and executions here are fictional.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
from http.server import ThreadingHTTPServer
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class MockBrokerTransport:
    """Explicit fixture transport: no socket, credential storage, or network."""
    APP_ID = 'fixture-app'
    TOKEN = 'fixture-pat-not-a-real-credential'
    DEMO = 'DEMO_TEST01'
    REAL = 'REAL_TEST02'

    def __init__(self):
        self.account_id = ''
        self.mode = ''
        self.buy_count = 0
        self.proposal_count = 0
        self.balances = {self.DEMO: 10000., self.REAL: 20000.}
        self.proposals = {}
        self.contracts = {}
        self.fault = ''
        self.market_metadata = {'R_100': {'market': 'synthetic_index'},
                                'frxEURUSD': {'market': 'forex'}}

    def accounts(self, app_id, token):
        from deriv_bridge import BridgeError
        if app_id != self.APP_ID or token != self.TOKEN:
            raise BridgeError('TEST DOUBLE HTTP 401 — authentication rejected; no real broker contacted')
        return [{'account_id': self.DEMO, 'account_type': 'demo', 'currency': 'USD'},
                {'account_id': self.REAL, 'account_type': 'real', 'currency': 'USD'}]

    def connect(self, app_id, token, account_id, mode):
        from deriv_bridge import BridgeError
        account = next((a for a in self.accounts(app_id, token)
                        if a['account_id'] == account_id and a['account_type'] == mode), None)
        if not account:
            raise BridgeError('TEST DOUBLE account/mode mismatch')
        self.account_id, self.mode = account_id, mode
        return account

    def close(self):
        self.account_id, self.mode = '', ''

    def balance(self):
        from deriv_bridge import BridgeError
        if not self.account_id or self.fault == 'disconnect':
            raise BridgeError('TEST DOUBLE disconnected')
        return {'balance': self.balances[self.account_id], 'currency': 'USD',
                'account_id': self.account_id}

    def portfolio(self):
        return {'contracts': [dict(item) for item in self.contracts.values()
                              if item['account_id'] == self.account_id and not item['is_sold']]}

    def symbols(self):
        if self.fault == 'markets_empty':
            return []
        return [{'symbol': 'R_100', 'name': 'TEST DOUBLE — Volatility 100'},
                {'symbol': 'frxEURUSD', 'name': 'TEST DOUBLE — EUR/USD'},
                {'symbol': 'NO_DURATION', 'name': 'TEST DOUBLE — no offered duration'}]

    def contracts_for(self, symbol):
        offered = [] if symbol == 'NO_DURATION' or self.fault == 'durations_none' else list(range(1, 16))
        return {'symbol': symbol, 'UP': offered, 'DOWN': offered,
                'contract_types': ['CALL', 'PUT'], 'note': 'TEST DOUBLE contract metadata'}

    def candles(self, symbol, count=140, granularity=60):
        from deriv_bridge import BridgeError
        if not 1 <= count <= 2500:
            raise BridgeError('TEST DOUBLE respects real adapter maximum history count')
        last = (int(time.time()) // granularity - 1) * granularity
        # Flat deterministic bars intentionally generate no fictitious edge or
        # winning strategy. Their only role is exercising data plumbing/controls.
        return [{'time': last - (count - 1 - i) * granularity,
                 'open': 100., 'high': 100.2, 'low': 99.8, 'close': 100.}
                for i in range(count)]

    def proposal(self, symbol, side, stake, minutes, currency):
        self.proposal_count += 1
        proposal_id = f'fixture-proposal-{self.proposal_count}'
        self.proposals[proposal_id] = {'stake': stake, 'symbol': symbol, 'side': side,
                                       'minutes': minutes, 'account_id': self.account_id}
        return {'id': proposal_id, 'ask_price': stake, 'payout': round(stake * 1.8, 2),
                'longcode': 'TEST DOUBLE quotation — not a Deriv quote'}

    def buy(self, proposal_id, ask_price):
        from deriv_bridge import UnknownExecution
        self.buy_count += 1
        quote = self.proposals[proposal_id]
        contract_id = str(100000 + self.buy_count)
        self.contracts[contract_id] = {**quote, 'contract_id': contract_id,
            'buy_price': ask_price, 'is_sold': 0, 'status': 'open', 'profit': 0.}
        self.balances[self.account_id] -= ask_price
        if self.fault == 'timeout':
            raise UnknownExecution('TEST DOUBLE purchase timeout: unknown outcome')
        return {'contract_id': contract_id, 'buy_price': ask_price}

    def contract(self, contract_id):
        return dict(self.contracts[str(contract_id)])

    def settle_all(self):
        for item in self.contracts.values():
            if not item['is_sold']:
                item.update(is_sold=1, status='sold', profit=round(item['buy_price'] * .8, 2))
                self.balances[item['account_id']] += item['buy_price'] + item['profit']


def create_handler(app, transport):
    class TestAPI(app.API):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            path = urlparse(self.path).path
            if path.startswith('/__test__/'):
                if not self.check_host():
                    return
                if path == '/__test__/status':
                    return self.send_json({'fixture': True, 'network': 'none',
                        'buy_count': transport.buy_count, 'proposal_count': transport.proposal_count,
                        'fault': transport.fault, 'broker': app.broker.status(),
                        'strategy': app.strategy_supervisor.status()})
                return self.error_json('Unknown test fixture endpoint', 404)
            return super().do_GET()

        def do_POST(self):
            path = urlparse(self.path).path
            if path.startswith('/__test__/'):
                if not self.check_host() or not self.check_origin():
                    return
                try:
                    size = int(self.headers.get('Content-Length', '0'))
                    if not 0 <= size <= 4096:
                        return self.error_json('Invalid fixture payload size', 413)
                    data = json.loads(self.rfile.read(size) or '{}')
                    if path == '/__test__/fault':
                        if data.get('fault', '') not in ('', 'timeout', 'markets_empty', 'durations_none', 'disconnect'):
                            raise ValueError('Unknown fixture fault')
                        transport.fault = data.get('fault', '')
                    elif path == '/__test__/settle':
                        transport.settle_all()
                    else:
                        return self.error_json('Unknown fixture endpoint', 404)
                    return self.send_json({'fixture': True, 'ok': True})
                except (ValueError, TypeError):
                    return self.error_json('Invalid fixture request', 400)
            return super().do_POST()
    return TestAPI


def prepare_app(data_dir):
    os.environ['MIKEIZU_DATA_DIR'] = str(data_dir)
    import deriv_server as app
    from deriv_bridge import BrokerController, DerivTransport
    # Defense in depth: even an accidental fallback to the production adapter
    # must fail inside this test process before any authenticated network call.
    def forbidden_network(*_args, **_kwargs):
        raise AssertionError('TEST ONLY fixture forbids real broker transport')
    DerivTransport._http = staticmethod(forbidden_network)
    DerivTransport._websocket = staticmethod(forbidden_network)
    from strategy_extension import StrategySupervisor
    transport = MockBrokerTransport()
    app.journal = app.Journal(Path(data_dir) / 'fixture_orders.db')
    app.broker = BrokerController(app.journal, transport)
    app.strategy_supervisor = StrategySupervisor(app.broker, Path(data_dir) / 'fixture_signals.db')
    app.simulator.DB_FILE = Path(data_dir) / 'fixture_simulator.db'
    app.simulator.db_initialize()
    return app, transport


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8892)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='mikeizu-broker-fixture-') as tmp:
        app, transport = prepare_app(Path(tmp))
        server = ThreadingHTTPServer(('127.0.0.1', args.port), create_handler(app, transport))
        print(f'TEST ONLY broker fixture on port {args.port}; all data/executions fictional; no external network.', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            app.strategy_supervisor.stop('Fixture closed')
            app.broker.disconnect()
            server.server_close()


if __name__ == '__main__':
    main()
