from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

import db
from access_control import require_editor, require_user
from api_models import FreezeDayIn, FreezeDayMonthIn


router = APIRouter()


@router.get('/api/freeze-days', dependencies=[Depends(require_user)])
def get_freeze_days_api():
    return db.get_all_freeze_days()


@router.post('/api/freeze-days', dependencies=[Depends(require_editor)])
def add_freeze_day_api(data: FreezeDayIn):
    if data.date:
        return {'success': db.add_freeze_day(data.date)}
    if data.start_date and data.end_date:
        count = db.add_freeze_range(data.start_date, data.end_date)
        return {'success': True, 'count': count}
    return JSONResponse({'error': 'Date or range required'}, status_code=400)


@router.put('/api/freeze-days/month', dependencies=[Depends(require_editor)])
def set_freeze_month_api(data: FreezeDayMonthIn):
    db.set_freeze_days_for_month(data.year, data.month, data.days)
    return {'success': True}


@router.delete('/api/freeze-days/month/{year}/{month}', dependencies=[Depends(require_editor)])
def delete_freeze_month_api(year: int, month: int):
    db.delete_freeze_days_by_month(year, month)
    return {'success': True}


@router.delete('/api/freeze-days/{date_str:path}', dependencies=[Depends(require_editor)])
def delete_freeze_day_api(date_str: str):
    db.remove_freeze_day(date_str)
    return {'success': True}
