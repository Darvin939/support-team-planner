"""Real HTTPS and HTTP startup/login with isolated SQLite and owned processes.

Run from the repo: PYTHONPATH=. SUPPORT_PLANNER_SKIP_DOTENV=1 python tests/tls_startup_smoke.py
Requires OpenSSL and the existing production UI test dependencies.
"""
import hashlib
import http.client
import json
import os
import socket
import ssl
import subprocess
import sys
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

from scripts.ui_test_harness import sqlite_backup, stop_process
from tls_test_support import create_test_pair


ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def backend_for(mode, output, pair):
    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1', 5093)) == 0:
            raise RuntimeError('Port 5093 is occupied; the existing process was left untouched')
    directory = output / mode
    directory.mkdir()
    database = directory / 'database.db'
    backup = directory / ('database.db.' + uuid4().hex + '.bak')
    sqlite_backup(database, backup)
    env = os.environ.copy()
    for name in ('SUPPORT_PLANNER_DATABASE_URL', 'SUPPORT_PLANNER_ENV_FILE',
                 'SUPPORT_PLANNER_TLS_CERT_FILE', 'SUPPORT_PLANNER_TLS_KEY_FILE',
                 'VAULT_ADDR', 'VAULT_TENANT', 'VAULT_KV_PATH', 'ROLE_ID', 'SECRET_ID'):
        env.pop(name, None)
    env.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8',
               SUPPORT_PLANNER_DB_PATH=str(database), SESSION_SECRET_KEY='isolated-tls-smoke-session')
    if mode == 'https':
        selected = directory / 'env'
        selected.write_text(
            'SUPPORT_PLANNER_TLS_CERT_FILE=%s\nSUPPORT_PLANNER_TLS_KEY_FILE=%s\n' % pair,
            encoding='utf-8',
        )
        env.pop('SUPPORT_PLANNER_SKIP_DOTENV', None)
        env['SUPPORT_PLANNER_ENV_FILE'] = str(selected)
    else:
        env['SUPPORT_PLANNER_SKIP_DOTENV'] = '1'
    base = mode + '://127.0.0.1:5093'
    context = ssl.create_default_context(cafile=str(pair[0])) if mode == 'https' else None
    process = None
    try:
        with (directory / 'backend.log').open('w', encoding='utf-8') as log:
            try:
                process = subprocess.Popen(
                    [sys.executable, str(ROOT / 'support_planner.py')], cwd=directory,
                    env=env, stdout=log, stderr=subprocess.STDOUT,
                )
                for _ in range(80):
                    if process.poll() is not None:
                        raise RuntimeError('Backend stopped; see %s' % directory)
                    try:
                        with urllib.request.urlopen(base + '/login', context=context, timeout=1) as response:
                            if response.status == 200:
                                break
                    except OSError:
                        time.sleep(0.25)
                else:
                    raise RuntimeError('Backend did not become ready; see %s' % directory)
                yield base, context
            finally:
                stop_process(process)
    finally:
        sqlite_backup(backup, database)
        (directory / 'restore-verified.txt').write_text('SQLite API restore, checkpoint and digest: OK\n', encoding='utf-8')


def main():
    output = ROOT / '.tmp' / ('tls-startup-' + uuid4().hex[:12])
    output.mkdir(parents=True)
    print('Artifacts:', output, flush=True)
    pair = create_test_pair(output / 'test-only-tls')
    env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
    command = ['cmd.exe', '/c', 'npm.cmd', 'run', 'build'] if os.name == 'nt' else ['npm', 'run', 'build']
    with (output / 'build.log').open('w', encoding='utf-8') as log:
        subprocess.run(command, cwd=ROOT / 'frontend', env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
    checks = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, channel=os.environ.get('SUPPORT_PLANNER_UI_BROWSER_CHANNEL'))
        try:
            for mode in ('https', 'http'):
                with backend_for(mode, output, pair) as (base, context):
                    if context is not None:
                        with socket.create_connection(('127.0.0.1', 5093), timeout=2) as raw:
                            with context.wrap_socket(raw, server_hostname='127.0.0.1') as connection:
                                expected = ssl.PEM_cert_to_DER_cert(pair[0].read_text(encoding='utf-8'))
                                assert connection.getpeercert(binary_form=True) == expected
                                checks.append({'tls_version': connection.version(), 'cert_sha256': hashlib.sha256(expected).hexdigest()})
                        try:
                            urllib.request.urlopen('http://127.0.0.1:5093/login', timeout=2).close()
                        except (OSError, http.client.HTTPException):
                            pass
                        else:
                            raise AssertionError('HTTPS listener unexpectedly served plain HTTP')
                    browser_context = browser.new_context(ignore_https_errors=mode == 'https', viewport={'width': 1440, 'height': 1000})
                    try:
                        page = browser_context.new_page()
                        errors = []
                        page.on('pageerror', lambda error: errors.append(str(error)))
                        page.goto(base + '/login')
                        page.locator('form input').nth(0).fill('admin')
                        page.locator('form input').nth(1).fill('q12345678')
                        page.locator('form button[type=submit]').click()
                        page.wait_for_url('**/planning**')
                        expect(page.get_by_role('heading', name='Планирование', exact=True)).to_be_visible()
                        response = page.request.get(base + '/api/me')
                        assert response.status == 200 and response.json()['login'] == 'admin'
                        assert any(cookie['name'] == 'sp_session' for cookie in browser_context.cookies())
                        assert not errors, errors
                        checks.append(mode + ': production real-form login, session cookie, protected page and API')
                    finally:
                        browser_context.close()
                checks.append(mode + ': owned backend stopped; SQLite backup restored and verified')
        finally:
            browser.close()
    (output / 'result.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(checks, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
