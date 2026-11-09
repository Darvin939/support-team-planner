"""The same behavioral tests run on real SQLite and PostgreSQL in separate processes."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend import db
from backend.application import app


def graph():
    segment = db.create_segment('Сегмент ? %')
    block = db.create_block('Блок')
    template = db.create_template('Шаблон', segment, [{'block_id': block}])
    team = db.create_team('Команда', [template])
    return team, segment, template


def task(team, segment, template, name='Ошибка биллинга', description=None):
    return db.create_or_update_task(None, team, name, description, segment_id=segment, completion_template_id=template)


def login(client):
    assert client.post('/login', data={'login': 'admin', 'password': 'q12345678'}).status_code == 200


def test_parameterized_rows_and_constraint_recovery(storage):
    team = db.create_team("Кавычка ' ? 100%")
    row = db.get_team_by_id(team)
    assert row[0] == row['id'] == dict(row)['id'] == team
    assert dict(row)['name'] == "Кавычка ' ? 100%"
    with pytest.raises(db.IntegrityConstraintError):
        db.create_team("Кавычка ' ? 100%")
    assert db.create_team('После ошибки') > team
    segment = db.create_segment('S')
    template = db.create_template('T', segment)
    with pytest.raises(db.IntegrityConstraintError):
        db.delete_segment(segment)
    # A FK must not be translated to a duplicate name error.
    with pytest.raises(db.IntegrityConstraintError, match='Нарушена связь'):
        db.create_template('Other', 999999)
    assert db.get_template_by_id(template)['name'] == 'T'


def test_conflict_ignore_and_atomic_rollback(storage):
    assert db.add_freeze_day('2026-11-01') is True
    assert db.add_freeze_day('2026-11-01') is False
    assert db.add_freeze_range('2026-11-01', '2026-11-03') == 2
    assert db.mark_release_versions_seen(1, ['x', 'x', 'y']) == 2
    assert db.mark_release_versions_seen(1, ['x']) == 0
    with pytest.raises(RuntimeError, match='failed DAO'):
        with db.composite_transaction():
            db.create_team('Must roll back')
            try:
                db.create_team('Must roll back')
            except db.IntegrityConstraintError:
                pass
    assert not any(row['name'] == 'Must roll back' for row in db.get_all_teams())
    assert db.create_team('After rollback')


def test_search_archive_history_and_include_ids(storage):
    team, segment, template = graph()
    first = task(team, segment, template)
    second = task(team, segment, template, 'Другая задача')
    assert db.get_tasks_count_by_team(team, search='биллинг ошибка') == 1
    assert [r['id'] for r in db.get_tasks_by_team(team, search='биллинга ошипка')] == [first]
    assert db.get_tasks_count_by_team(team, search='нет-совпадений') == 0
    included = db.get_active_tasks_flat(team, search='ошибка', limit=1, include_ids=[second])
    assert {row['id'] for row in included} == {first, second}
    assert db.get_team_history_count(team, search='ошибка') == 1
    db.update_task_status(first, 'done')
    assert db.get_tasks_count_by_team(team) == 1
    assert db.get_archived_tasks_count_by_team(team, search='ошибка', completed_from='2000-01-01', completed_to='2099-12-31') == 1
    assert db.get_archived_tasks_by_team(team, search='ошибка')[0]['id'] == first
    db.delete_task(first)
    assert db.get_team_history_count(team, search='ошибка') >= 1
    assert db.get_task_full_history(first)


def test_unicode_directories_acl_and_null_ordering(storage):
    team = db.create_team('Straße Команда')
    denied = db.create_team('Скрытая')
    user = db.create_user('Ёжов', 'Иван', login='ёж', role='editor', team_ids=[team])
    assert [u['id'] for u in db.get_users_page(search='редактор')['users']] == [user]
    assert [t['id'] for t in db.get_teams_page_for_user(user, 'editor', search='STRASSE')['teams']] == [team]
    assert db.get_teams_page_for_user(user, 'editor', search='Скрытая')['total'] == 0
    assert not db.user_can_access_team(user, 'editor', denied)
    assert db.get_users_page()['users'][0]['login'] == 'admin'


def test_assignments_swap_completion_and_full_rollback(storage):
    team, segment, template = graph()
    task_id = task(team, segment, template)
    for day in ('2026-11-01', '2026-11-02'):
        db.create_or_update_assignment(None, task_id, day, 'БЛОК', 'success', None, None)
    assert db.get_task_completion_suggestion(task_id)
    rows = db.get_successful_assignments_by_task(task_id)
    moves = [{'assignment_id': rows[0]['id'], 'new_date': rows[1]['date']},
             {'assignment_id': rows[1]['id'], 'new_date': rows[0]['date']}]
    assert db.bulk_reschedule_assignments(moves, 'admin') == 2
    with patch('backend.db.assignments._record_assignment_history', side_effect=RuntimeError('history failure')):
        with pytest.raises(RuntimeError):
            db.bulk_reschedule_assignments([{'assignment_id': rows[0]['id'], 'new_date': '2026-11-03'}], 'admin')
    assert all('__bulk' not in r['date'] for r in db.get_successful_assignments_by_task(task_id))


def test_api_lifecycle_roles_guards_and_notification_state(storage):
    team, segment, template = graph()
    first = task(team, segment, template)
    second = task(team, segment, template, 'Другая')
    with TestClient(app) as client:
        assert client.get('/api/me').status_code == 401
        login(client)
        assert client.post('/api/task-dependency', json={'task_id': first, 'depends_on_task_id': second}).status_code == 200
        assert client.post('/api/task-dependency', json={'task_id': second, 'depends_on_task_id': first}).status_code == 400
        assert client.get('/api/tasks/%s' % team).json()['total'] == 2
        assert client.get('/api/notifications/new-tasks').status_code == 200
        assert client.patch('/api/tasks/%s/status' % first, json={'status': 'done'}).status_code == 200
        assert client.post('/api/assignment', json={'task_id': first, 'date': '2026-11-09', 'status': 'new'}).status_code == 400
    # Clean readers must not take a write lock.
    with patch.object(storage, 'begin_write', side_effect=AssertionError('reader took lock')):
        assert db.get_task_by_id(second)
        assert db.get_application_metadata()
    with patch.object(storage, 'begin_write', wraps=storage.begin_write) as write_lock:
        db.get_new_task_notifications(1)
        write_lock.assert_called_once()


def test_write_lock_precedes_guards_on_two_connections(storage):
    team, segment, template = graph()
    task_id = task(team, segment, template)
    acquired, release, started = Event(), Event(), Event()
    def writer():
        with db.composite_transaction():
            db.create_or_update_assignment(None, task_id, '2026-11-01', 'БЛОК', 'new', None, None)
            acquired.set()
            assert release.wait(10)
    def competing():
        started.set()
        with db.composite_transaction():
            return db.task_has_any_assignments(task_id)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(writer)
        assert acquired.wait(10)
        second = pool.submit(competing)
        assert started.wait(10)
        release.set()
        first.result(timeout=10)
        assert second.result(timeout=10) is True


def test_search_scans_beyond_the_first_candidate_batch(storage):
    team, segment, template = graph()
    conn = db.get_db_connection()
    try:
        storage.begin_write(conn)
        conn.executemany(
            'INSERT INTO tasks (team_id, segment_id, completion_template_id, name) VALUES (%s)' % storage.placeholders(4),
            [(team, segment, template, 'Совсем другая работа %s' % index) for index in range(1001)],
        )
        conn.commit()
    finally:
        storage.close(conn)
    last = task(team, segment, template, 'Редкий результат', 'За первым пакетом')
    assert db.get_tasks_count_by_team(team, search='Редкий результат') == 1
    assert [row['id'] for row in db.get_tasks_by_team(team, search='Редкий результат')] == [last]
    assert db.get_tasks_count_by_team(team, search='   ') == 1002


def test_request_opens_one_connection_and_assets_open_none(storage):
    from backend.db import connection
    with TestClient(app) as client:
        login(client)
        with patch.object(db, 'get_db_connection', wraps=db.get_db_connection) as request_connect, \
                patch.object(connection, 'get_db_connection', wraps=connection.get_db_connection) as dao_connect:
            assert client.get('/api/users?limit=2').status_code == 200
            assert request_connect.call_count == 1
            assert dao_connect.call_count == 0
        with patch.object(db, 'get_db_connection', side_effect=AssertionError('asset opened storage')):
            assert client.get('/react-assets/does-not-exist.js').status_code == 404


def test_statistics_queries_and_null_filters(storage):
    team, segment, template = graph()
    task_id = task(team, segment, template)
    db.create_or_update_assignment(None, task_id, '2026-11-01', 'БЛОК', 'new', None, None)
    db.create_or_update_assignment(None, task_id, '2026-11-02', 'БЛОК', 'planned', None, None)
    rows = db.get_active_assignments_in_period(team, '2026-11-01', '2026-11-03')
    assert [row['status'] for row in rows] == ['new', 'planned']
    assert db.get_active_assignments_stats(team, '2026-11-01', '2026-11-03')['total'] == 2
    assert [dict(row) for row in db.get_active_assignment_counts_by_date(team, '2026-11-01', '2026-11-03')] == [
        {'date': '2026-11-01', 'count': 1}, {'date': '2026-11-02', 'count': 1},
    ]
    assert db.get_new_task_notifications(1, team_ids=[])['total'] == 0
    assert db.get_all_deps_for_team(team, task_ids=[]) == []
    db.update_task_status(task_id, 'done')
    assert db.get_archived_tasks_count_by_team(team, completed_to='9999-12-31') == 1
