#!/usr/bin/python3
"""Read account limits through Codex's local app-server, without reading tokens."""
import argparse
import concurrent.futures
import datetime as dt
import json
import math
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import subprocess
import time
from spending import summarize
import claude_usage

TIMEOUT = 40


class RpcError(Exception):
    def __init__(self, error):
        self.code = error.get('code') if isinstance(error, dict) else None
        self.message = str(error.get('message', '')) if isinstance(error, dict) else ''


def normalize(payload):
    if not isinstance(payload, dict) or not any(k in payload for k in ('rateLimits', 'rateLimitsByLimitId')):
        raise ValueError('Missing limits')
    buckets = payload.get('rateLimitsByLimitId')
    if isinstance(buckets, dict) and buckets:
        bucket = buckets.get('codex', {})
    else:
        bucket = payload.get('rateLimits') or {}
        if isinstance(bucket, dict) and bucket.get('limitId') not in (None, 'codex'):
            bucket = {}
    if not isinstance(bucket, dict):
        raise ValueError('Invalid limits')
    result = {'ok': True, 'updatedAt': dt.datetime.now(dt.timezone.utc).isoformat(), 'fiveHour': None, 'weekly': None}
    for name in ('primary', 'secondary'):
        window = bucket.get(name)
        if not isinstance(window, dict):
            continue
        duration, used = window.get('windowDurationMins'), window.get('usedPercent')
        if type(duration) not in (int, float) or type(used) not in (int, float):
            continue
        key = {300: 'fiveHour', 10080: 'weekly'}.get(duration)
        if not key or not math.isfinite(used) or not 0 <= used <= 100:
            continue
        reset = window.get('resetsAt')
        try:
            if type(reset) not in (int, float) or not math.isfinite(reset) or reset <= 0:
                raise ValueError('Invalid reset')
            reset = dt.datetime.fromtimestamp(reset, dt.timezone.utc).isoformat()
        except (ValueError, OverflowError, OSError):
            reset = None
        result[key] = {'used': used, 'remaining': round(100-used, 2), 'resetsAt': reset}
    return result


def find_codex(configured=''):
    """Find existing installs, including nvm installs absent from Plasma's PATH."""
    if configured:
        candidate = Path(configured).expanduser()
        return candidate if candidate.is_absolute() and candidate.is_file() and os.access(candidate, os.X_OK) else None
    found = shutil.which('codex')
    if found:
        return Path(found)
    home = Path.home()
    for candidate in (home / '.local/bin/codex', home / '.cargo/bin/codex', home / '.npm-global/bin/codex'):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    nvm = Path(os.environ.get('NVM_DIR') or home / '.nvm')
    candidates = list((nvm / 'versions/node').glob('v*/bin/codex'))
    def version(path):
        match = re.fullmatch(r'v(\d+)\.(\d+)\.(\d+)', path.parent.parent.name)
        return tuple(map(int, match.groups())) if match else (0, 0, 0)
    for candidate in sorted(candidates, key=version, reverse=True):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None


def codex_command(binary):
    """Use the matching node for an npm install, even in a desktop session."""
    resolved = binary.resolve()
    if resolved.suffix == '.js':
        node = binary.parent / 'node'
        if node.is_file() and os.access(node, os.X_OK):
            return [str(node), str(resolved)]
    return [str(binary)]


def read_limits(command, timeout=TIMEOUT):
    """One private stdio connection; initialize then read limits, never start a turn."""
    process = subprocess.Popen(command + ['app-server', '--listen', 'stdio://'],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, start_new_session=True)
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    buffer = b''
    deadline = time.monotonic() + timeout

    def send(message):
        process.stdin.write(json.dumps(message).encode() + b'\n')
        process.stdin.flush()

    def receive(request_id):
        nonlocal buffer
        while True:
            while b'\n' in buffer:
                line, buffer = buffer.split(b'\n', 1)
                if not line.strip():
                    continue
                message = json.loads(line)
                if not isinstance(message, dict):
                    raise ValueError('Invalid RPC message')
                if message.get('id') == request_id and ('result' in message or 'error' in message):
                    if 'error' in message:
                        raise RpcError(message['error'])
                    return message['result']
                # Decline any unexpected server request. Never return credentials.
                if 'id' in message and 'method' in message:
                    send({'id': message['id'], 'error': {'code': -32601, 'message': 'Unsupported method'}})
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not selector.select(remaining):
                raise TimeoutError('Codex timed out')
            chunk = os.read(process.stdout.fileno(), 65536)
            if not chunk:
                raise ValueError('Codex closed its output')
            buffer += chunk
            if len(buffer) > 2 * 1024 * 1024:
                raise ValueError('Response too large')

    try:
        send({'id': 1, 'method': 'initialize', 'params': {
            'clientInfo': {'name': 'codex_glass', 'title': 'Agent Glass', 'version': '3.0.0'}}})
        receive(1)
        send({'method': 'initialized', 'params': {}})
        send({'id': 2, 'method': 'account/rateLimits/read'})
        return receive(2)
    finally:
        selector.close()
        # Terminate only our new process group, including an npm wrapper's child.
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        process.stdin.close()
        process.stdout.close()


def main(configured=''):
    try:
        binary = find_codex(configured)
        if not binary:
            return {'ok': False, 'message': 'Codex not found. Select your existing Codex executable in widget settings.'}
        return normalize(read_limits(codex_command(binary)))
    except RpcError as error:
        message = error.message.lower()
        if error.code == -32601:
            text = 'This Codex version does not support usage reads. Update Codex.'
        elif any(word in message for word in ('auth', '401', '403', 'sign in', 'login', 'token', 'chatgpt', 'api key', 'apikey')):
            text = 'Sign in to Codex with your ChatGPT account, then refresh.'
        else:
            text = 'Unable to refresh Codex usage. Check your connection and try again.'
        return {'ok': False, 'message': text}
    except TimeoutError:
        return {'ok': False, 'message': 'Refresh timed out. Check your connection.'}
    except (ValueError, TypeError, OSError):
        return {'ok': False, 'message': 'Could not read usage. Check your Codex installation and login.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--codex', default='', help='Absolute path to an existing Codex executable')
    with concurrent.futures.ThreadPoolExecutor(1) as pool:
        claude = pool.submit(claude_usage.main)
        result = main(parser.parse_args().codex)
        try:
            result['claude'] = claude.result()
        except Exception:
            result['claude'] = {'ok': False, 'message': 'Could not read Claude usage.', 'spending': {'ok': False}}
    try:
        result['spending'] = summarize()
    except (OSError, ValueError, TypeError):
        result['spending'] = {'ok': False}
    print(json.dumps(result, allow_nan=False))
