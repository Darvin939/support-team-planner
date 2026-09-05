import unittest
import logging

from routers.debug import _log_entry, _safe_log
from support_planner import _is_debug_log_poll_access


class DebugConsolePolicyTests(unittest.TestCase):
    def test_secret_values_are_redacted_before_display(self):
        value = _safe_log('password=secret123 cookie:abc token = xyz')
        self.assertNotIn('secret123', value)
        self.assertNotIn('abc', value)
        self.assertNotIn('xyz', value)
        self.assertIn('[REDACTED]', value)

    def test_log_entry_exposes_level_and_logger(self):
        entry = _log_entry('2026-09-06 12:00:00 ERROR api Something failed')
        self.assertEqual('ERROR', entry['level'])
        self.assertEqual('api', entry['logger'])

    def test_debug_log_poll_access_is_excluded_only_for_uvicorn_access(self):
        access = logging.LogRecord('uvicorn.access', logging.INFO, '', 0, '%s - "GET /api/debug/logs?limit=500 HTTP/1.1" 200', ('127.0.0.1',), None)
        error = logging.LogRecord('uvicorn.error', logging.ERROR, '', 0, 'GET /api/debug/logs failed', (), None)
        self.assertTrue(_is_debug_log_poll_access(access, access.getMessage()))
        self.assertFalse(_is_debug_log_poll_access(error, error.getMessage()))


if __name__ == '__main__':
    unittest.main()
