import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'contents/code'))
from spending import summarize, price, Request, priority_turns, normalize_model

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
        self.write('sessions/fork.jsonl',rows,sid='child')
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




def ledger(response='response', inp=1000, cached=800, out=100, total=None, thread='session', turn='turn', time='2026-10-15T12:00:00Z'):
    usage={'input_tokens':inp,'cached_input_tokens':cached,'output_tokens':out}
    return {'timestamp':time,'type':'token_usage_record','payload':{
        'thread_id':thread,'session_id':thread,'turn_id':turn,'response_id':response,
        'usage':usage,'thread_token_usage':total or usage}}

class RequestAccountingTests(unittest.TestCase):
    setUp=SpendingTests.setUp
    tearDown=SpendingTests.tearDown
    write=SpendingTests.write
    summary=SpendingTests.summary
    def test_owned_ledger_and_notification_count_once(self):
        self.write('sessions/a.jsonl',[ledger(),event()])
        self.assertEqual(self.summary()['tokens'],1100)
    def test_ledger_response_identity_deduplicates_replays(self):
        self.write('sessions/a.jsonl',[ledger(),ledger()])
        self.assertEqual(self.summary()['tokens'],1100)
    def test_distinct_requests_survive_identical_counters(self):
        self.write('sessions/a.jsonl',[ledger('one'),ledger('two')])
        self.assertEqual(self.summary()['tokens'],2200)
    def test_copied_parent_ledger_not_owned_by_child(self):
        self.write('sessions/a.jsonl',[ledger(thread='parent')])
        self.assertEqual(self.summary()['tokens'],0)
    def test_explicit_subagent_ordinal_excludes_copied_prefix(self):
        meta={'type':'session_meta','payload':{'id':'session','subagent_history_start_ordinal':10}}
        inherited=event(); inherited['ordinal']=3
        owned=event(inp=2000,cached=1600,out=200); owned['ordinal']=10
        self.write('sessions/a.jsonl',[meta,inherited,owned])
        self.assertEqual(self.summary()['tokens'],1100)
    def test_owned_request_before_subagent_boundary_is_ignored(self):
        meta={'type':'session_meta','payload':{'id':'session','subagent_history_start_ordinal':10}}
        inherited=ledger('copy'); inherited['ordinal']=5
        owned=ledger('owned'); owned['ordinal']=10
        self.write('sessions/a.jsonl',[meta,inherited,owned])
        self.assertEqual(self.summary()['tokens'],1100)
    def test_copied_metadata_does_not_change_owner(self):
        copied={'type':'session_meta','payload':{'id':'another-thread'}}
        self.write('sessions/a.jsonl',[ledger('one'),copied,ledger('two')])
        self.assertEqual(self.summary()['tokens'],2200)
    def test_legacy_only_per_request_usage_is_accepted(self):
        row=event(); info=row['payload']['info']; info['last_token_usage']=info.pop('total_token_usage')
        self.write('sessions/a.jsonl',[row]); self.assertEqual(self.summary()['tokens'],1100)
    def test_offset_counter_mirror_after_resume(self):
        context={'type':'turn_context','payload':{'model':'gpt-6.1-sol','turn_id':'turn'}}
        notification=event(inp=1000,cached=800,out=100)
        notification['payload']['info']['last_token_usage']=dict(notification['payload']['info']['total_token_usage'])
        notification['timestamp']='2026-10-15T12:01:00Z'
        owned=ledger(total={'input_tokens':2000,'cached_input_tokens':1600,'output_tokens':200})
        self.write('sessions/a.jsonl',[context,owned,notification])
        self.assertEqual(self.summary()['tokens'],1100)
    def test_uncovered_identical_legacy_request_is_preserved(self):
        context={'type':'turn_context','payload':{'model':'gpt-6.1-sol','turn_id':'turn'}}
        first=event(); first['payload']['info']['last_token_usage']=dict(first['payload']['info']['total_token_usage'])
        second=event(inp=2000,cached=1600,out=200)
        second['payload']['info']['last_token_usage']=dict(first['payload']['info']['last_token_usage'])
        second['timestamp']='2026-10-15T12:00:01Z'
        self.write('sessions/a.jsonl',[context,ledger(),first,second])
        self.assertEqual(self.summary()['tokens'],2200)
    def test_pricing_uses_request_size_not_cumulative_size(self):
        self.write('sessions/a.jsonl',[ledger('one',inp=200000,cached=0,out=10),
                    ledger('two',inp=200000,cached=0,out=10,total={'input_tokens':400000,'cached_input_tokens':0,'output_tokens':20})])
        self.assertAlmostEqual(self.summary()['todayUsd'],.8002)

class PricingTests(unittest.TestCase):
    def request(self,model,usage,time='2026-10-15T12:00:00+00:00',fast=False):
        return Request(dt.datetime.fromisoformat(time),model,usage,priority=fast)
    def test_long_context_prices_whole_request(self):
        self.assertAlmostEqual(price(self.request('gpt-6.1-sol',(500000,400000,0,1000))),.495)
    def test_threshold_is_strictly_greater(self):
        self.assertAlmostEqual(price(self.request('gpt-6.1-sol',(272000,0,0,0))),.544)
        self.assertAlmostEqual(price(self.request('gpt-6.1-sol',(272001,0,0,0))),1.088004)
    def test_terra_is_priced(self):
        self.assertAlmostEqual(price(self.request('gpt-5.6-terra',(1000,0,0,1000))),.014)
    def test_historical_rates_use_request_date(self):
        self.assertAlmostEqual(price(self.request('gpt-5.6-terra',(1000,0,0,1000),'2026-07-29T12:00:00+00:00')),.0175)
        self.assertAlmostEqual(price(self.request('gpt-5.6-sol',(1000,0,0,1000),'2026-08-20T12:00:00+00:00')),.035)
    def test_published_fast_multiplier(self):
        self.assertAlmostEqual(price(self.request('gpt-5.5',(1000,0,0,100),fast=True)),.02)
        self.assertIsNone(price(self.request('gpt-5.5',(300000,0,0,100),fast=True)))
    def test_astra_fast_long_context(self):
        self.assertAlmostEqual(price(self.request('gpt-6-astra',(300000,0,0,100),fast=True)),12.015)
    def test_unknown_model_or_unpublished_fast_is_unpriced(self):
        self.assertIsNone(price(self.request('codex-auto-review',(1000,0,0,100))))
        self.assertIsNone(price(self.request('gpt-6.1-sol',(1000,0,0,100),fast=True)))
    def test_cached_input_is_subset_and_writes_are_not_double_billed(self):
        self.assertAlmostEqual(price(self.request('gpt-6.1-sol',(1000,600,200,100))),.00196)
    def test_dated_and_provider_prefixed_models(self):
        self.assertEqual(normalize_model('openai/gpt-6.1-sol-2026-10-01'),'gpt-6.1-sol')
        self.assertEqual(normalize_model('gpt-5.6'),'gpt-5.6-sol')
        self.assertEqual(normalize_model('gpt-5.5-pro'),'gpt-5.5-pro')
    def test_research_preview_is_zero_not_unknown(self):
        self.assertEqual(price(self.request('gpt-5.3-codex-spark',(1000,0,0,100))),0)
    def test_optional_trace_reads_only_priority_metadata(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as directory:
            home=Path(directory)
            with sqlite3.connect(home/'logs_2.sqlite') as conn:
                conn.execute('CREATE TABLE logs(ts INTEGER,feedback_log_body TEXT)')
                body='turn.id=turn-secret websocket request: '+json.dumps({'service_tier':'priority','input':'PRIVATE_PROMPT'})
                conn.execute('INSERT INTO logs VALUES(?,?)',(100,body))
            result=priority_turns(home,0,200)
            self.assertEqual(result,{'turn-secret'})
            self.assertNotIn('PRIVATE_PROMPT',str(result))

if __name__=='__main__': unittest.main()
