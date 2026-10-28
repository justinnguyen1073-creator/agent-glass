"""Local Codex request accounting and API-equivalent token pricing (USD)."""
import datetime as dt
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import sqlite3

# USD / million tokens: input, cached input, cache writes, output.
# Bundled snapshot cross-checked against OpenAI and CodexBar on 2026-10-15.
# https://developers.openai.com/api/docs/pricing
# https://github.com/steipete/CodexBar/blob/main/Sources/CodexBarCore/Vendored/CostUsage/CostUsagePricing.swift
PRICES = {
    'gpt-5': (1.25, .125, None, 10),
    'gpt-5-codex': (1.25, .125, None, 10),
    'gpt-5-mini': (.25, .025, None, 2),
    'gpt-5-nano': (.05, .005, None, .4),
    'gpt-5-pro': (15, None, None, 120),
    'gpt-5.1': (1.25, .125, None, 10),
    'gpt-5.1-codex': (1.25, .125, None, 10),
    'gpt-5.1-codex-max': (1.25, .125, None, 10),
    'gpt-5.1-codex-mini': (.25, .025, None, 2),
    'gpt-5.2': (1.75, .175, None, 14),
    'gpt-5.2-codex': (1.75, .175, None, 14),
    'gpt-5.2-pro': (21, None, None, 168),
    'gpt-5.3-codex': (1.75, .175, None, 14),
    'gpt-5.3-codex-spark': (0, 0, None, 0),
    'gpt-5.4': (2.5, .25, None, 15),
    'gpt-5.4-mini': (.75, .075, None, 4.5),
    'gpt-5.4-nano': (.2, .02, None, 1.25),
    'gpt-5.4-pro': (30, None, None, 180),
    'gpt-5.5': (5, .5, None, 30),
    'gpt-5.5-pro': (30, None, None, 180),
    'gpt-5.6-sol': (4, .4, 5, 20),
    'gpt-5.6-terra': (2, .2, 2.5, 12),
    'gpt-5.6-luna': (.2, .02, .25, 1.2),
    'gpt-5.6-cyber': (12.5, 1.25, 15.625, 75),
    'gpt-5.5-cyber': (12.5, 1.25, None, 75),
    'gpt-6.1-sol': (2, .1, 2.5, 10),
    'gpt-6.1-terra': (1, .05, 1.25, 5),
    'gpt-6-sol': (2, .2, 2.5, 10),
    'gpt-6-astra': (10, 1, 12.5, 50),
    'gpt-6-luna': (.1, .01, .125, .5),
}
LONG_CONTEXT = {'gpt-5.4', 'gpt-5.4-pro', 'gpt-5.5', 'gpt-5.5-pro',
                'gpt-5.6-sol', 'gpt-5.6-terra', 'gpt-5.6-luna',
                'gpt-6.1-sol', 'gpt-6.1-terra', 'gpt-6-sol', 'gpt-6-astra', 'gpt-6-luna'}
FAST_MULTIPLIERS = {'gpt-5.4': 2, 'gpt-5.4-mini': 2, 'gpt-5.5': 2.5,
                    'gpt-5.6-sol': 2, 'gpt-5.6-terra': 2, 'gpt-5.6-luna': 2, 'gpt-6-astra': 2,
                    'gpt-6.1-sol': 2, 'gpt-6.1-terra': 2, 'gpt-6-sol': 2, 'gpt-6-luna': 2}
# Fast also applies above 272K for these (2x the long-context rate).
LONG_FAST = {'gpt-5.6-sol', 'gpt-5.6-terra', 'gpt-5.6-luna', 'gpt-6-astra',
             'gpt-6.1-sol', 'gpt-6.1-terra', 'gpt-6-sol', 'gpt-6-luna'}
HISTORICAL = {
    'gpt-5.6-sol': ('2026-08-21T00:00:00+00:00', (5, .5, 6.25, 30)),
    'gpt-5.6-terra': ('2026-07-30T00:00:00+00:00', (2.5, .25, 3.125, 15)),
    'gpt-5.6-luna': ('2026-07-30T00:00:00+00:00', (1, .1, 1.25, 6)),
}
FIELDS = ('input_tokens', 'cached_input_tokens', 'cache_write_input_tokens', 'output_tokens')


def normalize_model(model):
    model = (model or '').strip().removeprefix('openai/')
    model = {'gpt-5.6': 'gpt-5.6-sol', 'gpt-reserve': 'gpt-5.6-luna',
             'gpt-daybreak-blue-latest': 'gpt-5.6-sol', 'gpt-daybreak-red-latest': 'gpt-5.6-cyber'}.get(model, model)
    base = re.sub(r'-\d{4}-\d{2}-\d{2}$', '', model)
    return base if base in PRICES else model


def values(payload):
    if not isinstance(payload, dict):
        return None
    result = tuple(payload.get(name, 0) for name in FIELDS)
    # Input/output must actually be supplied, rather than an invented zero usage.
    if not all(name in payload for name in ('input_tokens', 'output_tokens')):
        return None
    return result if all(type(n) is int and n >= 0 for n in result) else None


def timestamp(value):
    parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timestamp lacks timezone')
    return parsed


@dataclass
class Request:
    time: dt.datetime
    model: str
    usage: tuple
    turn: str = None
    priority: bool = False
    position: int = 0
    total: tuple = None
    response: str = None


def price(request):
    model = normalize_model(request.model)
    rates = PRICES.get(model)
    if rates is None:
        return None
    if model in HISTORICAL:
        cutoff, old_rates = HISTORICAL[model]
        if request.time < timestamp(cutoff):
            rates = old_rates
    inp, cached, writes, out = request.usage
    cached = min(cached, inp)
    writes = min(writes, inp-cached)
    long = model in LONG_CONTEXT and inp > 272000
    multiplier = 1
    if request.priority:
        multiplier = FAST_MULTIPLIERS.get(model)
        if multiplier is None or (inp > 272000 and model not in LONG_FAST):
            return None
    input_rate, cached_rate, write_rate, output_rate = rates
    cached_rate = input_rate if cached_rate is None else cached_rate
    write_rate = input_rate if write_rate is None else write_rate
    # The entire request, including cached input, switches tiers above the threshold.
    cost = ((inp-cached-writes)*input_rate + cached*cached_rate + writes*write_rate) * (2 if long else 1)
    cost += out*output_rate*(1.5 if long else 1)
    return cost*multiplier/1e6


def read_session(path):
    """Prefer owned request IDs; reconcile their legacy notification mirrors."""
    events = []
    with path.open() as stream:
        for line in stream:
            if not any(marker in line for marker in ('"session_meta"', '"turn_context"', '"token_count"',
                                                     '"token_usage_record"', '"task_started"', '"session_configured"')):
                continue
            try:
                event = json.loads(line)
                kind, payload = event.get('type'), event.get('payload', {})
                if not isinstance(payload, dict):
                    continue
                if kind in ('session_meta', 'turn_context', 'token_usage_record') or (
                        kind == 'event_msg' and payload.get('type') in ('token_count', 'task_started', 'session_configured')):
                    keys = {
                        'session_meta': ('id', 'session_id', 'timestamp', 'forked_from_id', 'forkedFromId',
                                         'parent_session_id', 'parentSessionId', 'subagent_history_start_ordinal'),
                        'turn_context': ('turn_id', 'turnId', 'id', 'model', 'model_name', 'service_tier'),
                        'token_usage_record': ('thread_id', 'session_id', 'response_id', 'turn_id', 'model',
                                               'service_tier', 'usage', 'thread_token_usage'),
                        'event_msg': ('type', 'turn_id', 'id', 'service_tier', 'info'),
                    }[kind]
                    safe = {key: payload[key] for key in keys if key in payload}
                    if kind == 'event_msg' and isinstance(safe.get('info'), dict):
                        safe['info'] = {key: safe['info'][key] for key in ('total_token_usage', 'last_token_usage')
                                        if key in safe['info']}
                    events.append({'type': kind, 'timestamp': event.get('timestamp'),
                                   'ordinal': event.get('ordinal', -1), 'payload': safe})
            except (ValueError, AttributeError):
                continue
    meta = {}
    for event in events:
        if event['type'] != 'session_meta':
            continue
        incoming = event['payload']
        # Copied histories may contain a different thread's metadata. Enrich
        # the owning file's first identity without switching ownership later.
        if meta and incoming.get('id') and incoming['id'] != meta.get('id'):
            continue
        meta.update({key: value for key, value in incoming.items() if value is not None})
        if not meta.get('timestamp') and event.get('timestamp'):
            meta['timestamp'] = event['timestamp']
    session_id = meta.get('id') or meta.get('session_id') or str(path)
    request_session = meta.get('session_id') or session_id
    fork = any(meta.get(key) for key in ('forked_from_id', 'forkedFromId', 'parent_session_id', 'parentSessionId'))
    cutoff = None
    if fork and meta.get('timestamp'):
        try:
            cutoff = timestamp(meta['timestamp'])
        except (ValueError, TypeError, AttributeError):
            pass
    start_ordinal = meta.get("subagent_history_start_ordinal")
    if type(start_ordinal) is not int or start_ordinal < 0:
        start_ordinal = None
    model = None
    turn = None
    priority = False
    turn_models = {}
    ledger = []
    legacy = []
    responses = set()
    for position, event in enumerate(events):
        payload, kind = event['payload'], event['type']
        try:
            if kind == 'turn_context':
                turn = payload.get('turn_id') or payload.get('turnId') or payload.get('id') or turn
                model = payload.get('model') or payload.get('model_name') or model
                if turn:
                    turn_models[turn] = model
                if 'service_tier' in payload:
                    priority = payload['service_tier'] == 'priority'
            elif kind == 'event_msg' and payload.get('type') in ('task_started', 'session_configured'):
                turn = payload.get('turn_id') or payload.get('id') or turn
                if 'service_tier' in payload:
                    priority = payload['service_tier'] == 'priority'
            elif kind == 'token_usage_record':
                if start_ordinal is not None and event.get('ordinal', -1) < start_ordinal:
                    continue
                # A copied parent/fork record is not usage owned by this thread.
                if payload.get('thread_id') != session_id or (payload.get('session_id') or request_session) != request_session:
                    continue
                response = payload.get('response_id')
                usage = values(payload.get('usage'))
                total = values(payload.get('thread_token_usage'))
                if not response or response in responses or not usage or not total or any(a < b for a, b in zip(total, usage)):
                    continue
                record_turn = payload.get('turn_id') or turn
                responses.add(response)
                ledger.append(Request(timestamp(event['timestamp']), payload.get('model') or turn_models.get(record_turn) or model,
                                      usage, record_turn, payload.get('service_tier', 'priority' if priority else '') == 'priority',
                                      position, total, response))
            elif kind == 'event_msg' and payload.get('type') == 'token_count':
                info = payload.get('info') or {}
                legacy.append((timestamp(event['timestamp']), model, values(info.get('total_token_usage')),
                               values(info.get('last_token_usage')), payload.get('turn_id') or turn, priority, position, event.get('ordinal', -1)))
        except (ValueError, TypeError, KeyError, AttributeError):
            continue
    requests = list(ledger)
    observed = set()
    previous = (0, 0, 0, 0)
    counted = (0, 0, 0, 0)
    divergent = False
    mirrored_responses = set()
    for time, model, total, last, turn, priority, position, ordinal in legacy:
        if total and total in observed:
            continue
        if total:
            observed.add(total)
        delta = tuple(max(0, a-b) for a, b in zip(total, previous)) if total else None
        usage = last or delta
        monotonic = total and all(a >= b for a, b in zip(total, previous))
        if last and total and not monotonic:
            # Slightly regressed snapshots are stale, rather than a new counter epoch.
            size, old, recent = sum(total), sum(previous), sum(last)
            if old and size and recent and (size*100 >= old*98 or size+recent*2 >= old):
                continue
        if last and total and not divergent and monotonic and all(a <= b for a, b in zip(delta, last)):
            usage = delta
        if total:
            previous = total
        if not usage:
            continue
        counted = tuple(a+b for a, b in zip(counted, usage))
        divergent = divergent or (total is not None and counted != total)
        if (start_ordinal is not None and ordinal < start_ordinal) or not (usage[0] or usage[3]) or (cutoff and time < cutoff):
            continue
        mirror = False
        candidates = sorted(ledger, key=lambda owned: (owned.total != total, abs(position-owned.position)))
        for owned in candidates:
            if owned.response in mirrored_responses:
                continue
            same_usage = last == owned.usage or (last is None and usage == owned.usage)
            if not same_usage:
                continue
            same_counter = total is not None and total == owned.total
            same_turn = turn is not None and turn == owned.turn
            # Physical adjacency + identical usage gives continuity even when a
            # resume changed the cumulative counter offset or notification time.
            near = abs((time-owned.time).total_seconds()) <= 5
            adjacent = abs(position-owned.position) <= 1
            if same_counter or (same_turn and (near or adjacent)):
                mirror = True
                mirrored_responses.add(owned.response)
                break
        if not mirror:
            requests.append(Request(time, model, usage, turn, priority, position, total))
    return session_id, requests


def priority_turns(home, start, end):
    """Read only tier/turn/model metadata from the optional local trace database."""
    database = home / 'logs_2.sqlite'
    if not database.is_file():
        return set()
    result = set()
    marker = 'websocket request:'
    try:
        with sqlite3.connect(database.resolve().as_uri()+'?mode=ro', uri=True, timeout=.25) as conn:
            conn.execute('PRAGMA query_only=ON')
            # JSON extraction stays inside SQLite: prompts never enter Python.
            query = '''SELECT substr(feedback_log_body,1,instr(feedback_log_body,?)-1),
                              json_extract(substr(feedback_log_body,instr(feedback_log_body,?)+?), '$.turn_id')
                       FROM logs WHERE ts >= ? AND ts < ? AND instr(feedback_log_body,?) > 0
                       AND json_valid(substr(feedback_log_body,instr(feedback_log_body,?)+?))
                       AND json_extract(substr(feedback_log_body,instr(feedback_log_body,?)+?), '$.service_tier')='priority' '''
            params = (marker, marker, len(marker), start, end, marker, marker, len(marker), marker, len(marker))
            for prefix, json_turn in conn.execute(query, params):
                match = re.search(r'(?:turn\.id|turn_id)=([^\s,\]}):]+)', prefix)
                turn = match.group(1).strip('"') if match else json_turn
                if turn:
                    result.add(turn)
    except sqlite3.Error:
        pass
    return result


def summarize(home=None, today=None):
    home = Path(home or os.environ.get('CODEX_HOME') or Path.home() / '.codex')
    today = today or dt.datetime.now().astimezone().date()
    start = today-dt.timedelta(days=29)
    days = {start+dt.timedelta(days=i): {'usd': 0.0, 'tokens': 0} for i in range(30)}
    start_time = dt.datetime.combine(start, dt.time()).astimezone().timestamp()
    end_time = dt.datetime.combine(today+dt.timedelta(days=1), dt.time()).astimezone().timestamp()
    fast_turns = priority_turns(home, start_time, end_time)
    seen = set()
    seen_responses = set()
    totals = [0]*len(FIELDS)
    unknown = priced_tokens = errors = 0
    found = False
    for folder in ('sessions', 'archived_sessions'):
        base = home/folder
        if not base.is_dir():
            continue
        found = True
        for path in sorted(base.rglob('*.jsonl')):
            try:
                if path.stat().st_mtime < start_time:
                    continue
                session_id, requests = read_session(path)
            except (OSError, ValueError):
                errors += 1
                continue
            if session_id in seen:
                continue
            seen.add(session_id)
            for request in requests:
                date = request.time.astimezone().date()
                if date not in days:
                    continue
                if request.response:
                    identity = (session_id, request.response)
                    if identity in seen_responses:
                        continue
                    seen_responses.add(identity)
                request.priority = request.priority or request.turn in fast_turns
                tokens = request.usage[0]+request.usage[3]
                days[date]['tokens'] += tokens
                totals = [a+b for a, b in zip(totals, request.usage)]
                cost = price(request)
                if cost is None:
                    unknown += tokens
                else:
                    days[date]['usd'] += cost
                    priced_tokens += tokens
    return {
        'ok': found and not (errors and not seen),
        'todayUsd': round(days[today]['usd'], 6) if priced_tokens else None,
        'monthUsd': round(sum(day['usd'] for day in days.values()), 6) if priced_tokens else None,
        'tokens': totals[0]+totals[3], 'input': totals[0], 'cached': totals[1], 'output': totals[3],
        'unpricedTokens': unknown, 'incomplete': bool(unknown or errors),
        'days': [{'date': date.isoformat(), 'usd': round(value['usd'], 6), 'tokens': value['tokens']} for date, value in days.items()],
        'basis': 'API-equivalent token estimate with request-level long-context, known Fast and historical rates. Local history only; excludes tools and unknown model prices.',
        'pricingDate': '2026-10-27',
    }
