import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import backend.db.sqlite as sqlite_backend
from backend import auth
from backend import db
from backend.app_metadata import load_application_metadata
from backend.release_change_log import load_release_changelog
from backend.application import app

RELEASE_VERSION = load_application_metadata()['release_version']


class ReleaseChangeLogSourceTests(unittest.TestCase):
    def _write_source(self, document):
        handle, path = tempfile.mkstemp(suffix='.json')
        os.close(handle)
        Path(path).write_text(json.dumps(document, ensure_ascii=False), encoding='utf-8')
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        return path

    def test_bundled_release_log_has_one_valid_entry_without_build_id(self):
        releases = load_release_changelog()
        self.assertEqual([RELEASE_VERSION], [release['version'] for release in releases])
        self.assertNotIn('build_id', releases[0])
        self.assertEqual(2, len(releases[0]['changes']))

    def test_source_sorts_releases_by_date_descending(self):
        path = self._write_source({'releases': [
            {'version': '1.0.0', 'date': '2026-01-01', 'title': 'Old', 'changes': ['Old change']},
            {'version': '1.1.0', 'date': '2026-02-01', 'title': 'New', 'changes': ['New change']},
        ]})
        self.assertEqual(['1.1.0', '1.0.0'], [item['version'] for item in load_release_changelog(path)])

    def test_source_rejects_duplicate_versions(self):
        record = {'version': '1.0.0', 'date': '2026-01-01', 'title': 'Release', 'changes': ['Change']}
        path = self._write_source({'releases': [record, record]})
        with self.assertRaisesRegex(ValueError, 'Duplicate change log release version'):
            load_release_changelog(path)

    def test_source_rejects_build_id_in_release_record(self):
        path = self._write_source({'releases': [{
            'version': '1.0.0', 'date': '2026-01-01', 'title': 'Release',
            'changes': ['Change'], 'build_id': 'must-not-key-release-notes',
        }]})
        with self.assertRaisesRegex(ValueError, 'Unsupported change log fields: build_id'):
            load_release_changelog(path)

    def test_source_rejects_invalid_date_and_change_count(self):
        for date, changes in (('2026-1-1', ['Change']), ('2026-01-01', []),
                              ('2026-01-01', ['1', '2', '3', '4', '5', '6'])):
            path = self._write_source({'releases': [{
                'version': '1.0.0', 'date': date, 'title': 'Release', 'changes': changes,
            }]})
            with self.subTest(date=date, changes=changes):
                with self.assertRaises(ValueError):
                    load_release_changelog(path)


class ReleaseChangeLogApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        handle, cls.database_path = tempfile.mkstemp(suffix='.db')
        os.close(handle)
        cls.previous_database_path = sqlite_backend.DB_PATH
        sqlite_backend.DB_PATH = cls.database_path
        db.init_db()
        password_hash = auth.hash_password('password123')
        conn = sqlite3.connect(cls.database_path)
        conn.executemany('''INSERT INTO users
            (id, first_name, role, login, password_hash, is_assignee)
            VALUES (?, ?, 'user', ?, ?, 1)''', [
            (501, 'Reader One', 'release-reader-one', password_hash),
            (502, 'Reader Two', 'release-reader-two', password_hash),
        ])
        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        sqlite_backend.DB_PATH = cls.previous_database_path
        for suffix in ('', '-wal', '-shm'):
            try:
                os.remove(cls.database_path + suffix)
            except FileNotFoundError:
                pass

    def _login(self, login='release-reader-one'):
        client = TestClient(app)
        response = client.post('/login', data={'login': login, 'password': 'password123'})
        self.assertEqual(200, response.status_code)
        return client

    def setUp(self):
        conn = sqlite3.connect(self.database_path)
        conn.execute('DELETE FROM user_release_change_log_seen')
        conn.commit()
        conn.close()

    def test_release_log_requires_authentication(self):
        self.assertEqual(401, TestClient(app).get('/api/release-change-log').status_code)

    def test_metadata_and_unseen_release_are_returned_then_acknowledged(self):
        with self._login() as client:
            response = client.get('/api/release-change-log')
            self.assertEqual(200, response.status_code)
            data = response.json()
            self.assertEqual({'release_version': RELEASE_VERSION, 'build_id': 'dev'}, data['application'])
            self.assertEqual([RELEASE_VERSION], [item['version'] for item in data['unseen_releases']])

            marked = client.post('/api/release-change-log/seen', json={'release_versions': [RELEASE_VERSION]})
            self.assertEqual({'success': True, 'marked': 1}, marked.json())
            again = client.post('/api/release-change-log/seen', json={'release_versions': [RELEASE_VERSION]})
            self.assertEqual({'success': True, 'marked': 0}, again.json())
            after = client.get('/api/release-change-log').json()
            self.assertEqual([], after['unseen_releases'])
            self.assertEqual([RELEASE_VERSION], [item['version'] for item in after['releases']])

    def test_seen_release_is_isolated_per_user(self):
        with self._login() as client:
            self.assertEqual(200, client.post(
                '/api/release-change-log/seen', json={'release_versions': [RELEASE_VERSION]}
            ).status_code)
        with self._login('release-reader-two') as other_client:
            data = other_client.get('/api/release-change-log').json()
            self.assertEqual([RELEASE_VERSION], [item['version'] for item in data['unseen_releases']])

    def test_seen_endpoint_rejects_unknown_versions(self):
        with self._login() as client:
            response = client.post('/api/release-change-log/seen', json={'release_versions': ['999.0.0']})
            self.assertEqual(400, response.status_code)
            self.assertEqual([RELEASE_VERSION], [
                item['version'] for item in client.get('/api/release-change-log').json()['unseen_releases']
            ])

    def test_startup_metadata_upsert_is_idempotent_and_preserves_seen_state(self):
        with self._login() as client:
            client.post('/api/release-change-log/seen', json={'release_versions': [RELEASE_VERSION]})
            db.upsert_application_metadata(RELEASE_VERSION, 'another-build')
            db.upsert_application_metadata(RELEASE_VERSION, 'another-build')
            metadata = db.get_application_metadata()
            self.assertEqual((RELEASE_VERSION, 'another-build'),
                             (metadata['release_version'], metadata['build_id']))
            self.assertEqual({RELEASE_VERSION}, db.get_seen_release_versions(501))
            conn = sqlite3.connect(self.database_path)
            self.assertEqual(1, conn.execute('SELECT COUNT(*) FROM application_metadata').fetchone()[0])
            conn.close()


if __name__ == '__main__':
    unittest.main()
