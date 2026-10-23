"""Claude Code plan limits and local API-equivalent spending (USD)."""
import datetime as dt
import fcntl
import json
import math
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.request

USAGE_URL = 'https://api.anthropic.com/api/oauth/usage'
TIMEOUT = 15
MIN_INTERVAL = 300  # seconds between real usage requests, shared by all widgets
MAX_BACKOFF = 3600

# USD / million tokens: input, 5-minute cache write, 1-hour cache write, cache read, output.
# Anthropic list prices, snapshot 2026-10-06. Writes are 1.25x / 2x input.
# https://platform.claude.com/docs/en/about-claude/pricing
def _rates(inp, out, read=None):
    return (inp, inp*1.25, inp*2, inp*.1 if read is None else read, out)


PRICES = {
    'claude-fable-5-1': _rates(10, 50, .25),
    'claude-mythos-5-1': _rates(10, 50, .25),
    'claude-fable-5': _rates(10, 50),
    'claude-opus-5-5': _rates(4, 20, .2),
    'claude-opus-5': _rates(5, 25),
    'claude-opus-4-8': _rates(5, 25),
    'claude-opus-4-7': _rates(5, 25),
    'claude-opus-4-6': _rates(5, 25),
    'claude-opus-4-5': _rates(5, 25),
    'claude-opus-4-1': _rates(15, 75),
    'claude-opus-4': _rates(15, 75),
    'claude-sonnet-5-5': _rates(2, 10, .2),
    'claude-sonnet-5': _rates(2, 10),
    'claude-sonnet-4-6': _rates(3, 15),
    'claude-sonnet-4-5': _rates(3, 15),
    'claude-sonnet-4': _rates(3, 15),
    'claude-haiku-5-5': _rates(.1, .5),
    'claude-haiku-4-5': _rates(1, 5),
    'claude-3-5-haiku': _rates(.8, 4),
}
# Haiku 5.5 prompts above 100K input tokens use the higher tier.
LONG_PRICES = {'claude-haiku-5-5': (100000, _rates(.5, 2.5))}
FAST_MULTIPLIERS = {'claude-opus-5-5': 2, 'claude-opus-5': 2, 'claude-opus-4-8': 2}


def normalize_model(model):
    model = (model or '').strip().removeprefix('anthropic.').split('[')[0]
    model = re.sub(r'(-\d{8}|@\d{8}|-v\d+(:\d+)?)$', '', model)
    return model


def price(model, usage):
    model = normalize_model(model)
    rates = PRICES.get(model)
    if rates is None:
        return None
    inp, w5, w1h, read, out = usage
    if model in LONG_PRICES and inp+w5+w1h+read > LONG_PRICES[model][0]:
        rates = LONG_PRICES[model][1]
    return sum(n*r for n, r in zip(usage, rates))/1e6


def token_values(usage):
    """(input, 5m writes, 1h writes, cache reads, output) from a message usage block."""
    if not isinstance(usage, dict):
        return None
    get = lambda key: usage.get(key) or 0
    writes = get('cache_creation_input_tokens')
    detail = usage.get('cache_creation') if isinstance(usage.get('cache_creation'), dict) else {}
    w1h = detail.get('ephemeral_1h_input_tokens') or 0
    w5 = detail.get('ephemeral_5m_input_tokens') or 0
    if w1h+w5 != writes:
        w5, w1h = writes-min(w1h, writes), min(w1h, writes)
    result = (get('input_tokens'), w5, w1h, get('cache_read_input_tokens'), get('output_tokens'))
    return result if all(type(n) is int and n >= 0 for n in result) else None


def summarize(home=None, today=None):
    home = Path(home or os.environ.get('CLAUDE_CONFIG_DIR') or Path.home()/'.claude')
    today = today or dt.datetime.now().astimezone().date()
    start = today-dt.timedelta(days=29)
    days = {start+dt.timedelta(days=i): {'usd': 0.0, 'tokens': 0} for i in range(30)}
    start_time = dt.datetime.combine(start, dt.time()).astimezone().timestamp()
    base = home/'projects'
    seen = set()
    totals = [0]*5
    unknown = priced = errors = 0
    for path in sorted(base.rglob('*.jsonl')) if base.is_dir() else ():
        try:
            if path.stat().st_mtime < start_time:
                continue
            stream = path.open(errors='replace')
        except OSError:
            errors += 1
            continue
        with stream:
            for line in stream:
                if '"usage"' not in line or '"assistant"' not in line:
                    continue
                try:
                    event = json.loads(line)
                    message = event.get('message') or {}
                    usage = token_values(message.get('usage'))
                    if event.get('type') != 'assistant' or not usage or message.get('model') == '<synthetic>':
                        continue
                    # Streamed messages are logged once per content block with identical usage.
                    identity = (message.get('id'), event.get('requestId'))
                    if identity[0] and identity in seen:
                        continue
                    seen.add(identity)
                    stamp = dt.datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00'))
                    date = stamp.astimezone().date()
                except (ValueError, TypeError, KeyError, AttributeError):
                    continue
                if date not in days:
                    continue
                tokens = sum(usage)
                days[date]['tokens'] += tokens
                totals = [a+b for a, b in zip(totals, usage)]
                cost = price(message.get('model'), usage)
                if cost is not None and message['usage'].get('speed') == 'fast':
                    multiplier = FAST_MULTIPLIERS.get(normalize_model(message.get('model')))
                    cost = cost*multiplier if multiplier else None
                if cost is None:
                    unknown += tokens
                else:
                    days[date]['usd'] += cost
                    priced += tokens
    inp, w5, w1h, read, out = totals
    return {
        'ok': base.is_dir(),
        'todayUsd': round(days[today]['usd'], 6) if priced else None,
        'monthUsd': round(sum(d['usd'] for d in days.values()), 6) if priced else None,
        # Match Codex's convention: "input" includes cached tokens.
        'tokens': sum(totals), 'input': inp+w5+w1h+read, 'cached': read, 'cacheWrites': w5+w1h, 'output': out,
        'unpricedTokens': unknown, 'incomplete': bool(unknown or errors),
        'days': [{'date': d.isoformat(), 'usd': round(v['usd'], 6), 'tokens': v['tokens']} for d, v in days.items()],
        'pricingDate': '2026-10-06',
    }


def normalize_limits(payload):
    if not isinstance(payload, dict):
        raise ValueError('Missing limits')
    result = {'ok': True, 'updatedAt': dt.datetime.now(dt.timezone.utc).isoformat(), 'fiveHour': None, 'weekly': None}
    for source, key in (('five_hour', 'fiveHour'), ('seven_day', 'weekly')):
        window = payload.get(source)
        if not isinstance(window, dict):
            continue
        used = window.get('utilization')
        if type(used) not in (int, float) or not math.isfinite(used):
            continue
        used = max(0, min(100, used))
        reset = window.get('resets_at')
        try:
            reset = dt.datetime.fromisoformat(reset.replace('Z', '+00:00')).isoformat()
        except (ValueError, AttributeError):
            reset = None
        result[key] = {'used': used, 'remaining': round(100-used, 2), 'resetsAt': reset}
    return result


def fetch_limits(home=None):
    """Read Claude Code's own sign-in and ask Anthropic for plan usage. Never refreshes or stores tokens."""
    home = Path(home or os.environ.get('CLAUDE_CONFIG_DIR') or Path.home()/'.claude')
    try:
        oauth = json.loads((home/'.credentials.json').read_text()).get('claudeAiOauth') or {}
    except (OSError, ValueError, AttributeError):
        return {'ok': False, 'message': 'Sign in to Claude Code with your Claude account, then refresh.'}
    token, expires = oauth.get('accessToken'), oauth.get('expiresAt')
    if not token:
        return {'ok': False, 'message': 'Sign in to Claude Code with your Claude account, then refresh.'}
    if type(expires) in (int, float) and expires/1000 < time.time():
        return {'ok': False, 'message': 'Claude sign-in expired. Open Claude Code once to renew it.'}
    request = urllib.request.Request(USAGE_URL, headers={
        'Authorization': 'Bearer '+token, 'anthropic-beta': 'oauth-2025-04-20',
        'User-Agent': 'agent-glass/3.0', 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return normalize_limits(json.loads(response.read(2*1024*1024)))
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            return {'ok': False, 'message': 'Claude sign-in expired. Open Claude Code once to renew it.'}
        if error.code == 429:
            return {'ok': False, 'rateLimited': True, 'retryAfter': error.headers.get('retry-after'),
                    'message': 'Claude is rate limiting usage checks. Retrying shortly.'}
        return {'ok': False, 'message': 'Unable to refresh Claude usage. Try again later.'}
    except (urllib.error.URLError, TimeoutError, OSError):
        return {'ok': False, 'message': 'Unable to reach Claude. Check your connection.'}
    except (ValueError, TypeError):
        return {'ok': False, 'message': 'Could not read Claude usage.'}


def read_limits(home=None, cache=None, now=None):
    """Share one Anthropic request across widget instances, and back off when rate limited.

    The cache holds only the normalized percentages and timing, never credentials."""
    now = time.time() if now is None else now
    cache = Path(cache or Path(os.environ.get('XDG_CACHE_HOME') or Path.home()/'.cache')/'agent-glass/claude-limits.json')
    cache.parent.mkdir(parents=True, exist_ok=True)
    with open(cache.with_suffix('.lock'), 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            state = json.loads(cache.read_text())
            if not isinstance(state, dict):
                state = {}
        except (OSError, ValueError):
            state = {}
        last = state.get('limits') if isinstance(state.get('limits'), dict) else None
        fresh = last and now - state.get('fetchedAt', 0) < MIN_INTERVAL
        if fresh or now < state.get('retryAt', 0):
            if last:
                result = dict(last)
                if not fresh and state.get('message'):
                    result['message'] = state['message']
                return result
            return {'ok': False, 'message': state.get('message') or 'Waiting to retry Claude usage.'}
        result = fetch_limits(home)
        if result.get('ok'):
            state = {'limits': result, 'fetchedAt': now}
        else:
            failures = state.get('failures', 0)+1
            wait = min(MAX_BACKOFF, MIN_INTERVAL * 2**(failures-1)) if result.get('rateLimited') else MIN_INTERVAL
            try:
                wait = max(wait, min(MAX_BACKOFF, float(result.get('retryAfter'))))
            except (TypeError, ValueError):
                pass
            state.update({'retryAt': now+wait, 'failures': failures, 'message': result['message']})
            if last:
                # Keep showing the last good numbers, labelled stale, rather than blanking the bars.
                result = dict(last, message=result['message'])
        tmp = cache.with_suffix('.tmp')
        tmp.write_text(json.dumps(state))
        tmp.replace(cache)
        return result


def main():
    result = read_limits()
    try:
        result['spending'] = summarize()
    except (OSError, ValueError, TypeError):
        result['spending'] = {'ok': False}
    return result


if __name__ == '__main__':
    print(json.dumps(main(), allow_nan=False))
