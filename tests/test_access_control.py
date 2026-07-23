import unittest

from access_control import required_rank


class RequiredRankTest(unittest.TestCase):
    def test_role_matrix(self):
        cases = [
            ('GET', '/api/users', 0),
            ('GET', '/api/teams', 0),
            ('POST', '/api/task', 0),
            ('POST', '/api/teams', 1),
            ('DELETE', '/api/segments/1', 1),
            ('POST', '/api/users', 2),
            ('GET', '/settings', 1),
        ]
        for method, path, expected in cases:
            with self.subTest(method=method, path=path):
                self.assertEqual(expected, required_rank(method, path))
