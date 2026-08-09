from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

import db
from access_control import require_editor, require_user
from api_models import BlockIn, BlockTemplateIn, SegmentIn


router = APIRouter()


@router.get('/api/blocks', dependencies=[Depends(require_user)])
def get_blocks_api():
    return db.get_all_blocks()


@router.post('/api/blocks', dependencies=[Depends(require_editor)])
def create_block_api(data: BlockIn):
    name = (data.name or '').strip()
    if not name:
        return JSONResponse({'error': 'Name required'}, status_code=400)
    try:
        return {'id': db.create_block(name), 'success': True}
    except db.IntegrityConstraintError as exc:
        return JSONResponse({'error': str(exc)}, status_code=400)


@router.delete('/api/blocks/{block_id}', dependencies=[Depends(require_editor)])
def delete_block_api(block_id: int):
    db.delete_block(block_id)
    return {'success': True}


@router.get('/api/block-templates', dependencies=[Depends(require_user)])
def get_templates_api():
    return db.get_all_templates()


@router.post('/api/block-templates', dependencies=[Depends(require_editor)])
def create_template_api(data: BlockTemplateIn):
    name = (data.name or '').strip()
    if not name:
        return JSONResponse({'error': 'Name required'}, status_code=400)
    if not data.segment_id or not any(s['id'] == data.segment_id for s in db.get_all_segments()):
        return JSONResponse({'error': 'Указан несуществующий сегмент'}, status_code=400)
    entries = [{'block_id': entry.block_id, 'shift_days': entry.shift_days} for entry in (data.entries or [])]
    try:
        return {'id': db.create_template(name, data.segment_id, entries), 'success': True}
    except db.IntegrityConstraintError as exc:
        return JSONResponse({'error': str(exc)}, status_code=400)


@router.put('/api/block-templates/{template_id}', dependencies=[Depends(require_editor)])
def update_template_api(template_id: int, data: BlockTemplateIn):
    name = (data.name or '').strip()
    if not name:
        return JSONResponse({'error': 'Name required'}, status_code=400)
    if not data.segment_id or not any(s['id'] == data.segment_id for s in db.get_all_segments()):
        return JSONResponse({'error': 'Указан несуществующий сегмент'}, status_code=400)
    if not db.get_template_by_id(template_id):
        return JSONResponse({'error': 'Template not found'}, status_code=404)
    entries = [{'block_id': entry.block_id, 'shift_days': entry.shift_days} for entry in (data.entries or [])]
    try:
        db.update_template(template_id, name, data.segment_id, entries)
        return {'success': True}
    except db.IntegrityConstraintError as exc:
        return JSONResponse({'error': str(exc)}, status_code=400)


@router.delete('/api/block-templates/{template_id}', dependencies=[Depends(require_editor)])
def delete_template_api(template_id: int):
    db.delete_template(template_id)
    return {'success': True}


@router.get('/api/segments', dependencies=[Depends(require_user)])
def get_segments_api():
    return db.get_all_segments()


@router.post('/api/segments', dependencies=[Depends(require_editor)])
def create_segment_api(data: SegmentIn):
    name = (data.name or '').strip()
    if not name:
        return JSONResponse({'error': 'Name required'}, status_code=400)
    try:
        return {'id': db.create_segment(name), 'success': True}
    except db.IntegrityConstraintError as exc:
        return JSONResponse({'error': str(exc)}, status_code=400)


@router.put('/api/segments/{segment_id}', dependencies=[Depends(require_editor)])
def update_segment_api(segment_id: int, data: SegmentIn):
    name = (data.name or '').strip()
    if not name:
        return JSONResponse({'error': 'Name required'}, status_code=400)
    try:
        db.update_segment(segment_id, name)
        return {'success': True}
    except db.IntegrityConstraintError as exc:
        return JSONResponse({'error': str(exc)}, status_code=400)


@router.delete('/api/segments/{segment_id}', dependencies=[Depends(require_editor)])
def delete_segment_api(segment_id: int):
    try:
        db.delete_segment(segment_id)
        return {'success': True}
    except db.IntegrityConstraintError as exc:
        return JSONResponse({'error': str(exc)}, status_code=400)
