"""Read release and build identifiers for the running application."""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parent
DEV_BUILD_ID = 'dev'


def _read_json(path):
    with open(path, encoding='utf-8') as source:
        return json.load(source)


def load_application_metadata(app_root=None, environ=None):
    """Return the configured release version and build id.

    Environment overrides support local/test runs and CI. Distribution builds
    provide app_build_metadata.json next to this module; development runs use
    the checked-in release version and the explicit ``dev`` build id.
    """
    root = Path(app_root) if app_root is not None else APP_ROOT
    env = os.environ if environ is None else environ

    release_version = env.get('SUPPORT_PLANNER_RELEASE_VERSION')
    if not release_version:
        version_file = root / 'application_version.json'
        if version_file.is_file():
            release_version = _read_json(version_file).get('release_version')
    if not isinstance(release_version, str) or not release_version.strip():
        raise RuntimeError('Application release version is missing or invalid')

    build_id = env.get('SUPPORT_PLANNER_BUILD_ID')
    if not build_id:
        build_metadata_file = root / 'app_build_metadata.json'
        if build_metadata_file.is_file():
            build_id = _read_json(build_metadata_file).get('build_id')
    if not isinstance(build_id, str) or not build_id.strip():
        build_id = DEV_BUILD_ID

    return {
        'release_version': release_version.strip(),
        'build_id': build_id.strip(),
    }


def generate_build_id(app_root=None, environ=None, run=None):
    """Create a unique UTC build id augmented with the source Git commit."""
    env = os.environ if environ is None else environ
    override = env.get('BUILD_ID')
    if override:
        return override.strip()

    root = Path(app_root) if app_root is not None else APP_ROOT
    run_command = run or subprocess.run
    try:
        revision = run_command(
            ['git', '-C', str(root), 'rev-parse', '--short=8', 'HEAD'],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        status = run_command(
            ['git', '-C', str(root), 'status', '--porcelain', '--untracked-files=normal'],
            check=True, capture_output=True, text=True,
        ).stdout
        if not revision:
            revision = 'nogit'
    except (OSError, subprocess.CalledProcessError):
        revision = 'nogit'
        status = ''

    dirty_suffix = '-dirty' if status else ''
    return '{}{}'.format(revision, dirty_suffix)


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == '--release-version':
        print(load_application_metadata()['release_version'])
    elif len(sys.argv) == 2 and sys.argv[1] == '--generate-build-id':
        print(generate_build_id())
    else:
        raise SystemExit('Usage: app_metadata.py --release-version | --generate-build-id')
