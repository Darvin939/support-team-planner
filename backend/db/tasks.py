import json
import uuid
from datetime import date, timedelta

from backend.db.connection import backend as _backend, with_db_connection
from backend.db.errors import IntegrityConstraintError
from backend.db.search import matching_ids_clause, task_matches
from backend.task_rules import is_terminal_task_status, terminal_task_status_sql

_PRIORITY_GAP = 1000
_UNCHANGED = object()


def _active_task_filter(qualified=False):
    prefix = 'tasks.' if qualified else ''
    predicate, params = terminal_task_status_sql(f'{prefix}task_status', negated=True, placeholder=_backend.placeholder)
    return f'AND {predicate}', list(params)

# === TASKS CRUD ===
def _fuzzy_search_clause(search, name_col='name', description_col='description', conn=None,
                         candidate_where=None, candidate_params=()):
    """Строит WHERE-фрагмент и параметры для нечёткого поиска задач по словам: каждое слово
    должно совпасть (через fuzzy_word_in) с name ИЛИ description. Пустой search -> ("", []).
    name_col/description_col позволяют квалифицировать колонки при JOIN (см. get_tasks_by_team)."""
    if not search or not search.split():
        return "", []
    if _backend.name == 'postgresql':
        clause, params = matching_ids_clause(
            conn, _backend,
            'SELECT tasks.id, tasks.name, tasks.description FROM tasks WHERE ' + candidate_where,
            candidate_params, lambda row: task_matches(row[1], row[2], search),
            'tasks.id' if '.' in name_col else 'id',
        )
        return 'AND ' + clause, params
    words = search.split()
    word_clauses = " AND ".join(
        f"(fuzzy_word_in({name_col}, {_backend.placeholder}) OR fuzzy_word_in({description_col}, {_backend.placeholder}))" for _ in words
    )
    params = []
    for word in words:
        params += [word, word]
    return f"AND ({word_clauses})", params


@with_db_connection(commit_on_success=False)
def get_tasks_by_team(conn, team_id, offset=0, limit=10, search=None):
    """Получить задачи команды с пагинацией и поиском"""
    completed_clause, completed_params = _active_task_filter(qualified=True)
    params = [team_id]
    params += completed_params
    search_clause, search_params = _fuzzy_search_clause(
        search, 'tasks.name', 'tasks.description', conn,
        f'tasks.team_id = {_backend.placeholder} AND tasks.is_deleted = 0 {completed_clause}', params,
    )
    params += search_params
    params += [limit, offset]
    # @formatter:off
    return conn.execute(
        f'''SELECT tasks.id, tasks.name, tasks.description, tasks.instruction_url,
                   tasks.criticality, tasks.task_status, tasks.psi_status,
                   tasks.segment_id, segments.name AS segment_name, tasks.completed_at,
                   tasks.completion_template_id, bt.name AS completion_template_name,
                   EXISTS(SELECT 1 FROM assignments a WHERE a.task_id = tasks.id AND a.is_deleted = 0)
                       AS has_assignments,
                   EXISTS(SELECT 1 FROM assignments a WHERE a.task_id = tasks.id AND a.is_deleted = 0
                          AND a.status NOT IN ('new', 'cancelled', 'unsuccessful')) AS has_active_assignments
            FROM tasks
            JOIN segments ON tasks.segment_id = segments.id
            LEFT JOIN block_templates bt ON bt.id = tasks.completion_template_id
            WHERE tasks.team_id = {_backend.placeholder}
              AND tasks.is_deleted = 0
            {completed_clause}
            {search_clause}
            ORDER BY CASE tasks.criticality
                         WHEN 'high'   THEN 0
                         WHEN 'medium' THEN 1
                         WHEN 'low'    THEN 2
                         ELSE 3
                         END,
                     tasks.priority DESC, tasks.id
            LIMIT {_backend.placeholder} OFFSET {_backend.placeholder}''',
        params
    ).fetchall()
    # @formatter:on


@with_db_connection(commit_on_success=False)
def get_tasks_count_by_team(conn, team_id, search=None):
    """Получить общее количество задач команды (с учётом поиска)"""
    completed_clause, completed_params = _active_task_filter()
    params = [team_id]
    params += completed_params
    search_clause, search_params = _fuzzy_search_clause(
        search, conn=conn,
        candidate_where=f'team_id = {_backend.placeholder} AND is_deleted = 0 {completed_clause}',
        candidate_params=params,
    )
    params += search_params
    return conn.execute(
        f"SELECT COUNT(*) FROM tasks WHERE team_id = {_backend.placeholder} AND is_deleted = 0 {completed_clause} {search_clause}",
        params
    ).fetchone()[0]


@with_db_connection(commit_on_success=False)
def get_task_by_id(conn, task_id):
    return conn.execute(
        f'''SELECT tasks.id, tasks.team_id, tasks.name, tasks.description, tasks.instruction_url, tasks.criticality,
                  tasks.task_status, tasks.psi_status, tasks.segment_id, segments.name AS segment_name,
                  tasks.completed_at,
                  tasks.completion_template_id, bt.name AS completion_template_name,
                  EXISTS(SELECT 1 FROM assignments a WHERE a.task_id = tasks.id AND a.is_deleted = 0)
                      AS has_assignments,
                  EXISTS(SELECT 1 FROM assignments a WHERE a.task_id = tasks.id AND a.is_deleted = 0
                         AND a.status NOT IN ('new', 'cancelled', 'unsuccessful')) AS has_active_assignments
             FROM tasks JOIN segments ON tasks.segment_id = segments.id
             LEFT JOIN block_templates bt ON bt.id = tasks.completion_template_id
            WHERE tasks.id = {_backend.placeholder} AND tasks.is_deleted = 0''',
        (task_id,),
    ).fetchone()


def _archive_filter(search, completed_from, completed_to, conn=None, team_id=None):
    terminal_clause, terminal_params = terminal_task_status_sql('tasks.task_status', placeholder=_backend.placeholder)
    clauses = [terminal_clause]
    params = list(terminal_params)
    if completed_from:
        clauses.append(f"tasks.completed_at >= {_backend.placeholder}")
        params.append(completed_from + ' 00:00:00')
    if completed_to:
        if completed_to == date.max.isoformat():
            clauses.append(f"tasks.completed_at <= {_backend.placeholder}")
            params.append(completed_to + ' 23:59:59')
        else:
            clauses.append(f"tasks.completed_at < {_backend.placeholder}")
            params.append((date.fromisoformat(completed_to) + timedelta(days=1)).isoformat() + ' 00:00:00')
    search_clause, search_params = _fuzzy_search_clause(
        search, 'tasks.name', 'tasks.description', conn,
        f'tasks.team_id = {_backend.placeholder} AND tasks.is_deleted = 0 AND ' + ' AND '.join(clauses),
        [team_id, *params],
    )
    if search_clause:
        clauses.append(search_clause.removeprefix('AND '))
        params.extend(search_params)
    return ' AND '.join(clauses), params


@with_db_connection(commit_on_success=False)
def get_archived_tasks_by_team(conn, team_id, offset=0, limit=20, search=None,
                               completed_from=None, completed_to=None):
    filters, filter_params = _archive_filter(search, completed_from, completed_to, conn, team_id)
    return conn.execute(
        f'''SELECT tasks.id, tasks.name, tasks.description, tasks.instruction_url,
                   tasks.criticality, tasks.task_status, tasks.psi_status,
                   tasks.segment_id, segments.name AS segment_name, tasks.completed_at,
                   tasks.completion_template_id, bt.name AS completion_template_name,
                   EXISTS(SELECT 1 FROM assignments a WHERE a.task_id = tasks.id AND a.is_deleted = 0)
                       AS has_assignments,
                   EXISTS(SELECT 1 FROM assignments a WHERE a.task_id = tasks.id AND a.is_deleted = 0
                          AND a.status NOT IN ('new', 'cancelled', 'unsuccessful')) AS has_active_assignments
              FROM tasks JOIN segments ON tasks.segment_id = segments.id
              LEFT JOIN block_templates bt ON bt.id = tasks.completion_template_id
             WHERE tasks.team_id = {_backend.placeholder} AND tasks.is_deleted = 0 AND {filters}
             ORDER BY tasks.completed_at IS NULL, tasks.completed_at DESC, tasks.id DESC
             LIMIT {_backend.placeholder} OFFSET {_backend.placeholder}''',
        [team_id, *filter_params, limit, offset],
    ).fetchall()


@with_db_connection(commit_on_success=False)
def get_archived_tasks_count_by_team(conn, team_id, search=None, completed_from=None, completed_to=None):
    filters, filter_params = _archive_filter(search, completed_from, completed_to, conn, team_id)
    return conn.execute(
        f'''SELECT COUNT(*) FROM tasks
             WHERE team_id = {_backend.placeholder} AND is_deleted = 0 AND {filters.replace('tasks.', '')}''',
        [team_id, *filter_params],
    ).fetchone()[0]


def _priority_at_tier_end(conn, team_id, criticality, exclude_task_id=None):
    """Значение priority, ставящее задачу в конец (наименее приоритетной позиции) её пары
    (team_id, criticality) — используется и при создании задачи, и при переносе существующей
    задачи в другой уровень критичности."""
    exclude_clause = f'AND id != {_backend.placeholder}' if exclude_task_id is not None else ''
    params = [team_id, criticality] + ([exclude_task_id] if exclude_task_id is not None else [])
    min_priority = conn.execute(
        f'SELECT MIN(priority) FROM tasks WHERE team_id = {_backend.placeholder} AND criticality = {_backend.placeholder} AND is_deleted = 0 {exclude_clause}',
        params
    ).fetchone()[0]
    return (min_priority - _PRIORITY_GAP) if min_priority is not None else 0


def _record_task_history(conn, task_id, action, field_name=None, old_value=None, new_value=None, changed_by=None,
                         event_id=None):
    conn.execute(
        f'''INSERT INTO task_history (task_id, action, field_name, old_value, new_value, changed_by_user_id, event_id)
           VALUES ({_backend.placeholder}, {_backend.placeholder}, {_backend.placeholder}, {_backend.placeholder}, {_backend.placeholder}, {_backend.placeholder}, {_backend.placeholder})''',
        (task_id, action, field_name, old_value, new_value, changed_by, event_id or uuid.uuid4().hex))


def _record_assignment_history(conn, assignment_id, task_id, date_str, action, field_name=None, old_value=None,
                                new_value=None, changed_by=None, event_id=None):
    conn.execute(
        f'''INSERT INTO assignment_history
               (assignment_id, task_id, date, action, field_name, old_value, new_value, changed_by_user_id, event_id)
           VALUES ({_backend.placeholder}, {_backend.placeholder}, {_backend.placeholder}, {_backend.placeholder}, {_backend.placeholder}, {_backend.placeholder}, {_backend.placeholder}, {_backend.placeholder}, {_backend.placeholder})''',
        (assignment_id, task_id, date_str, action, field_name, old_value, new_value, changed_by,
         event_id or uuid.uuid4().hex))


@with_db_connection(commit_on_success=False)
def task_exists(conn, task_id):
    """Проверить существование (неудалённой) задачи"""
    return conn.execute(f'SELECT 1 FROM tasks WHERE id = {_backend.placeholder} AND is_deleted = 0', (task_id,)).fetchone()


@with_db_connection(commit_on_success=False)
def task_has_active_assignments(conn, task_id):
    """Есть ли у задачи неудалённые назначения с активным рабочим статусом."""
    row = conn.execute(
        f"SELECT 1 FROM assignments WHERE task_id = {_backend.placeholder} AND is_deleted = 0 "
        "AND status NOT IN ('new', 'cancelled', 'unsuccessful') LIMIT 1",
        (task_id,)
    ).fetchone()
    return row is not None


@with_db_connection(commit_on_success=False)
def task_has_any_assignments(conn, task_id):
    """Есть ли у работы хотя бы одно неудалённое назначение."""
    return conn.execute(
        f'SELECT 1 FROM assignments WHERE task_id = {_backend.placeholder} AND is_deleted = 0 LIMIT 1', (task_id,)
    ).fetchone() is not None


@with_db_connection(write=True)
def create_or_update_task(conn, task_id, team_id, name, description, criticality='medium', psi_status='not_required',
                           segment_id=None, changed_by=None, instruction_url=None,
                           completion_template_id=_UNCHANGED):
    """Создать или обновить задачу. priority этой функцией напрямую не редактируется — им
    управляют reorder_team_tasks/move_task_to_edge — за исключением одного случая: если на UPDATE
    меняется criticality, задача пересчитывается в конец списка НОВОГО уровня критичности (как
    новая задача), т.к. её старое числовое значение priority больше ничего не значит относительно
    задач другого уровня. На CREATE новая задача всегда уходит в конец списка своего уровня
    критичности (наименьший приоритет внутри него)."""
    _backend.begin_write(conn)
    event_id = uuid.uuid4().hex
    existing = conn.execute(
        'SELECT name, description, instruction_url, criticality, psi_status, priority, segment_id, '
        'completion_template_id, team_id, task_status, is_deleted '
        f'FROM tasks WHERE id = {_backend.placeholder}',
                             (task_id,)).fetchone()
    # Omission preserves existing values and permits trusted legacy data imports.
    supplied_template = completion_template_id is not _UNCHANGED
    if not supplied_template:
        completion_template_id = existing['completion_template_id'] if existing else None
    if existing:
        if existing['is_deleted'] or is_terminal_task_status(existing['task_status']):
            raise IntegrityConstraintError('Нельзя редактировать завершённую или отменённую работу')
        if existing['team_id'] != team_id:
            raise IntegrityConstraintError('Нельзя изменять команду работы')
        has_assignments = conn.execute(
            f'SELECT 1 FROM assignments WHERE task_id = {_backend.placeholder} AND is_deleted = 0 LIMIT 1', (task_id,)
        ).fetchone() is not None
        if has_assignments and (
            existing['segment_id'] != segment_id
            or (existing['completion_template_id'] is not None
                and existing['completion_template_id'] != completion_template_id)
        ):
            raise IntegrityConstraintError('Перед изменением сегмента или шаблона удалите все назначения работы')
        if existing['completion_template_id'] is not None and completion_template_id is None:
            raise IntegrityConstraintError('Шаблон раскатки обязателен')
    elif supplied_template and completion_template_id is None:
        raise IntegrityConstraintError('Выберите шаблон раскатки')
    selection_changed = (not existing or existing['segment_id'] != segment_id
                         or existing['completion_template_id'] != completion_template_id)
    if selection_changed and completion_template_id is not None:
        valid_template = conn.execute(
            f'''SELECT 1 FROM block_templates bt JOIN team_templates tt ON tt.template_id = bt.id
               WHERE bt.id = {_backend.placeholder} AND bt.segment_id = {_backend.placeholder} AND tt.team_id = {_backend.placeholder}''',
            (completion_template_id, segment_id, team_id),
        ).fetchone()
        if not valid_template:
            raise IntegrityConstraintError('Выберите разрешённый команде шаблон указанного сегмента')
    elif selection_changed and existing and existing['segment_id'] != segment_id:
        raise IntegrityConstraintError('При изменении сегмента выберите шаблон раскатки')
    if existing:
        for field, new_val in (('name', name), ('description', description),
                                ('instruction_url', instruction_url), ('criticality', criticality),
                                ('psi_status', psi_status),
                                ('segment_id', segment_id),
                                ('completion_template_id', completion_template_id)):
            old_val = existing[field]
            if old_val != new_val:
                _record_task_history(conn, task_id, 'update', field_name=field,
                                      old_value=old_val, new_value=new_val, changed_by=changed_by, event_id=event_id)
        new_priority = existing['priority']
        if criticality != existing['criticality']:
            new_priority = _priority_at_tier_end(conn, team_id, criticality, exclude_task_id=task_id)
            if new_priority != existing['priority']:
                _record_task_history(conn, task_id, 'update', field_name='priority',
                                      old_value=str(existing['priority']), new_value=str(new_priority),
                                      changed_by=changed_by, event_id=event_id)
        conn.execute(
            f'''UPDATE tasks
               SET name        = {_backend.placeholder},
                   description = {_backend.placeholder},
                   instruction_url = {_backend.placeholder},
                   criticality = {_backend.placeholder},
                   psi_status  = {_backend.placeholder},
                   segment_id  = {_backend.placeholder},
                   completion_template_id = {_backend.placeholder},
                   priority    = {_backend.placeholder}
               WHERE id = {_backend.placeholder}''',
            (name, description, instruction_url, criticality, psi_status, segment_id,
             completion_template_id, new_priority, task_id)
        )
    else:
        new_priority = _priority_at_tier_end(conn, team_id, criticality)
        cursor = _backend.insert_id(
            conn, 'INSERT INTO tasks '
            '(team_id, name, description, instruction_url, criticality, psi_status, segment_id, priority, '
            f'completion_template_id) VALUES ({_backend.placeholder}, {_backend.placeholder}, {_backend.placeholder}, {_backend.placeholder}, {_backend.placeholder}, {_backend.placeholder}, {_backend.placeholder}, {_backend.placeholder}, {_backend.placeholder})',
            (team_id, name, description, instruction_url, criticality, psi_status, segment_id, new_priority,
             completion_template_id)
        )
        task_id = cursor
        snapshot = json.dumps({'team_id': team_id, 'name': name, 'description': description,
                                'instruction_url': instruction_url,
                                'criticality': criticality, 'psi_status': psi_status,
                                'segment_id': segment_id, 'priority': new_priority,
                                'completion_template_id': completion_template_id},
                               ensure_ascii=False)
        _record_task_history(conn, task_id, 'create', new_value=snapshot, changed_by=changed_by, event_id=event_id)
    return task_id


@with_db_connection(write=True)
def reorder_team_tasks(conn, team_id, task_ids, changed_by=None):
    """Переупорядочить задачи в пределах уже загруженной страницы (drag-and-drop).

    task_ids — новый порядок ровно тех задач, что были на странице, от самой важной к наименее
    важной. Алгоритм не создаёт новых значений priority и никогда не "выходит" за диапазон
    страницы: берёт ТЕКУЩИЕ priority ровно этого набора задач, сортирует их по убыванию и
    раздаёт заново в новом порядке — первая задача нового порядка получает наибольшее из уже
    существующих значений, и т.д. Только реально изменившиеся строки попадают в историю.

    Все task_ids должны принадлежать одному уровню критичности — приоритет можно менять только
    внутри уровня, не поперёк него (граница обеспечивается и на фронтенде, но здесь — источник
    истины). Ни одна из задач не должна быть в терминальном статусе (done/cancelled) — приоритет
    завершённой/отменённой работы больше не имеет смысла менять."""
    if len(task_ids) != len(set(task_ids)):
        raise ValueError('Дублирующиеся task_id')
    if not task_ids:
        return True

    placeholders = _backend.placeholders(len(task_ids))
    rows = conn.execute(
        f'''SELECT id, priority, criticality, task_status FROM tasks
            WHERE id IN ({placeholders}) AND team_id = {_backend.placeholder} AND is_deleted = 0''',
        (*task_ids, team_id)
    ).fetchall()
    priority_by_id = {r['id']: r['priority'] for r in rows}
    if set(priority_by_id) != set(task_ids):
        raise ValueError('Некоторые задачи не найдены в этой команде или удалены')
    if len({r['criticality'] for r in rows}) > 1:
        raise ValueError('Приоритет можно менять только в пределах одного уровня критичности')
    if any(is_terminal_task_status(r['task_status']) for r in rows):
        raise ValueError('Нельзя менять приоритет завершённой или отменённой задачи')

    priorities_desc = sorted(priority_by_id.values(), reverse=True)
    for tid, new_priority in zip(task_ids, priorities_desc):
        old_priority = priority_by_id[tid]
        if old_priority == new_priority:
            continue
        _record_task_history(conn, tid, 'update', field_name='priority',
                              old_value=str(old_priority), new_value=str(new_priority), changed_by=changed_by)
        conn.execute(f'UPDATE tasks SET priority = {_backend.placeholder} WHERE id = {_backend.placeholder}', (new_priority, tid))
    return True


@with_db_connection(write=True)
def move_task_to_edge(conn, task_id, position, changed_by=None):
    """Переместить задачу в начало (position='start') или конец ('end') списка её уровня
    критичности внутри её команды (контекстное меню). team_id намеренно не принимается параметром —
    команда (и уровень критичности) определяются самой задачей, так что подделать их через
    фронтенд нельзя."""
    task = conn.execute(f'SELECT priority, team_id, criticality, task_status, is_deleted FROM tasks WHERE id = {_backend.placeholder}',
                         (task_id,)).fetchone()
    if not task or task['is_deleted']:
        raise ValueError('Задача не найдена')
    if is_terminal_task_status(task['task_status']):
        raise ValueError('Нельзя менять приоритет завершённой или отменённой задачи')

    agg_col = 'MAX(priority)' if position == 'start' else 'MIN(priority)'
    edge_row = conn.execute(
        f'SELECT {agg_col} AS edge FROM tasks WHERE team_id = {_backend.placeholder} AND criticality = {_backend.placeholder} AND is_deleted = 0 AND id != {_backend.placeholder}',
        (task['team_id'], task['criticality'], task_id)
    ).fetchone()
    edge = edge_row['edge']
    old_priority = task['priority']

    if edge is None:
        return True  # единственная задача команды — двигать некуда

    already_there = old_priority >= edge if position == 'start' else old_priority <= edge
    if already_there:
        return True  # уже на нужном краю — no-op

    new_priority = edge + _PRIORITY_GAP if position == 'start' else edge - _PRIORITY_GAP
    _record_task_history(conn, task_id, 'update', field_name='priority',
                          old_value=str(old_priority), new_value=str(new_priority), changed_by=changed_by)
    conn.execute(f'UPDATE tasks SET priority = {_backend.placeholder} WHERE id = {_backend.placeholder}', (new_priority, task_id))
    return True


@with_db_connection(write=True)
def delete_task(conn, task_id, changed_by=None):
    """Мягко удалить задачу (is_deleted=1, без физического DELETE) вместе со всеми её назначениями"""
    task = conn.execute(f'SELECT is_deleted FROM tasks WHERE id = {_backend.placeholder}', (task_id,)).fetchone()
    if not task or task['is_deleted']:
        return  # не существует или уже удалена — идемпотентно
    _record_task_history(conn, task_id, 'update', field_name='is_deleted',
                          old_value='0', new_value='1', changed_by=changed_by)
    conn.execute(f'UPDATE tasks SET is_deleted = 1 WHERE id = {_backend.placeholder}', (task_id,))
    assignments = conn.execute(
        f'SELECT id, date FROM assignments WHERE task_id = {_backend.placeholder} AND is_deleted = 0', (task_id,)
    ).fetchall()
    for a in assignments:
        _record_assignment_history(conn, a['id'], task_id, a['date'], 'update', field_name='is_deleted',
                                    old_value='0', new_value='1', changed_by=changed_by)
    conn.execute(f'UPDATE assignments SET is_deleted = 1 WHERE task_id = {_backend.placeholder} AND is_deleted = 0', (task_id,))


@with_db_connection(commit_on_success=False)
def get_task_status(conn, task_id):
    """Получить текущий статус задачи и признак удаления"""
    return conn.execute(f'SELECT task_status, psi_status, is_deleted FROM tasks WHERE id = {_backend.placeholder}', (task_id,)).fetchone()


@with_db_connection(commit_on_success=False)
def get_task_status_by_assignment(conn, assignment_id):
    """Получить статус задачи, признак её удаления и статус самого назначения по ID назначения"""
    return conn.execute(
        'SELECT t.task_status, t.psi_status, t.is_deleted, a.status AS assignment_status '
        f'FROM assignments a JOIN tasks t ON a.task_id = t.id WHERE a.id = {_backend.placeholder}',
        (assignment_id,)
    ).fetchone()


@with_db_connection(commit_on_success=False)
def validate_bulk_task_template(conn, task_id, template_id):
    """Старые bulk-клиенты могут подтвердить, но не заменить шаблон работы."""
    _backend.begin_write(conn)
    task = conn.execute(f'SELECT completion_template_id FROM tasks WHERE id = {_backend.placeholder} AND is_deleted = 0',
                        (task_id,)).fetchone()
    if not task or task['completion_template_id'] != template_id:
        raise IntegrityConstraintError('Шаблон выбирается в работе и не может быть изменён при автоназначении')


@with_db_connection(write=True)
def update_task_status(conn, task_id, new_status, changed_by=None):
    """Обновить статус задачи"""
    current = conn.execute(f"SELECT task_status FROM tasks WHERE id = {_backend.placeholder}", (task_id,)).fetchone()
    if current and current['task_status'] != new_status:
        _record_task_history(conn, task_id, 'update', field_name='task_status',
                              old_value=current['task_status'], new_value=new_status, changed_by=changed_by)
    old_status = current['task_status'] if current else None
    old_terminal = is_terminal_task_status(old_status)
    new_terminal = is_terminal_task_status(new_status)
    if new_terminal and not old_terminal:
        conn.execute(f"UPDATE tasks SET task_status = {_backend.placeholder}, completed_at = {_backend.now_sql} WHERE id = {_backend.placeholder}",
                     (new_status, task_id))
    elif old_terminal and not new_terminal:
        conn.execute(f"UPDATE tasks SET task_status = {_backend.placeholder}, completed_at = NULL WHERE id = {_backend.placeholder}", (new_status, task_id))
    else:
        conn.execute(f"UPDATE tasks SET task_status = {_backend.placeholder} WHERE id = {_backend.placeholder}", (new_status, task_id))
    return True


@with_db_connection(write=True)
def update_task_psi_status(conn, task_id, new_status, changed_by=None):
    """Обновить результат ПСИ работы с записью изменения в историю."""
    current = conn.execute(f'SELECT psi_status FROM tasks WHERE id = {_backend.placeholder}', (task_id,)).fetchone()
    if current and current['psi_status'] != new_status:
        _record_task_history(
            conn,
            task_id,
            'update',
            field_name='psi_status',
            old_value=current['psi_status'],
            new_value=new_status,
            changed_by=changed_by,
        )
        conn.execute(f'UPDATE tasks SET psi_status = {_backend.placeholder} WHERE id = {_backend.placeholder}', (new_status, task_id))
    return True


@with_db_connection(write=True)
def restore_task(conn, task_id, changed_by=None):
    """Restore a terminal task without changing its related entities."""
    current = conn.execute(
        f'SELECT task_status, is_deleted FROM tasks WHERE id = {_backend.placeholder}', (task_id,)
    ).fetchone()
    if not current or current['is_deleted']:
        return False
    if not is_terminal_task_status(current['task_status']):
        raise ValueError('Восстановить можно только завершённую или отменённую работу')
    _record_task_history(conn, task_id, 'update', field_name='task_status',
                         old_value=current['task_status'], new_value='new', changed_by=changed_by)
    conn.execute(
        f"UPDATE tasks SET task_status = 'new', completed_at = NULL WHERE id = {_backend.placeholder}",
        (task_id,),
    )
    return True
