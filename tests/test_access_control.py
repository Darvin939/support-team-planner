import os
import sqlite3
import tempfile
import unittest

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

import auth
import db
import db.sqlite as sqlite_backend
from support_planner import app


def application_routes():
    for included in app.routes:
        router = getattr(included, 'original_router', None)
        if router is None:
            continue
        for route in router.routes:
            if isinstance(route, APIRoute):
                yield route


def declared_policy(route):
    policies = []
    for dependency in route.dependant.dependencies:
        call = dependency.call
        kind = getattr(call, 'access_policy', None)
        if kind:
            policies.append((kind, getattr(call, 'minimum_role', None)))
    return policies


class DeclarativeRoutePolicyTest(unittest.TestCase):
    EXPECTED_POLICY = {
        ('GET', '/'): ('role', 'user'),
        ('GET', '/login'): ('public', None),
        ('POST', '/login'): ('public', None),
        ('POST', '/logout'): ('public', None),
        ('GET', '/api/me'): ('role', 'user'),
        ('PUT', '/api/me'): ('role', 'user'),
        ('GET', '/planning'): ('role', 'user'),
        ('GET', '/planning/{team_id}'): ('role', 'user'),
        ('GET', '/settings'): ('role', 'editor'),
        ('GET', '/statistics'): ('role', 'user'),
        ('GET', '/journal'): ('role', 'user'),
        ('GET', '/journal/{team_id}'): ('role', 'user'),
    }

    USER_GET_PATHS = {
        '/api/blocks', '/api/block-templates', '/api/segments', '/api/freeze-days', '/api/teams',
        '/api/teams/{team_id}', '/api/teams/{team_id}/blocks', '/api/teams/{team_id}/assignees',
        '/api/users', '/api/assignments/{team_id}', '/api/assignment/{assignment_id}/history',
        '/api/active-assignments/{team_id}', '/api/tasks/{team_id}/deps',
        '/api/tasks/{team_id}/dependency-graph', '/api/tasks/{team_id}/active-list',
        '/api/tasks/{team_id}', '/api/task/{task_id}', '/api/tasks/{team_id}/archive',
        '/api/task/{task_id}/history', '/api/journal/{team_id}',
        '/api/notifications/new-tasks/preview', '/api/notifications/new-tasks',
    }
    USER_MUTATIONS = {
        ('POST', '/api/assignment'), ('POST', '/api/assignments/bulk'),
        ('POST', '/api/assignments/bulk-reschedule'), ('DELETE', '/api/assignment/{assignment_id}'),
        ('POST', '/api/assignments/bulk-delete'), ('POST', '/api/task-dependency'),
        ('DELETE', '/api/task-dependency'), ('POST', '/api/task'), ('DELETE', '/api/task/{task_id}'),
        ('PATCH', '/api/tasks/{team_id}/reorder'), ('PATCH', '/api/task/{task_id}/priority'),
        ('PATCH', '/api/tasks/{task_id}/psi-status'),
        ('POST', '/api/notifications/new-tasks/seen'),
    }
    EDITOR_MUTATIONS = {
        ('POST', '/api/blocks'), ('DELETE', '/api/blocks/{block_id}'),
        ('POST', '/api/block-templates'), ('PUT', '/api/block-templates/{template_id}'),
        ('DELETE', '/api/block-templates/{template_id}'), ('POST', '/api/segments'),
        ('PUT', '/api/segments/{segment_id}'), ('DELETE', '/api/segments/{segment_id}'),
        ('POST', '/api/freeze-days'), ('PUT', '/api/freeze-days/month'),
        ('DELETE', '/api/freeze-days/month/{year}/{month}'),
        ('DELETE', '/api/freeze-days/{date_str:path}'), ('POST', '/api/teams'),
        ('PUT', '/api/teams/{team_id}'), ('DELETE', '/api/teams/{team_id}'),
        ('POST', '/api/task/{task_id}/restore'), ('PATCH', '/api/tasks/{task_id}/status'),
    }
    ADMIN_MUTATIONS = {
        ('POST', '/api/users'), ('PUT', '/api/users/{user_id}'), ('DELETE', '/api/users/{user_id}'),
    }

    for path in USER_GET_PATHS:
        EXPECTED_POLICY[('GET', path)] = ('role', 'user')
    for route_key in USER_MUTATIONS:
        EXPECTED_POLICY[route_key] = ('role', 'user')
    for route_key in EDITOR_MUTATIONS:
        EXPECTED_POLICY[route_key] = ('role', 'editor')
    for route_key in ADMIN_MUTATIONS:
        EXPECTED_POLICY[route_key] = ('role', 'admin')

    def test_all_application_routes_have_exactly_one_explicit_policy(self):
        actual = {}
        for route in application_routes():
            for method in route.methods:
                key = (method, route.path)
                policies = declared_policy(route)
                self.assertEqual(1, len(policies), key)
                actual[key] = policies[0]
        self.assertEqual(self.EXPECTED_POLICY, actual)

    def test_static_assets_mount_is_explicitly_public(self):
        static_mount = next(route for route in app.routes if getattr(route, 'name', None) == 'react-assets')
        self.assertEqual(('public', None), static_mount.access_policy)


class RoleMatrixCharacterizationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        handle, cls.path = tempfile.mkstemp(suffix='.db')
        os.close(handle)
        cls.old_path = sqlite_backend.DB_PATH
        sqlite_backend.DB_PATH = cls.path
        db.init_db()
        conn = sqlite3.connect(cls.path)
        conn.executemany(
            '''INSERT INTO users (first_name, role, login, password_hash, is_assignee)
               VALUES (?, ?, ?, ?, 0)''',
            [
                ('Role user', 'user', 'role-user', auth.hash_password('password123')),
                ('Role editor', 'editor', 'role-editor', auth.hash_password('password123')),
            ],
        )
        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        sqlite_backend.DB_PATH = cls.old_path
        for suffix in ('', '-wal', '-shm'):
            try:
                os.remove(cls.path + suffix)
            except FileNotFoundError:
                pass

    def login(self, login, password='password123'):
        client = TestClient(app, follow_redirects=False)
        response = client.post('/login', data={'login': login, 'password': password})
        self.assertEqual(200, response.status_code)
        return client

    def test_unauthenticated_api_and_documents_keep_existing_responses(self):
        with TestClient(app, follow_redirects=False) as client:
            api_response = client.get('/api/users')
            document_response = client.get('/settings')
        self.assertEqual((401, {'error': 'Не авторизован'}), (api_response.status_code, api_response.json()))
        self.assertEqual((302, '/login'), (document_response.status_code, document_response.headers['location']))

    def test_user_can_read_users_but_cannot_mutate_editor_or_admin_resources(self):
        with self.login('role-user') as client:
            self.assertEqual(200, client.get('/api/users').status_code)
            self.assertEqual(403, client.post('/api/teams', json={'name': 'x'}).status_code)
            response = client.post('/api/users', json={'first_name': 'x', 'role': 'user'})
        self.assertEqual((403, {'error': 'Недостаточно прав'}), (response.status_code, response.json()))

    def test_editor_can_mutate_editor_resources_but_not_users(self):
        with self.login('role-editor') as client:
            editor_response = client.post('/api/teams', json={'name': ''})
            admin_response = client.post('/api/users', json={'first_name': 'x', 'role': 'user'})
        self.assertEqual(400, editor_response.status_code)
        self.assertEqual((403, {'error': 'Недостаточно прав'}), (admin_response.status_code, admin_response.json()))

    def test_admin_can_reach_admin_mutation(self):
        with self.login('admin', 'q12345678') as client:
            response = client.post('/api/users', json={'first_name': '', 'role': 'user'})
        self.assertEqual(400, response.status_code)

    def test_editor_only_document_keeps_redirect_contract(self):
        with self.login('role-user') as client:
            response = client.get('/settings')
        self.assertEqual((302, '/planning'), (response.status_code, response.headers['location']))

    def test_session_of_deleted_user_is_cleared(self):
        conn = sqlite3.connect(self.path)
        password_hash = auth.hash_password('password123')
        cursor = conn.execute(
            "INSERT INTO users (first_name, role, login, password_hash, is_assignee) VALUES ('Temporary', 'user', 'temporary-user', ?, 0)",
            (password_hash,),
        )
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()

        with self.login('temporary-user') as client:
            conn = sqlite3.connect(self.path)
            conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
            conn.commit()
            conn.close()
            first_response = client.get('/api/me')
            second_response = client.get('/api/me')

        self.assertEqual(401, first_response.status_code)
        self.assertEqual(401, second_response.status_code)
