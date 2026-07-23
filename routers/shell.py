import os

from fastapi import APIRouter, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

import auth
import db
from api_models import MyPasswordIn


router = APIRouter()
_REACT_DIST = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    'frontend',
    'dist',
)
_react_index_html = None


def _serve_react_index() -> str:
    global _react_index_html
    if _react_index_html is None:
        with open(os.path.join(_REACT_DIST, 'index.html'), encoding='utf-8') as index_file:
            _react_index_html = index_file.read()
    return _react_index_html


def register_shell(app: FastAPI) -> None:
    if os.path.isdir(_REACT_DIST):
        app.mount('/react-assets', StaticFiles(directory=_REACT_DIST), name='react-assets')
    app.include_router(router)


@router.get('/', response_class=HTMLResponse)
def root():
    return RedirectResponse(url='/planning', status_code=302)


@router.get('/login', response_class=HTMLResponse)
def login_page():
    return _serve_react_index()


@router.post('/login')
def login_submit(request: Request, login: str = Form(...), password: str = Form(...)):
    auth_row = db.get_user_auth_by_login(login.strip()) if login.strip() else None
    if not auth_row or not auth.verify_password(password, auth_row['password_hash']):
        return JSONResponse({'error': 'Неверный логин или пароль'}, status_code=401)
    request.session['user_id'] = auth_row['id']
    request.session['role'] = auth_row['role']
    return {'success': True}


@router.post('/logout')
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url='/login', status_code=302)


@router.get('/api/me')
def get_me(request: Request):
    user = db.get_user(request.session['user_id'])
    return {
        'user_id': user['id'],
        'role': user['role'],
        'last_name': user['last_name'],
        'first_name': user['first_name'],
        'middle_name': user['middle_name'],
    }


@router.put('/api/me')
def update_me_api(request: Request, data: MyPasswordIn):
    password_hash = auth.hash_password(data.password) if (data.password or '').strip() else None
    if password_hash is None:
        return JSONResponse({'error': 'Нечего обновлять'}, status_code=400)
    db.update_own_password(request.session['user_id'], password_hash)
    return {'success': True}


@router.get('/planning', response_class=HTMLResponse)
def planning_select():
    return _serve_react_index()


@router.get('/planning/{team_id}', response_class=HTMLResponse)
def planning(team_id: int):
    return _serve_react_index()


@router.get('/settings', response_class=HTMLResponse)
def settings_page():
    return _serve_react_index()


@router.get('/statistics', response_class=HTMLResponse)
def statistics_page():
    return _serve_react_index()


@router.get('/journal', response_class=HTMLResponse)
def journal_select():
    return _serve_react_index()


@router.get('/journal/{team_id}', response_class=HTMLResponse)
def journal_page(team_id: int):
    return _serve_react_index()
