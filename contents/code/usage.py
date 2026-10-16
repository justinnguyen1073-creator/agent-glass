#!/usr/bin/python3
"""Read CodexBar; output only sanitized limits, never account or credential data."""
import datetime as dt
import json
import math
import os
from pathlib import Path
import shutil
import subprocess


def normalize(payload):
    if not isinstance(payload, list):
        raise ValueError('Invalid response')
    entry = next((x for x in payload if isinstance(x, dict) and x.get('provider') == 'codex'), {})
    if entry.get('error'):
        message = str(entry['error'].get('message', '')).lower()
        if any(x in message for x in ('401', 'unauthorized', 'expired', 'login', 'authentication')):
            return {'ok': False, 'message': 'Authentication expired. Sign in to Codex again.'}
        return {'ok': False, 'message': 'Unable to refresh. Check your connection and CodexBar.'}
    usage = entry.get('usage')
    if not isinstance(usage, dict):
        raise ValueError('Missing usage')
    result = {'ok': True, 'updatedAt': usage.get('updatedAt'), 'fiveHour': None, 'weekly': None}
    for name in ('primary', 'secondary', 'tertiary'):
        window = usage.get(name)
        if not isinstance(window, dict):
            continue
        key = {300: 'fiveHour', 10080: 'weekly'}.get(window.get('windowMinutes'))
        value = window.get('usedPercent')
        if key and type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 100:
            reset = window.get('resetsAt')
            try:
                parsed = dt.datetime.fromisoformat(reset.replace('Z', '+00:00'))
                if parsed.tzinfo is None:
                    reset = None
            except (ValueError, TypeError, AttributeError):
                reset = None
            result[key] = {'used': value, 'remaining': round(100-value, 2), 'resetsAt': reset}
    return result


def main():
    binary = shutil.which('codexbar')
    if not binary:
        candidate = Path.home() / '.local/bin/codexbar'
        binary = str(candidate) if candidate.is_file() and os.access(candidate, os.X_OK) else None
    if not binary:
        return {'ok': False, 'message': 'CodexBar is missing. Install it in PATH or ~/.local/bin.'}
    try:
        process = subprocess.run([binary, '--provider', 'codex', '--format', 'json'], capture_output=True, text=True, timeout=40)
        result = normalize(json.loads(process.stdout))
        if process.returncode and result['ok']:
            return {'ok': False, 'message': 'CodexBar failed. Retry the refresh.'}
        return result
    except subprocess.TimeoutExpired:
        return {'ok': False, 'message': 'Refresh timed out. Check your connection.'}
    except (ValueError, TypeError, OSError, StopIteration):
        return {'ok': False, 'message': 'Could not read CodexBar usage. Check its installation and login.'}

if __name__ == '__main__':
    print(json.dumps(main(), allow_nan=False))
