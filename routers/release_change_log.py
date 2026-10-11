from fastapi import APIRouter, Depends, HTTPException

import db
from access_control import CurrentUser, require_user
from api_models import MarkReleaseChangeLogSeenIn
from release_change_log import get_release_change_log, load_release_changelog


router = APIRouter()
MAX_RELEASE_VERSIONS_PER_REQUEST = 100


@router.get('/api/release-change-log')
def get_release_change_log_api(current_user: CurrentUser = Depends(require_user)):
    return get_release_change_log(current_user.id)


@router.post('/api/release-change-log/seen')
def mark_release_change_log_seen(
    data: MarkReleaseChangeLogSeenIn,
    current_user: CurrentUser = Depends(require_user),
):
    versions = list(dict.fromkeys(data.release_versions))
    if len(versions) > MAX_RELEASE_VERSIONS_PER_REQUEST:
        raise HTTPException(status_code=400, detail='Слишком много релизов для одного запроса')
    known_versions = {release['version'] for release in load_release_changelog()}
    unknown_versions = [version for version in versions if version not in known_versions]
    if unknown_versions:
        raise HTTPException(status_code=400, detail='Неизвестная версия релиза')
    marked = db.mark_release_versions_seen(current_user.id, versions)
    return {'success': True, 'marked': marked}
