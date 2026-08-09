from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

import auth
import db
from access_control import CurrentUser, require_admin, require_user
from api_models import UserIn


router = APIRouter()
_VALID_ROLES = {'admin', 'editor', 'user'}


@router.get('/api/users', dependencies=[Depends(require_user)])
def get_users_api(offset: Optional[int] = None, limit: Optional[int] = None, search: Optional[str] = None):
    if offset is None and limit is None and search is None:
        return db.get_all_users()
    safe_offset = max(offset or 0, 0)
    safe_limit = min(max(limit or 20, 1), 100)
    return db.get_users_page(safe_offset, safe_limit, search)


@router.post('/api/users', dependencies=[Depends(require_admin)])
def create_user_api(data: UserIn):
    last_name = data.last_name.strip() or None
    first_name = data.first_name.strip()
    middle_name = (data.middle_name or '').strip() or None
    password_hash = auth.hash_password(data.password) if (data.password or '').strip() else None
    login = (data.login or '').strip() or None
    if not first_name:
        return JSONResponse({'error': 'Имя обязательно'}, status_code=400)
    if data.role not in _VALID_ROLES:
        return JSONResponse({'error': 'Недопустимая роль'}, status_code=400)
    try:
        user_id = db.create_user(
            last_name, first_name, middle_name, password_hash, data.role, login, data.is_assignee, data.team_ids,
        )
        return {'id': user_id, 'success': True}
    except db.DuplicateEntityError as exc:
        return JSONResponse({'error': str(exc)}, status_code=400)


@router.put('/api/users/{user_id}', dependencies=[Depends(require_admin)])
def update_user_api(user_id: int, data: UserIn):
    last_name = data.last_name.strip() or None
    first_name = data.first_name.strip()
    middle_name = (data.middle_name or '').strip() or None
    password_hash = auth.hash_password(data.password) if (data.password or '').strip() else None
    login = (data.login or '').strip() or None
    if not first_name and not db.is_bootstrap_admin_id(user_id):
        return JSONResponse({'error': 'Имя обязательно'}, status_code=400)
    if data.role not in _VALID_ROLES:
        return JSONResponse({'error': 'Недопустимая роль'}, status_code=400)
    try:
        db.update_user(
            user_id, last_name, first_name, middle_name, password_hash, data.role, login,
            data.is_assignee, data.team_ids,
        )
        return {'success': True}
    except db.DuplicateEntityError as exc:
        return JSONResponse({'error': str(exc)}, status_code=400)
    except db.EntityNotFoundError as exc:
        return JSONResponse({'error': str(exc)}, status_code=404)


@router.delete('/api/users/{user_id}')
def delete_user_api(user_id: int, current_user: CurrentUser = Depends(require_admin)):
    try:
        db.delete_user(user_id, changed_by=current_user.id)
        return {'success': True}
    except ValueError as exc:
        return JSONResponse({'error': str(exc)}, status_code=400)
