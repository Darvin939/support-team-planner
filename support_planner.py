import json
import os
from datetime import date, timedelta
from typing import Optional, List, Union

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

import auth
import db
import utils
from ssl_context import get_cert

app = FastAPI()

# React (Vite/antd) migration, page by page — see plan doc. `frontend/dist` only exists after
# `npm run build`; the mount is skipped in dev if it hasn't been built yet, matching the current
# no-build-step-required philosophy for anyone just running the Python app without touching the
# frontend at all.
_REACT_DIST = os.path.join(os.path.dirname(__file__), 'frontend', 'dist')
if os.path.isdir(_REACT_DIST):
    app.mount("/react-assets", StaticFiles(directory=_REACT_DIST), name="react-assets")

_react_index_html: Optional[str] = None


def _serve_react_index() -> str:
    """Отдать собранный React SPA (frontend/dist/index.html) для уже перенесённых страниц —
    index.html читается с диска не более одного раза за жизнь процесса и дальше кэшируется в
    памяти, т.к. это билд-артефакт, не меняющийся, пока сервер запущен (без перезапуска процесса
    сборку заново всё равно не подхватить)."""
    global _react_index_html
    if _react_index_html is None:
        with open(os.path.join(_REACT_DIST, 'index.html'), encoding='utf-8') as f:
            _react_index_html = f.read()
    return _react_index_html


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
_EDITOR_API_PREFIXES = ('/api/teams', '/api/freeze-days', '/api/blocks', '/api/block-templates', '/api/segments')


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
# below is called. db_connection_per_request (registered further down, between this function and
# add_middleware(SessionMiddleware)) must run BEFORE require_login so that require_login's own
# db.user_exists call also reuses the request-scoped connection — giving the execution order
# SessionMiddleware -> db_connection_per_request -> require_login -> route.
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


# Открывает одно SQLite-соединение на весь HTTP-запрос и кладёт его в contextvar
# (db.set_request_connection), чтобы все db.*-вызовы в рамках запроса — включая db.user_exists
# внутри require_login выше — переиспользовали его вместо connect()/close() на каждый вызов DAO
# (см. db.with_db_connection). Регистрируется здесь совершенно намеренно: ПОСЛЕ require_login и
# ДО add_middleware(SessionMiddleware) ниже, чтобы попасть между ними в цепочке выполнения
# (см. комментарий над require_login). /react-assets/* пропускается — статике соединение не нужно.
@app.middleware('http')
async def db_connection_per_request(request: Request, call_next):
    if request.url.path.startswith('/react-assets/'):
        return await call_next(request)
    conn = db.get_db_connection()
    token = db.set_request_connection(conn)
    try:
        return await call_next(request)
    finally:
        db.clear_request_connection(token)
        conn.close()


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
    time_spent: Optional[str] = None


class AssignmentRescheduleIn(BaseModel):
    assignment_id: int
    new_date: str


class BulkAssignmentRescheduleIn(BaseModel):
    moves: List[AssignmentRescheduleIn]


class TaskIn(BaseModel):
    task_id: Optional[Union[int, str]] = None
    team_id: Optional[int] = None
    name: str = ""
    description: Optional[str] = None
    criticality: str = "medium"
    segment_id: Optional[int] = None
    dependency_ids: Optional[List[int]] = None


class TeamIn(BaseModel):
    name: str = ""
    template_ids: Optional[List[int]] = None


class BlockIn(BaseModel):
    name: str = ""


class SegmentIn(BaseModel):
    name: str = ""


class TemplateEntryIn(BaseModel):
    block_id: int
    shift_days: int = 0


class BlockTemplateIn(BaseModel):
    name: str = ""
    segment_id: Optional[int] = None
    entries: Optional[List[TemplateEntryIn]] = None


class UserIn(BaseModel):
    last_name: str = ""
    first_name: str = ""
    middle_name: Optional[str] = None
    password: Optional[str] = None
    role: str = "user"
    login: Optional[str] = None
    is_assignee: bool = True
    team_ids: Optional[List[int]] = None


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


# Единственный источник истины — frontend/src/data/taskTransitions.json, читается и фронтендом
# (PlanningPage.tsx), и бэкендом, чтобы правила переходов статуса задачи не могли разойтись между
# ними (см. openspec/changes/shared-task-transitions-source).
with open(os.path.join(os.path.dirname(__file__), 'frontend', 'src', 'data', 'taskTransitions.json'),
          encoding='utf-8') as _f:
    VALID_TASK_TRANSITIONS = {k: set(v) for k, v in json.load(_f).items()}


def _task_is_locked(task) -> bool:
    """Задача в терминальном статусе (выполнено/отменено) или мягко удалена — блокирует
    редактирование/удаление самой задачи и её назначений."""
    return task['task_status'] in ('done', 'cancelled') or task['is_deleted']


def _parse_int_csv(value: Optional[str]) -> Optional[List[int]]:
    """Распарсить query-параметр вида '1,2,3' в список int; None/пусто -> None (без фильтрации)."""
    return [int(x) for x in value.split(',') if x.strip()] if value else None


def _access_user(request: Request):
    return request.session['user_id'], request.state.role


def _require_team_access(request: Request, team_id: Optional[int]):
    if team_id is None:
        raise HTTPException(status_code=404, detail='Команда не найдена')
    user_id, role = _access_user(request)
    if not db.user_can_access_team(user_id, role, team_id):
        raise HTTPException(status_code=403, detail='Нет доступа к команде')
    return team_id


def _require_task_access(request: Request, task_id: int):
    team_id = db.get_task_team_id(task_id)
    return _require_team_access(request, team_id)


def _require_assignment_access(request: Request, assignment_id: int):
    team_id = db.get_assignment_team_id(assignment_id)
    return _require_team_access(request, team_id)


def _require_team_list_access(request: Request, team_ids: List[int]):
    for team_id in team_ids:
        _require_team_access(request, team_id)


def _effective_team_filter(request: Request):
    user_id, role = _access_user(request)
    return db.get_effective_team_ids(user_id, role)


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
def get_assignments_api(request: Request, team_id: int, start_date: Optional[str] = None,
                        end_date: Optional[str] = None,
                        task_ids: Optional[str] = None):
    """API для получения назначений команды"""
    _require_team_access(request, team_id)
    if not start_date or not end_date:
        today = date.today()
        start_date = start_date or (today - timedelta(days=30)).strftime('%Y-%m-%d')
        end_date = end_date or (today + timedelta(days=60)).strftime('%Y-%m-%d')
    parsed_task_ids = _parse_int_csv(task_ids)
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
    team_id = _require_task_access(request, data.task_id)
    if data.assignment_id:
        _require_assignment_access(request, data.assignment_id)
    if data.user_id is not None and not db.user_is_eligible_assignee(data.user_id, team_id):
        return JSONResponse({'error': 'Пользователь недоступен для назначения в этой команде'}, status_code=400)

    task = db.get_task_status(data.task_id)
    if task and _task_is_locked(task):
        return JSONResponse({'error': 'Нельзя изменять назначения завершённой или отменённой задачи'}, status_code=400)

    if request.state.role == 'user':
        if data.status != 'new':
            return JSONResponse(
                {'error': 'Недостаточно прав: можно создавать и изменять назначения только со статусом «Новый»'},
                status_code=403)
        if data.assignment_id:
            existing = db.get_task_status_by_assignment(data.assignment_id)
            if existing and existing['assignment_status'] != 'new':
                return JSONResponse(
                    {'error': 'Недостаточно прав: нельзя изменять назначение в статусе, отличном от «Новый»'},
                    status_code=403)

    changed_by = request.session.get('user_id')
    db.create_or_update_assignment(data.assignment_id, data.task_id, data.date, block, data.status, data.user_id,
                                   comment, time_spent, changed_by=changed_by)
    return {'success': True}


@app.post('/api/assignments/bulk-reschedule')
def bulk_reschedule_assignments_api(request: Request, data: BulkAssignmentRescheduleIn):
    """Атомарно перенести несколько назначений на итоговые даты."""
    for move in data.moves:
        _require_assignment_access(request, move.assignment_id)
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


@app.delete('/api/assignment/{assignment_id}')
def delete_assignment_api(request: Request, assignment_id: int):
    """API для удаления назначения"""
    _require_assignment_access(request, assignment_id)
    task = db.get_task_status_by_assignment(assignment_id)
    if task and _task_is_locked(task):
        return JSONResponse({'error': 'Нельзя изменять назначения завершённой или отменённой задачи'}, status_code=400)
    if request.state.role == 'user' and task and task['assignment_status'] != 'new':
        return JSONResponse(
            {'error': 'Недостаточно прав: нельзя удалить назначение в статусе, отличном от «Новый»'},
            status_code=403)
    db.delete_assignment(assignment_id, changed_by=request.session.get('user_id'))
    return {'success': True}


@app.get('/api/assignment/{assignment_id}/history')
def get_assignment_history_api(request: Request, assignment_id: int, offset: int = 0, limit: int = 20):
    """История изменений назначения (с пагинацией)"""
    _require_assignment_access(request, assignment_id)
    return {
        'history': db.get_assignment_history(assignment_id, offset=offset, limit=limit),
        'total': db.get_assignment_history_count(assignment_id)
    }


# === API для задач ===

@app.get('/api/tasks/{team_id}')
def get_tasks_api(request: Request, team_id: int, offset: int = 0, limit: int = 20, search: str = "",
                  show_completed: bool = False,
                  task_id: Optional[int] = None):
    """API для получения задач команды с пагинацией"""
    _require_team_access(request, team_id)
    search_val = search.strip() or None
    tasks = db.get_tasks_by_team(team_id, offset=offset, limit=limit, search=search_val, show_completed=show_completed,
                                 task_id=task_id)
    total = db.get_tasks_count_by_team(team_id, search=search_val, show_completed=show_completed)
    return {
        'tasks': [{'id': t['id'], 'name': t['name'], 'description': t['description'],
                   'criticality': t['criticality'], 'task_status': t['task_status'],
                   'segment_id': t['segment_id'], 'segment_name': t['segment_name'],
                   'has_active_assignments': bool(t['has_active_assignments'])} for t in tasks],
        'total': total
    }


@app.post('/api/task')
def save_task_api(request: Request, data: TaskIn):
    """API для сохранения задачи"""
    name = data.name.strip()
    description = (data.description or '').strip() or None

    if not data.team_id or not name:
        return JSONResponse({'error': 'Team ID and name required'}, status_code=400)
    _require_team_access(request, data.team_id)
    if data.criticality not in ('low', 'medium', 'high'):
        return JSONResponse({'error': 'criticality must be low, medium or high'}, status_code=400)
    if not data.segment_id or not any(s['id'] == data.segment_id for s in db.get_all_segments()):
        return JSONResponse({'error': 'Указан несуществующий сегмент'}, status_code=400)

    if data.task_id:
        if not db.task_exists(data.task_id):
            return JSONResponse({'error': 'Задача не найдена'}, status_code=404)
        _require_task_access(request, int(data.task_id))
        task = db.get_task_status(data.task_id)
        if task and _task_is_locked(task):
            return JSONResponse({'error': 'Нельзя редактировать завершённую или отменённую задачу'}, status_code=400)

    task_id = int(db.create_or_update_task(data.task_id, data.team_id, name, description, data.criticality,
                                           segment_id=data.segment_id,
                                           changed_by=request.session.get('user_id')))

    if data.dependency_ids is not None:
        if data.dependency_ids and db.has_dependency_cycle(task_id, data.dependency_ids):
            return JSONResponse({'error': 'Обнаружена циклическая зависимость'}, status_code=400)
        db.set_task_dependencies(task_id, data.dependency_ids)

    return {'id': task_id, 'success': True}


@app.get('/api/tasks/{team_id}/deps')
def get_team_deps(request: Request, team_id: int, task_ids: Optional[str] = None):
    _require_team_access(request, team_id)
    parsed_task_ids = _parse_int_csv(task_ids)
    rows = db.get_all_deps_for_team(team_id, task_ids=parsed_task_ids)
    return [{'task_id': r['task_id'], 'dep_id': r['dep_id'], 'dep_name': r['dep_name'],
             'dep_status': r['dep_status'], 'dep_is_deleted': bool(r['dep_is_deleted']),
             'dep_criticality': r['dep_criticality'], 'dep_segment_id': r['dep_segment_id'],
             'dep_segment_name': r['dep_segment_name']} for r in rows]


@app.get('/api/tasks/{team_id}/dependency-graph')
def get_team_dependency_graph(request: Request, team_id: int, task_id: Optional[int] = None):
    """Граф зависимостей для визуализации — в отличие от /deps не ограничен списком уже
    загруженных на странице задач. Без task_id — весь граф команды (задачи без единой связи
    исключены). С task_id — только связная компонента конкретной задачи (её предки и потомки)."""
    _require_team_access(request, team_id)
    if task_id is not None:
        _require_task_access(request, task_id)
    graph = db.get_dependency_graph_for_team(team_id, task_id=task_id)
    return {
        'nodes': [{'id': n['id'], 'name': n['name'], 'description': n['description'],
                   'task_status': n['task_status'], 'criticality': n['criticality'],
                   'segment_id': n['segment_id'], 'segment_name': n['segment_name']} for n in graph['nodes']],
        'edges': [{'task_id': e['task_id'], 'dep_id': e['dep_id']} for e in graph['edges']],
    }


class TaskDependencyIn(BaseModel):
    task_id: int
    depends_on_task_id: int


def _validate_task_dependency_edit(data: 'TaskDependencyIn'):
    """Общие проверки для добавления/удаления одной связи зависимости с графа: обе задачи
    существуют и не удалены, принадлежат одной команде, а зависящая задача (task_id) не в
    терминальном статусе — те же правила, что уже действуют при редактировании зависимостей
    через форму задачи (POST /api/task)."""
    task, dep_task = db.get_tasks_for_dependency_edit(data.task_id, data.depends_on_task_id)
    if not task or not dep_task or task['is_deleted'] or dep_task['is_deleted']:
        return JSONResponse({'error': 'Задача не найдена'}, status_code=404)
    if task['team_id'] != dep_task['team_id']:
        return JSONResponse({'error': 'Задачи принадлежат разным командам'}, status_code=400)
    if task['task_status'] in ('done', 'cancelled'):
        return JSONResponse({'error': 'Нельзя редактировать завершённую или отменённую задачу'}, status_code=400)
    return None


@app.post('/api/task-dependency')
def add_task_dependency_api(request: Request, data: TaskDependencyIn):
    """Добавить одну связь зависимости прямо с графа (без пересохранения всей задачи)."""
    _require_task_access(request, data.task_id)
    _require_task_access(request, data.depends_on_task_id)
    error = _validate_task_dependency_edit(data)
    if error:
        return error
    if db.has_dependency_cycle(data.task_id, [data.depends_on_task_id]):
        return JSONResponse({'error': 'Обнаружена циклическая зависимость'}, status_code=400)
    db.add_task_dependency(data.task_id, data.depends_on_task_id)
    return {'success': True}


@app.delete('/api/task-dependency')
def remove_task_dependency_api(request: Request, data: TaskDependencyIn):
    """Удалить одну связь зависимости прямо с графа."""
    _require_task_access(request, data.task_id)
    _require_task_access(request, data.depends_on_task_id)
    error = _validate_task_dependency_edit(data)
    if error:
        return error
    db.remove_task_dependency(data.task_id, data.depends_on_task_id)
    return {'success': True}


@app.get('/api/tasks/{team_id}/active-list')
def get_active_tasks_list(request: Request, team_id: int, search: str = "", limit: int = 50,
                          include_ids: Optional[str] = None):
    _require_team_access(request, team_id)
    search_val = search.strip() or None
    parsed_include_ids = _parse_int_csv(include_ids)
    rows = db.get_active_tasks_flat(team_id, search=search_val, limit=limit, include_ids=parsed_include_ids)
    return [{'id': r['id'], 'name': r['name'], 'task_status': r['task_status'],
             'criticality': r['criticality']} for r in rows]


@app.delete('/api/task/{task_id}')
def delete_task_api(request: Request, task_id: int):
    """API для удаления задачи"""
    _require_task_access(request, task_id)
    task = db.get_task_status(task_id)
    if task and _task_is_locked(task):
        return JSONResponse({'error': 'Нельзя удалить завершённую или отменённую задачу'}, status_code=400)
    if request.state.role == 'user' and db.task_has_active_assignments(task_id):
        return JSONResponse(
            {
                'error': 'Недостаточно прав: нельзя удалить работу, у которой есть назначения в статусе, отличном от «Новый»'},
            status_code=403)
    db.delete_task(task_id, changed_by=request.session.get('user_id'))
    return {'success': True}


@app.patch('/api/tasks/{task_id}/status')
def update_task_status_api(request: Request, task_id: int, data: TaskStatusIn):
    """Обновить статус задачи"""
    _require_task_access(request, task_id)
    task = db.get_task_status(task_id)
    if not task:
        return JSONResponse({'error': 'Task not found'}, status_code=404)
    if request.state.role == 'user':
        return JSONResponse({'error': 'Недостаточно прав для изменения статуса задачи'}, status_code=403)
    current_status = task['task_status']
    allowed = VALID_TASK_TRANSITIONS.get(current_status, set())
    if data.status not in allowed:
        return JSONResponse({'error': f'Недопустимый переход: {current_status} → {data.status}'}, status_code=400)
    db.update_task_status(task_id, data.status, changed_by=request.session.get('user_id'))
    return {'success': True}


@app.patch('/api/tasks/{team_id}/reorder')
def reorder_tasks_api(request: Request, team_id: int, data: TaskReorderIn):
    """Переупорядочить задачи в пределах одной уже загруженной страницы (drag-and-drop)"""
    _require_team_access(request, team_id)
    if not data.task_ids:
        return JSONResponse({'error': 'task_ids required'}, status_code=400)
    try:
        db.reorder_team_tasks(team_id, data.task_ids, changed_by=request.session.get('user_id'))
    except ValueError as e:
        return JSONResponse({'error': str(e)}, status_code=400)
    return {'success': True}


@app.patch('/api/task/{task_id}/priority')
def move_task_priority_api(request: Request, task_id: int, data: TaskPriorityIn):
    """Переместить задачу в начало/конец списка её уровня критичности (контекстное меню)"""
    _require_task_access(request, task_id)
    if data.position not in ('start', 'end'):
        return JSONResponse({'error': 'position must be start or end'}, status_code=400)
    try:
        db.move_task_to_edge(task_id, data.position, changed_by=request.session.get('user_id'))
    except ValueError as e:
        return JSONResponse({'error': str(e)}, status_code=400)
    return {'success': True}


@app.get('/api/task/{task_id}/history')
def get_task_history_api(request: Request, task_id: int, offset: int = 0, limit: int = 20):
    """Объединённая история задачи и всех связанных с ней назначений (с пагинацией)"""
    _require_task_access(request, task_id)
    return {
        'history': db.get_task_full_history(task_id, offset=offset, limit=limit),
        'total': db.get_task_full_history_count(task_id)
    }


@app.get('/api/journal/{team_id}')
def get_team_history_api(request: Request, team_id: int, offset: int = 0, limit: int = 50, search: str = "",
                         date_from: str = "", date_to: str = "",
                         changed_by_user_id: Optional[int] = None):
    """Журнал изменений команды: все изменения задач и назначений (с пагинацией и фильтрами
    по названию задачи, периоду изменения и автору изменения)"""
    _require_team_access(request, team_id)
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
def get_teams_api(request: Request, offset: Optional[int] = None, limit: Optional[int] = None,
                  search: Optional[str] = None):
    """Получить все команды с разрешёнными шаблонами"""
    if offset is not None or limit is not None or search is not None:
        safe_offset = max(offset or 0, 0)
        safe_limit = min(max(limit or 20, 1), 100)
        return db.get_teams_page_for_user(
            request.session['user_id'], request.state.role, safe_offset, safe_limit, search,
        )
    return db.get_teams_for_user(request.session['user_id'], request.state.role)


@app.get('/api/teams/{team_id}')
def get_team_api(request: Request, team_id: int):
    """Получить одну команду с разрешёнными шаблонами"""
    _require_team_access(request, team_id)
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
def get_team_blocks_api(request: Request, team_id: int, segment_id: Optional[int] = None):
    """Уникальные блоки из разрешённых шаблонов команды — для ручного выбора блока
    в модалке назначения (React); та же выборка, что раньше шла в Jinja-контекст /planning/{team_id}.
    segment_id, если передан, дополнительно сужает выборку до шаблонов конкретного сегмента."""
    _require_team_access(request, team_id)
    return db.get_blocks_for_team(team_id, segment_id=segment_id)


@app.get('/api/teams/{team_id}/assignees')
def get_team_assignees_api(request: Request, team_id: int):
    _require_team_access(request, team_id)
    return db.get_team_assignees(team_id)


@app.post('/api/teams')
def create_team_api(request: Request, data: TeamIn):
    """Создать команду"""
    name = (data.name or '').strip()
    if not name:
        return JSONResponse({'error': 'Name required'}, status_code=400)

    try:
        team_id = db.create_team(name, data.template_ids or [])
        db.grant_team_access_if_restricted(request.session['user_id'], request.state.role, team_id)
        return {'id': team_id, 'success': True}
    except db.IntegrityConstraintError as e:
        return JSONResponse({'error': str(e)}, status_code=400)


@app.put('/api/teams/{team_id}')
def update_team_api(request: Request, team_id: int, data: TeamIn):
    """Обновить команду"""
    _require_team_access(request, team_id)
    name = (data.name or '').strip()
    if not name:
        return JSONResponse({'error': 'Name required'}, status_code=400)

    try:
        db.update_team(team_id, name, data.template_ids or [])
        return {'success': True}
    except db.IntegrityConstraintError as e:
        return JSONResponse({'error': str(e)}, status_code=400)


@app.delete('/api/teams/{team_id}')
def delete_team_api(request: Request, team_id: int):
    """Удалить команду (каскадно удаляются задачи и блоки)"""
    _require_team_access(request, team_id)
    db.delete_team(team_id)
    return {'success': True}


# === API для пользователей ===

@app.get('/api/users')
def get_users_api(offset: Optional[int] = None, limit: Optional[int] = None, search: Optional[str] = None):
    """Получить всех пользователей"""
    if offset is None and limit is None and search is None:
        return db.get_all_users()
    safe_offset = max(offset or 0, 0)
    safe_limit = min(max(limit or 20, 1), 100)
    return db.get_users_page(safe_offset, safe_limit, search)


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

    user_id = db.create_user(last_name, first_name, middle_name, password_hash, data.role, login, data.is_assignee,
                             data.team_ids)
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
                             data.is_assignee, data.team_ids)
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
def get_active_assignments_api(request: Request, team_id: int, start_date: Optional[str] = None,
                               end_date: Optional[str] = None,
                               team_ids: Optional[str] = None, offset: int = 0, limit: Optional[int] = None):
    """Активные назначения (new/planned) за период, с опциональной пагинацией (limit не задан -> вся выборка)"""
    today_str = date.today().strftime('%Y-%m-%d')
    start_date = start_date or today_str
    end_date = end_date or today_str

    parsed_team_ids = _parse_int_csv(team_ids)
    if parsed_team_ids:
        _require_team_list_access(request, parsed_team_ids)
    elif team_id:
        _require_team_access(request, team_id)
    else:
        parsed_team_ids = _effective_team_filter(request)
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
            'criticality': a['criticality'],
            'date': a['date'],
            'block': a['block'],
            'status': a['status'],
            'user_name': user_name,
            'comment': a['comment'],
            'team_id': a['team_id'],
            'team_name': a['team_name'],
        })
    return {
        'items': items,
        'total': stats['total'],
        'stats': {
            'status': {'new': stats['status_new'], 'planned': stats['status_planned']},
            'criticality': {'high': stats['crit_high'], 'medium': stats['crit_medium'], 'low': stats['crit_low']},
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
    except db.IntegrityConstraintError as e:
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
    if not data.segment_id or not any(s['id'] == data.segment_id for s in db.get_all_segments()):
        return JSONResponse({'error': 'Указан несуществующий сегмент'}, status_code=400)
    entries = [{'block_id': e.block_id, 'shift_days': e.shift_days} for e in (data.entries or [])]
    try:
        tmpl_id = db.create_template(name, data.segment_id, entries)
        return {'id': tmpl_id, 'success': True}
    except db.IntegrityConstraintError as e:
        return JSONResponse({'error': str(e)}, status_code=400)


@app.put('/api/block-templates/{template_id}')
def update_template_api(template_id: int, data: BlockTemplateIn):
    """Обновить шаблон блоков"""
    name = (data.name or '').strip()
    if not name:
        return JSONResponse({'error': 'Name required'}, status_code=400)
    if not data.segment_id or not any(s['id'] == data.segment_id for s in db.get_all_segments()):
        return JSONResponse({'error': 'Указан несуществующий сегмент'}, status_code=400)
    t = db.get_template_by_id(template_id)
    if not t:
        return JSONResponse({'error': 'Template not found'}, status_code=404)
    entries = [{'block_id': e.block_id, 'shift_days': e.shift_days} for e in (data.entries or [])]
    try:
        db.update_template(template_id, name, data.segment_id, entries)
        return {'success': True}
    except db.IntegrityConstraintError as e:
        return JSONResponse({'error': str(e)}, status_code=400)


@app.delete('/api/block-templates/{template_id}')
def delete_template_api(template_id: int):
    """Удалить шаблон блоков"""
    db.delete_template(template_id)
    return {'success': True}


# === API для сегментов ===

@app.get('/api/segments')
def get_segments_api():
    """Получить все сегменты"""
    return db.get_all_segments()


@app.post('/api/segments')
def create_segment_api(data: SegmentIn):
    """Создать сегмент"""
    name = (data.name or '').strip()
    if not name:
        return JSONResponse({'error': 'Name required'}, status_code=400)
    try:
        segment_id = db.create_segment(name)
        return {'id': segment_id, 'success': True}
    except db.IntegrityConstraintError as e:
        return JSONResponse({'error': str(e)}, status_code=400)


@app.put('/api/segments/{segment_id}')
def update_segment_api(segment_id: int, data: SegmentIn):
    """Обновить сегмент"""
    name = (data.name or '').strip()
    if not name:
        return JSONResponse({'error': 'Name required'}, status_code=400)
    try:
        db.update_segment(segment_id, name)
        return {'success': True}
    except db.IntegrityConstraintError as e:
        return JSONResponse({'error': str(e)}, status_code=400)


@app.delete('/api/segments/{segment_id}')
def delete_segment_api(segment_id: int):
    """Удалить сегмент"""
    try:
        db.delete_segment(segment_id)
        return {'success': True}
    except db.IntegrityConstraintError as e:
        return JSONResponse({'error': str(e)}, status_code=400)


if __name__ == '__main__':
    import uvicorn

    cert, key = get_cert()
    if cert and key:
        uvicorn.run(app, port=5093, host="0.0.0.0", ssl_keyfile=key, ssl_certfile=cert)
    else:
        uvicorn.run(app, port=5093, host="0.0.0.0")
