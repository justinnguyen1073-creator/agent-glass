import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'contents/code'))
from spending import summarize

TODAY = dt.date(2026, 10, 15)

def event(day='2026-10-15', inp=1000, cached=800, out=100):
    return {'timestamp': day+'T12:00:00Z', 'type':'event_msg', 'payload':{'type':'token_count','info':{'total_token_usage':{'input_tokens':inp,'cached_input_tokens':cached,'output_tokens':out}}}}

class SpendingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.home=Path(self.tmp.name)
        (self.home/'sessions').mkdir()
    def tearDown(self): self.tmp.cleanup()
    def write(self, name, rows, sid='session'):
        path=self.home/name; path.parent.mkdir(exist_ok=True)
        records=[{'type':'session_meta','payload':{'id':sid}}, {'type':'turn_context','payload':{'model':'gpt-6.1-sol'}}]+rows
        path.write_text('\n'.join(json.dumps(row) for row in records)+'\n')
    def summary(self): return summarize(self.home, TODAY)
    def test_cached_discount_and_duplicate_notifications(self):
        self.write('sessions/a.jsonl',[event(),event()])
        result=self.summary()
        self.assertEqual(result['tokens'],1100)
        self.assertAlmostEqual(result['todayUsd'],.00148)
        self.assertEqual(len(result['days']),30)
    def test_cumulative_deltas_not_repeated_totals(self):
        self.write('sessions/a.jsonl',[event(inp=1000),event(inp=2000,cached=1600,out=200)])
        self.assertEqual(self.summary()['tokens'],2200)
    def test_duplicate_session_copy(self):
        self.write('sessions/a.jsonl',[event()])
        self.write('archived_sessions/copy.jsonl',[event()])
        self.assertEqual(self.summary()['tokens'],1100)
    def test_local_today_and_thirty_days(self):
        self.write('sessions/a.jsonl',[event('2026-09-01'),event('2026-10-14',inp=2000,cached=1600,out=200),event(inp=3000,cached=2400,out=300)])
        result=self.summary()
        self.assertEqual(result['tokens'],2200)
        self.assertAlmostEqual(result['monthUsd'],2*result['todayUsd'])
    def test_unknown_model_is_not_priced_as_zero(self):
        self.write('sessions/a.jsonl',[{'type':'turn_context','payload':{'model':'unknown'}},event()])
        result=self.summary()
        self.assertIsNone(result['monthUsd'])
        self.assertEqual(result['unpricedTokens'],1100)
        self.assertTrue(result['incomplete'])
    def test_invalid_or_partial_lines(self):
        self.write('sessions/a.jsonl',[event(inp=-1),event()])
        with (self.home/'sessions/a.jsonl').open('a') as stream: stream.write('{"type":"token_count"')
        self.assertEqual(self.summary()['tokens'],1100)
    def test_output_reasoning_not_double_counted(self):
        row=event(); row['payload']['info']['total_token_usage']['reasoning_output_tokens']=90
        self.write('sessions/a.jsonl',[row]); self.assertEqual(self.summary()['output'],100)
    def test_fork_inherited_rows_are_excluded(self):
        rows=[{'type':'session_meta','timestamp':'2026-10-15T11:00:00Z','payload':{'id':'child','forked_from_id':'parent'}},
              event('2026-10-14'),event(inp=2000,cached=1600,out=200)]
        self.write('sessions/fork.jsonl',rows)
        self.assertEqual(self.summary()['tokens'],1100)
    def test_date_uses_local_timezone(self):
        row=event(); row['timestamp']='2026-10-16T00:30:00+05:00'
        self.write('sessions/a.jsonl',[row])
        expected=dt.datetime.fromisoformat(row['timestamp']).astimezone().date().isoformat()
        day=next(day for day in self.summary()['days'] if day['tokens'])
        self.assertEqual(day['date'],expected)
    def test_missing_history(self):
        result=summarize(self.home/'missing',TODAY)
        self.assertFalse(result['ok']); self.assertIsNone(result['monthUsd'])
    def test_no_private_content_in_result(self):
        self.write('sessions/a.jsonl',[{'type':'response_item','payload':{'message':'SECRET_TEXT'}},event()])
        self.assertNotIn('SECRET_TEXT',json.dumps(self.summary()))

if __name__=='__main__': unittest.main()
