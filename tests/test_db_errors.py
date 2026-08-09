import sqlite3
import unittest
from unittest.mock import patch

import db.users


class DatabaseErrorPropagationTest(unittest.TestCase):
    def test_unexpected_update_error_is_not_masked(self):
        conn = sqlite3.connect(':memory:')
        with patch('db.connection.get_db_connection', return_value=conn), \
                patch.object(db.users, '_update_user', side_effect=sqlite3.OperationalError('unexpected')):
            with self.assertRaisesRegex(sqlite3.OperationalError, 'unexpected'):
                db.users.update_user(1, None, 'Test')


if __name__ == '__main__':
    unittest.main()
