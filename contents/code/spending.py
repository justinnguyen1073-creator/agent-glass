"""Local-only token history estimates; never publish prompts or session metadata."""
import datetime as dt
import json
import os
from pathlib import Path

# USD / million tokens: input, cached input, cache writes, output.
# Standard short-context list prices, verified 2026-10-15:
# https://developers.openai.com/api/docs/pricing
PRICES = {
    # https://developers.openai.com/api/docs/models/gpt-5.5
    'gpt-5.5': (5, .50, None, 30),
    'gpt-6.1-sol': (2, .10, 2.50, 10),
    'gpt-6-astra': (10, 1, 12.50, 50),
    'gpt-6-luna': (.10, .01, .125, .50),
    'gpt-5.6-sol': (4, .40, 5, 20),
    'gpt-5.3-codex': (1.75, .175, None, 14),
}
FIELDS = ('input_tokens', 'cached_input_tokens', 'cache_write_input_tokens', 'output_tokens')


def read_session(path):
    """Use cumulative deltas so repeated token_count notifications count once."""
    previous = [0] * len(FIELDS)
    model = None
    session_id = None
    cutoff = None
    rows = []
    with path.open() as stream:
        for line in stream:
            # Do not even decode conversation messages or tool results.
            if not any(marker in line for marker in ('"session_meta"', '"turn_context"', '"token_count"')):
                continue
            try:
                event = json.loads(line)
                payload = event.get('payload', {})
                kind = event.get('type')
                if kind == 'session_meta':
                    session_id = payload.get('id')
                    if payload.get('forked_from_id'):
                        cutoff = dt.datetime.fromisoformat(payload.get('timestamp', event['timestamp']).replace('Z', '+00:00'))
                elif kind == 'turn_context':
                    model = payload.get('model')
                elif kind == 'event_msg' and payload.get('type') == 'token_count':
                    total = (payload.get('info') or {}).get('total_token_usage')
                    if not isinstance(total, dict):
                        continue
                    current = [total.get(name, 0) for name in FIELDS]
                    if any(type(value) is not int or value < 0 for value in current):
                        continue
                    delta = [max(0, value-old) for value, old in zip(current, previous)]
                    previous = [max(value, old) for value, old in zip(current, previous)]
                    timestamp = dt.datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00'))
                    if timestamp.tzinfo is None or (cutoff and timestamp < cutoff):
                        continue
                    if delta[0] or delta[3]:
                        rows.append((timestamp.astimezone().date(), model, delta))
            except (ValueError, TypeError, KeyError, AttributeError):
                continue
    return session_id or str(path), rows


def summarize(home=None, today=None):
    home = Path(home or os.environ.get('CODEX_HOME') or Path.home() / '.codex')
    today = today or dt.datetime.now().astimezone().date()
    start = today - dt.timedelta(days=29)
    days = {start + dt.timedelta(days=index): {'usd': 0.0, 'tokens': 0} for index in range(30)}
    seen = set()
    totals = [0] * len(FIELDS)
    unknown = 0
    priced_tokens = 0
    errors = 0
    found = False
    for folder in ('sessions', 'archived_sessions'):
        base = home / folder
        if not base.is_dir():
            continue
        found = True
        for path in sorted(base.rglob('*.jsonl')):
            try:
                if dt.datetime.fromtimestamp(path.stat().st_mtime).date() < start:
                    continue
                session_id, rows = read_session(path)
            except (OSError, ValueError):
                errors += 1
                continue
            if session_id in seen:
                continue
            seen.add(session_id)
            for date, model, values in rows:
                if date not in days:
                    continue
                tokens = values[0] + values[3]
                days[date]['tokens'] += tokens
                totals = [a+b for a, b in zip(totals, values)]
                rates = PRICES.get(model)
                if rates is None or (values[2] and rates[2] is None):
                    unknown += tokens
                    continue
                inp, cached, writes, out = values
                cached = min(cached, inp)
                writes = min(writes, inp-cached)
                cost = sum(amount * (rate or 0) for amount, rate in zip((inp-cached-writes, cached, writes, out), rates)) / 1e6
                days[date]['usd'] += cost
                priced_tokens += tokens
    return {
        'ok': found and not (errors and not seen),
        'todayUsd': round(days[today]['usd'], 6) if priced_tokens else None,
        'monthUsd': round(sum(day['usd'] for day in days.values()), 6) if priced_tokens else None,
        'tokens': totals[0] + totals[3], 'input': totals[0], 'cached': totals[1], 'output': totals[3],
        'unpricedTokens': unknown, 'incomplete': bool(unknown or errors),
        'days': [{'date': date.isoformat(), 'usd': round(value['usd'], 6), 'tokens': value['tokens']} for date, value in days.items()],
        'basis': 'Standard short-context token rates; excludes tools and speed/long-context premiums. Local history only.',
        'pricingDate': '2026-10-15',
    }
