"""Production UI regression. Run explicitly; restores the real database in finally."""
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
from datetime import datetime
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parent.parent
BASE = 'http://127.0.0.1:5093'
ARTIFACTS = ROOT / '.tmp' / 'task-rollout-ui'


def digest(connection):
    return hashlib.sha256('\n'.join(connection.iterdump()).encode('utf-8')).hexdigest()


def main():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    with closing(socket.socket()) as probe:
        if probe.connect_ex(('127.0.0.1', 5093)) == 0:
            raise RuntimeError('Port 5093 is already in use; existing process was left untouched')
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
    browser = None
    page = None
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
                raise RuntimeError('Backend stopped before startup; see backend.log')
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
                context = browser.new_context(viewport={'width': 1440, 'height': 1000})
                page = context.new_page()
                page.on('request', lambda request: result.setdefault('task_save_payloads', []).append(request.post_data_json)
                        if request.method == 'POST' and request.url == BASE + '/api/task' else None)
                page.on('pageerror', lambda error: result.setdefault('browser_errors', []).append(str(error)))
                page.goto(BASE + '/login')
                page.locator('form input').nth(0).fill('admin')
                page.locator('form input').nth(1).fill('q12345678')
                page.locator("form button[type='submit']").click()
                page.wait_for_url('**/planning**')
                expect(page.get_by_role('heading', name='Планирование', exact=True)).to_be_visible()
                # The release notification is real application UI and may appear once after login.
                page.wait_for_load_state('networkidle')
                if page.get_by_role('button', name='Понятно', exact=True).is_visible():
                    page.get_by_role('button', name='Понятно', exact=True).click()
                    expect(page.locator('.ant-modal:visible')).to_have_count(0)

                def api(method, path, data=None, status=200):
                    response = page.request.fetch(BASE + path, method=method, data=data)
                    assert response.status == status, '{} {}: {}'.format(method, path, response.text())
                    return response.json()

                suffix = uuid.uuid4().hex[:7]
                segment_name = '000 UI segment ' + suffix
                second_segment_name = '001 UI segment ' + suffix
                segment = api('POST', '/api/segments', {'name': segment_name})['id']
                second_segment = api('POST', '/api/segments', {'name': second_segment_name})['id']
                block_a = api('POST', '/api/blocks', {'name': 'UI block A ' + suffix})['id']
                block_b = api('POST', '/api/blocks', {'name': 'UI block B ' + suffix})['id']
                template_name = '000 UI template ' + suffix
                template = api('POST', '/api/block-templates', {'name': template_name, 'segment_id': segment,
                    'entries': [{'block_id': block_a, 'shift_days': 0}, {'block_id': block_b, 'shift_days': 1}]})['id']
                second_template = api('POST', '/api/block-templates', {'name': '001 UI template ' + suffix,
                    'segment_id': second_segment, 'entries': [{'block_id': block_a, 'shift_days': 0}]})['id']
                team_name = '000 UI team ' + suffix
                team = api('POST', '/api/teams', {'name': team_name, 'template_ids': [template, second_template]})['id']
                page.reload()
                expect(page.get_by_role('heading', name='Планирование', exact=True)).to_be_visible()
                select = page.get_by_role('combobox').first
                select.fill(team_name)
                page.locator('.ant-select-dropdown:visible').get_by_text(team_name, exact=True).click()
                page.wait_for_url('**/planning/{}'.format(team))
                page.get_by_role('button', name='Добавить работу', exact=True).click()
                dialog = page.get_by_role('dialog')
                expect(dialog.get_by_label('Сегмент', exact=True)).to_have_value('')
                expect(dialog.get_by_label('Шаблон раскатки', exact=True)).to_be_disabled()
                task_name = 'UI rollout work ' + suffix
                dialog.get_by_role('button', name='Создать', exact=True).click()
                expect(dialog.locator('.ant-form-item-explain-error').get_by_text('Введите имя', exact=True)).to_be_visible()
                dialog.get_by_role('button', name='Close', exact=True).click()
                expect(dialog).not_to_be_visible()
                page.get_by_role('button', name='Добавить работу', exact=True).click()
                dialog = page.get_by_role('dialog')
                expect(dialog).to_be_visible()
                expect(dialog.locator('.ant-form-item-has-error')).to_have_count(0)
                expect(dialog.get_by_label('Имя', exact=True)).to_have_value('')
                dialog.get_by_role('button', name='Создать', exact=True).click()
                expect(dialog.locator('.ant-form-item-explain-error').get_by_text('Введите имя', exact=True)).to_be_visible()
                expect(dialog.locator('.ant-form-item-explain-error').get_by_text('Выберите сегмент', exact=True)).to_be_visible()
                dialog.get_by_label('Имя', exact=True).fill(task_name)
                result['checks'].append('validation-errors-reset-on-reopen-and-reappear-on-submit')

                def choose(label, value):
                    control = dialog.get_by_label(label, exact=True)
                    expect(page.locator('.ant-select-dropdown:visible')).to_have_count(0)
                    control.focus()
                    control.press('ArrowDown')
                    list_id = control.get_attribute('aria-controls')
                    assert list_id, 'Select has no associated option list'
                    dropdown = page.locator('.ant-select-dropdown:visible').filter(
                        has=page.locator('[id="{}"]'.format(list_id)))
                    expect(dropdown).to_have_count(1)
                    active = dropdown.locator('.ant-select-item-option-active .ant-select-item-option-content')
                    expect(active).to_be_visible()
                    for _ in range(100):
                        if active.inner_text() == value:
                            control.press('Enter')
                            expect(dropdown).to_have_count(0)
                            return
                        control.press('ArrowDown')
                    raise AssertionError('Option is unavailable: ' + value)

                choose('Сегмент', segment_name)
                choose('Шаблон раскатки', template_name)
                parameters = dialog.get_by_role('group', name='Параметры работы', exact=True)
                rollout_parameters = dialog.get_by_role('group', name='Параметры раскатки', exact=True)
                criticality_box = parameters.locator('.ant-select').bounding_box()
                psi_box = parameters.get_by_text('Требуется ПСИ', exact=True).bounding_box()
                assert criticality_box and psi_box
                assert abs((criticality_box['y'] + criticality_box['height'] / 2)
                           - (psi_box['y'] + psi_box['height'] / 2)) <= 3
                result['layout'] = {'desktop_form_height': dialog.bounding_box()['height'],
                                    'parameter_card_height': parameters.bounding_box()['height'],
                                    'rollout_card_height': rollout_parameters.bounding_box()['height']}
                # The preceding 1440x1000 production capture had a 740px create dialog.
                assert result['layout']['desktop_form_height'] <= 764, result['layout']
                page.screenshot(path=str(ARTIFACTS / 'task-desktop.png'), animations='disabled')
                dialog.get_by_role('button', name='Создать', exact=True).click()
                expect(dialog).not_to_be_visible()
                task = next(t for t in api('GET', '/api/tasks/{}?limit=100'.format(team))['tasks'] if t['name'] == task_name)
                assert task['completion_template_id'] == template
                task_id = task['id']
                row = page.locator('tr[data-row-key="{}"]'.format(task_id))
                expect(row).to_be_visible()
                row.locator('[data-schedule-cell]').first.click()
                dialog = page.get_by_role('dialog')
                dialog.get_by_role('switch', name='Автоназначение').click()
                expect(dialog.locator('[data-planning-grid-scroll="data-auto-schedule-grid"]')).to_be_visible()
                assert dialog.locator('.ant-select').count() == 1, 'Only the status Select should remain in auto mode'
                page.screenshot(path=str(ARTIFACTS / 'auto-desktop.png'), animations='disabled')
                dialog.get_by_role('button', name='Создать', exact=True).click()
                expect(dialog).not_to_be_visible()
                assignments = api('GET', '/api/assignments/{}?start_date=2000-01-01&end_date=2099-12-31&task_ids={}'.format(team, task_id))
                assert len(assignments) == 2
                result['checks'].append('real-login-create-work-and-autoassign-without-template-select')

                row.get_by_title('Редактировать', exact=True).click()
                dialog = page.get_by_role('dialog')
                expect(dialog.get_by_label('Сегмент', exact=True)).to_be_disabled()
                expect(dialog.get_by_label('Шаблон раскатки', exact=True)).to_be_disabled()
                page.set_viewport_size({'width': 390, 'height': 844})
                expect(dialog).to_be_visible()
                page.wait_for_function("""() => {
                    const rect = document.querySelector('.ant-modal[role="dialog"]').getBoundingClientRect();
                    return rect.x >= 0 && rect.width <= 390
                      && document.documentElement.scrollWidth <= innerWidth + 1;
                }""")
                box = dialog.bounding_box()
                assert box and box['x'] >= 0 and box['width'] <= 390
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                page.screenshot(path=str(ARTIFACTS / 'task-mobile.png'), animations='disabled')
                parameters = dialog.get_by_role('group', name='Параметры работы', exact=True)
                rollout_parameters = dialog.get_by_role('group', name='Параметры раскатки', exact=True)
                criticality_box = parameters.locator('.ant-select').bounding_box()
                psi_box = parameters.get_by_text('Требуется ПСИ', exact=True).bounding_box()
                segment_box = rollout_parameters.locator('.ant-select').nth(0).bounding_box()
                template_box = rollout_parameters.locator('.ant-select').nth(1).bounding_box()
                assert psi_box['y'] >= criticality_box['y'] + criticality_box['height'] - 1
                assert template_box['y'] >= segment_box['y'] + segment_box['height'] - 1
                dialog.get_by_role('button', name='Обновить', exact=True).scroll_into_view_if_needed()
                expect(dialog.get_by_role('button', name='Обновить', exact=True)).to_be_visible()
                page.screenshot(path=str(ARTIFACTS / 'task-mobile-bottom.png'), animations='disabled')
                result['checks'].append('compact-cards-desktop-alignment-mobile-stacking-and-reachable-footer')
                dialog.get_by_role('button', name='Close', exact=True).click()
                page.set_viewport_size({'width': 1440, 'height': 1000})
                expect(dialog).not_to_be_visible()
                for assignment in assignments:
                    api('DELETE', '/api/assignment/{}'.format(assignment['id']))
                page.reload()
                page.wait_for_url('**/planning/{}'.format(team))
                expect(page.get_by_role('button', name='Добавить работу')).to_be_visible()
                row.get_by_title('Редактировать', exact=True).click()
                dialog = page.get_by_role('dialog')
                expect(dialog.get_by_label('Сегмент', exact=True)).to_be_enabled()
                expect(dialog.get_by_label('Шаблон раскатки', exact=True)).to_be_enabled()
                choose('Сегмент', second_segment_name)
                expect(dialog.get_by_label('Шаблон раскатки', exact=True)).to_have_value('')
                choose('Шаблон раскатки', '001 UI template ' + suffix)
                page.screenshot(path=str(ARTIFACTS / 'task-updated.png'), animations='disabled')
                dialog.get_by_role('button', name='Обновить', exact=True).click()
                expect(dialog).not_to_be_visible()
                result['latest_task'] = api('GET', '/api/task/{}'.format(task_id))
                assert result['latest_task']['completion_template_id'] == second_template
                result['checks'].append('assignment-lock-unlock-and-segment-change-clears-template-desktop-mobile')

                page.locator('.ant-menu-item:visible').get_by_text('Настройки', exact=True).click()
                page.wait_for_url('**/settings')
                expect(page.get_by_role('heading', name='Настройки', exact=True)).to_be_visible()
                page.get_by_role('tab', name='Справочники работ', exact=True).click()
                search = page.get_by_placeholder('Поиск шаблонов', exact=True)
                search.fill('001 UI template ' + suffix)
                template_row = page.get_by_role('row').filter(has_text='001 UI template ' + suffix)
                template_row.get_by_role('button', name='Удалить шаблон', exact=True).click()
                page.locator('.ant-popover:visible').get_by_role('button', name='Удалить', exact=True).click()
                expect(page.locator('.ant-message-notice').get_by_text(
                    'Шаблон используется работами: удаление и смена сегмента запрещены', exact=True)).to_be_visible()
                expect(template_row).to_be_visible()
                template_row.get_by_role('button', name='Редактировать шаблон', exact=True).click()
                dialog = page.get_by_role('dialog')
                choose('Сегмент', segment_name)
                dialog.get_by_role('button', name='Обновить', exact=True).click()
                expect(dialog).to_be_visible()
                expect(page.locator('.ant-message-notice').get_by_text(
                    'Шаблон используется работами: удаление и смена сегмента запрещены', exact=True).last).to_be_visible()
                assert next(t for t in api('GET', '/api/block-templates')
                            if t['id'] == second_template)['segment_id'] == second_segment
                result['checks'].append('settings-protect-used-template-delete-and-segment-change')
                assert not result.get('browser_errors'), result.get('browser_errors')
            except BaseException:
                if page is not None:
                    page.screenshot(path=str(ARTIFACTS / 'failure.png'), full_page=True)
                    (ARTIFACTS / 'failure.txt').write_text(page.locator('body').inner_text(), encoding='utf-8')
                raise
            finally:
                browser.close()
                browser = None
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
                assert digest(target) == original_digest, 'Restored database differs from backup'
        result['restored'] = True
        (ARTIFACTS / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
