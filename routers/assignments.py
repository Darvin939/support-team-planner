from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

import db
import utils
from access_control import (
    effective_team_filter,
    require_assignment_access,
    require_task_access,
    require_team_access,
    require_team_list_access,
)
from api_models import AssignmentIn, BulkAssignmentRescheduleIn, BulkAssignmentResult, BulkAssignmentUpsertIn
from query_parsing import parse_int_csv
from task_rules import task_is_locked


router = APIRouter()


@router.get('/api/assignments/{team_id}')
def get_assignments_api(
    request: Request,
    team_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    task_ids: Optional[str] = None,
):
    require_team_access(request, team_id)
    if not start_date or not end_date:
        today = date.today()
        start_date = start_date or (today - timedelta(days=30)).strftime('%Y-%m-%d')
        end_date = end_date or (today + timedelta(days=60)).strftime('%Y-%m-%d')
    assignments = db.get_assignments_by_team_in_period(
        team_id, start_date, end_date, task_ids=parse_int_csv(task_ids),
    )
    return [
        {
            'id': assignment['id'],
            'task_id': assignment['task_id'],
            'date': assignment['date'],
            'block': assignment['block'],
            'status': assignment['status'],
            'user_id': assignment['user_id'],
            'user_name': utils.format_user_name(
                assignment['user_last_name'], assignment['user_first_name'], assignment['user_middle_name'],
            ),
            'comment': assignment['comment'],
            'time_spent': assignment['time_spent'],
        }
        for assignment in assignments
    ]


def _save_assignment(request: Request, data: AssignmentIn):
    block = (data.block or '').strip() or None
    comment = (data.comment or '').strip() or None
    time_spent = (data.time_spent or '').strip() or None
    if not data.task_id:
        raise HTTPException(status_code=400, detail='Task ID required')
    if not db.task_exists(data.task_id):
        raise HTTPException(status_code=404, detail='Task not found')
    team_id = require_task_access(request, data.task_id)
    if data.assignment_id:
        require_assignment_access(request, data.assignment_id)
    if data.user_id is not None and not db.user_is_eligible_assignee(data.user_id, team_id):
        raise HTTPException(status_code=400, detail='Пользователь недоступен для назначения в этой команде')
    task = db.get_task_status(data.task_id)
    if task and task_is_locked(task):
        raise HTTPException(status_code=400, detail='Нельзя изменять назначения завершённой или отменённой задачи')
    if request.state.role == 'user':
        if data.status != 'new':
            raise HTTPException(status_code=403, detail='Недостаточно прав: можно создавать и изменять назначения только со статусом «Новый»')
        if data.assignment_id:
            existing = db.get_task_status_by_assignment(data.assignment_id)
            if existing and existing['assignment_status'] != 'new':
                raise HTTPException(status_code=403, detail='Недостаточно прав: нельзя изменять назначение в статусе, отличном от «Новый»')
    db.create_or_update_assignment(
        data.assignment_id, data.task_id, data.date, block, data.status, data.user_id,
        comment, time_spent, changed_by=request.session.get('user_id'),
    )


@router.post('/api/assignment')
def save_assignment_api(request: Request, data: AssignmentIn):
    _save_assignment(request, data)
    return {'success': True}


@router.post('/api/assignments/bulk', response_model=BulkAssignmentResult)
def bulk_save_assignments_api(request: Request, data: BulkAssignmentUpsertIn):
    if not data.assignments:
        raise HTTPException(status_code=400, detail='Не выбраны назначения для сохранения')
    if len(data.assignments) > 200:
        raise HTTPException(status_code=400, detail='За один раз можно сохранить не более 200 назначений')
    with db.composite_transaction():
        for assignment in data.assignments:
            _save_assignment(request, assignment)
    return {'success': True, 'saved': len(data.assignments)}


@router.post('/api/assignments/bulk-reschedule')
def bulk_reschedule_assignments_api(request: Request, data: BulkAssignmentRescheduleIn):
    for move in data.moves:
        require_assignment_access(request, move.assignment_id)
    try:
        moved = db.bulk_reschedule_assignments(
            [move.model_dump() for move in data.moves],
            role=request.state.role,
            changed_by=request.session.get('user_id'),
        )
    except db.BulkAssignmentRescheduleError as exc:
        return JSONResponse({'error': str(exc)}, status_code=exc.status_code)
    except Exception:
        return JSONResponse({'error': 'Не удалось перенести назначения'}, status_code=500)
    return {'success': True, 'moved': moved}


@router.delete('/api/assignment/{assignment_id}')
def delete_assignment_api(request: Request, assignment_id: int):
    require_assignment_access(request, assignment_id)
    task = db.get_task_status_by_assignment(assignment_id)
    if task and task_is_locked(task):
        return JSONResponse({'error': 'Нельзя изменять назначения завершённой или отменённой задачи'}, status_code=400)
    if request.state.role == 'user' and task and task['assignment_status'] != 'new':
        return JSONResponse(
            {'error': 'Недостаточно прав: нельзя удалить назначение в статусе, отличном от «Новый»'},
            status_code=403,
        )
    db.delete_assignment(assignment_id, changed_by=request.session.get('user_id'))
    return {'success': True}


@router.get('/api/assignment/{assignment_id}/history')
def get_assignment_history_api(request: Request, assignment_id: int, offset: int = 0, limit: int = 20):
    require_assignment_access(request, assignment_id)
    return {
        'history': db.get_assignment_history(assignment_id, offset=offset, limit=limit),
        'total': db.get_assignment_history_count(assignment_id),
    }


@router.get('/api/active-assignments/{team_id}')
def get_active_assignments_api(
    request: Request,
    team_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    team_ids: Optional[str] = None,
    offset: int = 0,
    limit: Optional[int] = None,
):
    today_str = date.today().strftime('%Y-%m-%d')
    start_date = start_date or today_str
    end_date = end_date or today_str
    parsed_team_ids = parse_int_csv(team_ids)
    if parsed_team_ids:
        require_team_list_access(request, parsed_team_ids)
    elif team_id:
        require_team_access(request, team_id)
    else:
        parsed_team_ids = effective_team_filter(request)
    assignments = db.get_active_assignments_in_period(
        team_id, start_date, end_date, team_ids=parsed_team_ids, offset=offset, limit=limit,
    )
    stats = db.get_active_assignments_stats(team_id, start_date, end_date, team_ids=parsed_team_ids)
    items = []
    for assignment in assignments:
        items.append({
            'id': assignment['id'],
            'task_id': assignment['task_id'],
            'task_name': assignment['task_name'],
            'criticality': assignment['criticality'],
            'date': assignment['date'],
            'block': assignment['block'],
            'status': assignment['status'],
            'user_name': utils.format_user_name(
                assignment['user_last_name'], assignment['user_first_name'], assignment['user_middle_name'],
            ),
            'comment': assignment['comment'],
            'team_id': assignment['team_id'],
            'team_name': assignment['team_name'],
        })
    return {
        'items': items,
        'total': stats['total'],
        'stats': {
            'status': {'new': stats['status_new'], 'planned': stats['status_planned']},
            'criticality': {'high': stats['crit_high'], 'medium': stats['crit_medium'], 'low': stats['crit_low']},
        },
    }
