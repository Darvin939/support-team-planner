from datetime import datetime, timezone

from backend.db.connection import backend as _backend, with_db_connection


def _utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


@with_db_connection(write=True)
def upsert_application_metadata(conn, release_version, build_id):
    conn.execute(f'''
        INSERT INTO application_metadata (id, release_version, build_id, updated_at)
        VALUES (1, {_backend.placeholder}, {_backend.placeholder}, {_backend.placeholder})
        ON CONFLICT(id) DO UPDATE SET
            release_version = excluded.release_version,
            build_id = excluded.build_id,
            updated_at = excluded.updated_at
    ''', (release_version, build_id, _utc_now()))


@with_db_connection(commit_on_success=False)
def get_application_metadata(conn):
    row = conn.execute('''
        SELECT release_version, build_id, updated_at
          FROM application_metadata
         WHERE id = 1
    ''').fetchone()
    return dict(row) if row else None


@with_db_connection(commit_on_success=False)
def get_seen_release_versions(conn, user_id):
    rows = conn.execute(f'''
        SELECT release_version
          FROM user_release_change_log_seen
         WHERE user_id = {_backend.placeholder}
    ''', (user_id,)).fetchall()
    return {row['release_version'] for row in rows}


@with_db_connection(write=True)
def mark_release_versions_seen(conn, user_id, release_versions):
    seen_at = _utc_now()
    cursor = conn.executemany(f'''
        INSERT INTO user_release_change_log_seen
            (user_id, release_version, seen_at)
        VALUES ({_backend.placeholder}, {_backend.placeholder}, {_backend.placeholder})
    {_backend.conflict_ignore(("user_id", "release_version"))}''', [(user_id, version, seen_at) for version in release_versions])
    return cursor.rowcount
