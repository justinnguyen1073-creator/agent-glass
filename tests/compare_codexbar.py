"""Optional developer check; CodexBar is not needed by the widget or unit tests.

Compare a frozen CODEX_HOME copy against JSON exported by CodexBar from that
same copy. Do not publish the logs or raw CodexBar JSON; they may be private.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'contents/code'))
from spending import summarize

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--history', type=Path, required=True)
parser.add_argument('--reference', type=Path, required=True)
parser.add_argument('--date', type=dt.date.fromisoformat, default=dt.datetime.now().astimezone().date())
args=parser.parse_args()
payload=json.loads(args.reference.read_text())
reference=next(row for row in payload if row.get('provider')=='codex')
ours=summarize(args.history, args.date)
errors=[]
for actual, expected in [('todayUsd','sessionCostUSD'),('monthUsd','last30DaysCostUSD'),('tokens','last30DaysTokens')]:
    a,b=ours[actual],reference.get(expected)
    if a!=b and (a is None or b is None or abs(a-b)>=1e-6): errors.append(actual)
for actual,expected in [('input','inputTokens'),('cached','cacheReadTokens'),('output','outputTokens')]:
    if ours[actual]!=reference['totals'].get(expected): errors.append(actual)
days={day['date']:day for day in reference.get('daily',[])}
for day in ours['days']:
    ref=days.get(day['date'],{})
    if day['tokens']!=ref.get('totalTokens',0) or abs(day['usd']-(ref.get('totalCost') or 0))>=1e-6:
        errors.append('daily bucket '+day['date'])
if errors:
    print('Mismatch: '+', '.join(errors)); sys.exit(1)
print('PASS: totals, token categories, and daily buckets match CodexBar (cost tolerance $0.000001).')
