from dataclasses import dataclass
from typing import Callable, List, Optional

from fastapi import HTTPException, Request

import db


_ROLE_RANK = {'user': 0, 'editor': 1, 'admin': 2}


@dataclass(frozen=True)
class CurrentUser:
    id: int
    role: str


def _access_policy(kind: str, minimum_role: Optional[str] = None):
    def decorate(dependency: Callable):
        dependency.access_policy = kind
        dependency.minimum_role = minimum_role
        return dependency
    return decorate


@_access_policy('public')
def allow_public() -> None:
    """Явный маркер публичного маршрута для декларации и route-аудита."""


@_access_policy('authenticated')
def get_current_user(request: Request) -> CurrentUser:
    user_id = request.session.get('user_id')
    user = db.user_exists(user_id) if user_id else None
    if not user_id or not user:
        request.session.clear()
        raise HTTPException(status_code=401, detail='Не авторизован')
    current_user = CurrentUser(id=user_id, role=user['role'])
    request.state.current_user = current_user
    return current_user


def _minimum_role_dependency(minimum_role: str):
    minimum_rank = _ROLE_RANK[minimum_role]

    @_access_policy('role', minimum_role)
    def dependency(request: Request) -> CurrentUser:
        current_user = get_current_user(request)
        if _ROLE_RANK.get(current_user.role, 0) < minimum_rank:
            raise HTTPException(status_code=403, detail='Недостаточно прав')
        return current_user

    dependency.__name__ = f'require_{minimum_role}'
    return dependency


require_user = _minimum_role_dependency('user')
require_editor = _minimum_role_dependency('editor')
require_admin = _minimum_role_dependency('admin')


def access_user(request: Request):
    current_user = request.state.current_user
    return current_user.id, current_user.role


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
