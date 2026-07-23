from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

import db
from access_control import require_task_access, require_team_access
from api_models import TaskDependencyIn
from query_parsing import parse_int_csv
from task_dependency_rules import TaskDependencyEditError, validate_task_dependency_edit


router = APIRouter()


@router.get('/api/tasks/{team_id}/deps')
def get_team_deps(request: Request, team_id: int, task_ids: Optional[str] = None):
    require_team_access(request, team_id)
    rows = db.get_all_deps_for_team(team_id, task_ids=parse_int_csv(task_ids))
    return [
        {
            'task_id': row['task_id'],
            'dep_id': row['dep_id'],
            'dep_name': row['dep_name'],
            'dep_status': row['dep_status'],
            'dep_is_deleted': bool(row['dep_is_deleted']),
            'dep_criticality': row['dep_criticality'],
            'dep_segment_id': row['dep_segment_id'],
            'dep_segment_name': row['dep_segment_name'],
        }
        for row in rows
    ]


@router.get('/api/tasks/{team_id}/dependency-graph')
def get_team_dependency_graph(request: Request, team_id: int, task_id: Optional[int] = None):
    require_team_access(request, team_id)
    if task_id is not None:
        require_task_access(request, task_id)
    graph = db.get_dependency_graph_for_team(team_id, task_id=task_id)
    return {
        'nodes': [
            {
                'id': node['id'],
                'name': node['name'],
                'description': node['description'],
                'task_status': node['task_status'],
                'criticality': node['criticality'],
                'segment_id': node['segment_id'],
                'segment_name': node['segment_name'],
            }
            for node in graph['nodes']
        ],
        'edges': [
            {'task_id': edge['task_id'], 'dep_id': edge['dep_id']}
            for edge in graph['edges']
        ],
    }


def _validate_or_error(data: TaskDependencyIn):
    try:
        validate_task_dependency_edit(data.task_id, data.depends_on_task_id)
    except TaskDependencyEditError as exc:
        return JSONResponse({'error': str(exc)}, status_code=exc.status_code)
    return None


@router.post('/api/task-dependency')
def add_task_dependency_api(request: Request, data: TaskDependencyIn):
    require_task_access(request, data.task_id)
    require_task_access(request, data.depends_on_task_id)
    error = _validate_or_error(data)
    if error:
        return error
    if db.has_dependency_cycle(data.task_id, [data.depends_on_task_id]):
        return JSONResponse({'error': 'Обнаружена циклическая зависимость'}, status_code=400)
    db.add_task_dependency(data.task_id, data.depends_on_task_id)
    return {'success': True}


@router.delete('/api/task-dependency')
def remove_task_dependency_api(request: Request, data: TaskDependencyIn):
    require_task_access(request, data.task_id)
    require_task_access(request, data.depends_on_task_id)
    error = _validate_or_error(data)
    if error:
        return error
    db.remove_task_dependency(data.task_id, data.depends_on_task_id)
    return {'success': True}


@router.get('/api/tasks/{team_id}/active-list')
def get_active_tasks_list(
    request: Request,
    team_id: int,
    search: str = '',
    limit: int = 50,
    include_ids: Optional[str] = None,
):
    require_team_access(request, team_id)
    rows = db.get_active_tasks_flat(
        team_id,
        search=search.strip() or None,
        limit=limit,
        include_ids=parse_int_csv(include_ids),
    )
    return [
        {
            'id': row['id'],
            'name': row['name'],
            'task_status': row['task_status'],
            'criticality': row['criticality'],
        }
        for row in rows
    ]
