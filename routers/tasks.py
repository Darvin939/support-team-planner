from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

import db
from access_control import require_task_access, require_team_access
from api_models import TaskIn, TaskPriorityIn, TaskReorderIn, TaskStatusIn
from db.pagination import page_result
from task_dependency_rules import TaskDependencyCycleError
from task_rules import VALID_TASK_TRANSITIONS, task_is_locked


router = APIRouter()


def _task_json(task):
    return {
        'id': task['id'],
        'name': task['name'],
        'description': task['description'],
        'criticality': task['criticality'],
        'task_status': task['task_status'],
        'segment_id': task['segment_id'],
        'segment_name': task['segment_name'],
        'completed_at': task['completed_at'],
        'has_active_assignments': bool(task['has_active_assignments']),
    }


@router.get('/api/tasks/{team_id}')
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


@router.get('/api/task/{task_id}')
def get_task_api(request: Request, task_id: int):
    task = db.get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail='Работа не найдена')
    require_team_access(request, task['team_id'])
    return _task_json(task)


@router.post('/api/task/{task_id}/restore')
def restore_task_api(request: Request, task_id: int):
    task = db.get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail='Работа не найдена')
    require_team_access(request, task['team_id'])
    if request.state.role not in ('editor', 'admin'):
        raise HTTPException(status_code=403, detail='Недостаточно прав для восстановления работы')
    try:
        restored = db.restore_task(task_id, changed_by=request.session.get('user_id'))
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if not restored:
        raise HTTPException(status_code=404, detail='Работа не найдена')
    return {'success': True}


@router.get('/api/tasks/{team_id}/archive')
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
def save_task_api(request: Request, data: TaskIn):
    name = data.name.strip()
    description = (data.description or '').strip() or None
    if not data.team_id or not name:
        return JSONResponse({'error': 'Team ID and name required'}, status_code=400)
    require_team_access(request, data.team_id)
    if data.criticality not in ('low', 'medium', 'high'):
        return JSONResponse({'error': 'criticality must be low, medium or high'}, status_code=400)
    if not data.segment_id or not any(segment['id'] == data.segment_id for segment in db.get_all_segments()):
        return JSONResponse({'error': 'Указан несуществующий сегмент'}, status_code=400)
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
    try:
        with db.composite_transaction():
            task_id = int(
                db.create_or_update_task(
                    data.task_id,
                    data.team_id,
                    name,
                    description,
                    data.criticality,
                    segment_id=data.segment_id,
                    changed_by=request.session.get('user_id'),
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
def delete_task_api(request: Request, task_id: int):
    require_task_access(request, task_id)
    task = db.get_task_status(task_id)
    if task and task_is_locked(task):
        return JSONResponse(
            {'error': 'Нельзя удалить завершённую или отменённую задачу'},
            status_code=400,
        )
    if request.state.role == 'user' and db.task_has_active_assignments(task_id):
        return JSONResponse(
            {
                'error': 'Недостаточно прав: нельзя удалить работу, у которой есть назначения в статусе, отличном от «Новый»'
            },
            status_code=403,
        )
    db.delete_task(task_id, changed_by=request.session.get('user_id'))
    return {'success': True}


@router.patch('/api/tasks/{task_id}/status')
def update_task_status_api(request: Request, task_id: int, data: TaskStatusIn):
    require_task_access(request, task_id)
    task = db.get_task_status(task_id)
    if not task:
        return JSONResponse({'error': 'Task not found'}, status_code=404)
    if request.state.role == 'user':
        return JSONResponse(
            {'error': 'Недостаточно прав для изменения статуса задачи'},
            status_code=403,
        )
    current_status = task['task_status']
    allowed = VALID_TASK_TRANSITIONS.get(current_status, set())
    if data.status not in allowed:
        return JSONResponse(
            {'error': f'Недопустимый переход: {current_status} → {data.status}'},
            status_code=400,
        )
    db.update_task_status(task_id, data.status, changed_by=request.session.get('user_id'))
    return {'success': True}


@router.patch('/api/tasks/{team_id}/reorder')
def reorder_tasks_api(request: Request, team_id: int, data: TaskReorderIn):
    require_team_access(request, team_id)
    if not data.task_ids:
        return JSONResponse({'error': 'task_ids required'}, status_code=400)
    try:
        db.reorder_team_tasks(team_id, data.task_ids, changed_by=request.session.get('user_id'))
    except ValueError as error:
        return JSONResponse({'error': str(error)}, status_code=400)
    return {'success': True}


@router.patch('/api/task/{task_id}/priority')
def move_task_priority_api(request: Request, task_id: int, data: TaskPriorityIn):
    require_task_access(request, task_id)
    if data.position not in ('start', 'end'):
        return JSONResponse({'error': 'position must be start or end'}, status_code=400)
    try:
        db.move_task_to_edge(
            task_id,
            data.position,
            changed_by=request.session.get('user_id'),
        )
    except ValueError as error:
        return JSONResponse({'error': str(error)}, status_code=400)
    return {'success': True}


@router.get('/api/task/{task_id}/history')
def get_task_history_api(request: Request, task_id: int, offset: int = 0, limit: int = 20):
    require_task_access(request, task_id)
    return {
        'history': db.get_task_full_history(task_id, offset=offset, limit=limit),
        'total': db.get_task_full_history_count(task_id),
    }
