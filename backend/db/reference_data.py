from backend.db.connection import backend as _backend, with_db_connection
from backend.db.errors import IntegrityConstraintError
from backend.db.grouping import group_rows

# === SEGMENTS CRUD ===
@with_db_connection(commit_on_success=False)
def get_all_segments(conn):
    """Получить все сегменты"""
    rows = conn.execute('SELECT id, name FROM segments ORDER BY name').fetchall()
    return [{'id': r['id'], 'name': r['name']} for r in rows]


@with_db_connection(write=True)
def create_segment(conn, name):
    """Создать сегмент"""
    try:
        cursor = _backend.insert_id(conn, f'INSERT INTO segments (name) VALUES ({_backend.placeholder})', (name.strip(),))
    except _backend.duplicate_error as exc:
        if not _backend.is_unique(exc):
            raise
        raise IntegrityConstraintError('Сегмент с таким названием уже существует')
    return cursor


@with_db_connection(write=True)
def update_segment(conn, segment_id, name):
    """Обновить сегмент"""
    try:
        conn.execute(f'UPDATE segments SET name = {_backend.placeholder} WHERE id = {_backend.placeholder}', (name.strip(), segment_id))
    except _backend.duplicate_error as exc:
        if not _backend.is_unique(exc):
            raise
        raise IntegrityConstraintError('Сегмент с таким названием уже существует')


@with_db_connection(write=True)
def delete_segment(conn, segment_id):
    """Удалить сегмент. Падает с IntegrityConstraintError, если сегмент ещё используется в tasks/
    block_templates (FK без ON DELETE) — маршрут превращает это в 400, как и для blocks/teams."""
    try:
        conn.execute(f'DELETE FROM segments WHERE id = {_backend.placeholder}', (segment_id,))
    except _backend.integrity_error as exc:
        if not _backend.is_foreign_key(exc):
            raise
        raise IntegrityConstraintError('Нельзя удалить сегмент: он используется в задачах или шаблонах блоков')


# === BLOCKS CRUD ===
@with_db_connection(commit_on_success=False)
def get_all_blocks(conn):
    """Получить все блоки"""
    rows = conn.execute('SELECT id, name FROM blocks ORDER BY name').fetchall()
    return [{'id': r['id'], 'name': r['name']} for r in rows]


@with_db_connection(write=True)
def create_block(conn, name):
    """Создать блок"""
    name = name.strip().upper()
    try:
        cursor = _backend.insert_id(conn, f'INSERT INTO blocks (name) VALUES ({_backend.placeholder})', (name,))
    except _backend.duplicate_error as exc:
        if not _backend.is_unique(exc):
            raise
        raise IntegrityConstraintError('Блок с таким названием уже существует')
    return cursor


@with_db_connection(write=True)
def delete_block(conn, block_id):
    """Удалить блок (template_blocks.block_id — ON DELETE CASCADE, поэтому удаление автоматически
    убирает блок из всех шаблонов; физически не может нарушить внешний ключ)"""
    conn.execute(f'DELETE FROM blocks WHERE id = {_backend.placeholder}', (block_id,))


# === BLOCK TEMPLATES CRUD ===
def _get_template_blocks(conn, template_id):
    """Блоки шаблона (id, name, shift_days), упорядоченные по смещению и имени — общий запрос для
    get_all_templates/get_template_by_id/get_team_allowed_templates."""
    blocks = conn.execute(
        f'''SELECT b.id, b.name, tb.schedule_offset AS shift_days
           FROM template_blocks tb
           JOIN blocks b ON tb.block_id = b.id
           WHERE tb.template_id = {_backend.placeholder}
           ORDER BY tb.schedule_offset ASC, b.name ASC''',
        (template_id,)
    ).fetchall()
    return [{'id': b['id'], 'name': b['name'], 'shift_days': b['shift_days']} for b in blocks]


def _get_template_blocks_map(conn, template_ids):
    if not template_ids:
        return {}
    placeholders = _backend.placeholders(len(template_ids))
    rows = conn.execute(
        f'''SELECT tb.template_id, b.id, b.name, tb.schedule_offset AS shift_days
            FROM template_blocks tb
            JOIN blocks b ON tb.block_id = b.id
            WHERE tb.template_id IN ({placeholders})
            ORDER BY tb.template_id, tb.schedule_offset ASC, b.name ASC''',
        template_ids,
    ).fetchall()
    return {
        template_id: [
            {'id': row['id'], 'name': row['name'], 'shift_days': row['shift_days']}
            for row in entries
        ]
        for template_id, entries in group_rows(rows, 'template_id').items()
    }


@with_db_connection(commit_on_success=False)
def get_all_templates(conn):
    """Получить все шаблоны блоков с их блоками, смещениями и сегментом"""
    tmpls = conn.execute('SELECT id, name, segment_id FROM block_templates ORDER BY name').fetchall()
    blocks_by_template = _get_template_blocks_map(conn, [template['id'] for template in tmpls])
    result = []
    for t in tmpls:
        result.append({
            'id': t['id'],
            'name': t['name'],
            'segment_id': t['segment_id'],
            'blocks': blocks_by_template.get(t['id'], [])
        })
    return result


@with_db_connection(commit_on_success=False)
def get_template_by_id(conn, template_id):
    """Получить шаблон по ID с блоками и сегментом"""
    t = conn.execute(f'SELECT id, name, segment_id FROM block_templates WHERE id = {_backend.placeholder}', (template_id,)).fetchone()
    if not t:
        return None
    return {
        'id': t['id'],
        'name': t['name'],
        'segment_id': t['segment_id'],
        'blocks': _get_template_blocks(conn, template_id)
    }


def _set_template_blocks(conn, template_id, entries):
    """Заменить блоки шаблона (без коммита). entries=[{block_id, shift_days}]"""
    conn.execute(f'DELETE FROM template_blocks WHERE template_id = {_backend.placeholder}', (template_id,))
    for e in (entries or []):
        try:
            block_id = int(e.get('block_id'))
            shift_days = int(e.get('shift_days', 0) or 0)
        except (TypeError, ValueError):
            continue
        conn.execute(
            f'INSERT INTO template_blocks (template_id, block_id, schedule_offset) VALUES ({_backend.placeholder}, {_backend.placeholder}, {_backend.placeholder}){_backend.conflict_ignore(("template_id", "block_id"))}',
            (template_id, block_id, shift_days)
        )


@with_db_connection(write=True)
def create_template(conn, name, segment_id, entries=None):
    """Создать шаблон блоков"""
    try:
        cursor = _backend.insert_id(
            conn, f'INSERT INTO block_templates (name, segment_id) VALUES ({_backend.placeholder}, {_backend.placeholder})', (name.strip(), segment_id)
        )
    except _backend.duplicate_error as exc:
        if not _backend.is_unique(exc):
            raise
        raise IntegrityConstraintError('Шаблон с таким названием уже существует')
    template_id = cursor
    _set_template_blocks(conn, template_id, entries)
    return template_id


@with_db_connection(write=True)
def update_template(conn, template_id, name, segment_id, entries=None):
    """Обновить шаблон и его блоки, сохраняя сегмент связанных работ."""
    _backend.begin_write(conn)
    existing = conn.execute(f'SELECT segment_id FROM block_templates WHERE id = {_backend.placeholder}', (template_id,)).fetchone()
    if existing and existing['segment_id'] != segment_id:
        _check_template_unused(conn, template_id)
    try:
        conn.execute(
            f'UPDATE block_templates SET name = {_backend.placeholder}, segment_id = {_backend.placeholder} WHERE id = {_backend.placeholder}', (name.strip(), segment_id, template_id)
        )
    except _backend.duplicate_error as exc:
        if not _backend.is_unique(exc):
            raise
        raise IntegrityConstraintError('Шаблон с таким названием уже существует')
    _set_template_blocks(conn, template_id, entries)


@with_db_connection(write=True)
def delete_template(conn, template_id):
    """Удалить шаблон (записи template_blocks и team_templates удаляются каскадно — оба ON DELETE
    CASCADE на template_id, поэтому физически не может нарушить внешний ключ)"""
    _backend.begin_write(conn)
    _check_template_unused(conn, template_id)
    conn.execute(f'DELETE FROM block_templates WHERE id = {_backend.placeholder}', (template_id,))


def _check_template_unused(conn, template_id):
    if conn.execute(f'SELECT 1 FROM tasks WHERE completion_template_id = {_backend.placeholder} LIMIT 1', (template_id,)).fetchone():
        raise IntegrityConstraintError('Шаблон используется работами: удаление и смена сегмента запрещены')
