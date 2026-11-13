import json
import os
import runpy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


class SettingsEnvironmentTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix='planner-settings-')
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.settings = self.root / 'backend' / 'settings.py'
        self.settings.parent.mkdir()
        self.settings.write_text((ROOT / 'backend/settings.py').read_text(encoding='utf-8'), encoding='utf-8')
        environ = patch.dict(os.environ, {
            'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8',
        }, clear=True)
        environ.start()
        self.addCleanup(environ.stop)

    def write_env(self, name, content):
        path = self.root / name
        path.write_text(content, encoding='utf-8')
        return path

    def load_settings(self):
        runpy.run_path(str(self.settings))

    def run_python(self, code):
        env = os.environ.copy()
        env['PYTHONPATH'] = str(ROOT)
        env['SUPPORT_PLANNER_DB_PATH'] = str(self.root / 'must-not-open.db')
        return subprocess.run(
            [sys.executable, '-c', code], cwd=self.root, env=env,
            capture_output=True, text=True, encoding='utf-8', timeout=10,
        )

    def test_loads_explicit_dotenv_file_with_spaces_in_path(self):
        path = self.write_env('planner env',
                              'SUPPORT_PLANNER_DATABASE_URL=postgresql://fixture@host/planner\n'
                              'SUPPORT_PLANNER_DATABASE_SCHEMA=planner\n'
                              'SESSION_SECRET_KEY=fixture-session\nPGPASSWORD=fixture-password\n')
        os.environ['SUPPORT_PLANNER_ENV_FILE'] = str(path)
        self.load_settings()
        self.assertEqual(os.environ['SUPPORT_PLANNER_DATABASE_URL'], 'postgresql://fixture@host/planner')
        self.assertEqual(os.environ['SUPPORT_PLANNER_DATABASE_SCHEMA'], 'planner')
        self.assertEqual(os.environ['SESSION_SECRET_KEY'], 'fixture-session')
        self.assertEqual(os.environ['PGPASSWORD'], 'fixture-password')

    def test_environment_including_empty_values_has_priority(self):
        path = self.write_env('env', 'PGPASSWORD=file\nSESSION_SECRET_KEY=file\n')
        os.environ.update(SUPPORT_PLANNER_ENV_FILE=str(path), PGPASSWORD='process', SESSION_SECRET_KEY='')
        self.load_settings()
        self.assertEqual(os.environ['PGPASSWORD'], 'process')
        self.assertEqual(os.environ['SESSION_SECRET_KEY'], '')

    def test_explicit_file_preserves_secret_without_interpolation_or_shell_execution(self):
        value = 'пароль \' " \\ ${SESSION_SECRET_KEY} $HOME $(touch injected) `touch injected`\nстрока # конец'
        escaped = value.replace('\\', '\\\\').replace("'", "\\'")
        path = self.write_env('env', "PGPASSWORD='%s'\n" % escaped)
        os.environ.update(SUPPORT_PLANNER_ENV_FILE=str(path), SESSION_SECRET_KEY='do-not-substitute')
        self.load_settings()
        self.assertEqual(os.environ['PGPASSWORD'], value)
        self.assertFalse((self.root / 'injected').exists())

    def test_default_dotenv_keeps_existing_search_interpolation_and_priority(self):
        self.write_env('.env', 'ENV_DOMAIN=file.example\nDERIVED_URL=https://${ENV_DOMAIN}\n')
        os.environ['ENV_DOMAIN'] = 'process.example'
        self.load_settings()
        self.assertEqual(os.environ['ENV_DOMAIN'], 'process.example')
        self.assertEqual(os.environ['DERIVED_URL'], 'https://process.example')

    def test_explicit_file_replaces_default_dotenv_search(self):
        self.write_env('.env', 'LOCAL_ONLY=must-not-load\n')
        path = self.write_env('selected', 'PGPASSWORD=chosen\n')
        os.environ['SUPPORT_PLANNER_ENV_FILE'] = str(path)
        self.load_settings()
        self.assertEqual(os.environ['PGPASSWORD'], 'chosen')
        self.assertNotIn('LOCAL_ONLY', os.environ)

    def test_skip_flag_ignores_default_and_explicit_files(self):
        self.write_env('.env', 'LOCAL_ONLY=must-not-load\n')
        os.environ['SUPPORT_PLANNER_SKIP_DOTENV'] = '1'
        for selected in (None, str(self.root / 'missing')):
            with self.subTest(selected=selected):
                if selected is not None:
                    os.environ['SUPPORT_PLANNER_ENV_FILE'] = selected
                self.load_settings()
                self.assertNotIn('LOCAL_ONLY', os.environ)

    def test_file_errors_do_not_fall_back_or_echo_contents(self):
        self.write_env('.env', 'LOCAL_ONLY=must-not-load\n')
        invalid = self.root / 'invalid-utf8'
        invalid.write_bytes(b'PGPASSWORD=not-for-logs\n\xff')
        for path in ('', str(self.root / 'missing'), str(self.root), str(invalid)):
            with self.subTest(path=path):
                os.environ['SUPPORT_PLANNER_ENV_FILE'] = path
                with self.assertRaisesRegex(RuntimeError, 'SUPPORT_PLANNER_ENV_FILE') as error:
                    self.load_settings()
                self.assertNotIn('not-for-logs', str(error.exception))
                self.assertNotIn('LOCAL_ONLY', os.environ)
                self.assertNotIn('PGPASSWORD', os.environ)

    def test_unreadable_file_is_a_configuration_error(self):
        path = self.write_env('unreadable', 'PGPASSWORD=not-for-logs\n')
        path.chmod(0)
        try:
            if os.access(str(path), os.R_OK):
                self.skipTest('This user can read files without permission bits')
            os.environ['SUPPORT_PLANNER_ENV_FILE'] = str(path)
            with self.assertRaisesRegex(RuntimeError, 'SUPPORT_PLANNER_ENV_FILE'):
                self.load_settings()
        finally:
            path.chmod(0o600)

    def test_empty_readable_file_is_valid(self):
        os.environ['SUPPORT_PLANNER_ENV_FILE'] = str(self.write_env('empty', ''))
        self.load_settings()
        self.assertNotIn('SUPPORT_PLANNER_DATABASE_URL', os.environ)

    def test_tls_module_does_not_load_another_dotenv(self):
        self.write_env('.env', 'LOCAL_ONLY=must-not-load\n')
        os.environ['SUPPORT_PLANNER_ENV_FILE'] = str(self.write_env('selected', 'PGPASSWORD=chosen\n'))
        self.load_settings()
        with patch('dotenv.load_dotenv', side_effect=AssertionError('Unexpected second dotenv load')):
            runpy.run_path(str(ROOT / 'backend/ssl_context.py'))
        self.assertNotIn('LOCAL_ONLY', os.environ)
        self.assertEqual(os.environ['PGPASSWORD'], 'chosen')

    def test_file_is_loaded_before_storage_backend_selection(self):
        path = self.write_env('env',
                              'SUPPORT_PLANNER_DATABASE_URL=postgresql://fixture@127.0.0.1:1/planner\n'
                              'SUPPORT_PLANNER_DATABASE_SCHEMA=custom_schema\n'
                              'SESSION_SECRET_KEY=fixture-session\n')
        os.environ['SUPPORT_PLANNER_ENV_FILE'] = str(path)
        result = self.run_python(
            'import json, os; from backend.db.connection import backend; '
            'print(json.dumps([backend.name, backend.schema, os.environ["SESSION_SECRET_KEY"]]))'
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), ['postgresql', 'custom_schema', 'fixture-session'])
        self.assertFalse((self.root / 'must-not-open.db').exists())

    def test_missing_config_stops_before_opening_default_database(self):
        os.environ['SUPPORT_PLANNER_ENV_FILE'] = str(self.root / 'missing')
        result = self.run_python('from backend.db.connection import backend')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('SUPPORT_PLANNER_ENV_FILE', result.stderr)
        self.assertFalse((self.root / 'must-not-open.db').exists())
        self.assertFalse((self.root / 'database.db').exists())


if __name__ == '__main__':
    unittest.main()
