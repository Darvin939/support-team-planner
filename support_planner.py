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

# React (Vite/antd) migration, page by page — see plan doc. `frontend/dist` only exists after
# `npm run build`; the mount is skipped in dev if it hasn't been built yet, matching the current
# no-build-step-required philosophy for anyone just running the Python app without touching the
# frontend at all.
_REACT_DIST = os.path.join(os.path.dirname(__file__), 'frontend', 'dist')
if os.path.isdir(_REACT_DIST):
    app.mount("/react-assets", StaticFiles(directory=_REACT_DIST), name="react-assets")


def _serve_react_index() -> str:
    """Отдать собранный React SPA (frontend/dist/index.html) для уже перенесённых страниц."""
    with open(os.path.join(_REACT_DIST, 'index.html'), encoding='utf-8') as f:
        return f.read()

_SESSION_SECRET_KEY = os.environ.get('SESSION_SECRET_KEY')
if not _SESSION_SECRET_KEY:
    _SESSION_SECRET_KEY = 'dev-insecure-secret-change-me'
    print('WARNING: SESSION_SECRET_KEY не задан, используется небезопасный ключ по умолчанию '
          '(сессии не переживут смену ключа; задайте переменную окружения для продакшена)')

_PUBLIC_PATHS = {'/login', '/logout'}

# Ранги ролей: user < editor < admin — каждая следующая роль включает права предыдущей.
_ROLE_RANK = {'user': 0, 'editor': 1, 'admin': 2}

# Мутирующие эндпоинты, требующие роль не ниже admin (управление учётными записями — единственное,
# что запрещено editor'у). GET /api/users остаётся доступен всем ролям (нужен для выпадающих
# списков назначения исполнителя в планировщике).
_ADMIN_ONLY_API_PREFIXES = ('/api/users',)

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
    if path in _PUBLIC_PATHS or path.startswith('/react-assets/'):
        return await call_next(request)
    user_id = request.session.get('user_id')
    user = db.user_exists(user_id) if user_id else None
    if not user_id or not user:
        # Сессия может ссылаться на пользователя, которого больше нет (удалили, БД пересоздали) —
        # обращаемся с этим так же, как с отсутствием сессии, а не пропускаем дальше: иначе запись
        # в task_history/assignment_history упадёт с FOREIGN KEY constraint failed при первом же
        # создании/изменении задачи или назначения.
        request.session.clear()
        if path.startswith('/api/'):
            return JSONResponse({'error': 'Не авторизован'}, status_code=401)
        return RedirectResponse(url='/login', status_code=302)

    # Роль читается из БД на каждый запрос (не из сессии), чтобы смена роли применялась
    # немедленно, без необходимости перелогина.
    role = user['role']
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
    user_id: Optional[int] = None
    comment: Optional[str] = None
    is_psi: bool = False
    time_spent: Optional[str] = None


class TaskIn(BaseModel):
    task_id: Optional[Union[int, str]] = None
    team_id: Optional[int] = None
    name: str = ""
    description: Optional[str] = None
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


class UserIn(BaseModel):
    last_name: str = ""
    first_name: str = ""
    middle_name: Optional[str] = None
    password: Optional[str] = None
    role: str = "user"
    login: Optional[str] = None
    is_assignee: bool = True


class MyPasswordIn(BaseModel):
    password: Optional[str] = None


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


class TaskReorderIn(BaseModel):
    task_ids: List[int]


class TaskPriorityIn(BaseModel):
    position: str


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


@app.post('/login')
def login_submit(request: Request, login: str = Form(...), password: str = Form(...)):
    """Обработка входа по логину и паролю"""
    auth_row = db.get_user_auth_by_login(login.strip()) if login.strip() else None
    if not auth_row or not auth.verify_password(password, auth_row['password_hash']):
        return JSONResponse({'error': 'Неверный логин или пароль'}, status_code=401)

    request.session['user_id'] = auth_row['id']
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
    user = db.get_user(request.session['user_id'])
    return {
        'user_id': user['id'],
        'role': user['role'],
        'last_name': user['last_name'],
        'first_name': user['first_name'],
        'middle_name': user['middle_name'],
    }


@app.put('/api/me')
def update_me_api(request: Request, data: MyPasswordIn):
    """Пользователь меняет пароль собственной учётной записи — доступно любой роли. Логин
    (в отличие от пароля) теперь может менять только admin, через /api/users."""
    password_hash = auth.hash_password(data.password) if (data.password or '').strip() else None
    if password_hash is None:
        return JSONResponse({'error': 'Нечего обновлять'}, status_code=400)

    db.update_own_password(request.session['user_id'], password_hash)
    return {'success': True}


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
        user_name = utils.format_user_name(a['user_last_name'],
                                            a['user_first_name'],
                                            a['user_middle_name'])
        result.append({
            'id': a['id'],
            'task_id': a['task_id'],
            'date': a['date'],
            'block': a['block'],
            'status': a['status'],
            'user_id': a['user_id'],
            'user_name': user_name,
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

    changed_by = request.session.get('user_id')
    db.create_or_update_assignment(data.assignment_id, data.task_id, data.date, block, data.status, data.user_id,
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
    db.delete_assignment(assignment_id, changed_by=request.session.get('user_id'))
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
def get_tasks_api(team_id: int, offset: int = 0, limit: int = 20, search: str = "", show_completed: bool = False,
                   task_id: Optional[int] = None):
    """API для получения задач команды с пагинацией"""
    search_val = search.strip() or None
    tasks = db.get_tasks_by_team(team_id, offset=offset, limit=limit, search=search_val, show_completed=show_completed,
                                  task_id=task_id)
    total = db.get_tasks_count_by_team(team_id, search=search_val, show_completed=show_completed)
    return {
        'tasks': [{'id': t['id'], 'name': t['name'], 'description': t['description'],
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

    task_id = int(db.create_or_update_task(data.task_id, data.team_id, name, description,
                                            changed_by=request.session.get('user_id')))

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
def get_active_tasks_list(team_id: int, search: str = "", limit: int = 50, include_ids: Optional[str] = None):
    search_val = search.strip() or None
    parsed_include_ids = [int(x) for x in include_ids.split(',') if x.strip()] if include_ids else None
    rows = db.get_active_tasks_flat(team_id, search=search_val, limit=limit, include_ids=parsed_include_ids)
    return [{'id': r['id'], 'name': r['name'], 'task_status': r['task_status']} for r in rows]


@app.delete('/api/task/{task_id}')
def delete_task_api(request: Request, task_id: int):
    """API для удаления задачи"""
    task = db.get_task_status(task_id)
    if task and (task['task_status'] in ('done', 'cancelled') or task['is_deleted']):
        return JSONResponse({'error': 'Нельзя удалить завершённую или отменённую задачу'}, status_code=400)
    db.delete_task(task_id, changed_by=request.session.get('user_id'))
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
    db.update_task_status(task_id, data.status, changed_by=request.session.get('user_id'))
    return {'success': True}


@app.patch('/api/tasks/{team_id}/reorder')
def reorder_tasks_api(request: Request, team_id: int, data: TaskReorderIn):
    """Переупорядочить задачи в пределах одной уже загруженной страницы (drag-and-drop)"""
    if not data.task_ids:
        return JSONResponse({'error': 'task_ids required'}, status_code=400)
    try:
        db.reorder_team_tasks(team_id, data.task_ids, changed_by=request.session.get('user_id'))
    except ValueError as e:
        return JSONResponse({'error': str(e)}, status_code=400)
    return {'success': True}


@app.patch('/api/task/{task_id}/priority')
def move_task_priority_api(request: Request, task_id: int, data: TaskPriorityIn):
    """Переместить задачу в начало/конец списка всей команды (контекстное меню)"""
    if data.position not in ('start', 'end'):
        return JSONResponse({'error': 'position must be start or end'}, status_code=400)
    try:
        db.move_task_to_edge(task_id, data.position, changed_by=request.session.get('user_id'))
    except ValueError as e:
        return JSONResponse({'error': str(e)}, status_code=404)
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
                          changed_by_user_id: Optional[int] = None):
    """Журнал изменений команды: все изменения задач и назначений (с пагинацией и фильтрами
    по названию задачи, периоду изменения и автору изменения)"""
    search_val = search.strip() or None
    date_from_val = date_from.strip() or None
    date_to_val = date_to.strip() or None
    return {
        'items': db.get_team_history(team_id, offset=offset, limit=limit, search=search_val,
                                      date_from=date_from_val, date_to=date_to_val,
                                      changed_by_user_id=changed_by_user_id),
        'total': db.get_team_history_count(team_id, search=search_val, date_from=date_from_val,
                                            date_to=date_to_val,
                                            changed_by_user_id=changed_by_user_id)
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


# === API для пользователей ===

@app.get('/api/users')
def get_users_api():
    """Получить всех пользователей"""
    return db.get_all_users()


_VALID_ROLES = {'admin', 'editor', 'user'}


@app.post('/api/users')
def create_user_api(data: UserIn):
    """Создать пользователя"""
    last_name = data.last_name.strip() or None
    first_name = data.first_name.strip()
    middle_name = (data.middle_name or '').strip() or None
    password_hash = auth.hash_password(data.password) if (data.password or '').strip() else None
    login = (data.login or '').strip() or None

    if not first_name:
        return JSONResponse({'error': 'Имя обязательно'}, status_code=400)
    if data.role not in _VALID_ROLES:
        return JSONResponse({'error': 'Недопустимая роль'}, status_code=400)

    user_id = db.create_user(last_name, first_name, middle_name, password_hash, data.role, login, data.is_assignee)
    if user_id:
        return {'id': user_id, 'success': True}
    else:
        return JSONResponse({'error': 'Пользователь с таким логином уже существует'}, status_code=400)


@app.put('/api/users/{user_id}')
def update_user_api(user_id: int, data: UserIn):
    """Обновить пользователя"""
    last_name = data.last_name.strip() or None
    first_name = data.first_name.strip()
    middle_name = (data.middle_name or '').strip() or None
    password_hash = auth.hash_password(data.password) if (data.password or '').strip() else None
    login = (data.login or '').strip() or None

    if not first_name and not db.is_bootstrap_admin_id(user_id):
        return JSONResponse({'error': 'Имя обязательно'}, status_code=400)
    if data.role not in _VALID_ROLES:
        return JSONResponse({'error': 'Недопустимая роль'}, status_code=400)

    success = db.update_user(user_id, last_name, first_name, middle_name, password_hash, data.role, login,
                              data.is_assignee)
    if success:
        return {'success': True}
    else:
        return JSONResponse({'error': 'Пользователь с таким логином уже существует'}, status_code=400)


@app.delete('/api/users/{user_id}')
def delete_user_api(request: Request, user_id: int):
    """Удалить пользователя"""
    try:
        db.delete_user(user_id, changed_by=request.session.get('user_id'))
        return {'success': True}
    except ValueError as e:
        return JSONResponse({'error': str(e)}, status_code=400)


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
                               team_ids: Optional[str] = None, offset: int = 0, limit: Optional[int] = None):
    """Активные назначения (new/planned) за период, с опциональной пагинацией (limit не задан -> вся выборка)"""
    today_str = date.today().strftime('%Y-%m-%d')
    start_date = start_date or today_str
    end_date = end_date or today_str

    parsed_team_ids = [int(x) for x in team_ids.split(',') if x.strip()] if team_ids else None
    assignments = db.get_active_assignments_in_period(team_id, start_date, end_date, team_ids=parsed_team_ids,
                                                       offset=offset, limit=limit)
    stats = db.get_active_assignments_stats(team_id, start_date, end_date, team_ids=parsed_team_ids)

    items = []
    for a in assignments:
        user_name = utils.format_user_name(
            a['user_last_name'], a['user_first_name'], a['user_middle_name']
        )
        items.append({
            'id': a['id'],
            'task_id': a['task_id'],
            'task_name': a['task_name'],
            'date': a['date'],
            'block': a['block'],
            'status': a['status'],
            'user_name': user_name,
            'comment': a['comment'],
            'team_id': a['team_id'],
            'team_name': a['team_name'],
            'is_psi': bool(a['is_psi']),
        })
    return {
        'items': items,
        'total': stats['total'],
        'stats': {
            'status': {'new': stats['status_new'], 'planned': stats['status_planned']},
        },
    }


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
