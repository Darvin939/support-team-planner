import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

from backend.app_metadata import generate_build_id, load_application_metadata


class ApplicationMetadataTests(unittest.TestCase):
    def test_development_metadata_uses_version_file_and_dev_build_id(self):
        metadata = load_application_metadata(environ={})
        version_file = Path(__file__).resolve().parents[1] / 'application_version.json'
        version = json.loads(version_file.read_text(encoding='utf-8'))['release_version']
        self.assertEqual(metadata['release_version'], version)
        self.assertEqual(metadata['build_id'], 'dev')

    def test_distribution_metadata_is_loaded_from_distribution_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backend_root = root / 'backend'
            backend_root.mkdir()
            (root / 'application_version.json').write_text(
                json.dumps({'release_version': '1.2.3'}), encoding='utf-8'
            )
            (root / 'app_build_metadata.json').write_text(
                json.dumps({'build_id': 'dist-build'}), encoding='utf-8'
            )

            metadata = load_application_metadata(app_root=backend_root, environ={})

        self.assertEqual(metadata, {
            'release_version': '1.2.3',
            'build_id': 'dist-build',
        })

    def test_environment_overrides_release_and_build_metadata(self):
        metadata = load_application_metadata(environ={
            'SUPPORT_PLANNER_RELEASE_VERSION': '2.3.4',
            'SUPPORT_PLANNER_BUILD_ID': 'build-from-test',
        })
        self.assertEqual(metadata, {
            'release_version': '2.3.4',
            'build_id': 'build-from-test',
        })

    def test_generated_build_id_includes_utc_time_and_git_sha(self):
        run = Mock(side_effect=[
            Mock(stdout='ab12cd34\n'),
            Mock(stdout=''),
        ])
        build_time = datetime(2026, 10, 11, 12, 34, 56, tzinfo=timezone.utc)
        self.assertEqual(
            generate_build_id(environ={}, build_time=build_time, run=run),
            '20261011T123456Z-ab12cd34',
        )

    def test_generated_build_id_marks_dirty_worktree(self):
        run = Mock(side_effect=[Mock(stdout='ab12cd34'), Mock(stdout=' M support_planner.py')])
        build_time = datetime(2026, 10, 11, tzinfo=timezone.utc)
        self.assertEqual(
            generate_build_id(environ={}, build_time=build_time, run=run),
            '20261011T000000Z-ab12cd34-dirty',
        )

    def test_build_id_override_skips_git_and_timestamp_generation(self):
        run = Mock(side_effect=AssertionError('git should not be called'))
        self.assertEqual(
            generate_build_id(environ={'BUILD_ID': 'ci-418'}, run=run),
            'ci-418',
        )
        run.assert_not_called()

    def test_missing_git_checkout_uses_nogit_suffix(self):
        run = Mock(side_effect=OSError('git executable unavailable'))
        build_time = datetime(2026, 10, 11, tzinfo=timezone.utc)
        self.assertEqual(
            generate_build_id(environ={}, build_time=build_time, run=run),
            '20261011T000000Z-nogit',
        )


if __name__ == '__main__':
    unittest.main()
