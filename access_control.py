from typing import List, Optional

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

import db

_PUBLIC_PATHS = {'/login', '/logout'}
_ROLE_RANK = {'user': 0, 'editor': 1, 'admin': 2}
_ADMIN_ONLY_API_PREFIXES = ('/api/users',)
_EDITOR_API_PREFIXES = ('/api/teams', '/api/freeze-days', '/api/blocks', '/api/block-templates', '/api/segments')


def required_rank(method: str, path: str) -> int:
    if path == '/settings':
        return _ROLE_RANK['editor']
    if method == 'GET':
        return _ROLE_RANK['user']
    if any(path.startswith(prefix) for prefix in _ADMIN_ONLY_API_PREFIXES):
        return _ROLE_RANK['admin']
    if any(path.startswith(prefix) for prefix in _EDITOR_API_PREFIXES):
        return _ROLE_RANK['editor']
    return _ROLE_RANK['user']


async def require_login(request: Request, call_next):
    path = request.url.path
    if path in _PUBLIC_PATHS or path.startswith('/react-assets/'):
        return await call_next(request)
    user_id = request.session.get('user_id')
    user = db.user_exists(user_id) if user_id else None
    if not user_id or not user:
        request.session.clear()
        if path.startswith('/api/'):
            return JSONResponse({'error': 'Не авторизован'}, status_code=401)
        return RedirectResponse(url='/login', status_code=302)
    role = user['role']
    request.state.role = role
    if _ROLE_RANK.get(role, 0) < required_rank(request.method, path):
        if path.startswith('/api/'):
            return JSONResponse({'error': 'Недостаточно прав'}, status_code=403)
        return RedirectResponse(url='/planning', status_code=302)
    return await call_next(request)


def access_user(request: Request):
    return request.session['user_id'], request.state.role


def require_team_access(request: Request, team_id: Optional[int]):
    if team_id is None:
        raise HTTPException(status_code=404, detail='Команда не найдена')
    user_id, role = access_user(request)
    if not db.user_can_access_team(user_id, role, team_id):
        raise HTTPException(status_code=403, detail='Нет доступа к команде')
    return team_id


def require_task_access(request: Request, task_id: int):
    return require_team_access(request, db.get_task_team_id(task_id))


def require_assignment_access(request: Request, assignment_id: int):
    return require_team_access(request, db.get_assignment_team_id(assignment_id))


def require_team_list_access(request: Request, team_ids: List[int]):
    for team_id in team_ids:
        require_team_access(request, team_id)


def effective_team_filter(request: Request):
    user_id, role = access_user(request)
    return db.get_effective_team_ids(user_id, role)
