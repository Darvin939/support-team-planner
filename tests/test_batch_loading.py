import sqlite3
import unittest

import db


class BatchLoadingTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        self.conn.create_function('casefold', 1, lambda value: (value or '').casefold(), deterministic=True)
        self.conn.executescript('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY, last_name TEXT, first_name TEXT NOT NULL,
                middle_name TEXT, role TEXT NOT NULL, login TEXT, is_assignee INTEGER NOT NULL
            );
            CREATE TABLE user_team_access (user_id INTEGER, team_id INTEGER);
            CREATE TABLE block_templates (id INTEGER PRIMARY KEY, name TEXT, segment_id INTEGER);
            CREATE TABLE blocks (id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE template_blocks (template_id INTEGER, block_id INTEGER, schedule_offset INTEGER);
        ''')
        self.conn.executemany(
            'INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?)',
            [(1, 'One', 'User', None, 'editor', 'one', 1), (2, 'Two', 'User', None, 'user', 'two', 1)],
        )
        self.conn.executemany(
            'INSERT INTO user_team_access VALUES (?, ?)', [(1, 10), (1, 20), (2, 20)]
        )
        self.conn.executemany(
            'INSERT INTO block_templates VALUES (?, ?, ?)', [(1, 'First', 1), (2, 'Second', 1)]
        )
        self.conn.executemany(
            'INSERT INTO blocks VALUES (?, ?)', [(1, 'A'), (2, 'B'), (3, 'C')]
        )
        self.conn.executemany(
            'INSERT INTO template_blocks VALUES (?, ?, ?)', [(1, 1, 0), (1, 2, 2), (2, 3, 1)]
        )

    def tearDown(self):
        self.conn.close()

    def count_selects(self, callback):
        queries = []
        self.conn.set_trace_callback(lambda query: queries.append(query) if query.lstrip().upper().startswith('SELECT') else None)
        try:
            result = callback()
        finally:
            self.conn.set_trace_callback(None)
        return result, queries

    def test_users_batch_team_access_preserves_result_and_query_count(self):
        result, queries = self.count_selects(lambda: db.get_all_users.__wrapped__(self.conn))
        by_id = {user['id']: user['team_ids'] for user in result}
        self.assertEqual({1: [10, 20], 2: [20]}, by_id)
        self.assertEqual(2, len(queries))

    def test_templates_batch_blocks_preserves_result_and_query_count(self):
        result, queries = self.count_selects(lambda: db.get_all_templates.__wrapped__(self.conn))
        self.assertEqual(
            [[(1, 0), (2, 2)], [(3, 1)]],
            [[(block['id'], block['shift_days']) for block in template['blocks']] for template in result],
        )
        self.assertEqual(2, len(queries))


if __name__ == '__main__':
    unittest.main()
