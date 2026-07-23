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


if __name__ == '__main__':
    unittest.main()
