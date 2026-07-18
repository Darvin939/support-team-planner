import sqlite3
import unittest

import db


class UsersPaginationTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        self.conn.create_function('casefold', 1, lambda value: (value or '').casefold(), deterministic=True)
        self.conn.execute(
            '''CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                last_name TEXT,
                first_name TEXT NOT NULL,
                middle_name TEXT,
                role TEXT NOT NULL,
                login TEXT,
                is_assignee INTEGER NOT NULL
            )'''
        )
        self.conn.executemany(
            'INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?)',
            [
                (1, 'Иванов', 'Иван', 'Иванович', 'editor', 'ivanov', 1),
                (2, 'Петрова', 'Анна', None, 'user', 'petrova', 1),
                (3, None, 'Администратор', None, 'admin', 'admin', 0),
            ],
        )

    def tearDown(self):
        self.conn.close()

    def page(self, offset=0, limit=20, search=None):
        return db.get_users_page.__wrapped__(self.conn, offset, limit, search)

    def test_filters_by_login_full_name_and_localized_role(self):
        self.assertEqual([1], [u['id'] for u in self.page(search='IVANOV')['users']])
        self.assertEqual([2], [u['id'] for u in self.page(search='петрова анна')['users']])
        self.assertEqual([3], [u['id'] for u in self.page(search='администратор')['users']])

    def test_filters_before_pagination_and_returns_total(self):
        result = self.page(offset=1, limit=1, search='пользователь')
        self.assertEqual(1, result['total'])
        self.assertEqual([], result['users'])

    def test_returns_requested_page(self):
        result = self.page(offset=1, limit=1)
        self.assertEqual(3, result['total'])
        self.assertEqual(1, len(result['users']))
        self.assertIsInstance(result['users'][0]['is_assignee'], bool)

    def test_legacy_full_list_stays_an_array(self):
        result = db.get_all_users.__wrapped__(self.conn)
        self.assertIsInstance(result, list)
        self.assertEqual(3, len(result))


if __name__ == '__main__':
    unittest.main()
