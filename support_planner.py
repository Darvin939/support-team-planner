import json
import os
from datetime import date
from typing import Optional, List

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from api_models import (
    MyPasswordIn,
    TaskIn,
    TaskPriorityIn,
    TaskReorderIn,
    TaskStatusIn,
    TemplateEntryIn,
)
import auth
import db
from access_control import (
    access_user as _access_user,
    require_login,
    require_task_access as _require_task_access,
    require_team_access as _require_team_access,
)
from ssl_context import get_cert
from routers.reference_data import router as reference_data_router
from routers.freeze_days import router as freeze_days_router
from routers.teams import router as teams_router
from routers.users import router as users_router
from routers.assignments import router as assignments_router
from routers.task_dependencies import router as task_dependencies_router
from task_dependency_rules import TaskDependencyCycleError
from task_rules import task_is_locked as _task_is_locked

app = FastAPI()
app.include_router(reference_data_router)
app.include_router(freeze_days_router)
app.include_router(teams_router)
app.include_router(users_router)
app.include_router(assignments_router)
app.include_router(task_dependencies_router)


def _api_error(message: str, status_code: int, headers=None) -> JSONResponse:
    return JSONResponse({'error': message}, status_code=status_code, headers=headers)


@app.exception_handler(HTTPException)
async def api_http_exception_handler(request: Request, exc: HTTPException):
    if not request.url.path.startswith('/api/'):
        return await http_exception_handler(request, exc)
    message = exc.detail if isinstance(exc.detail, str) and exc.detail.strip() else 'Ошибка запроса'
    return _api_error(message, exc.status_code, exc.headers)


@app.exception_handler(RequestValidationError)
async def api_validation_exception_handler(request: Request, exc: RequestValidationError):
    if not request.url.path.startswith('/api/'):
        return await request_validation_exception_handler(request, exc)
    return _api_error('Некорректный запрос', 422)

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

# Starlette's add_middleware() prepends to the middleware stack, so the middleware added
# LAST runs FIRST. require_login must run only after SessionMiddleware has populated
# request.session, so it's registered (via @app.middleware) before add_middleware(SessionMiddleware)
# below is called. db_connection_per_request (registered further down, between this function and
# add_middleware(SessionMiddleware)) must run BEFORE require_login so that require_login's own
# db.user_exists call also reuses the request-scoped connection — giving the execution order
# SessionMiddleware -> db_connection_per_request -> require_login -> route.
app.middleware('http')(require_login)


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


# Единственный источник истины — frontend/src/data/taskTransitions.json, читается и фронтендом
# (PlanningPage.tsx), и бэкендом, чтобы правила переходов статуса задачи не могли разойтись между
# ними (см. openspec/changes/shared-task-transitions-source).
with open(os.path.join(os.path.dirname(__file__), 'frontend', 'src', 'data', 'taskTransitions.json'),
          encoding='utf-8') as _f:
    VALID_TASK_TRANSITIONS = {k: set(v) for k, v in json.load(_f).items()}


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


# === API для задач ===

@app.get('/api/tasks/{team_id}')
def get_tasks_api(request: Request, team_id: int, offset: int = 0, limit: int = 20, search: str = "",
                  include_recent_completed: bool = False):
    """API для получения задач команды с пагинацией"""
    _require_team_access(request, team_id)
    search_val = search.strip() or None
    tasks = db.get_tasks_by_team(team_id, offset=offset, limit=limit, search=search_val,
                                 include_recent_completed=include_recent_completed)
    total = db.get_tasks_count_by_team(team_id, search=search_val,
                                       include_recent_completed=include_recent_completed)
    return {
        'tasks': [{'id': t['id'], 'name': t['name'], 'description': t['description'],
                   'criticality': t['criticality'], 'task_status': t['task_status'],
                   'segment_id': t['segment_id'], 'segment_name': t['segment_name'],
                   'completed_at': t['completed_at'],
                   'has_active_assignments': bool(t['has_active_assignments'])} for t in tasks],
        'total': total
    }


def _task_json(task):
    return {'id': task['id'], 'name': task['name'], 'description': task['description'],
            'criticality': task['criticality'], 'task_status': task['task_status'],
            'segment_id': task['segment_id'], 'segment_name': task['segment_name'],
            'completed_at': task['completed_at'],
            'has_active_assignments': bool(task['has_active_assignments'])}


@app.get('/api/task/{task_id}')
def get_task_api(request: Request, task_id: int):
    task = db.get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail='Работа не найдена')
    _require_team_access(request, task['team_id'])
    return _task_json(task)


@app.post('/api/task/{task_id}/restore')
def restore_task_api(request: Request, task_id: int):
    task = db.get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail='Работа не найдена')
    _require_team_access(request, task['team_id'])
    if request.state.role not in ('editor', 'admin'):
        raise HTTPException(status_code=403, detail='Недостаточно прав для восстановления работы')
    try:
        restored = db.restore_task(task_id, changed_by=request.session.get('user_id'))
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if not restored:
        raise HTTPException(status_code=404, detail='Работа не найдена')
    return {'success': True}


@app.get('/api/tasks/{team_id}/archive')
def get_tasks_archive_api(request: Request, team_id: int, offset: int = 0, limit: int = 20,
                          search: str = "", completed_from: Optional[date] = None,
                          completed_to: Optional[date] = None):
    _require_team_access(request, team_id)
    if offset < 0 or limit < 1 or limit > 100:
        raise HTTPException(status_code=422, detail='Некорректная пагинация')
    if completed_from and completed_to and completed_from > completed_to:
        raise HTTPException(status_code=422, detail='Начало периода позже окончания')
    search_val = search.strip() or None
    date_from = completed_from.isoformat() if completed_from else None
    date_to = completed_to.isoformat() if completed_to else None
    tasks = db.get_archived_tasks_by_team(team_id, offset, limit, search_val, date_from, date_to)
    total = db.get_archived_tasks_count_by_team(team_id, search_val, date_from, date_to)
    return {'tasks': [_task_json(task) for task in tasks], 'total': total}


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

    try:
        with db.composite_transaction():
            task_id = int(db.create_or_update_task(
                data.task_id, data.team_id, name, description, data.criticality,
                segment_id=data.segment_id,
                changed_by=request.session.get('user_id'),
            ))

            if data.dependency_ids is not None:
                if data.dependency_ids and db.has_dependency_cycle(task_id, data.dependency_ids):
                    raise TaskDependencyCycleError
                db.set_task_dependencies(task_id, data.dependency_ids)
    except TaskDependencyCycleError:
        return JSONResponse({'error': 'Обнаружена циклическая зависимость'}, status_code=400)

    return {'id': task_id, 'success': True}


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


if __name__ == '__main__':
    import uvicorn

    cert, key = get_cert()
    if cert and key:
        uvicorn.run(app, port=5093, host="0.0.0.0", ssl_keyfile=key, ssl_certfile=cert)
    else:
        uvicorn.run(app, port=5093, host="0.0.0.0")
