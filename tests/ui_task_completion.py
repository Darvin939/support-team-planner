"""Production completion regression; backs up and restores the real database."""
import hashlib
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
from datetime import date, datetime, timedelta
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parent.parent
BASE = 'http://127.0.0.1:5093'
ARTIFACTS = ROOT / '.tmp' / 'task-completion-ui'


def digest(conn):
    return hashlib.sha256('\n'.join(conn.iterdump()).encode('utf-8')).hexdigest()


def main():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    with closing(socket.socket()) as probe:
        if probe.connect_ex(('127.0.0.1', 5093)) == 0:
            raise RuntimeError('Port 5093 is already occupied; existing process left untouched')
    backup = ROOT / ('database.db.ui-test-{}-{}.bak'.format(
        datetime.now().strftime('%Y%m%d-%H%M%S'), uuid.uuid4().hex[:8]))
    with backup.open('xb'):
        pass
    with closing(sqlite3.connect(str(ROOT / 'database.db'))) as source:
        with closing(sqlite3.connect(str(backup))) as target:
            source.backup(target)
            original = digest(target)
    env = os.environ.copy()
    env.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
    env.pop('SUPPORT_PLANNER_DB_PATH', None)
    backend = None
    result = {'backup': str(backup), 'checks': [], 'restored': False}
    log = (ARTIFACTS / 'backend.log').open('w', encoding='utf-8')
    try:
        with (ARTIFACTS / 'build.log').open('w', encoding='utf-8') as build_log:
            subprocess.run(['cmd.exe', '/c', 'npm.cmd', 'run', 'build'], cwd=str(ROOT / 'frontend'),
                           env=env, stdout=build_log, stderr=subprocess.STDOUT, check=True)
        backend = subprocess.Popen([sys.executable, 'support_planner.py'], cwd=str(ROOT), env=env,
                                   stdout=log, stderr=subprocess.STDOUT)
        for _ in range(40):
            if backend.poll() is not None:
                raise RuntimeError('Backend stopped before startup')
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
            try:
                page = browser.new_page(viewport={'width': 1440, 'height': 1000})
                page.on('pageerror', lambda error: result.setdefault('browser_errors', []).append(str(error)))
                page.on('response', lambda response: result.setdefault('block_responses', []).append(
                    {'url': response.url, 'status': response.status, 'body': response.text()})
                    if '/blocks?' in response.url else None)
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
                    assert response.status == 200, '{} {}: {}'.format(method, path, response.text())
                    return response.json()

                suffix = uuid.uuid4().hex[:7]
                segment = api('POST', '/api/segments', {'name': 'Completion ' + suffix})['id']
                a_name, b_name = ('Completion A ' + suffix).upper(), ('Completion B ' + suffix).upper()
                a = api('POST', '/api/blocks', {'name': a_name})['id']
                b = api('POST', '/api/blocks', {'name': b_name})['id']
                template = api('POST', '/api/block-templates', {'name': 'Completion ' + suffix,
                    'segment_id': segment, 'entries': [{'block_id': a, 'shift_days': 0},
                                                       {'block_id': b, 'shift_days': 1}]})['id']
                team_name = 'Completion ' + suffix
                team = api('POST', '/api/teams', {'name': team_name, 'template_ids': [template]})['id']
                result['blocks'] = api('GET', '/api/teams/{}/blocks?segment_id={}'.format(team, segment))
                task = api('POST', '/api/task', {'team_id': team, 'name': 'Completion work ' + suffix,
                    'criticality': 'medium', 'segment_id': segment, 'completion_template_id': template})['id']
                today = date.today().isoformat()
                for day, block, status in [('2001-01-01', a_name, 'success'),
                                           (today, b_name, 'new'),
                                           ((date.today() + timedelta(days=1)).isoformat(), a_name, 'planned')]:
                    api('POST', '/api/assignment', {'task_id': task, 'date': day, 'block': block, 'status': status})
                page.reload()
                expect(page.get_by_role('heading', name='Планирование', exact=True)).to_be_visible()
                select = page.get_by_role('combobox').first
                select.fill(team_name)
                page.locator('.ant-select-dropdown:visible').get_by_text(team_name, exact=True).click()
                page.wait_for_url('**/planning/{}'.format(team))
                row = page.locator('tr[data-row-key="{}"]'.format(task))
                expect(row).to_be_visible()
                expect(row.get_by_role('button', name='Завершить работу', exact=True)).to_have_count(0)
                row.locator('[data-schedule-cell][data-date="{}"]'.format(today)).click()
                dialog = page.get_by_role('dialog')
                expect(dialog.locator('.ant-select-selection-item').get_by_text(b_name, exact=True)).to_be_visible()
                dialog.get_by_label('Статус', exact=True).click()
                page.locator('.ant-select-dropdown:visible').get_by_text('Успешно', exact=True).click()
                dialog.get_by_role('button', name='Обновить', exact=True).click()
                completion = page.get_by_role('dialog', name='Все блоки шаблона выполнены', exact=True)
                expect(completion).to_be_visible()
                expect(completion).to_have_css('opacity', '1')
                page.screenshot(path=str(ARTIFACTS / 'completion-desktop.png'))
                completion.get_by_role('button', name='Оставить без изменений', exact=True).click()
                expect(completion).not_to_be_visible()
                expect(row.get_by_role('button', name='Завершить работу', exact=True)).to_be_visible()
                assert api('GET', '/api/task/{}'.format(task))['task_status'] == 'new'
                result['checks'].append('last-block-form-save-prompts-with-planned-duplicate-and-old-success')

                page.reload()
                page.wait_for_url('**/planning/{}'.format(team))
                expect(row.get_by_role('button', name='Завершить работу', exact=True)).to_be_visible()
                expect(page.get_by_role('dialog')).to_have_count(0)
                result['checks'].append('dismiss-and-reload-preserve-action-without-auto-modal')
                page.set_viewport_size({'width': 390, 'height': 844})
                row.get_by_role('button', name='Завершить работу', exact=True).click()
                expect(completion).to_be_visible()
                page.wait_for_function('document.documentElement.scrollWidth <= innerWidth + 1')
                box = completion.bounding_box()
                assert box and box['x'] >= 0 and box['x'] + box['width'] <= 391
                expect(completion).to_have_css('opacity', '1')
                page.screenshot(path=str(ARTIFACTS / 'completion-mobile.png'))
                completion.get_by_role('button', name='Перевести в Выполнена', exact=True).click()
                expect(completion).not_to_be_visible()
                expect(row).to_have_count(0)
                assert api('GET', '/api/task/{}'.format(task))['task_status'] == 'done'
                result['checks'].append('mobile-action-confirms-standard-done-transition')
                assert not result.get('browser_errors'), result.get('browser_errors')
            except BaseException:
                page.screenshot(path=str(ARTIFACTS / 'failure.png'))
                (ARTIFACTS / 'failure.html').write_text(page.content(), encoding='utf-8')
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
                assert digest(target) == original, 'Restored DB differs from backup'
        result['restored'] = True
        (ARTIFACTS / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
