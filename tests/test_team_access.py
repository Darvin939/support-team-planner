import sqlite3
import unittest

import db


class TeamAccessDaoTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            '''
            CREATE TABLE teams (id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE users (
                id INTEGER PRIMARY KEY, last_name TEXT, first_name TEXT, middle_name TEXT,
                role TEXT, login TEXT, is_assignee INTEGER
            );
            CREATE TABLE user_team_access (user_id INTEGER, team_id INTEGER, PRIMARY KEY(user_id, team_id));
            CREATE TABLE tasks (id INTEGER PRIMARY KEY, team_id INTEGER);
            CREATE TABLE assignments (id INTEGER PRIMARY KEY, task_id INTEGER);
            INSERT INTO teams VALUES (1, 'A'), (2, 'B');
            INSERT INTO users VALUES
                (1, NULL, 'Admin', NULL, 'admin', 'admin', 1),
                (2, NULL, 'Open', NULL, 'user', 'open', 1),
                (3, NULL, 'Limited', NULL, 'user', 'limited', 1);
            INSERT INTO user_team_access VALUES (3, 1);
            INSERT INTO tasks VALUES (10, 1), (20, 2);
            INSERT INTO assignments VALUES (100, 10), (200, 20);
            '''
        )

    def tearDown(self):
        self.conn.close()

    def call(self, function, *args):
        return function.__wrapped__(self.conn, *args)

    def test_admin_and_unrestricted_user_access_all_teams(self):
        self.assertTrue(self.call(db.user_can_access_team, 1, 'admin', 2))
        self.assertTrue(self.call(db.user_can_access_team, 2, 'user', 2))

    def test_limited_user_accesses_only_explicit_team(self):
        self.assertTrue(self.call(db.user_can_access_team, 3, 'user', 1))
        self.assertFalse(self.call(db.user_can_access_team, 3, 'user', 2))

    def test_resolves_team_through_task_and_assignment(self):
        self.assertEqual(2, self.call(db.get_task_team_id, 20))
        self.assertEqual(2, self.call(db.get_assignment_team_id, 200))

    def test_assignee_list_respects_team_access(self):
        users = self.call(db.get_team_assignees, 2)
        self.assertEqual({1, 2}, {user['id'] for user in users})
        self.assertFalse(self.call(db.user_is_eligible_assignee, 3, 2))


if __name__ == '__main__':
    unittest.main()
