import subprocess
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock

from app_metadata import generate_build_id, load_application_metadata


class ApplicationMetadataTests(unittest.TestCase):
    def test_development_metadata_uses_version_file_and_dev_build_id(self):
        metadata = load_application_metadata(environ={})
        self.assertEqual(metadata['release_version'], '0.1.0')
        self.assertEqual(metadata['build_id'], 'dev')

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
