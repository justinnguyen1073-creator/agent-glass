import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('usage', ROOT / 'contents/code/usage.py')
u = importlib.util.module_from_spec(spec)
spec.loader.exec_module(u)


def window(minutes=300, used=31, reset=1792119391):
    return {'windowDurationMins': minutes, 'usedPercent': used, 'resetsAt': reset}


class UsageTests(unittest.TestCase):
    def test_verified_shape(self):
        data = u.normalize({'rateLimitsByLimitId': {'codex': {'primary': window(), 'secondary': window(10080, 5)}}})
        self.assertEqual(data['fiveHour']['remaining'], 69)
        self.assertEqual(data['weekly']['used'], 5)
        self.assertEqual(data['fiveHour']['resetsAt'], '2026-10-16T02:56:31+00:00')

    def test_missing_and_reordered(self):
        data = u.normalize({'rateLimits': {'primary': window(10080, 9)}})
        self.assertIsNone(data['fiveHour'])
        self.assertEqual(data['weekly']['used'], 9)

    def test_prefer_codex_bucket(self):
        data = u.normalize({'rateLimits': {'primary': window(300, 90)}, 'rateLimitsByLimitId': {
            'codex': {'primary': window(300, 10)}, 'other': {'primary': window(300, 80)}}})
        self.assertEqual(data['fiveHour']['used'], 10)

    def test_do_not_substitute_other_bucket(self):
        for payload in ({'rateLimits': {'limitId': 'other', 'primary': window()}},
                        {'rateLimitsByLimitId': {'other': {'primary': window()}}}):
            self.assertIsNone(u.normalize(payload)['fiveHour'])

    def test_invalid_percent(self):
        for value in (-1, 101, float('nan'), True, '10'):
            self.assertIsNone(u.normalize({'rateLimits': {'primary': window(300, value)}})['fiveHour'])

    def test_bad_reset_does_not_hide_usage(self):
        for value in (None, True, 'tomorrow', float('inf'), 10**30):
            data = u.normalize({'rateLimits': {'primary': window(reset=value)}})
            self.assertIsNone(data['fiveHour']['resetsAt'])
            self.assertEqual(data['fiveHour']['used'], 31)

    def test_bad_payload(self):
        for payload in ([], {}, None):
            with self.assertRaises(ValueError):
                u.normalize(payload)

    def test_privacy(self):
        data = u.normalize({'accountId': 'private', 'rateLimits': {'accountEmail': 'private@example.test',
                          'credits': {'secret': 'no'}, 'primary': window()}})
        self.assertNotIn('private', str(data))
        self.assertNotIn('secret', str(data))

    def test_error_messages(self):
        for error, expected in ((u.RpcError({'code': 401, 'message': 'private expired token'}), 'Sign in'),
                                (u.RpcError({'code': -32601}), 'Update Codex'),
                                (u.RpcError({'message': 'network private'}), 'connection'),
                                (TimeoutError(), 'timed out')):
            with patch.object(u, 'find_codex', return_value=Path('/bin/codex')), patch.object(u, 'read_limits', side_effect=error):
                data = u.main()
                self.assertFalse(data['ok'])
                self.assertIn(expected, data['message'])
                self.assertNotIn('private', data['message'])

    def test_missing(self):
        with patch.object(u, 'find_codex', return_value=None):
            self.assertIn('Codex not found', u.main()['message'])

    def test_nvm_discovery_without_shell_path(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            binary = home / '.nvm/versions/node/v20.20.2/bin/codex'
            binary.parent.mkdir(parents=True)
            binary.write_text('#!/bin/sh\n')
            binary.chmod(0o755)
            with patch.object(u.shutil, 'which', return_value=None), patch.object(u.Path, 'home', return_value=home), patch.dict(os.environ, {'NVM_DIR': str(home / '.nvm')}):
                self.assertEqual(u.find_codex(), binary)

    def test_configured_path(self):
        self.assertIsNone(u.find_codex('relative/path'))
        self.assertIsNone(u.find_codex('/nonexistent/codex'))

    def test_npm_matching_node(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / 'codex.js'; script.touch()
            binary = root / 'codex'; binary.symlink_to(script)
            node = root / 'node'; node.touch(); node.chmod(0o755)
            self.assertEqual(u.codex_command(binary), [str(node), str(script)])

    def test_rpc_handshake_and_request(self):
        # Real pipes/processes, fragmented JSON, unrelated notifications, and an
        # unexpected request exercise the transport without needing an account.
        server = '''import sys, json, time
read = lambda: json.loads(sys.stdin.readline())
init = read()
assert init['method'] == 'initialize'
sys.stdout.write('{"id":1,'); sys.stdout.flush()
time.sleep(0.01)
sys.stdout.write('"result":{}}\\n'); sys.stdout.flush()
assert read()['method'] == 'initialized'
request = read()
assert request == {'id':2, 'method':'account/rateLimits/read'}
print(json.dumps({'method':'notification', 'params':{}}), flush=True)
print(json.dumps({'id':9, 'method':'unexpected/credentials'}), flush=True)
assert read()['error']['code'] == -32601
print(json.dumps({'id':2,'result':{'rateLimits':{'primary':{'windowDurationMins':300,'usedPercent':7,'resetsAt':1792119391}}}}), flush=True)
time.sleep(20)
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'server.py'; path.write_text(server)
            data = u.normalize(u.read_limits([sys.executable, str(path)], timeout=3))
            self.assertEqual(data['fiveHour']['used'], 7)

    def test_rpc_timeout(self):
        with self.assertRaises(TimeoutError):
            u.read_limits([sys.executable, '-c', 'import time; time.sleep(20)'], timeout=0.05)

    def test_rpc_closed_pipe(self):
        with self.assertRaises((ValueError, OSError)):
            u.read_limits([sys.executable, '-c', 'pass'], timeout=1)


if __name__ == '__main__':
    unittest.main()
