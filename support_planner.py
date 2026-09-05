import os
import logging
import re
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

import db
from routers.assignments import router as assignments_router
from routers.freeze_days import router as freeze_days_router
from routers.debug import LOG_PATH, router as debug_router
from routers.journal import router as journal_router
from routers.notifications import router as notifications_router
from routers.reference_data import router as reference_data_router
from routers.shell import register_shell
from routers.task_dependencies import router as task_dependencies_router
from routers.tasks import router as tasks_router
from routers.teams import router as teams_router
from routers.users import router as users_router
from ssl_context import get_cert


_SECRET_LOG_PATTERN = re.compile(r'(?i)(password|token|cookie|secret)(\s*[=:]\s*)[^\s,;]+')
_DEBUG_LOG_POLL_PATTERN = re.compile(r'\bGET\s+/api/debug/logs(?:\?|\s)')


def _is_debug_log_poll_access(record, rendered: str) -> bool:
    return record.name == 'uvicorn.access' and bool(_DEBUG_LOG_POLL_PATTERN.search(rendered))


app = FastAPI()
app.include_router(reference_data_router)
app.include_router(freeze_days_router)
app.include_router(teams_router)
app.include_router(users_router)
app.include_router(assignments_router)
app.include_router(task_dependencies_router)
app.include_router(tasks_router)
app.include_router(journal_router)
app.include_router(notifications_router)
app.include_router(debug_router)
register_shell(app)


def _configure_application_logging():
    class RedactingFilter(logging.Filter):
        def filter(self, record):
            rendered = record.getMessage()
            if _is_debug_log_poll_access(record, rendered):
                return False
            record.msg = _SECRET_LOG_PATTERN.sub(r'\1\2[REDACTED]', rendered)
            record.args = ()
            return True

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    existing = next((item for item in root_logger.handlers if isinstance(item, RotatingFileHandler) and item.baseFilename.endswith(LOG_PATH)), None)
    if existing is None:
        existing = RotatingFileHandler(LOG_PATH, maxBytes=2_000_000, backupCount=3, encoding='utf-8')
        existing.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s'))
        existing.addFilter(RedactingFilter())
        root_logger.addHandler(existing)
    for logger_name in ('uvicorn', 'uvicorn.error', 'uvicorn.access', 'support_planner'):
        named_logger = logging.getLogger(logger_name)
        if existing not in named_logger.handlers:
            named_logger.addHandler(existing)
        named_logger.propagate = False


_configure_application_logging()


def _api_error(message: str, status_code: int, headers=None) -> JSONResponse:
    return JSONResponse({'error': message}, status_code=status_code, headers=headers)


@app.exception_handler(HTTPException)
async def api_http_exception_handler(request: Request, exc: HTTPException):
    if not request.url.path.startswith('/api/'):
        if exc.status_code == 401:
            return RedirectResponse(url='/login', status_code=302)
        if exc.status_code == 403:
            return RedirectResponse(url='/planning', status_code=302)
        return await http_exception_handler(request, exc)
    message = exc.detail if isinstance(exc.detail, str) and exc.detail.strip() else 'Ошибка запроса'
    return _api_error(message, exc.status_code, exc.headers)


@app.exception_handler(RequestValidationError)
async def api_validation_exception_handler(request: Request, exc: RequestValidationError):
    if not request.url.path.startswith('/api/'):
        return await request_validation_exception_handler(request, exc)
    return _api_error('Некорректный запрос', 422)


_SESSION_SECRET_KEY = os.environ.get('SESSION_SECRET_KEY')
if not _SESSION_SECRET_KEY:
    _SESSION_SECRET_KEY = 'dev-insecure-secret-change-me'
    print(
        'WARNING: SESSION_SECRET_KEY не задан, используется небезопасный ключ по умолчанию '
        '(сессии не переживут смену ключа; задайте переменную окружения для продакшена)'
    )


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


if __name__ == '__main__':
    import uvicorn

    cert, key = get_cert()
    if cert and key:
        uvicorn.run(app, port=5093, host='0.0.0.0', ssl_keyfile=key, ssl_certfile=cert, log_config=None)
    else:
        uvicorn.run(app, port=5093, host='0.0.0.0', log_config=None)
