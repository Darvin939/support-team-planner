from fastapi import APIRouter
from fastapi.responses import JSONResponse

import db
from api_models import BlockIn, BlockTemplateIn, SegmentIn


router = APIRouter()


@router.get('/api/blocks')
def get_blocks_api():
    return db.get_all_blocks()


@router.post('/api/blocks')
def create_block_api(data: BlockIn):
    name = (data.name or '').strip()
    if not name:
        return JSONResponse({'error': 'Name required'}, status_code=400)
    try:
        return {'id': db.create_block(name), 'success': True}
    except db.IntegrityConstraintError as exc:
        return JSONResponse({'error': str(exc)}, status_code=400)


@router.delete('/api/blocks/{block_id}')
def delete_block_api(block_id: int):
    db.delete_block(block_id)
    return {'success': True}


@router.get('/api/block-templates')
def get_templates_api():
    return db.get_all_templates()


@router.post('/api/block-templates')
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


@router.put('/api/block-templates/{template_id}')
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


@router.delete('/api/block-templates/{template_id}')
def delete_template_api(template_id: int):
    db.delete_template(template_id)
    return {'success': True}


@router.get('/api/segments')
def get_segments_api():
    return db.get_all_segments()


@router.post('/api/segments')
def create_segment_api(data: SegmentIn):
    name = (data.name or '').strip()
    if not name:
        return JSONResponse({'error': 'Name required'}, status_code=400)
    try:
        return {'id': db.create_segment(name), 'success': True}
    except db.IntegrityConstraintError as exc:
        return JSONResponse({'error': str(exc)}, status_code=400)


@router.put('/api/segments/{segment_id}')
def update_segment_api(segment_id: int, data: SegmentIn):
    name = (data.name or '').strip()
    if not name:
        return JSONResponse({'error': 'Name required'}, status_code=400)
    try:
        db.update_segment(segment_id, name)
        return {'success': True}
    except db.IntegrityConstraintError as exc:
        return JSONResponse({'error': str(exc)}, status_code=400)


@router.delete('/api/segments/{segment_id}')
def delete_segment_api(segment_id: int):
    try:
        db.delete_segment(segment_id)
        return {'success': True}
    except db.IntegrityConstraintError as exc:
        return JSONResponse({'error': str(exc)}, status_code=400)
