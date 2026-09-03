from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

import db
import utils
from access_control import (
    CurrentUser,
    effective_team_filter,
    require_assignment_access,
    require_task_access,
    require_team_access,
    require_team_list_access,
    require_user,
)
from api_models import (
    ActiveAssignmentsPage,
    AssignmentIn,
    AssignmentOut,
    BulkAssignmentDeleteIn,
    BulkAssignmentDeleteResult,
    BulkAssignmentRescheduleIn,
    BulkAssignmentResult,
    BulkAssignmentUpsertIn,
    HistoryPage,
)
from query_parsing import parse_int_csv
from task_rules import task_is_locked
from task_rules import VALID_TASK_TRANSITIONS


router = APIRouter()


def _validate_user_assignment_status(current_user: CurrentUser, data: AssignmentIn):
    if current_user.role != 'user':
        return
    if not data.assignment_id:
        if data.status != 'new':
            raise HTTPException(
                status_code=403,
                detail='Недостаточно прав: пользователь может создать назначение только со статусом «Новый»',
            )
        return

    existing = db.get_task_status_by_assignment(data.assignment_id)
    if existing and data.status != existing['assignment_status']:
        raise HTTPException(
            status_code=403,
            detail='Недостаточно прав: пользователь не может менять статус назначения',
        )


@router.get('/api/assignments/{team_id}', dependencies=[Depends(require_user)], response_model=list[AssignmentOut])
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


@router.get(
    '/api/assignments/{team_id}/task/{task_id}/successful-history',
    dependencies=[Depends(require_user)],
    response_model=list[AssignmentOut],
)
def get_successful_assignment_history_api(request: Request, team_id: int, task_id: int):
    require_team_access(request, team_id)
    task_team_id = require_task_access(request, task_id)
    if task_team_id != team_id:
        raise HTTPException(status_code=404, detail='Работа не найдена в указанной команде')

    assignments = db.get_successful_assignments_by_task(task_id)
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


def _save_assignment(request: Request, current_user: CurrentUser, data: AssignmentIn):
    block = (data.block or '').strip() or None
    comment = (data.comment or '').strip() or None
    time_spent = (data.time_spent or '').strip() or None
    if not data.task_id:
        raise HTTPException(status_code=400, detail='Task ID required')
    if not db.task_exists(data.task_id):
        raise HTTPException(status_code=404, detail='Task not found')
    team_id = require_task_access(request, data.task_id)
    previous_status = None
    existing_assignment = None
    if data.assignment_id:
        require_assignment_access(request, data.assignment_id)
        existing_status = db.get_task_status_by_assignment(data.assignment_id)
        existing_assignment = db.get_assignment_by_id(data.assignment_id)
        if existing_status:
            previous_status = existing_status['assignment_status']
    if data.user_id is not None and not db.user_is_eligible_assignee(data.user_id, team_id):
        raise HTTPException(status_code=400, detail='Пользователь недоступен для назначения в этой команде')
    task = db.get_task_status(data.task_id)
    if task and task_is_locked(task):
        raise HTTPException(status_code=400, detail='Нельзя изменять назначения завершённой или отменённой задачи')
    if task and task['psi_status'] == 'required':
        planning_changed = not existing_assignment or any((
            existing_assignment['task_id'] != data.task_id,
            existing_assignment['date'] != data.date,
            existing_assignment['block'] != block,
            existing_assignment['user_id'] != data.user_id,
        ))
        if planning_changed:
            raise HTTPException(status_code=400, detail='Нельзя планировать назначения: требуется пройти ПСИ')
    _validate_user_assignment_status(current_user, data)
    db.create_or_update_assignment(
        data.assignment_id, data.task_id, data.date, block, data.status, data.user_id,
        comment, time_spent, changed_by=current_user.id,
    )
    if data.status == 'success' and previous_status != 'success':
        suggestion = db.get_task_completion_suggestion(data.task_id)
        if suggestion and 'done' in VALID_TASK_TRANSITIONS.get(suggestion['task_status'], set()):
            return {
                'task_id': suggestion['task_id'],
                'task_name': suggestion['task_name'],
            }
    return None


@router.post('/api/assignment')
def save_assignment_api(request: Request, data: AssignmentIn, current_user: CurrentUser = Depends(require_user)):
    suggestion = _save_assignment(request, current_user, data)
    response = {'success': True}
    if suggestion:
        response['task_completion_suggestion'] = suggestion
    return response


@router.post('/api/assignments/bulk', response_model=BulkAssignmentResult)
def bulk_save_assignments_api(
    request: Request, data: BulkAssignmentUpsertIn, current_user: CurrentUser = Depends(require_user),
):
    if not data.assignments:
        raise HTTPException(status_code=400, detail='Не выбраны назначения для сохранения')
    if len(data.assignments) > 200:
        raise HTTPException(status_code=400, detail='За один раз можно сохранить не более 200 назначений')
    task_ids = {assignment.task_id for assignment in data.assignments}
    if data.template_id is not None:
        if len(task_ids) != 1 or None in task_ids:
            raise HTTPException(status_code=400, detail='Шаблон можно сохранить только для назначений одной работы')
        if not db.get_template_by_id(data.template_id):
            raise HTTPException(status_code=400, detail='Шаблон не найден')
    with db.composite_transaction():
        for assignment in data.assignments:
            _save_assignment(request, current_user, assignment)
        if data.template_id is not None:
            db.set_task_completion_template(next(iter(task_ids)), data.template_id)
    return {'success': True, 'saved': len(data.assignments)}


@router.post('/api/assignments/bulk-reschedule')
def bulk_reschedule_assignments_api(
    request: Request, data: BulkAssignmentRescheduleIn, current_user: CurrentUser = Depends(require_user),
):
    for move in data.moves:
        require_assignment_access(request, move.assignment_id)
    try:
        moved = db.bulk_reschedule_assignments(
            [move.model_dump() for move in data.moves],
            role=current_user.role,
            changed_by=current_user.id,
        )
    except db.BulkAssignmentRescheduleError as exc:
        return JSONResponse({'error': str(exc)}, status_code=exc.status_code)
    except Exception:
        return JSONResponse({'error': 'Не удалось перенести назначения'}, status_code=500)
    return {'success': True, 'moved': moved}


def _validate_assignment_delete(request: Request, current_user: CurrentUser, assignment_id: int):
    require_assignment_access(request, assignment_id)
    task = db.get_task_status_by_assignment(assignment_id)
    if not task:
        raise HTTPException(status_code=404, detail='Назначение не найдено')
    if task and task_is_locked(task):
        raise HTTPException(status_code=400, detail='Нельзя изменять назначения завершённой или отменённой задачи')
    if current_user.role == 'user' and task and task['assignment_status'] != 'new':
        raise HTTPException(
            status_code=403,
            detail='Недостаточно прав: нельзя удалить назначение в статусе, отличном от «Новый»',
        )


@router.delete('/api/assignment/{assignment_id}')
def delete_assignment_api(
    request: Request, assignment_id: int, current_user: CurrentUser = Depends(require_user),
):
    _validate_assignment_delete(request, current_user, assignment_id)
    db.delete_assignment(assignment_id, changed_by=current_user.id)
    return {'success': True}


@router.post('/api/assignments/bulk-delete', response_model=BulkAssignmentDeleteResult)
def bulk_delete_assignments_api(
    request: Request, data: BulkAssignmentDeleteIn, current_user: CurrentUser = Depends(require_user),
):
    assignment_ids = data.assignment_ids
    if not assignment_ids:
        raise HTTPException(status_code=400, detail='Не выбраны назначения для удаления')
    if len(assignment_ids) > 200:
        raise HTTPException(status_code=400, detail='За один раз можно удалить не более 200 назначений')
    if len(set(assignment_ids)) != len(assignment_ids):
        raise HTTPException(status_code=400, detail='Список содержит повторяющиеся назначения')

    for assignment_id in assignment_ids:
        _validate_assignment_delete(request, current_user, assignment_id)
    with db.composite_transaction():
        for assignment_id in assignment_ids:
            db.delete_assignment(assignment_id, changed_by=current_user.id)
    return {'success': True, 'deleted': len(assignment_ids)}


@router.get(
    '/api/assignment/{assignment_id}/history', dependencies=[Depends(require_user)],
    response_model=HistoryPage, response_model_exclude_unset=True,
)
def get_assignment_history_api(request: Request, assignment_id: int, offset: int = 0, limit: int = 20):
    require_assignment_access(request, assignment_id)
    return {
        'history': db.get_assignment_history(assignment_id, offset=offset, limit=limit),
        'total': db.get_assignment_history_count(assignment_id),
    }


@router.get('/api/active-assignments/{team_id}', dependencies=[Depends(require_user)], response_model=ActiveAssignmentsPage)
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
