import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
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
            with urllib.request.urlopen('http://127.0.0.1:5093/login', timeout=1) as response:
                if response.status == 200:
                    break
        except Exception:
            time.sleep(0.25)
    else:
        raise RuntimeError('Backend did not become ready')

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 1440, 'height': 1000})
            page.goto('http://127.0.0.1:5093/login')
            page.locator('form input').nth(0).fill('admin')
            page.locator('form input').nth(1).fill('q12345678')
            page.locator("form button[type='submit']").click()
            page.wait_for_url('**/planning**')
            page.locator('.ant-menu-item:visible').filter(has_text='Планирование').click()
            page.get_by_role('combobox').first.click()
            page.locator('.ant-select-item-option:visible').first.click()
            page.wait_for_timeout(1200)

            page.locator('.ant-btn:visible').nth(3).click()
            page.get_by_role('dialog').wait_for()
            page.get_by_role('dialog').locator('.ant-table-row-expand-icon').first.click()
            page.get_by_role('dialog').locator('[data-assignment-timeline]').first.wait_for()
        finally:
            browser.close()
finally:
    backend.terminate()
    try:
        backend.wait(timeout=5)
    except subprocess.TimeoutExpired:
        backend.kill()
        backend.wait(timeout=5)
