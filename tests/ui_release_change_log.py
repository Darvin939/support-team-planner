import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = 'http://127.0.0.1:5093'
env = os.environ.copy()
env['PYTHONUTF8'] = '1'
env['PYTHONIOENCODING'] = 'utf-8'

backend = subprocess.Popen(
    [sys.executable, 'support_planner.py'],
    cwd=ROOT,
    env=env,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.STDOUT,
)

try:
    for _ in range(40):
        if backend.poll() is not None:
            raise RuntimeError('Backend stopped before startup')
        try:
            with urllib.request.urlopen(BASE_URL + '/login', timeout=1) as response:
                if response.status == 200:
                    break
        except Exception:
            time.sleep(0.25)
    else:
        raise RuntimeError('Backend did not become ready on port 5093')

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 1440, 'height': 1000})
            page.goto(BASE_URL + '/login')
            page.locator('form input').nth(0).fill('admin')
            page.locator('form input').nth(1).fill('q12345678')
            page.locator("form button[type='submit']").click()
            page.wait_for_url('**/planning**')
            version_button = page.get_by_role('button', name='Открыть историю изменений')
            expect(version_button).to_be_visible()

            summary = page.get_by_role('dialog', name='Что нового')
            expect(summary).to_be_visible()
            expect(summary.get_by_text('История изменений приложения')).to_be_visible()
            expect(version_button).to_contain_text('v0.1.0 · dev')
            summary.get_by_role('button', name='Понятно').click()
            expect(summary).to_be_hidden()

            page.reload()
            expect(page.get_by_role('button', name='Открыть историю изменений')).to_be_visible()
            expect(page.get_by_role('dialog', name='Что нового')).to_be_hidden()

            page.get_by_role('button', name='Открыть историю изменений').click()
            history = page.get_by_role('dialog', name='История изменений')
            expect(history).to_be_visible()
            expect(history.get_by_text('История изменений приложения')).to_be_visible()
            expect(history.get_by_text('2026-10-11')).to_be_visible()
        finally:
            browser.close()
finally:
    backend.terminate()
    try:
        backend.wait(timeout=5)
    except subprocess.TimeoutExpired:
        backend.kill()
        backend.wait(timeout=5)
