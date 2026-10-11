"""Load and validate the bundled editorial release notes."""

import json
from datetime import datetime
from pathlib import Path


CHANGELOG_PATH = Path(__file__).resolve().parent.parent / 'changelog.json'


def load_release_changelog(path=None):
    source_path = Path(path) if path is not None else CHANGELOG_PATH
    with open(source_path, encoding='utf-8') as source:
        document = json.load(source)
    if not isinstance(document, dict) or not isinstance(document.get('releases'), list):
        raise ValueError('Change log must contain a releases array')

    versions = set()
    normalized = []
    for release in document['releases']:
        if not isinstance(release, dict):
            raise ValueError('Each change log release must be an object')
        unexpected_fields = set(release) - {'version', 'date', 'title', 'changes'}
        if unexpected_fields:
            raise ValueError('Unsupported change log fields: {}'.format(', '.join(sorted(unexpected_fields))))
        version = release.get('version')
        date = release.get('date')
        title = release.get('title')
        changes = release.get('changes')
        if not isinstance(version, str) or not version.strip():
            raise ValueError('Each change log release must have a version')
        version = version.strip()
        if version in versions:
            raise ValueError('Duplicate change log release version: {}'.format(version))
        versions.add(version)
        if not isinstance(date, str):
            raise ValueError('Release {} must have a date'.format(version))
        try:
            parsed_date = datetime.strptime(date, '%Y-%m-%d')
        except ValueError as exc:
            raise ValueError('Release {} date must use YYYY-MM-DD'.format(version)) from exc
        if parsed_date.strftime('%Y-%m-%d') != date:
            raise ValueError('Release {} date must use YYYY-MM-DD'.format(version))
        if not isinstance(title, str) or not title.strip():
            raise ValueError('Release {} must have a title'.format(version))
        if not isinstance(changes, list) or not 1 <= len(changes) <= 5:
            raise ValueError('Release {} must have between 1 and 5 change items'.format(version))
        if any(not isinstance(item, str) or not item.strip() for item in changes):
            raise ValueError('Release {} change items must be non-empty strings'.format(version))
        normalized.append({
            'version': version,
            'date': date,
            'title': title.strip(),
            'changes': [item.strip() for item in changes],
        })

    return sorted(normalized, key=lambda release: release['date'], reverse=True)


def get_release_change_log(user_id):
    from backend import db
    from backend.app_metadata import load_application_metadata

    releases = load_release_changelog()
    seen_versions = db.get_seen_release_versions(user_id)
    unseen = [release for release in releases if release['version'] not in seen_versions]
    application = db.get_application_metadata()
    if application is None:
        application = load_application_metadata()
    return {
        'application': {
            'release_version': application['release_version'],
            'build_id': application['build_id'],
        },
        'releases': releases,
        'unseen_releases': unseen,
    }
