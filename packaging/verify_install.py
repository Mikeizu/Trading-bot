#!/usr/bin/env python3
"""Verify a release, install it offline in a fresh temporary venv and smoke test.

Only local synthetic endpoints are used. No account credentials or broker
requests are involved. The test reports the OS whose launcher actually ran.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import signal
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener
import zipfile

from build_bundle import PREFIX, verify_bundle


def check_install(bundle: Path, *, timeout=40.0) -> dict:
    verification = verify_bundle(bundle)
    checks = []
    with tempfile.TemporaryDirectory(prefix='TradeLab package check ') as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(bundle) as archive:
            archive.extractall(root)  # Paths and symlinks were validated above.
        project = root / PREFIX
        venv = project / '.venv'
        env = dict(os.environ)
        env.update(PIP_CONFIG_FILE=os.devnull, PIP_NO_INDEX='1', PIP_DISABLE_PIP_VERSION_CHECK='1',
                   PYTHONNOUSERSITE='1', MIKEIZU_DATA_DIR=str(root / 'private-state'))
        subprocess.run([sys.executable, '-m', 'venv', str(venv)], env=env, check=True,
                       capture_output=True, text=True, timeout=60)
        python = venv / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        install = subprocess.run([str(python), '-m', 'pip', 'install', '--no-index',
                                  '--find-links', str(project/'vendor/wheels'),
                                  '--require-hashes', '-r', str(project/'requirements.lock')],
                                 env=env, cwd=project, check=True,
                                 capture_output=True, text=True, timeout=60)
        checks.append('fresh virtual environment; hash-locked dependency installed with --no-index')
        version = subprocess.check_output([str(python), '-c',
            'import importlib.metadata; print(importlib.metadata.version("websocket-client"))'],
            env=env, cwd=project, text=True).strip()
        if version != '1.9.2':
            raise AssertionError('Unexpected installed WebSocket dependency version')
        subprocess.run([str(python), '-m', 'pip', 'check'], env=env, cwd=project,
                       check=True, capture_output=True, text=True, timeout=20)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        launcher = 'START_WINDOWS.bat' if os.name == 'nt' else 'START_MAC_LINUX.sh'
        command = (['cmd.exe', '/d', '/c', str(project/launcher), '--no-browser', '--port', str(port)]
                   if os.name == 'nt' else
                   ['bash', str(project/launcher), '--no-browser', '--port', str(port)])
        options = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {'start_new_session': True}
        log_path = root / 'startup.log'
        opener = build_opener(ProxyHandler({}))
        base = f'http://127.0.0.1:{port}'

        def request(path, data=None, expected=200):
            body = None if data is None else json.dumps(data).encode()
            req = Request(base+path, data=body, headers={'Content-Type': 'application/json'})
            try:
                with opener.open(req, timeout=5) as response:
                    status, payload = response.status, response.read()
            except HTTPError as exc:
                status, payload = exc.code, exc.read()
            if status != expected:
                raise AssertionError(f'{path}: expected HTTP {expected}, got {status}')
            return json.loads(payload)

        with log_path.open('w+', encoding='utf-8') as log:
            process = subprocess.Popen(command, cwd=project, env=env, stdin=subprocess.DEVNULL,
                                       stdout=log, stderr=subprocess.STDOUT, **options)
            try:
                deadline = time.monotonic()+timeout
                while True:
                    if process.poll() is not None:
                        log.seek(0)
                        raise RuntimeError('Extracted launcher exited early: '+log.read()[-4000:])
                    try:
                        health = request('/api/system/health')
                        break
                    except (URLError, TimeoutError, ConnectionError, OSError):
                        if time.monotonic() >= deadline:
                            raise TimeoutError('Extracted application did not become ready')
                        time.sleep(.1)
                if not health['ok'] or not all(health['workers'].values()) or not health['audit_integrity']:
                    raise AssertionError('Extracted process/worker/audit readiness failed')
                if health['live_execution'] or health['broker']['connected']:
                    raise AssertionError('Package smoke test requires a disconnected, live-disabled app')
                checks.append('actual extracted launcher starts local API with all workers and valid audit')
                catalog = request('/api/strategy/catalog')
                if len(catalog['strategies']) < 18 or not {'RSI','MACD','CCI','SMA','BOLLINGER','STOCHASTIC'}.issubset(catalog['strategies']):
                    raise AssertionError('Strategy catalog incomplete')
                for asset in ('/', '/styles.css', '/app.js', '/deriv_ui.js',
                              '/strategies_ui.js', '/terminal_controls.js', '/sw.js'):
                    with opener.open(base+asset, timeout=5) as response:
                        if response.status != 200 or not response.read():
                            raise AssertionError('Missing frontend asset: '+asset)
                checks.append('frontend shell/assets and complete technical strategy catalog served')
                before = request('/api/bootstrap')
                if before['robot']['active']:
                    raise AssertionError('Synthetic automation started without explicit activation')
                request('/api/advance', {})
                after = request('/api/bootstrap')
                if after['candles'][-1]['tick'] != before['candles'][-1]['tick']+1:
                    raise AssertionError('Synthetic bar advancement failed')
                checks.append('synthetic data request changes the expected stored candle')
                report = request('/api/strategy/backtest', {
                    'source': 'synthetic', 'strategy': 'RSI', 'profile': 'scalping',
                    'timeframe': '5m', 'payout': .8, 'stake': 1, 'expiry_bars': 3,
                    'target_win_rate': 65})
                if ('Synthetic' not in report['source'] or
                        len(report['provenance']['dataset_sha256']) != 64 or
                        'walk_forward' not in report):
                    raise AssertionError('Synthetic research/report provenance failed')
                checks.append('synthetic backtest, provenance and walk-forward response validated')
                request('/api/risk/kill', {'reason': 'isolated extracted-package acceptance check'})
                if not request('/api/risk/status')['halted']:
                    raise AssertionError('Emergency stop was not persisted')
                request('/api/robot', {'active': True}, expected=400)
                request('/api/risk/resume', {'confirmation': 'RESUME DEMO TRADING'})
                if request('/api/risk/status')['halted'] or request('/api/bootstrap')['robot']['active']:
                    raise AssertionError('Resume must clear halt without starting automation')
                checks.append('persistent emergency stop blocks entries; explicit resume starts no robot')
            finally:
                if process.poll() is None:
                    try:
                        if os.name == 'nt':
                            process.send_signal(signal.CTRL_BREAK_EVENT)
                        else:
                            os.killpg(process.pid, signal.SIGINT)
                        process.wait(timeout=8)
                    except (ProcessLookupError, subprocess.TimeoutExpired, OSError):
                        if os.name == 'nt':
                            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                           capture_output=True, check=False)
                        else:
                            try: os.killpg(process.pid, signal.SIGKILL)
                            except ProcessLookupError: pass
                        process.wait(timeout=8)
    return {
        'result': 'passed', 'archive': str(bundle.resolve()), 'verification': verification,
        'platform_tested': platform.system(), 'python_tested': platform.python_version(),
        'launcher_tested': launcher, 'websocket_client_version': version,
        'offline_install': True, 'checks': checks, 'standalone_executable': False,
        'windows_launcher_executed': os.name == 'nt',
        'broker_verification': 'not attempted; local synthetic workflow only',
        'limitations': ['Python 3.10+ is required; Python itself is not bundled.',
                        'A Linux launcher test does not verify Windows execution.',
                        'No authenticated broker connection or purchase is tested.'],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    report = check_install(args.bundle)
    rendered = json.dumps(report, indent=2, sort_keys=True)+'\n'
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding='utf-8')
    print(rendered, end='')


if __name__ == '__main__':
    main()
