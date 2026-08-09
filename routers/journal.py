from typing import Optional

from fastapi import APIRouter, Depends, Request

import db
from access_control import require_team_access, require_user
from api_models import JournalPage


router = APIRouter()


@router.get(
    '/api/journal/{team_id}', dependencies=[Depends(require_user)],
    response_model=JournalPage, response_model_exclude_unset=True,
)
def get_team_history_api(
    request: Request,
    team_id: int,
    offset: int = 0,
    limit: int = 50,
    search: str = '',
    date_from: str = '',
    date_to: str = '',
    changed_by_user_id: Optional[int] = None,
):
    require_team_access(request, team_id)
    search_val = search.strip() or None
    date_from_val = date_from.strip() or None
    date_to_val = date_to.strip() or None
    return {
        'items': db.get_team_history(
            team_id,
            offset=offset,
            limit=limit,
            search=search_val,
            date_from=date_from_val,
            date_to=date_to_val,
            changed_by_user_id=changed_by_user_id,
        ),
        'total': db.get_team_history_count(
            team_id,
            search=search_val,
            date_from=date_from_val,
            date_to=date_to_val,
            changed_by_user_id=changed_by_user_id,
        ),
    }
