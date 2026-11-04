import sqlite3
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend import auth, db
from backend.application import app
from backend.db import sqlite as sqlite_backend


@pytest.fixture
def completion_db(tmp_path, monkeypatch):
    path = str(tmp_path / 'completion.db')
    monkeypatch.setattr(sqlite_backend, 'DB_PATH', path)
    db.init_db()
    with sqlite3.connect(path) as conn:
        conn.executescript("""
            INSERT INTO teams (id, name) VALUES (1, 'Completion');
            INSERT INTO segments (id, name) VALUES (1, 'Segment');
            INSERT INTO blocks (id, name) VALUES (1, 'A'), (2, 'B'), (3, 'Outside');
            INSERT INTO block_templates (id, name, segment_id) VALUES (1, 'AB', 1), (2, 'Empty', 1);
            INSERT INTO template_blocks (template_id, block_id, schedule_offset) VALUES (1, 1, 0), (1, 2, 1);
            INSERT INTO team_templates (team_id, template_id) VALUES (1, 1), (1, 2);
            INSERT INTO tasks (id, team_id, segment_id, name, criticality, task_status, completion_template_id)
            VALUES (10, 1, 1, 'First', 'medium', 'new', 1), (11, 1, 1, 'Second', 'low', 'new', 1);
            INSERT INTO users (id, first_name, role, login, password_hash)
            VALUES (2, 'Reader', 'user', 'reader', 'unused');
            INSERT INTO user_team_access (user_id, team_id) VALUES (2, 1);
        """)
        conn.execute('UPDATE users SET password_hash = ? WHERE id = 2', (auth.hash_password('password123'),))
    yield path


def write(path, sql, params=()):
    with sqlite3.connect(path) as conn:
        conn.execute(sql, params)


def assignment(path, task_id=10, block=' A, B, , Outside ', status='success', deleted=0):
    with sqlite3.connect(path) as conn:
        count = conn.execute('SELECT COUNT(*) FROM assignments').fetchone()[0]
    day = (date(2001, 1, 1) + timedelta(days=count)).isoformat()
    write(path, '''INSERT INTO assignments (task_id, date, block, status, is_deleted)
                   VALUES (?, ?, ?, ?, ?)''', (task_id, day, block, status, deleted))


def login(client, reader=False):
    result = client.post('/login', data={
        'login': 'reader' if reader else 'admin',
        'password': 'password123' if reader else 'q12345678',
    })
    assert result.status_code == 200


@pytest.mark.parametrize('status', ['new', 'planned', 'rollback', 'unsuccessful', 'cancelled'])
def test_successful_blocks_survive_other_attempts(completion_db, status):
    assignment(completion_db)
    assignment(completion_db, block='A, B', status=status)
    assert db.get_task_completion_suggestion(10) is not None


@pytest.mark.parametrize('template,status,deleted', [
    (None, 'new', 0), (2, 'new', 0), (1, 'done', 0), (1, 'cancelled', 0), (1, 'new', 1),
])
def test_unavailable_or_terminal_task_is_not_ready(completion_db, template, status, deleted):
    assignment(completion_db)
    write(completion_db, 'UPDATE tasks SET completion_template_id=?, task_status=?, is_deleted=? WHERE id=10',
          (template, status, deleted))
    assert db.get_task_completion_suggestion(10) is None


def test_only_undeleted_success_covers_current_template(completion_db):
    assignment(completion_db, block='A')
    assignment(completion_db, block='B', status='unsuccessful')
    assignment(completion_db, block='B', deleted=1)
    assert db.get_task_completion_suggestion(10) is None
    assignment(completion_db, block='B')
    assert db.get_task_completion_suggestion(10)
    write(completion_db, 'INSERT INTO template_blocks (template_id, block_id, schedule_offset) VALUES (1,3,2)')
    assert db.get_task_completion_suggestion(10) is None


def test_reads_include_full_history_and_batch_queries(completion_db):
    assignment(completion_db)
    assignment(completion_db, task_id=11)
    conn = db.get_db_connection()
    statements = []
    conn.set_trace_callback(statements.append)
    with patch('backend.db.connection.get_db_connection', return_value=conn):
        assert set(db.get_task_completion_suggestions([10, 11])) == {10, 11}
    assert len([sql for sql in statements if sql.lstrip().startswith('SELECT')]) == 3
    with TestClient(app) as client:
        login(client)
        assert client.get('/api/task/10').json()['completion_ready'] is True
        rows = client.get('/api/tasks/1').json()['tasks']
        assert len(rows) == 2 and all(row['completion_ready'] for row in rows)


def test_bulk_reports_all_newly_ready_and_never_repeats(completion_db):
    payload = {'assignments': [
        {'task_id': task_id, 'date': '2026-11-04', 'block': 'A, B', 'status': 'success'}
        for task_id in (10, 11)
    ]}
    with TestClient(app) as client:
        login(client)
        result = client.post('/api/assignments/bulk', json=payload)
        assert result.status_code == 200, result.text
        assert [item['task_id'] for item in result.json()['task_completion_suggestions']] == [10, 11]
        response = client.post('/api/assignment', json={
            'task_id': 10, 'date': '2026-11-05', 'block': 'A', 'status': 'success',
        })
        assert 'task_completion_suggestion' not in response.json()


def test_bulk_final_state_and_rollback(completion_db):
    with TestClient(app) as client:
        login(client)
        real_save = db.create_or_update_assignment
        calls = []

        def fail_second(*args, **kwargs):
            calls.append(1)
            if len(calls) == 2:
                raise db.IntegrityConstraintError('rejected')
            return real_save(*args, **kwargs)

        payload = {'assignments': [
            {'task_id': 10, 'date': '2026-11-04', 'block': 'A, B', 'status': 'success'},
            {'task_id': 11, 'date': '2026-11-04', 'block': 'A, B', 'status': 'success'},
        ]}
        with patch.object(db, 'create_or_update_assignment', side_effect=fail_second):
            result = client.post('/api/assignments/bulk', json=payload)
        assert result.status_code == 400
        assert not db.get_task_completion_suggestions([10, 11])


def test_bulk_does_not_suggest_intermediate_readiness(completion_db):
    assignment(completion_db, block='A, B', status='new')
    with sqlite3.connect(completion_db) as conn:
        assignment_id = conn.execute('SELECT id FROM assignments').fetchone()[0]
    with TestClient(app) as client:
        login(client)
        payload = {'assignment_id': assignment_id, 'task_id': 10, 'date': '2001-01-01', 'block': 'A, B'}
        result = client.post('/api/assignments/bulk', json={'assignments': [
            dict(payload, status='success'), dict(payload, status='cancelled'),
        ]})
        assert result.status_code == 200, result.text
        assert not result.json().get('task_completion_suggestions')
        assert client.get('/api/task/10').json()['completion_ready'] is False


def test_moving_success_updates_both_tasks(completion_db):
    assignment(completion_db)
    with sqlite3.connect(completion_db) as conn:
        assignment_id = conn.execute('SELECT id FROM assignments').fetchone()[0]
    with TestClient(app) as client:
        login(client)
        result = client.post('/api/assignment', json={
            'assignment_id': assignment_id, 'task_id': 11, 'date': '2001-01-01',
            'block': 'A, B', 'status': 'success',
        })
        assert result.status_code == 200, result.text
        assert result.json()['task_completion_suggestion']['task_id'] == 11
        assert client.get('/api/task/10').json()['completion_ready'] is False
        assert client.get('/api/task/11').json()['completion_ready'] is True


def test_late_template_selection_and_reader_policy(completion_db):
    assignment(completion_db)
    write(completion_db, 'UPDATE tasks SET completion_template_id=NULL WHERE id=10')
    with TestClient(app) as client:
        login(client)
        response = client.post('/api/task', json={
            'task_id': 10, 'team_id': 1, 'name': 'First', 'segment_id': 1,
            'criticality': 'medium', 'completion_template_id': 1,
        })
        assert response.status_code == 200, response.text
        assert response.json()['task_completion_suggestion']['task_id'] == 10
        login(client, reader=True)
        response = client.post('/api/assignment', json={
            'task_id': 10, 'date': '2026-11-05', 'block': 'Outside', 'status': 'new',
        })
        assert response.status_code == 200
        assert 'task_completion_suggestion' not in response.json()
        assert client.patch('/api/tasks/10/status', json={'status': 'done'}).status_code == 403


def test_cancelling_and_deleting_success_remove_readiness(completion_db):
    assignment(completion_db)
    with TestClient(app) as client:
        login(client)
        with sqlite3.connect(completion_db) as conn:
            assignment_id = conn.execute('SELECT id FROM assignments').fetchone()[0]
        assert client.post('/api/assignment', json={
            'assignment_id': assignment_id, 'task_id': 10, 'date': '2001-01-01',
            'block': 'A, B', 'status': 'cancelled',
        }).status_code == 200
        assert client.get('/api/task/10').json()['completion_ready'] is False
        result = client.post('/api/assignment', json={
            'assignment_id': assignment_id, 'task_id': 10, 'date': '2001-01-01',
            'block': 'A, B', 'status': 'success',
        })
        assert result.json()['task_completion_suggestion']['task_id'] == 10
        assert client.post('/api/assignments/bulk-delete', json={'assignment_ids': [assignment_id]}).status_code == 200
        assert client.get('/api/task/10').json()['completion_ready'] is False
