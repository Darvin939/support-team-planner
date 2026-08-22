from datetime import date
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

import db
from access_control import CurrentUser, require_editor, require_task_access, require_team_access, require_user
from api_models import (
    HistoryPage, TaskIn, TaskOut, TaskPriorityIn, TaskPsiStatusIn, TaskReorderIn, TasksPage, TaskStatusIn,
)
from db.pagination import page_result
from task_dependency_rules import TaskDependencyCycleError
from task_rules import VALID_TASK_TRANSITIONS, task_is_locked


router = APIRouter()


def _validate_psi_status_change(task_id: int, task, psi_status: str):
    if task and task_is_locked(task):
        return JSONResponse(
            {'error': 'Нельзя изменять ПСИ завершённой или отменённой работы'},
            status_code=400,
        )
    current_psi_status = task['psi_status']
    blocked_with_assignments = (
        (psi_status == 'required' and current_psi_status != 'required')
        or (psi_status == 'not_required' and current_psi_status != 'not_required')
    )
    if blocked_with_assignments and db.task_has_any_assignments(task_id):
        return JSONResponse(
            {'error': 'Перед изменением требования ПСИ удалите назначения работы'},
            status_code=400,
        )
    return None


def _task_json(task):
    return {
        'id': task['id'],
        'name': task['name'],
        'description': task['description'],
        'instruction_url': task['instruction_url'],
        'criticality': task['criticality'],
        'task_status': task['task_status'],
        'psi_status': task['psi_status'],
        'segment_id': task['segment_id'],
        'segment_name': task['segment_name'],
        'completed_at': task['completed_at'],
        'has_active_assignments': bool(task['has_active_assignments']),
        'has_assignments': bool(task['has_assignments']),
    }


@router.get('/api/tasks/{team_id}', dependencies=[Depends(require_user)], response_model=TasksPage)
def get_tasks_api(
    request: Request,
    team_id: int,
    offset: int = 0,
    limit: int = 20,
    search: str = '',
    include_recent_completed: bool = False,
):
    require_team_access(request, team_id)
    search_val = search.strip() or None
    tasks = db.get_tasks_by_team(
        team_id,
        offset=offset,
        limit=limit,
        search=search_val,
        include_recent_completed=include_recent_completed,
    )
    total = db.get_tasks_count_by_team(
        team_id,
        search=search_val,
        include_recent_completed=include_recent_completed,
    )
    return page_result([_task_json(task) for task in tasks], total, 'tasks')


@router.get('/api/task/{task_id}', dependencies=[Depends(require_user)], response_model=TaskOut)
def get_task_api(request: Request, task_id: int):
    task = db.get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail='Работа не найдена')
    require_team_access(request, task['team_id'])
    return _task_json(task)


@router.post('/api/task/{task_id}/restore')
def restore_task_api(
    request: Request, task_id: int, current_user: CurrentUser = Depends(require_editor),
):
    task = db.get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail='Работа не найдена')
    require_team_access(request, task['team_id'])
    try:
        restored = db.restore_task(task_id, changed_by=current_user.id)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if not restored:
        raise HTTPException(status_code=404, detail='Работа не найдена')
    return {'success': True}


@router.get('/api/tasks/{team_id}/archive', dependencies=[Depends(require_user)], response_model=TasksPage)
def get_tasks_archive_api(
    request: Request,
    team_id: int,
    offset: int = 0,
    limit: int = 20,
    search: str = '',
    completed_from: Optional[date] = None,
    completed_to: Optional[date] = None,
):
    require_team_access(request, team_id)
    if offset < 0 or limit < 1 or limit > 100:
        raise HTTPException(status_code=422, detail='Некорректная пагинация')
    if completed_from and completed_to and completed_from > completed_to:
        raise HTTPException(status_code=422, detail='Начало периода позже окончания')
    search_val = search.strip() or None
    date_from = completed_from.isoformat() if completed_from else None
    date_to = completed_to.isoformat() if completed_to else None
    tasks = db.get_archived_tasks_by_team(team_id, offset, limit, search_val, date_from, date_to)
    total = db.get_archived_tasks_count_by_team(team_id, search_val, date_from, date_to)
    return page_result([_task_json(task) for task in tasks], total, 'tasks')


@router.post('/api/task')
def save_task_api(request: Request, data: TaskIn, current_user: CurrentUser = Depends(require_user)):
    name = data.name.strip()
    description = (data.description or '').strip() or None
    instruction_url = (data.instruction_url or '').strip() or None
    if not data.team_id or not name:
        return JSONResponse({'error': 'Team ID and name required'}, status_code=400)
    require_team_access(request, data.team_id)
    if instruction_url:
        parsed_instruction_url = urlparse(instruction_url)
        if (
            len(instruction_url) > 2048
            or parsed_instruction_url.scheme not in ('http', 'https')
            or not parsed_instruction_url.hostname
        ):
            return JSONResponse({'error': 'Некорректная ссылка на инструкцию'}, status_code=400)
    if not data.segment_id or not any(segment['id'] == data.segment_id for segment in db.get_all_segments()):
        return JSONResponse({'error': 'Указан несуществующий сегмент'}, status_code=400)
    psi_status = data.psi_status or 'not_required'
    if data.task_id:
        if not db.task_exists(data.task_id):
            return JSONResponse({'error': 'Задача не найдена'}, status_code=404)
        require_task_access(request, int(data.task_id))
        task = db.get_task_status(data.task_id)
        if task and task_is_locked(task):
            return JSONResponse(
                {'error': 'Нельзя редактировать завершённую или отменённую задачу'},
                status_code=400,
            )
        if data.psi_status is None:
            psi_status = task['psi_status']
        psi_error = _validate_psi_status_change(int(data.task_id), task, psi_status)
        if psi_error:
            return psi_error
    try:
        with db.composite_transaction():
            task_id = int(
                db.create_or_update_task(
                    data.task_id,
                    data.team_id,
                    name,
                    description,
                    data.criticality,
                    psi_status=psi_status,
                    segment_id=data.segment_id,
                    changed_by=current_user.id,
                    instruction_url=instruction_url,
                )
            )
            if data.dependency_ids is not None:
                if data.dependency_ids and db.has_dependency_cycle(task_id, data.dependency_ids):
                    raise TaskDependencyCycleError
                db.set_task_dependencies(task_id, data.dependency_ids)
    except TaskDependencyCycleError:
        return JSONResponse({'error': 'Обнаружена циклическая зависимость'}, status_code=400)
    return {'id': task_id, 'success': True}


@router.delete('/api/task/{task_id}')
def delete_task_api(request: Request, task_id: int, current_user: CurrentUser = Depends(require_user)):
    require_task_access(request, task_id)
    task = db.get_task_status(task_id)
    if task and task_is_locked(task):
        return JSONResponse(
            {'error': 'Нельзя удалить завершённую или отменённую задачу'},
            status_code=400,
        )
    if current_user.role == 'user' and db.task_has_active_assignments(task_id):
        return JSONResponse(
            {
                'error': 'Недостаточно прав: нельзя удалить работу, у которой есть назначения в статусе, отличном от «Новый»'
            },
            status_code=403,
        )
    db.delete_task(task_id, changed_by=current_user.id)
    return {'success': True}


@router.patch('/api/tasks/{task_id}/status')
def update_task_status_api(
    request: Request, task_id: int, data: TaskStatusIn, current_user: CurrentUser = Depends(require_editor),
):
    require_task_access(request, task_id)
    task = db.get_task_status(task_id)
    if not task:
        return JSONResponse({'error': 'Task not found'}, status_code=404)
    current_status = task['task_status']
    allowed = VALID_TASK_TRANSITIONS.get(current_status, set())
    if data.status not in allowed:
        return JSONResponse(
            {'error': f'Недопустимый переход: {current_status} → {data.status}'},
            status_code=400,
        )
    db.update_task_status(task_id, data.status, changed_by=current_user.id)
    return {'success': True}


@router.patch('/api/tasks/{task_id}/psi-status')
def update_task_psi_status_api(
    request: Request, task_id: int, data: TaskPsiStatusIn, current_user: CurrentUser = Depends(require_user),
):
    require_task_access(request, task_id)
    task = db.get_task_status(task_id)
    if not task or task['is_deleted']:
        return JSONResponse({'error': 'Работа не найдена'}, status_code=404)
    if task['psi_status'] not in ('required', 'passed'):
        return JSONResponse(
            {'error': 'Результат ПСИ можно изменить только для работы, которой требуется ПСИ'},
            status_code=400,
        )
    psi_error = _validate_psi_status_change(task_id, task, data.psi_status)
    if psi_error:
        return psi_error
    db.update_task_psi_status(task_id, data.psi_status, changed_by=current_user.id)
    return {'success': True}


@router.patch('/api/tasks/{team_id}/reorder')
def reorder_tasks_api(
    request: Request, team_id: int, data: TaskReorderIn, current_user: CurrentUser = Depends(require_user),
):
    require_team_access(request, team_id)
    if not data.task_ids:
        return JSONResponse({'error': 'task_ids required'}, status_code=400)
    try:
        db.reorder_team_tasks(team_id, data.task_ids, changed_by=current_user.id)
    except ValueError as error:
        return JSONResponse({'error': str(error)}, status_code=400)
    return {'success': True}


@router.patch('/api/task/{task_id}/priority')
def move_task_priority_api(
    request: Request, task_id: int, data: TaskPriorityIn, current_user: CurrentUser = Depends(require_user),
):
    require_task_access(request, task_id)
    try:
        db.move_task_to_edge(
            task_id,
            data.position,
            changed_by=current_user.id,
        )
    except ValueError as error:
        return JSONResponse({'error': str(error)}, status_code=400)
    return {'success': True}


@router.get(
    '/api/task/{task_id}/history', dependencies=[Depends(require_user)],
    response_model=HistoryPage, response_model_exclude_unset=True,
)
def get_task_history_api(request: Request, task_id: int, offset: int = 0, limit: int = 20):
    require_task_access(request, task_id)
    return {
        'history': db.get_task_full_history(task_id, offset=offset, limit=limit),
        'total': db.get_task_full_history_count(task_id),
    }
