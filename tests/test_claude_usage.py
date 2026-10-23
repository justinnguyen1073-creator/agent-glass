import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'contents/code'))
import claude_usage


def line(message_id, model='claude-opus-5-5', when='2026-10-20T12:00:00Z', **usage):
    usage = {'input_tokens': 1000, 'output_tokens': 1000, 'cache_read_input_tokens': 0,
             'cache_creation_input_tokens': 0, **usage}
    return json.dumps({'type': 'assistant', 'timestamp': when, 'requestId': 'req_' + message_id,
                       'message': {'id': message_id, 'model': model, 'usage': usage}}) + '\n'


class ClaudeUsageTest(unittest.TestCase):
    def summarize(self, *lines):
        with tempfile.TemporaryDirectory() as home:
            folder = Path(home) / 'projects/p'
            folder.mkdir(parents=True)
            (folder / 's.jsonl').write_text(''.join(lines))
            return claude_usage.summarize(home, dt.date(2026, 10, 20))

    def test_prices_and_dedupes_streamed_blocks(self):
        result = self.summarize(line('a'), line('a'), line('b', model='claude-sonnet-5-5'))
        self.assertAlmostEqual(result['monthUsd'], (4+20)/1000 + (2+10)/1000)
        self.assertEqual(result['tokens'], 4000)

    def test_cache_tiers(self):
        result = self.summarize(line('a', input_tokens=0, output_tokens=0, cache_read_input_tokens=1000000,
                                     cache_creation_input_tokens=2000000,
                                     cache_creation={'ephemeral_5m_input_tokens': 1000000, 'ephemeral_1h_input_tokens': 1000000}))
        self.assertAlmostEqual(result['monthUsd'], .2 + 5 + 8)
        self.assertEqual(result['cached'], 1000000)

    def test_unknown_model_and_outside_window(self):
        result = self.summarize(line('a', model='claude-future-9'), line('b', when='2026-08-01T00:00:00Z'))
        self.assertIsNone(result['monthUsd'])
        self.assertEqual(result['unpricedTokens'], 2000)
        self.assertTrue(result['incomplete'])

    def test_fast_mode(self):
        result = self.summarize(line('a', speed='fast'))
        self.assertAlmostEqual(result['monthUsd'], 2 * (4+20)/1000)

    def test_normalize_limits(self):
        result = claude_usage.normalize_limits({'five_hour': {'utilization': 6.0, 'resets_at': '2026-10-23T18:00:00+00:00'},
                                                'seven_day': None})
        self.assertEqual(result['fiveHour']['remaining'], 94)
        self.assertIsNone(result['weekly'])

    def test_missing_credentials(self):
        with tempfile.TemporaryDirectory() as home:
            self.assertFalse(claude_usage.fetch_limits(home)['ok'])

    def test_cache_shares_requests_and_backs_off(self):
        calls = []
        good = {'ok': True, 'fiveHour': {'used': 5, 'remaining': 95, 'resetsAt': None}, 'weekly': None}
        limited = {'ok': False, 'rateLimited': True, 'retryAfter': None, 'message': 'limited'}
        original = claude_usage.fetch_limits
        try:
            with tempfile.TemporaryDirectory() as folder:
                cache = Path(folder) / 'c.json'
                claude_usage.fetch_limits = lambda home=None: calls.append(1) or good
                self.assertEqual(claude_usage.read_limits(cache=cache, now=1000)['fiveHour']['used'], 5)
                claude_usage.read_limits(cache=cache, now=1100)
                self.assertEqual(len(calls), 1)
                claude_usage.fetch_limits = lambda home=None: calls.append(1) or limited
                stale = claude_usage.read_limits(cache=cache, now=1400)
                self.assertTrue(stale['ok'])
                self.assertEqual(stale['message'], 'limited')
                claude_usage.read_limits(cache=cache, now=1500)
                self.assertEqual(len(calls), 2)
        finally:
            claude_usage.fetch_limits = original


if __name__ == '__main__':
    unittest.main()
