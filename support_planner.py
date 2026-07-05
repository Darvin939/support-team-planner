import os
from datetime import date, timedelta
from typing import Optional, List, Union

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

import auth
import db
import utils

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

# React (Vite/antd) migration, page by page — see plan doc. `frontend/dist` only exists after
# `npm run build`; the mount is skipped in dev if it hasn't been built yet, matching the current
# no-build-step-required philosophy for anyone just running the Python app without touching the
# frontend at all.
_REACT_DIST = os.path.join(os.path.dirname(__file__), 'frontend', 'dist')
if os.path.isdir(os.path.join(_REACT_DIST, 'assets')):
    app.mount("/react-assets/assets", StaticFiles(directory=os.path.join(_REACT_DIST, 'assets')), name="react-assets")


def _serve_react_index() -> str:
    """Отдать собранный React SPA (frontend/dist/index.html) для уже перенесённых страниц."""
    with open(os.path.join(_REACT_DIST, 'index.html'), encoding='utf-8') as f:
        return f.read()

_SESSION_SECRET_KEY = os.environ.get('SESSION_SECRET_KEY')
if not _SESSION_SECRET_KEY:
    _SESSION_SECRET_KEY = 'dev-insecure-secret-change-me'
    print('WARNING: SESSION_SECRET_KEY не задан, используется небезопасный ключ по умолчанию '
          '(сессии не переживут смену ключа; задайте переменную окружения для продакшена)')

_PUBLIC_PATHS = {'/login', '/logout', '/api/login-employees'}

# Ранги ролей: user < editor < admin — каждая следующая роль включает права предыдущей.
_ROLE_RANK = {'user': 0, 'editor': 1, 'admin': 2}

# Мутирующие эндпоинты, требующие роль не ниже admin (управление учётными записями — единственное,
# что запрещено editor'у). GET /api/employees остаётся доступен всем ролям (нужен для выпадающих
# списков назначения исполнителя в планировщике).
_ADMIN_ONLY_API_PREFIXES = ('/api/employees',)

# Мутирующие эндпоинты настроек, требующие роль не ниже editor (всё, кроме учётных записей).
_EDITOR_API_PREFIXES = ('/api/teams', '/api/freeze-days', '/api/blocks', '/api/block-templates')


def _required_rank(method: str, path: str) -> int:
    """Минимальный ранг роли, необходимый для данного метода+пути. Страница /settings целиком
    закрыта для user; GET-запросы везде остаются доступны любой роли (нужны планировщику)."""
    if path == '/settings':
        return _ROLE_RANK['editor']
    if method == 'GET':
        return _ROLE_RANK['user']
    if any(path.startswith(p) for p in _ADMIN_ONLY_API_PREFIXES):
        return _ROLE_RANK['admin']
    if any(path.startswith(p) for p in _EDITOR_API_PREFIXES):
        return _ROLE_RANK['editor']
    return _ROLE_RANK['user']


# Starlette's add_middleware() prepends to the middleware stack, so the middleware added
# LAST runs FIRST. require_login must run only after SessionMiddleware has populated
# request.session, so it's registered (via @app.middleware) before add_middleware(SessionMiddleware)
# below is called.
@app.middleware('http')
async def require_login(request: Request, call_next):
    path = request.url.path
    if path in _PUBLIC_PATHS or path.startswith('/static/') or path.startswith('/react-assets/'):
        return await call_next(request)
    employee_id = request.session.get('employee_id')
    emp = db.employee_exists(employee_id) if employee_id else None
    if not employee_id or not emp:
        # Сессия может ссылаться на сотрудника, которого больше нет (удалили, БД пересоздали) —
        # обращаемся с этим так же, как с отсутствием сессии, а не пропускаем дальше: иначе запись
        # в task_history/assignment_history упадёт с FOREIGN KEY constraint failed при первом же
        # создании/изменении задачи или назначения.
        request.session.clear()
        if path.startswith('/api/'):
            return JSONResponse({'error': 'Не авторизован'}, status_code=401)
        return RedirectResponse(url='/login', status_code=302)

    # Роль читается из БД на каждый запрос (не из сессии), чтобы смена роли применялась
    # немедленно, без необходимости перелогина.
    role = emp['role']
    request.state.role = role
    if _ROLE_RANK.get(role, 0) < _required_rank(request.method, path):
        if path.startswith('/api/'):
            return JSONResponse({'error': 'Недостаточно прав'}, status_code=403)
        return RedirectResponse(url='/planning', status_code=302)

    return await call_next(request)


app.add_middleware(
    SessionMiddleware,
    secret_key=_SESSION_SECRET_KEY,
    session_cookie='sp_session',
    max_age=60 * 60 * 24 * 30,
    same_site='lax',
)


# === Pydantic-модели для тела запросов ===

class AssignmentIn(BaseModel):
    assignment_id: Optional[int] = None
    task_id: Optional[int] = None
    date: Optional[str] = None
    block: Optional[str] = None
    status: str = "new"
    employee_id: Optional[int] = None
    comment: Optional[str] = None
    is_psi: bool = False
    time_spent: Optional[str] = None


class TaskIn(BaseModel):
    task_id: Optional[Union[int, str]] = None
    team_id: Optional[int] = None
    name: str = ""
    description: Optional[str] = None
    criticality: str = "medium"
    dependency_ids: Optional[List[int]] = None


class TeamIn(BaseModel):
    name: str = ""
    template_ids: Optional[List[int]] = None


class BlockIn(BaseModel):
    name: str = ""


class TemplateEntryIn(BaseModel):
    block_id: int
    shift_days: int = 0


class BlockTemplateIn(BaseModel):
    name: str = ""
    entries: Optional[List[TemplateEntryIn]] = None


class EmployeeIn(BaseModel):
    last_name: str = ""
    first_name: str = ""
    middle_name: Optional[str] = None
    password: Optional[str] = None
    role: str = "user"


class FreezeDayIn(BaseModel):
    date: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class FreezeDayMonthIn(BaseModel):
    year: int
    month: int
    days: List[int] = []


class TaskStatusIn(BaseModel):
    status: str


VALID_TASK_TRANSITIONS = {
    'new': {'ready', 'in_progress', 'cancelled'},
    'ready': {'in_progress', 'cancelled'},
    'in_progress': {'done', 'cancelled'},
}


# === Роуты ===

@app.get('/', response_class=HTMLResponse)
def root():
    return RedirectResponse(url='/planning', status_code=302)


@app.get('/login', response_class=HTMLResponse)
def login_page():
    """Страница входа (React)"""
    return _serve_react_index()


@app.get('/api/login-employees')
def login_employees():
    """Публичный (без авторизации) список сотрудников для выпадающего списка на странице входа —
    те же поля, что показывались в незалогиненном login.html и раньше."""
    employees = db.get_all_employees()
    return [{'id': e['id'], 'last_name': e['last_name'], 'first_name': e['first_name'],
              'middle_name': e['middle_name']} for e in employees]


@app.post('/login')
def login_submit(request: Request, employee_id: str = Form(...), password: str = Form(...)):
    """Обработка входа по сотруднику и паролю"""
    try:
        emp_id = int(employee_id)
    except (TypeError, ValueError):
        emp_id = None

    auth_row = db.get_employee_auth(emp_id) if emp_id else None
    if not auth_row or not auth.verify_password(password, auth_row['password_hash']):
        return JSONResponse({'error': 'Неверный сотрудник или пароль'}, status_code=401)

    request.session['employee_id'] = emp_id
    request.session['role'] = auth_row['role']
    return {'success': True}


@app.post('/logout')
def logout(request: Request):
    """Выход из системы"""
    request.session.clear()
    return RedirectResponse(url='/login', status_code=302)


@app.get('/api/me')
def get_me(request: Request):
    """Личность и роль текущего пользователя — то же самое, что require_login уже вычисляет
    в request.state.role, но в виде JSON для клиентских (React) страниц, у которых нет доступа
    к current_role из Jinja-контекста."""
    emp = db.get_employee(request.session['employee_id'])
    return {
        'employee_id': emp['id'],
        'role': emp['role'],
        'last_name': emp['last_name'],
        'first_name': emp['first_name'],
        'middle_name': emp['middle_name'],
    }


@app.get('/planning', response_class=HTMLResponse)
def planning_select():
    """Страница планирования — выбор команды (React)"""
    return _serve_react_index()


@app.get('/planning/{team_id}', response_class=HTMLResponse)
def planning(team_id: int):
    """Страница планирования команды (React) — валидность team_id проверяется на клиенте"""
    return _serve_react_index()


@app.get('/settings', response_class=HTMLResponse)
def settings_page():
    """Страница настроек (React)"""
    return _serve_react_index()


@app.get('/statistics', response_class=HTMLResponse)
def statistics_page():
    """Страница статистики (React)"""
    return _serve_react_index()


@app.get('/journal', response_class=HTMLResponse)
def journal_select():
    """Страница журнала изменений — выбор команды (React)"""
    return _serve_react_index()


@app.get('/journal/{team_id}', response_class=HTMLResponse)
def journal_page(team_id: int):
    """Журнал изменений команды (React) — валидность team_id проверяется на клиенте"""
    return _serve_react_index()


# === API для назначений ===

@app.get('/api/assignments/{team_id}')
def get_assignments_api(team_id: int, start_date: Optional[str] = None, end_date: Optional[str] = None,
                        task_ids: Optional[str] = None):
    """API для получения назначений команды"""
    if not start_date or not end_date:
        today = date.today()
        start_date = start_date or (today - timedelta(days=30)).strftime('%Y-%m-%d')
        end_date = end_date or (today + timedelta(days=60)).strftime('%Y-%m-%d')
    parsed_task_ids = [int(x) for x in task_ids.split(',') if x.strip()] if task_ids else None
    assignments = db.get_assignments_by_team_in_period(team_id, start_date, end_date, task_ids=parsed_task_ids)

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
            'comment': a['comment'],
            'is_psi': bool(a['is_psi']),
            'time_spent': a['time_spent']
        })

    return result


@app.post('/api/assignment')
def save_assignment_api(request: Request, data: AssignmentIn):
    """API для сохранения назначения"""
    block = (data.block or '').strip() or None
    comment = (data.comment or '').strip() or None
    time_spent = (data.time_spent or '').strip() or None

    if not data.task_id:
        return JSONResponse({'error': 'Task ID required'}, status_code=400)

    if not db.task_exists(data.task_id):
        return JSONResponse({'error': 'Task not found'}, status_code=404)

    task = db.get_task_status(data.task_id)
    if task and (task['task_status'] in ('done', 'cancelled') or task['is_deleted']):
        return JSONResponse({'error': 'Нельзя изменять назначения завершённой или отменённой задачи'}, status_code=400)

    changed_by = request.session.get('employee_id')
    db.create_or_update_assignment(data.assignment_id, data.task_id, data.date, block, data.status, data.employee_id,
                                   comment, 1 if data.is_psi else 0, time_spent, changed_by=changed_by)
    if data.status == 'planned':
        db.maybe_advance_task_to_in_progress(data.task_id)
    return {'success': True}


@app.delete('/api/assignment/{assignment_id}')
def delete_assignment_api(request: Request, assignment_id: int):
    """API для удаления назначения"""
    task = db.get_task_status_by_assignment(assignment_id)
    if task and (task['task_status'] in ('done', 'cancelled') or task['is_deleted']):
        return JSONResponse({'error': 'Нельзя изменять назначения завершённой или отменённой задачи'}, status_code=400)
    db.delete_assignment(assignment_id, changed_by=request.session.get('employee_id'))
    return {'success': True}


@app.get('/api/assignment/{assignment_id}/history')
def get_assignment_history_api(assignment_id: int, offset: int = 0, limit: int = 20):
    """История изменений назначения (с пагинацией)"""
    return {
        'history': db.get_assignment_history(assignment_id, offset=offset, limit=limit),
        'total': db.get_assignment_history_count(assignment_id)
    }


# === API для задач ===

@app.get('/api/tasks/{team_id}')
def get_tasks_api(team_id: int, offset: int = 0, limit: int = 20, search: str = "", show_completed: bool = False):
    """API для получения задач команды с пагинацией"""
    search_val = search.strip() or None
    tasks = db.get_tasks_by_team(team_id, offset=offset, limit=limit, search=search_val, show_completed=show_completed)
    total = db.get_tasks_count_by_team(team_id, search=search_val, show_completed=show_completed)
    return {
        'tasks': [{'id': t['id'], 'name': t['name'], 'description': t['description'], 'criticality': t['criticality'],
                   'task_status': t['task_status']} for t in tasks],
        'total': total
    }


@app.post('/api/task')
def save_task_api(request: Request, data: TaskIn):
    """API для сохранения задачи"""
    name = data.name.strip()
    description = (data.description or '').strip() or None

    if not data.team_id or not name:
        return JSONResponse({'error': 'Team ID and name required'}, status_code=400)

    if data.task_id:
        task = db.get_task_status(data.task_id)
        if task and (task['task_status'] in ('done', 'cancelled') or task['is_deleted']):
            return JSONResponse({'error': 'Нельзя редактировать завершённую или отменённую задачу'}, status_code=400)

    task_id = int(db.create_or_update_task(data.task_id, data.team_id, name, description, data.criticality,
                                            changed_by=request.session.get('employee_id')))

    if data.dependency_ids is not None:
        if data.dependency_ids and db.has_dependency_cycle(task_id, data.dependency_ids):
            return JSONResponse({'error': 'Обнаружена циклическая зависимость'}, status_code=400)
        db.set_task_dependencies(task_id, data.dependency_ids)

    return {'id': task_id, 'success': True}


@app.get('/api/tasks/{team_id}/deps')
def get_team_deps(team_id: int, task_ids: Optional[str] = None):
    parsed_task_ids = [int(x) for x in task_ids.split(',') if x.strip()] if task_ids else None
    rows = db.get_all_deps_for_team(team_id, task_ids=parsed_task_ids)
    return [{'task_id': r['task_id'], 'dep_id': r['dep_id'], 'dep_name': r['dep_name'],
             'dep_status': r['dep_status'], 'dep_is_deleted': bool(r['dep_is_deleted'])} for r in rows]


@app.get('/api/tasks/{team_id}/active-list')
def get_active_tasks_list(team_id: int):
    rows = db.get_active_tasks_flat(team_id)
    return [{'id': r['id'], 'name': r['name'], 'task_status': r['task_status'],
             'criticality': r['criticality']} for r in rows]


@app.delete('/api/task/{task_id}')
def delete_task_api(request: Request, task_id: int):
    """API для удаления задачи"""
    task = db.get_task_status(task_id)
    if task and (task['task_status'] in ('done', 'cancelled') or task['is_deleted']):
        return JSONResponse({'error': 'Нельзя удалить завершённую или отменённую задачу'}, status_code=400)
    db.delete_task(task_id, changed_by=request.session.get('employee_id'))
    return {'success': True}


@app.patch('/api/tasks/{task_id}/status')
def update_task_status_api(request: Request, task_id: int, data: TaskStatusIn):
    """Обновить статус задачи"""
    task = db.get_task_status(task_id)
    if not task:
        return JSONResponse({'error': 'Task not found'}, status_code=404)
    current_status = task['task_status']
    allowed = VALID_TASK_TRANSITIONS.get(current_status, set())
    if data.status not in allowed:
        return JSONResponse({'error': f'Недопустимый переход: {current_status} → {data.status}'}, status_code=400)
    db.update_task_status(task_id, data.status, changed_by=request.session.get('employee_id'))
    return {'success': True}


@app.get('/api/task/{task_id}/history')
def get_task_history_api(task_id: int, offset: int = 0, limit: int = 20):
    """Объединённая история задачи и всех связанных с ней назначений (с пагинацией)"""
    return {
        'history': db.get_task_full_history(task_id, offset=offset, limit=limit),
        'total': db.get_task_full_history_count(task_id)
    }


@app.get('/api/journal/{team_id}')
def get_team_history_api(team_id: int, offset: int = 0, limit: int = 50, search: str = "",
                          date_from: str = "", date_to: str = "",
                          changed_by_employee_id: Optional[int] = None):
    """Журнал изменений команды: все изменения задач и назначений (с пагинацией и фильтрами
    по названию задачи, периоду изменения и автору изменения)"""
    search_val = search.strip() or None
    date_from_val = date_from.strip() or None
    date_to_val = date_to.strip() or None
    return {
        'items': db.get_team_history(team_id, offset=offset, limit=limit, search=search_val,
                                      date_from=date_from_val, date_to=date_to_val,
                                      changed_by_employee_id=changed_by_employee_id),
        'total': db.get_team_history_count(team_id, search=search_val, date_from=date_from_val,
                                            date_to=date_to_val,
                                            changed_by_employee_id=changed_by_employee_id)
    }


# === API для команд ===

@app.get('/api/teams')
def get_teams_api():
    """Получить все команды с разрешёнными шаблонами"""
    return db.get_all_teams_with_templates()


@app.get('/api/teams/{team_id}')
def get_team_api(team_id: int):
    """Получить одну команду с разрешёнными шаблонами"""
    team = db.get_team_by_id(team_id)
    if not team:
        return JSONResponse({'error': 'Team not found'}, status_code=404)
    tmpls = db.get_team_allowed_templates(team_id)
    return {
        'id': team['id'],
        'name': team['name'],
        'templates': tmpls,
        'template_ids': [t['id'] for t in tmpls],
    }


@app.get('/api/teams/{team_id}/blocks')
def get_team_blocks_api(team_id: int):
    """Уникальные блоки из разрешённых шаблонов команды — для ручного выбора блока
    в модалке назначения (React); та же выборка, что раньше шла в Jinja-контекст /planning/{team_id}."""
    return db.get_blocks_for_team(team_id)


@app.post('/api/teams')
def create_team_api(data: TeamIn):
    """Создать команду"""
    name = (data.name or '').strip()
    if not name:
        return JSONResponse({'error': 'Name required'}, status_code=400)

    try:
        team_id = db.create_team(name, data.template_ids or [])
        return {'id': team_id, 'success': True}
    except Exception as e:
        return JSONResponse({'error': str(e)}, status_code=400)


@app.put('/api/teams/{team_id}')
def update_team_api(team_id: int, data: TeamIn):
    """Обновить команду"""
    name = (data.name or '').strip()
    if not name:
        return JSONResponse({'error': 'Name required'}, status_code=400)

    try:
        db.update_team(team_id, name, data.template_ids or [])
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


_VALID_ROLES = {'admin', 'editor', 'user'}


@app.post('/api/employees')
def create_employee_api(data: EmployeeIn):
    """Создать сотрудника"""
    last_name = data.last_name.strip()
    first_name = data.first_name.strip()
    middle_name = (data.middle_name or '').strip() or None
    password_hash = auth.hash_password(data.password) if (data.password or '').strip() else None

    if not last_name or not first_name:
        return JSONResponse({'error': 'Фамилия и имя обязательны'}, status_code=400)
    if data.role not in _VALID_ROLES:
        return JSONResponse({'error': 'Недопустимая роль'}, status_code=400)

    employee_id = db.create_employee(last_name, first_name, middle_name, password_hash, data.role)
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
    password_hash = auth.hash_password(data.password) if (data.password or '').strip() else None

    if not last_name or not first_name:
        return JSONResponse({'error': 'Фамилия и имя обязательны'}, status_code=400)
    if data.role not in _VALID_ROLES:
        return JSONResponse({'error': 'Недопустимая роль'}, status_code=400)

    success = db.update_employee(employee_id, last_name, first_name, middle_name, password_hash, data.role)
    if success:
        return {'success': True}
    else:
        return JSONResponse({'error': 'Сотрудник с таким ФИО уже существует'}, status_code=400)


@app.delete('/api/employees/{employee_id}')
def delete_employee_api(request: Request, employee_id: int):
    """Удалить сотрудника"""
    db.delete_employee(employee_id, changed_by=request.session.get('employee_id'))
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


@app.put('/api/freeze-days/month')
def set_freeze_month_api(data: FreezeDayMonthIn):
    db.set_freeze_days_for_month(data.year, data.month, data.days)
    return {'success': True}


@app.delete('/api/freeze-days/month/{year}/{month}')
def delete_freeze_month_api(year: int, month: int):
    db.delete_freeze_days_by_month(year, month)
    return {'success': True}


@app.delete('/api/freeze-days/{date_str:path}')
def delete_freeze_day_api(date_str: str):
    """Удалить день фриза"""
    db.remove_freeze_day(date_str)
    return {'success': True}


# === API для статистики ===

@app.get('/api/active-assignments/{team_id}')
def get_active_assignments_api(team_id: int, start_date: Optional[str] = None, end_date: Optional[str] = None,
                               team_ids: Optional[str] = None):
    """Активные назначения (new/planned) за период"""
    today_str = date.today().strftime('%Y-%m-%d')
    start_date = start_date or today_str
    end_date = end_date or today_str

    parsed_team_ids = [int(x) for x in team_ids.split(',') if x.strip()] if team_ids else None
    assignments = db.get_active_assignments_in_period(team_id, start_date, end_date, team_ids=parsed_team_ids)

    result = []
    for a in assignments:
        employee_name = utils.format_employee_name(
            a['employee_last_name'], a['employee_first_name'], a['employee_middle_name']
        )
        result.append({
            'id': a['id'],
            'task_name': a['task_name'],
            'criticality': a['criticality'],
            'date': a['date'],
            'block': a['block'],
            'status': a['status'],
            'employee_name': employee_name,
            'comment': a['comment'],
            'team_name': a['team_name'],
            'is_psi': bool(a['is_psi']),
        })
    return result


# === API для блоков ===

@app.get('/api/blocks')
def get_blocks_api():
    """Получить все блоки"""
    return db.get_all_blocks()


@app.post('/api/blocks')
def create_block_api(data: BlockIn):
    """Создать блок"""
    name = (data.name or '').strip()
    if not name:
        return JSONResponse({'error': 'Name required'}, status_code=400)
    try:
        block_id = db.create_block(name)
        return {'id': block_id, 'success': True}
    except Exception as e:
        return JSONResponse({'error': str(e)}, status_code=400)


@app.delete('/api/blocks/{block_id}')
def delete_block_api(block_id: int):
    """Удалить блок"""
    db.delete_block(block_id)
    return {'success': True}


# === API для шаблонов блоков ===

@app.get('/api/block-templates')
def get_templates_api():
    """Получить все шаблоны блоков"""
    return db.get_all_templates()


@app.post('/api/block-templates')
def create_template_api(data: BlockTemplateIn):
    """Создать шаблон блоков"""
    name = (data.name or '').strip()
    if not name:
        return JSONResponse({'error': 'Name required'}, status_code=400)
    entries = [{'block_id': e.block_id, 'shift_days': e.shift_days} for e in (data.entries or [])]
    try:
        tmpl_id = db.create_template(name, entries)
        return {'id': tmpl_id, 'success': True}
    except Exception as e:
        return JSONResponse({'error': str(e)}, status_code=400)


@app.put('/api/block-templates/{template_id}')
def update_template_api(template_id: int, data: BlockTemplateIn):
    """Обновить шаблон блоков"""
    name = (data.name or '').strip()
    if not name:
        return JSONResponse({'error': 'Name required'}, status_code=400)
    t = db.get_template_by_id(template_id)
    if not t:
        return JSONResponse({'error': 'Template not found'}, status_code=404)
    entries = [{'block_id': e.block_id, 'shift_days': e.shift_days} for e in (data.entries or [])]
    try:
        db.update_template(template_id, name, entries)
        return {'success': True}
    except Exception as e:
        return JSONResponse({'error': str(e)}, status_code=400)


@app.delete('/api/block-templates/{template_id}')
def delete_template_api(template_id: int):
    """Удалить шаблон блоков"""
    db.delete_template(template_id)
    return {'success': True}


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, port=5093, host="0.0.0.0")
