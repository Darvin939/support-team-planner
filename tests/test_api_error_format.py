import os
import tempfile
import unittest

from fastapi.testclient import TestClient

import db
import db.sqlite as sqlite_backend
from support_planner import app


class ApiErrorFormatTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        handle, cls.path = tempfile.mkstemp(suffix='.db')
        os.close(handle)
        cls.old_path = sqlite_backend.DB_PATH
        sqlite_backend.DB_PATH = cls.path
        db.init_db()

    @classmethod
    def tearDownClass(cls):
        sqlite_backend.DB_PATH = cls.old_path
        for suffix in ('', '-wal', '-shm'):
            try:
                os.remove(cls.path + suffix)
            except FileNotFoundError:
                pass

    def login(self):
        client = TestClient(app, follow_redirects=False)
        response = client.post('/login', data={'login': 'admin', 'password': 'q12345678'})
        self.assertEqual(200, response.status_code)
        return client

    def test_manual_api_error_uses_error_field(self):
        with self.login() as client:
            response = client.put('/api/me', json={})
        self.assertEqual(400, response.status_code)
        self.assertEqual({'error': 'Нечего обновлять'}, response.json())

    def test_api_http_exception_maps_detail_to_error(self):
        with self.login() as client:
            response = client.get('/api/task/999999')
        self.assertEqual(404, response.status_code)
        self.assertEqual({'error': 'Работа не найдена'}, response.json())

    def test_api_validation_error_uses_stable_string(self):
        with self.login() as client:
            response = client.get('/api/tasks/not-an-integer')
        self.assertEqual(422, response.status_code)
        self.assertEqual({'error': 'Некорректный запрос'}, response.json())

    def test_api_body_validation_error_uses_stable_string(self):
        with self.login() as client:
            response = client.post('/api/assignment', json={'assignment_id': []})
        self.assertEqual(422, response.status_code)
        self.assertEqual({'error': 'Некорректный запрос'}, response.json())

    def test_non_api_validation_keeps_default_detail(self):
        with TestClient(app, follow_redirects=False) as client:
            response = client.post('/login', data={'login': 'admin'})
        self.assertEqual(422, response.status_code)
        self.assertIn('detail', response.json())
        self.assertNotIn('error', response.json())

    def test_non_api_redirect_is_not_converted_to_json(self):
        with TestClient(app, follow_redirects=False) as client:
            response = client.get('/')
        self.assertEqual(302, response.status_code)
        self.assertEqual('/login', response.headers['location'])
        self.assertNotEqual('application/json', response.headers.get('content-type'))

    def test_unauthorized_api_uses_error_contract(self):
        with TestClient(app, follow_redirects=False) as client:
            response = client.get('/api/me')
        self.assertEqual(401, response.status_code)
        self.assertEqual({'error': 'Не авторизован'}, response.json())

    def test_reference_data_validation_and_duplicate_errors_are_stable(self):
        with self.login() as client:
            empty = client.post('/api/blocks', json={'name': ' '})
            created = client.post('/api/blocks', json={'name': 'Contract block'})
            duplicate = client.post('/api/blocks', json={'name': 'Contract block'})
        self.assertEqual((400, {'error': 'Name required'}), (empty.status_code, empty.json()))
        self.assertEqual(200, created.status_code)
        self.assertEqual(400, duplicate.status_code)
        self.assertIn('error', duplicate.json())

    def test_reference_data_not_found_error_is_stable(self):
        with self.login() as client:
            segment = client.post('/api/segments', json={'name': 'Contract segment'}).json()
            response = client.put(
                '/api/block-templates/999999',
                json={'name': 'Missing', 'segment_id': segment['id'], 'entries': []},
            )
        self.assertEqual(404, response.status_code)
        self.assertEqual({'error': 'Template not found'}, response.json())

    def test_freeze_day_single_range_month_and_delete_routes(self):
        with self.login() as client:
            single = client.post('/api/freeze-days', json={'date': '2040-01-10'})
            date_delete = client.delete('/api/freeze-days/2040-01-10')
            date_range = client.post(
                '/api/freeze-days',
                json={'start_date': '2040-02-01', 'end_date': '2040-02-02'},
            )
            month = client.put(
                '/api/freeze-days/month',
                json={'year': 2040, 'month': 3, 'days': [1, 2]},
            )
            month_delete = client.delete('/api/freeze-days/month/2040/3')
        self.assertEqual(200, single.status_code)
        self.assertEqual({'success': True}, date_delete.json())
        self.assertEqual({'success': True, 'count': 2}, date_range.json())
        self.assertEqual({'success': True}, month.json())
        self.assertEqual({'success': True}, month_delete.json())


if __name__ == '__main__':
    unittest.main()
