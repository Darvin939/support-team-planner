from datetime import date, timedelta
from typing import Optional, List

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

import database as db
import utils

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# === Pydantic-модели для тела запросов ===

class AssignmentIn(BaseModel):
    assignment_id: Optional[int] = None
    task_id: Optional[int] = None
    date: Optional[str] = None
    block: Optional[str] = None
    status: str = "new"
    employee_id: Optional[int] = None
    comment: Optional[str] = None


class TaskIn(BaseModel):
    task_id: Optional[int] = None
    team_id: Optional[int] = None
    name: str = ""
    description: Optional[str] = None
    criticality: str = "medium"


class TeamIn(BaseModel):
    name: str = ""
    blocks: Optional[List[dict]] = None


class EmployeeIn(BaseModel):
    last_name: str = ""
    first_name: str = ""
    middle_name: Optional[str] = None


class FreezeDayIn(BaseModel):
    date: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


# === Роуты ===

@app.get('/', response_class=HTMLResponse)
def index(request: Request):
    """Главная страница со статистикой"""
    teams = db.get_all_teams()
    stats = db.get_all_teams_stats()

    criticality_data = {}
    for item in stats['criticality']:
        criticality_data[item['criticality']] = item['count']

    status_data = {}
    for item in stats['status_today']:
        status_data[item['status']] = item['count']

    all_statuses = ['new', 'planned', 'rollback', 'success']
    status_counts = {}
    for s in all_statuses:
        status_counts[s] = status_data.get(s, 0)

    return templates.TemplateResponse(request, 'index.html', {
        'teams': teams,
        'total_active': stats['total_active'],
        'criticality_data': criticality_data,
        'status_counts': status_counts,
    })


@app.get('/planning/{team_id}', response_class=HTMLResponse)
def planning(request: Request, team_id: int):
    """Страница планирования команды"""
    team = db.get_team_by_id(team_id)
    if not team:
        return RedirectResponse(url='/', status_code=302)

    employees = db.get_all_employees()
    freeze_days = db.get_all_freeze_days()
    team_blocks = db.get_team_blocks(team_id)

    today = date.today()
    start_date = today - timedelta(days=7)
    end_date = today + timedelta(days=30)

    return templates.TemplateResponse(request, 'planning.html', {
        'team': team,
        'employees': employees,
        'freeze_days': freeze_days,
        'team_blocks': team_blocks,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
    })


@app.get('/settings', response_class=HTMLResponse)
def settings_page(request: Request):
    """Страница настроек"""
    teams = db.get_all_teams_with_blocks()
    employees = db.get_all_employees()
    freeze_days = db.get_all_freeze_days()

    return templates.TemplateResponse(request, 'settings.html', {
        'teams': teams,
        'employees': employees,
        'freeze_days': freeze_days,
    })


@app.get('/statistics', response_class=HTMLResponse)
def statistics_page(request: Request):
    """Страница статистики"""
    teams = db.get_all_teams()
    return templates.TemplateResponse(request, 'statistics.html', {
        'teams': teams,
    })


# === API для назначений ===

@app.get('/api/assignments/{team_id}')
def get_assignments_api(team_id: int, start_date: Optional[str] = None, end_date: Optional[str] = None):
    """API для получения назначений команды"""
    if start_date and end_date:
        assignments = db.get_assignments_by_team_in_period(team_id, start_date, end_date)
    else:
        assignments = db.get_assignments_by_team(team_id)

    result = []
    for a in assignments:
        employee_name = utils.format_employee_name(a['employee_last_name'],
                                                   a['employee_first_name'],
                                                   a['employee_middle_name'])
        result.append({
            'id': a['id'],
            'task_id': a['task_id'],
            'date': a['date'],
            'block': a['block'],
            'status': a['status'],
            'employee_id': a['employee_id'],
            'employee_name': employee_name,
            'comment': a['comment']
        })

    return result


@app.post('/api/assignment')
def save_assignment_api(data: AssignmentIn):
    """API для сохранения назначения"""
    block = (data.block or '').strip() or None
    comment = (data.comment or '').strip() or None

    if not data.task_id:
        return JSONResponse({'error': 'Task ID required'}, status_code=400)

    task = db.get_task_by_id(data.task_id)
    if not task:
        return JSONResponse({'error': 'Task not found'}, status_code=404)

    db.create_or_update_assignment(data.assignment_id, data.task_id, data.date, block, data.status, data.employee_id, comment)
    return {'success': True}


@app.delete('/api/assignment/{assignment_id}')
def delete_assignment_api(assignment_id: int):
    """API для удаления назначения"""
    db.delete_assignment(assignment_id)
    return {'success': True}


# === API для задач ===

@app.get('/api/tasks/{team_id}')
def get_tasks_api(team_id: int):
    """API для получения задач команды"""
    tasks = db.get_tasks_by_team(team_id)
    result = []
    for t in tasks:
        result.append({
            'id': t['id'],
            'name': t['name'],
            'description': t['description'],
            'criticality': t['criticality']
        })
    return result


@app.post('/api/task')
def save_task_api(data: TaskIn):
    """API для сохранения задачи"""
    name = data.name.strip()
    description = (data.description or '').strip() or None

    if not data.team_id or not name:
        return JSONResponse({'error': 'Team ID and name required'}, status_code=400)

    task_id = db.create_or_update_task(data.task_id, data.team_id, name, description, data.criticality)
    return {'id': task_id, 'success': True}


@app.delete('/api/task/{task_id}')
def delete_task_api(task_id: int):
    """API для удаления задачи"""
    db.delete_task(task_id)
    return {'success': True}


# === API для команд ===

@app.get('/api/teams')
def get_teams_api():
    """Получить все команды с их блоками"""
    return db.get_all_teams_with_blocks()


@app.get('/api/teams/{team_id}')
def get_team_api(team_id: int):
    """Получить одну команду с блоками"""
    team = db.get_team_by_id(team_id)
    if not team:
        return JSONResponse({'error': 'Team not found'}, status_code=404)
    blocks = db.get_team_blocks(team_id)
    return {'id': team['id'], 'name': team['name'], 'blocks': blocks}


@app.post('/api/teams')
def create_team_api(data: TeamIn):
    """Создать команду"""
    name = (data.name or '').strip()
    blocks = data.blocks or []
    if not name:
        return JSONResponse({'error': 'Name required'}, status_code=400)

    try:
        team_id = db.create_team(name, blocks)
        return {'id': team_id, 'success': True}
    except Exception as e:
        return JSONResponse({'error': str(e)}, status_code=400)


@app.put('/api/teams/{team_id}')
def update_team_api(team_id: int, data: TeamIn):
    """Обновить команду"""
    name = (data.name or '').strip()
    blocks = data.blocks or []
    if not name:
        return JSONResponse({'error': 'Name required'}, status_code=400)

    try:
        db.update_team(team_id, name, blocks)
        return {'success': True}
    except Exception as e:
        return JSONResponse({'error': str(e)}, status_code=400)


@app.delete('/api/teams/{team_id}')
def delete_team_api(team_id: int):
    """Удалить команду (каскадно удаляются задачи и блоки)"""
    db.delete_team(team_id)
    return {'success': True}


# === API для сотрудников ===

@app.get('/api/employees')
def get_employees_api():
    """Получить всех сотрудников"""
    return db.get_all_employees()


@app.post('/api/employees')
def create_employee_api(data: EmployeeIn):
    """Создать сотрудника"""
    last_name = data.last_name.strip()
    first_name = data.first_name.strip()
    middle_name = (data.middle_name or '').strip() or None

    if not last_name or not first_name:
        return JSONResponse({'error': 'Фамилия и имя обязательны'}, status_code=400)

    employee_id = db.create_employee(last_name, first_name, middle_name)
    if employee_id:
        return {'id': employee_id, 'success': True}
    else:
        return JSONResponse({'error': 'Сотрудник с таким ФИО уже существует'}, status_code=400)


@app.put('/api/employees/{employee_id}')
def update_employee_api(employee_id: int, data: EmployeeIn):
    """Обновить сотрудника"""
    last_name = data.last_name.strip()
    first_name = data.first_name.strip()
    middle_name = (data.middle_name or '').strip() or None

    if not last_name or not first_name:
        return JSONResponse({'error': 'Фамилия и имя обязательны'}, status_code=400)

    success = db.update_employee(employee_id, last_name, first_name, middle_name)
    if success:
        return {'success': True}
    else:
        return JSONResponse({'error': 'Сотрудник с таким ФИО уже существует'}, status_code=400)


@app.delete('/api/employees/{employee_id}')
def delete_employee_api(employee_id: int):
    """Удалить сотрудника"""
    db.delete_employee(employee_id)
    return {'success': True}


# === API для дней фризов ===

@app.get('/api/freeze-days')
def get_freeze_days_api():
    """Получить все дни фриза"""
    return db.get_all_freeze_days()


@app.post('/api/freeze-days')
def add_freeze_day_api(data: FreezeDayIn):
    """Добавить день фриза"""
    if data.date:
        success = db.add_freeze_day(data.date)
        return {'success': success}
    elif data.start_date and data.end_date:
        count = db.add_freeze_range(data.start_date, data.end_date)
        return {'success': True, 'count': count}
    else:
        return JSONResponse({'error': 'Date or range required'}, status_code=400)


@app.delete('/api/freeze-days/{date_str:path}')
def delete_freeze_day_api(date_str: str):
    """Удалить день фриза"""
    db.remove_freeze_day(date_str)
    return {'success': True}


# === API для статистики ===

@app.get('/api/statistics/{team_id}')
def get_statistics_api(team_id: int):
    """API для получения статистики по команде"""
    if team_id == 0:
        stats = db.get_all_teams_stats()
    else:
        stats = db.get_team_stats(team_id)

    criticality_data = {}
    for item in stats['criticality']:
        criticality_data[item['criticality']] = item['count']

    status_data = {}
    for item in stats['status_today']:
        status_data[item['status']] = item['count']

    all_statuses = ['new', 'planned', 'rollback', 'success']
    status_counts = {}
    for s in all_statuses:
        status_counts[s] = status_data.get(s, 0)

    return {
        'total_active': stats['total_active'],
        'criticality': criticality_data,
        'status_today': status_counts
    }


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=5000)
