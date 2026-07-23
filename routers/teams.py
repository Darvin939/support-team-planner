from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

import db
from access_control import require_team_access
from api_models import TeamIn


router = APIRouter()


@router.get('/api/teams')
def get_teams_api(
    request: Request,
    offset: Optional[int] = None,
    limit: Optional[int] = None,
    search: Optional[str] = None,
):
    if offset is not None or limit is not None or search is not None:
        safe_offset = max(offset or 0, 0)
        safe_limit = min(max(limit or 20, 1), 100)
        return db.get_teams_page_for_user(
            request.session['user_id'], request.state.role, safe_offset, safe_limit, search,
        )
    return db.get_teams_for_user(request.session['user_id'], request.state.role)


@router.get('/api/teams/{team_id}')
def get_team_api(request: Request, team_id: int):
    require_team_access(request, team_id)
    team = db.get_team_by_id(team_id)
    if not team:
        return JSONResponse({'error': 'Team not found'}, status_code=404)
    templates = db.get_team_allowed_templates(team_id)
    return {
        'id': team['id'],
        'name': team['name'],
        'templates': templates,
        'template_ids': [template['id'] for template in templates],
    }


@router.get('/api/teams/{team_id}/blocks')
def get_team_blocks_api(request: Request, team_id: int, segment_id: Optional[int] = None):
    require_team_access(request, team_id)
    return db.get_blocks_for_team(team_id, segment_id=segment_id)


@router.get('/api/teams/{team_id}/assignees')
def get_team_assignees_api(request: Request, team_id: int):
    require_team_access(request, team_id)
    return db.get_team_assignees(team_id)


@router.post('/api/teams')
def create_team_api(request: Request, data: TeamIn):
    name = (data.name or '').strip()
    if not name:
        return JSONResponse({'error': 'Name required'}, status_code=400)
    try:
        with db.composite_transaction():
            team_id = db.create_team(name, data.template_ids or [])
            db.grant_team_access_if_restricted(request.session['user_id'], request.state.role, team_id)
        return {'id': team_id, 'success': True}
    except db.IntegrityConstraintError as exc:
        return JSONResponse({'error': str(exc)}, status_code=400)


@router.put('/api/teams/{team_id}')
def update_team_api(request: Request, team_id: int, data: TeamIn):
    require_team_access(request, team_id)
    name = (data.name or '').strip()
    if not name:
        return JSONResponse({'error': 'Name required'}, status_code=400)
    try:
        db.update_team(team_id, name, data.template_ids or [])
        return {'success': True}
    except db.IntegrityConstraintError as exc:
        return JSONResponse({'error': str(exc)}, status_code=400)


@router.delete('/api/teams/{team_id}')
def delete_team_api(request: Request, team_id: int):
    require_team_access(request, team_id)
    db.delete_team(team_id)
    return {'success': True}
