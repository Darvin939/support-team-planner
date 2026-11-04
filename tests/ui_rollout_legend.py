"""Explicit production UI regression; restores the database through SQLite backup."""
import json
import os
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.request
import uuid
from contextlib import closing
from datetime import datetime
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from ui_task_rollout import digest

ROOT = Path(__file__).resolve().parent.parent
BASE = 'http://127.0.0.1:5093'
ARTIFACTS = ROOT / '.tmp' / 'rollout-legend-ui'


def main():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    with closing(socket.socket()) as probe:
        if probe.connect_ex(('127.0.0.1', 5093)) == 0:
            raise RuntimeError('Port 5093 is in use; existing process left untouched')
    backup = ROOT / ('database.db.ui-test-{}-{}.bak'.format(
        datetime.now().strftime('%Y%m%d-%H%M%S'), uuid.uuid4().hex[:8]))
    with backup.open('xb'):
        pass
    with closing(sqlite3.connect(str(ROOT / 'database.db'))) as source:
        with closing(sqlite3.connect(str(backup))) as target:
            source.backup(target)
            original_digest = digest(target)
    env = os.environ.copy()
    env['PYTHONUTF8'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'
    env.pop('SUPPORT_PLANNER_DB_PATH', None)
    backend = None
    result = {'backup': str(backup), 'checks': [], 'restored': False, 'browser_errors': []}
    log = (ARTIFACTS / 'backend.log').open('w', encoding='utf-8')
    try:
        with (ARTIFACTS / 'build.log').open('w', encoding='utf-8') as build_log:
            subprocess.run(['cmd.exe', '/c', 'npm.cmd', 'run', 'build'], cwd=str(ROOT / 'frontend'),
                           env=env, stdout=build_log, stderr=subprocess.STDOUT, check=True)
        backend = subprocess.Popen([sys.executable, 'support_planner.py'], cwd=str(ROOT), env=env,
                                   stdout=log, stderr=subprocess.STDOUT)
        for _ in range(40):
            if backend.poll() is not None:
                raise RuntimeError('Backend stopped; see backend.log')
            try:
                with urllib.request.urlopen(BASE + '/login', timeout=1) as response:
                    if response.status == 200:
                        break
            except Exception:
                time.sleep(0.25)
        else:
            raise RuntimeError('Backend did not become ready')
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = None
            try:
                context = browser.new_context(viewport={'width': 1440, 'height': 1000})
                page = context.new_page()
                page.on('pageerror', lambda error: result['browser_errors'].append(str(error)))
                page.goto(BASE + '/login')
                page.locator('form input').nth(0).fill('admin')
                page.locator('form input').nth(1).fill('q12345678')
                page.locator("form button[type='submit']").click()
                page.wait_for_url('**/planning**')
                expect(page.get_by_role('heading', name='Планирование', exact=True)).to_be_visible()
                page.wait_for_load_state('networkidle')
                if page.get_by_role('button', name='Понятно', exact=True).is_visible():
                    page.get_by_role('button', name='Понятно', exact=True).click()
                    expect(page.locator('.ant-modal:visible')).to_have_count(0)

                def api(method, path, data=None):
                    response = page.request.fetch(BASE + path, method=method, data=data)
                    assert response.ok, '{} {}: {}'.format(method, path, response.text())
                    return response.json()

                suffix = uuid.uuid4().hex[:7]
                segment = api('POST', '/api/segments', {'name': 'Legend segment ' + suffix})['id']
                names = ['Блок А ' + suffix, 'Блок Б ' + suffix, 'Блок В ' + suffix]
                names += ['ДлинноеНазваниеБлокаБезПробелов' * 4 + str(index) + suffix for index in range(18)]
                blocks = [api('POST', '/api/blocks', {'name': name})['id'] for name in names]
                # The reference directory normalizes block names to uppercase.
                names = [name.upper() for name in names]
                template_name = 'Легенда: ' + 'длинное название шаблона ' * 5 + suffix
                template = api('POST', '/api/block-templates', {
                    'name': template_name, 'segment_id': segment,
                    'entries': [{'block_id': block, 'shift_days': 0 if index == 0 else max(1, index - 1)}
                                for index, block in enumerate(blocks)],
                })['id']
                team_name = '000 Legend UI ' + suffix
                team = api('POST', '/api/teams', {'name': team_name, 'template_ids': [template]})['id']
                task_name = 'Ручная раскатка ' + suffix
                task = api('POST', '/api/task', {'team_id': team, 'name': task_name,
                    'segment_id': segment, 'completion_template_id': template})['id']
                today = datetime.now().strftime('%Y-%m-%d')
                api('POST', '/api/assignment', {'task_id': task, 'date': today,
                    'block': names[0], 'status': 'new'})
                page.reload()
                expect(page.get_by_role('heading', name='Планирование', exact=True)).to_be_visible()
                select = page.get_by_role('combobox').first
                select.fill(team_name)
                page.locator('.ant-select-dropdown:visible').get_by_text(team_name, exact=True).click()
                page.wait_for_url('**/planning/{}'.format(team))

                def check_legend(label):
                    legend = page.locator('[data-rollout-legend]:visible')
                    expect(legend).to_be_visible()
                    expect(legend.get_by_text(template_name, exact=True)).to_be_visible()
                    stages = legend.get_by_role('listitem')
                    expect(stages).to_have_count(20)
                    expect(stages.nth(0).get_by_text('День 0', exact=True)).to_be_visible()
                    expect(stages.nth(1).get_by_text('+1 день', exact=True)).to_be_visible()
                    expect(stages.nth(1).get_by_text(', '.join(names[1:3]), exact=True)).to_be_visible()
                    page.wait_for_function('''() => {
                        const el = document.querySelector('[data-rollout-legend]');
                        if (!el) return false;
                        const box = el.getBoundingClientRect();
                        return box.x >= 0 && box.right <= window.innerWidth
                            && box.y >= 0 && box.bottom <= window.innerHeight;
                    }''', timeout=5000)
                    assert legend.evaluate('(el) => el.scrollWidth <= el.clientWidth + 1')
                    assert legend.evaluate('(el) => el.scrollHeight > el.clientHeight')
                    page.screenshot(path=str(ARTIFACTS / (label + '-top.png')), animations='disabled')
                    legend.evaluate('(el) => el.scrollTop = el.scrollHeight')
                    expect(legend.get_by_text(names[-1], exact=True)).to_be_visible()
                    page.screenshot(path=str(ARTIFACTS / (label + '.png')), animations='disabled')
                    result['checks'].append(label + '-grouping-wrap-scroll')

                for label, width, height in [('desktop', 1440, 1000), ('mobile', 390, 844)]:
                    page.set_viewport_size({'width': width, 'height': height})
                    button = page.get_by_role('button', name='Схема раскатки: ' + task_name, exact=True)
                    expect(button).to_be_visible()
                    button.scroll_into_view_if_needed()
                    button.focus()
                    button.press('Enter')
                    check_legend(label + '-table')
                    expect(page.locator('.ant-modal:visible')).to_have_count(0)
                    button.press('Escape')
                    expect(page.locator('[data-rollout-legend]:visible')).to_have_count(0)
                    # The existing sticky name column covers date cells at 390px.
                    # Open the assignment at desktop width, then test its mobile layout.
                    if label == 'mobile':
                        page.set_viewport_size({'width': 1440, 'height': 1000})
                    cell = page.locator('[data-schedule-cell][data-task-id="{}"][data-date="{}"]'.format(task, today))
                    cell.click()
                    dialog = page.get_by_role('dialog')
                    expect(dialog).to_be_visible()
                    page.set_viewport_size({'width': width, 'height': height})
                    selected_before = dialog.locator('.ant-select-selection-item').all_text_contents()
                    dialog.get_by_role('button', name='Схема раскатки: ' + task_name, exact=True).click()
                    check_legend(label + '-assignment')
                    assert selected_before == dialog.locator('.ant-select-selection-item').all_text_contents()
                    page.get_by_role('button', name='Закрыть схему раскатки', exact=True).click()
                    expect(page.locator('[data-rollout-legend]:visible')).to_have_count(0)
                    dialog.get_by_role('button', name='Close', exact=True).click()
                    expect(dialog).not_to_be_visible()
                assert not result['browser_errors'], result['browser_errors']
            except BaseException:
                if page is not None:
                    page.screenshot(path=str(ARTIFACTS / 'failure.png'), full_page=True)
                    (ARTIFACTS / 'failure.txt').write_text(page.locator('body').inner_text(), encoding='utf-8')
                raise
            finally:
                browser.close()
    finally:
        if backend is not None:
            backend.terminate()
            try:
                backend.wait(timeout=5)
            except subprocess.TimeoutExpired:
                backend.kill()
                backend.wait(timeout=5)
        log.close()
        with closing(sqlite3.connect(str(backup))) as source:
            with closing(sqlite3.connect(str(ROOT / 'database.db'))) as target:
                source.backup(target)
                target.execute('PRAGMA wal_checkpoint(TRUNCATE)')
                assert target.execute('PRAGMA quick_check').fetchone()[0] == 'ok'
                assert digest(target) == original_digest
        result['restored'] = True
        (ARTIFACTS / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
