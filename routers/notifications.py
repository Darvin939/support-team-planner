from typing import Optional

from fastapi import APIRouter, Depends

import db
import utils
from access_control import CurrentUser, require_user
from api_models import MarkNewTasksSeenIn, NewTaskNotificationsPage


router = APIRouter()
PREVIEW_LIMIT = 30


def _response(current_user, offset, limit, watermark_at=None, watermark_id=None):
    team_ids = db.get_effective_team_ids(current_user.id, current_user.role)
    watermark = None
    if watermark_at is not None and watermark_id is not None:
        watermark = (watermark_at, watermark_id)
    result = db.get_new_task_notifications(
        current_user.id, team_ids=team_ids, offset=offset, limit=limit, watermark=watermark,
    )
    for item in result['items']:
        item['author_name'] = utils.format_user_name(
            item.pop('author_last_name'), item.pop('author_first_name'), item.pop('author_middle_name'),
        ) or None
    return result


@router.get('/api/notifications/new-tasks/preview', response_model=NewTaskNotificationsPage)
def get_new_tasks_preview(current_user: CurrentUser = Depends(require_user)):
    return _response(current_user, 0, PREVIEW_LIMIT)


@router.get('/api/notifications/new-tasks', response_model=NewTaskNotificationsPage)
def get_new_tasks(
    offset: int = 0,
    limit: int = 20,
    watermark_at: Optional[str] = None,
    watermark_id: Optional[int] = None,
    current_user: CurrentUser = Depends(require_user),
):
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    return _response(current_user, offset, limit, watermark_at, watermark_id)


@router.post('/api/notifications/new-tasks/seen')
def mark_new_tasks_seen(data: MarkNewTasksSeenIn, current_user: CurrentUser = Depends(require_user)):
    db.mark_new_tasks_seen(current_user.id, data.watermark.changed_at, data.watermark.history_id)
    return {'success': True}
