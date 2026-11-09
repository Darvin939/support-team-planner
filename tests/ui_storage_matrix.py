"""Production smoke for both stores: real login, writes, navigation and responsive layout."""
import json
import os
from datetime import date
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

from scripts.ui_test_harness import production_backend


def main():
    with production_backend() as (base, output):
        results = []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, channel=os.environ.get('SUPPORT_PLANNER_UI_BROWSER_CHANNEL'))
            try:
                page = browser.new_page(viewport={'width': 1440, 'height': 1000})
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(base + '/login')
                page.locator('form input').nth(0).fill('admin')
                page.locator('form input').nth(1).fill('q12345678')
                page.locator('form button[type=submit]').click()
                page.wait_for_url('**/planning**')
                expect(page.get_by_role('heading', name='Планирование', exact=True)).to_be_visible()
                results.append('real-login')
                if page.get_by_role('button', name='Понятно', exact=True).is_visible():
                    page.get_by_role('button', name='Понятно', exact=True).click()
                    expect(page.locator('.ant-modal:visible')).to_have_count(0)

                def api(method, path, data=None):
                    response = page.request.fetch(base + path, method=method, data=data)
                    assert response.status == 200, (path, response.status, response.text())
                    return response.json()

                suffix = uuid4().hex[:8]
                segment = api('POST', '/api/segments', {'name': 'Storage ' + suffix})['id']
                block_name = 'STORAGE ' + suffix.upper()
                block = api('POST', '/api/blocks', {'name': block_name})['id']
                template = api('POST', '/api/block-templates', {'name': 'Storage ' + suffix, 'segment_id': segment,
                    'entries': [{'block_id': block, 'shift_days': 0}]})['id']
                team_name = 'Storage ' + suffix
                team = api('POST', '/api/teams', {'name': team_name, 'template_ids': [template]})['id']
                task = api('POST', '/api/task', {'name': 'Проверка БД ' + suffix, 'team_id': team,
                    'segment_id': segment, 'completion_template_id': template})['id']
                today = date.today().isoformat()
                api('POST', '/api/assignment', {'task_id': task, 'date': today, 'block': block_name, 'status': 'new'})
                assignment = api('GET', '/api/assignments/{}?start_date={}&end_date={}'.format(team, today, today))[0]['id']
                api('POST', '/api/assignments/bulk-reschedule', {'moves': [{'assignment_id': assignment, 'new_date': '2026-12-01'}]})
                api('POST', '/api/assignments/bulk-reschedule', {'moves': [{'assignment_id': assignment, 'new_date': today}]})
                results.append('planning-and-bulk-reschedule')
                page.reload()
                expect(page.get_by_role('heading', name='Планирование', exact=True)).to_be_visible()
                select = page.get_by_role('combobox').first
                select.fill(team_name)
                page.locator('.ant-select-dropdown:visible').get_by_text(team_name, exact=True).click()
                page.wait_for_url('**/planning/{}'.format(team))
                expect(page.locator('tr[data-row-key="{}"]'.format(task))).to_be_visible()
                page.screenshot(path=str(output / 'planning-desktop.png'))
                for name, heading, path in [('Журнал', 'Журнал изменений', 'journal'), ('Статистика', 'Статистика', 'statistics'),
                                             ('Планирование', 'Планирование', 'planning')]:
                    navigation = page.locator('.ant-menu-item:visible').filter(has_text=name).first
                    navigation.click()
                    page.wait_for_url('**/{}**'.format(path))
                    expect(page.get_by_role('heading', name=heading, exact=True)).to_be_visible()
                    results.append('navigation-' + path)
                api('PATCH', '/api/tasks/{}/status'.format(task), {'status': 'done'})
                assert api('GET', '/api/tasks/{}/archive'.format(team))['total'] == 1
                assert api('GET', '/api/journal/{}'.format(team))['total'] > 0
                assert api('GET', '/api/notifications/new-tasks')['total'] >= 0
                results.extend(['archive', 'history', 'notifications'])
                page.set_viewport_size({'width': 390, 'height': 844})
                page.reload()
                expect(page.get_by_role('heading', name='Планирование', exact=True)).to_be_visible()
                page.wait_for_function('document.documentElement.scrollWidth <= innerWidth + 1')
                page.screenshot(path=str(output / 'planning-mobile.png'))
                # Role checks also authenticate through the real form and session cookie.
                for role in ('editor', 'user'):
                    login_name = role + '-' + suffix
                    api('POST', '/api/users', {'first_name': role, 'last_name': 'UI', 'role': role,
                        'login': login_name, 'password': 'password123', 'team_ids': [team]})
                    context = browser.new_context(viewport={'width': 1440, 'height': 1000})
                    try:
                        role_page = context.new_page()
                        role_page.goto(base + '/login')
                        role_page.locator('form input').nth(0).fill(login_name)
                        role_page.locator('form input').nth(1).fill('password123')
                        role_page.locator('form button[type=submit]').click()
                        role_page.wait_for_url('**/planning**')
                        expect(role_page.get_by_role('heading', name='Планирование', exact=True)).to_be_visible()
                        assert role_page.request.get(base + '/api/me').json()['role'] == role
                        assert role_page.request.post(base + '/api/users', data={'first_name': 'Forbidden', 'last_name': 'UI'}).status == 403
                        results.append('real-login-' + role)
                    finally:
                        context.close()
                assert not errors, errors
                (output / 'result.json').write_text(json.dumps({'checks': results, 'browser_errors': errors}, ensure_ascii=False, indent=2), encoding='utf-8')
                print('UI checks:', ', '.join(results), '; artifacts:', output)
            finally:
                browser.close()


if __name__ == '__main__':
    main()
