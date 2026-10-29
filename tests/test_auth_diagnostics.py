"""Offline regression tests for Deriv REST authentication. No network or orders."""
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from deriv_bridge import BridgeError, DerivTransport


class AuthDiagnosticTests(unittest.TestCase):
    def test_request_sends_pat_headers_correctly(self):
        captured = {}
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return None
            def read(self): return b'{"data": []}'
        def fake_open(req, timeout):
            captured['url'] = req.full_url
            captured['auth'] = req.get_header('Authorization')
            captured['app'] = req.get_header('Deriv-app-id')
            captured['timeout'] = timeout
            return Response()
        with patch('deriv_bridge.urlopen', side_effect=fake_open):
            data = DerivTransport._http('GET','/trading/v1/options/accounts','new-PAT-app-123','secret-token-123')
        self.assertEqual(data, {'data': []})
        self.assertEqual(captured['auth'], 'Bearer secret-token-123')
        self.assertEqual(captured['app'], 'new-PAT-app-123')
        self.assertEqual(captured['url'], 'https://api.derivws.com/trading/v1/options/accounts')

    def _check(self, code, body, expected):
        def reject(req, timeout):
            raise HTTPError(req.full_url, code, 'Unauthorized', {}, io.BytesIO(body))
        with patch('deriv_bridge.urlopen', side_effect=reject):
            with self.assertRaises(BridgeError) as err:
                DerivTransport._http('GET', '/trading/v1/options/accounts', 'some-app', 'private-secret')
        msg = str(err.exception)
        self.assertIn(expected, msg)
        self.assertNotIn('private-secret', msg)
        return msg

    def test_401_empty_response_explains_what_to_do(self):
        msg=self._check(401, b'', 'PAT-type App ID')
        self.assertIn('trade permission', msg)
    def test_401_html_response_does_not_leak_body(self):
        msg=self._check(401, b'<html>private-secret</html>', 'HTTP 401')
        self.assertNotIn('html', msg)
    def test_401_deriv_json_shows_specific_header_hint(self):
        body=json.dumps({'errors':[{'message':'Deriv-App-ID header is required for PAT tokens'}]}).encode()
        self.assertIn('header is missing', self._check(401,body,'HTTP 401'))
    def test_403_permission_hint(self):
        self._check(403,b'', 'trade permission')
    def test_429_reports_rate_limit_without_retry_or_response_leak(self):
        calls=[]
        def reject(req,timeout):
            calls.append(req.full_url)
            raise HTTPError(req.full_url,429,'Too Many Requests',{},io.BytesIO(b'private-secret'))
        with patch('deriv_bridge.urlopen',side_effect=reject):
            with self.assertRaises(BridgeError) as error:
                DerivTransport._http('GET','/trading/v1/options/accounts','test-app','private-secret')
        self.assertIn('rate limit',str(error.exception))
        self.assertNotIn('private-secret',str(error.exception))
        self.assertEqual(len(calls),1)

if __name__ == '__main__': unittest.main()
