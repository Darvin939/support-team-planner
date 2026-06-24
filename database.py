import os
import sqlite3
from datetime import datetime, date, timedelta
from functools import wraps

DB_PATH = 'database.db'


def get_db_connection():
    """Получить соединение с базой данных"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON;')
    return conn


def with_db_connection(default_return=None, raise_on_error=True, commit_on_success=True):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            conn = get_db_connection()
            try:
                result = func(conn, *args, **kwargs)
                if commit_on_success:
                    conn.commit()
                return result
            except sqlite3.Error as e:
                if raise_on_error:
                    raise sqlite3.DatabaseError(e, func.__name__, args, kwargs)
                return default_return
            finally:
                conn.close()

        return wrapper

    return decorator


@with_db_connection()
def init_db(conn):
    """Инициализация базы данных"""
    cursor = conn.cursor()

    cursor.execute("PRAGMA foreign_keys = ON;")

    # Создание таблиц
    # @formatter:off
    cursor.executescript('''
        CREATE TABLE if NOT EXISTS teams (
            id INTEGER PRIMARY key autoincrement,
            name text NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS team_blocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            block_name TEXT NOT NULL,
            schedule_offset INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (team_id) REFERENCES teams (id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_team_blocks_team_id ON team_blocks (team_id);

        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY key autoincrement,
            last_name TEXT NOT NULL,
            first_name TEXT NOT NULL,
            middle_name TEXT,
            UNIQUE(last_name, first_name, middle_name)
        );
        
        CREATE TABLE if NOT EXISTS freeze_days (
            id INTEGER PRIMARY key autoincrement,
            date DATE NOT NULL UNIQUE
        );
        
        CREATE TABLE if NOT EXISTS tasks (
            id INTEGER PRIMARY key autoincrement,
            team_id INTEGER NOT NULL,
            name text NOT NULL,
            description text,
            criticality text NOT NULL DEFAULT 'medium',
            FOREIGN key (team_id) REFERENCES teams (id) ON DELETE cascade
        );
        
        CREATE TABLE if NOT EXISTS assignments (
            id INTEGER PRIMARY key autoincrement,
            task_id INTEGER NOT NULL,
            date DATE NOT NULL,
            block text,
            status text NOT NULL DEFAULT 'new',
            employee_id INTEGER,
            comment text,
            FOREIGN key (task_id) REFERENCES tasks (id) ON DELETE cascade,
            FOREIGN key (employee_id) REFERENCES employees (id),
            UNIQUE (task_id, date)
        );
        
        CREATE index if NOT EXISTS idx_assignments_task_id ON assignments (task_id);
        CREATE index if NOT EXISTS idx_assignments_date ON assignments (date);
        CREATE index if NOT EXISTS idx_assignments_status ON assignments (status);
        CREATE index if NOT EXISTS idx_tasks_team_id ON tasks (team_id);
        ''')
    # @formatter:on


@with_db_connection()
def ensure_schema(conn):
    """Догоняющая миграция: создаёт/чинит таблицу team_blocks на уже существующей БД.

    На некоторых БД таблица team_blocks могла быть создана раньше с
    ограничением UNIQUE(team_id, schedule_offset), которое не позволяет
    указать несколько блоков с одинаковым сдвигом. Если такое ограничение
    обнаружено, таблица пересобирается без него, данные сохраняются.
    """
    conn.execute('PRAGMA foreign_keys = OFF;')

    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='team_blocks'"
    ).fetchone()

    if row is None:
        conn.executescript('''
            CREATE TABLE team_blocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL,
                block_name TEXT NOT NULL,
                schedule_offset INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (team_id) REFERENCES teams (id) ON DELETE CASCADE
            );
        ''')
    else:
        existing_sql = (row['sql'] or row[0] or '')
        has_bad_unique = 'UNIQUE' in existing_sql.upper() and 'SCHEDULE_OFFSET' in existing_sql.upper()
        if has_bad_unique:
            conn.executescript('''
                ALTER TABLE team_blocks RENAME TO team_blocks_old;
                CREATE TABLE team_blocks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    team_id INTEGER NOT NULL,
                    block_name TEXT NOT NULL,
                    schedule_offset INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (team_id) REFERENCES teams (id) ON DELETE CASCADE
                );
                INSERT INTO team_blocks (id, team_id, block_name, schedule_offset)
                    SELECT id, team_id, block_name, schedule_offset FROM team_blocks_old;
                DROP TABLE team_blocks_old;
            ''')

    conn.execute('CREATE INDEX IF NOT EXISTS idx_team_blocks_team_id ON team_blocks (team_id);')
    conn.execute('PRAGMA foreign_keys = ON;')


# === TEAMS CRUD ===
@with_db_connection(commit_on_success=False)
def get_all_teams(conn):
    """Получить все команды"""
    return conn.execute('SELECT id, name FROM teams ORDER BY name').fetchall()


@with_db_connection(commit_on_success=False)
def get_all_teams_with_blocks(conn):
    """Получить все команды вместе с их блоками раскатки"""
    teams = conn.execute('SELECT id, name FROM teams ORDER BY name').fetchall()
    blocks = conn.execute(
        'SELECT id, team_id, block_name, schedule_offset FROM team_blocks ORDER BY schedule_offset ASC, block_name ASC'
    ).fetchall()

    blocks_by_team = {}
    for b in blocks:
        blocks_by_team.setdefault(b['team_id'], []).append({
            'id': b['id'],
            'name': b['block_name'],
            'shift_days': b['schedule_offset']
        })

    result = []
    for t in teams:
        result.append({
            'id': t['id'],
            'name': t['name'],
            'blocks': blocks_by_team.get(t['id'], [])
        })
    return result


@with_db_connection(commit_on_success=False)
def get_team_by_id(conn, team_id):
    """Получить команду по ID"""
    return conn.execute('SELECT id, name FROM teams WHERE id = ?', (team_id,)).fetchone()


@with_db_connection(commit_on_success=False)
def get_team_blocks(conn, team_id):
    """Получить блоки раскатки команды (сортировка по возрастанию сдвига)"""
    rows = conn.execute(
        'SELECT id, block_name, schedule_offset FROM team_blocks WHERE team_id = ? ORDER BY schedule_offset ASC, block_name ASC',
        (team_id,)
    ).fetchall()
    return [{'id': r['id'], 'name': r['block_name'], 'shift_days': r['schedule_offset']} for r in rows]


def _set_team_blocks(conn, team_id, blocks):
    """Заменить набор блоков команды (внутренняя функция, без коммита)"""
    conn.execute('DELETE FROM team_blocks WHERE team_id = ?', (team_id,))
    for b in (blocks or []):
        block_name = (b.get('name') or '').strip()
        if not block_name:
            continue
        try:
            shift_days = int(b.get('shift_days', 0) or 0)
        except (TypeError, ValueError):
            shift_days = 0
        conn.execute(
            'INSERT INTO team_blocks (team_id, block_name, schedule_offset) VALUES (?, ?, ?)',
            (team_id, block_name, shift_days)
        )


@with_db_connection(commit_on_success=False)
def create_team(conn, name, blocks=None):
    """Создать команду вместе с блоками раскатки"""
    cursor = conn.execute('INSERT INTO teams (name) VALUES (?)', (name,))
    team_id = cursor.lastrowid
    _set_team_blocks(conn, team_id, blocks)
    conn.commit()
    return team_id


@with_db_connection()
def update_team(conn, team_id, name, blocks=None):
    """Обновить команду и её блоки раскатки"""
    conn.execute('UPDATE teams SET name = ? WHERE id = ?', (name, team_id))
    _set_team_blocks(conn, team_id, blocks)


@with_db_connection()
def delete_team(conn, team_id):
    """Удалить команду (блоки и задачи удаляются каскадно)"""
    conn.execute('DELETE FROM teams WHERE id = ?', (team_id,))


# === EMPLOYEES CRUD ===
@with_db_connection(commit_on_success=False)
def get_all_employees(conn):
    """Получить всех сотрудников"""
    employees = conn.execute('SELECT id, last_name, first_name, middle_name FROM employees ORDER BY last_name, first_name, middle_name').fetchall()
    return [dict(emp) for emp in employees]


@with_db_connection(commit_on_success=False)
def create_employee(conn, last_name, first_name, middle_name=None):
    """Создать сотрудника"""
    cursor = conn.execute(
        '''INSERT INTO employees (last_name, first_name, middle_name)
           VALUES (?, ?, ?)''',
        (last_name, first_name, middle_name))
    conn.commit()
    employee_id = cursor.lastrowid
    return employee_id


@with_db_connection(default_return=False, raise_on_error=False)
def update_employee(conn, employee_id, last_name, first_name, middle_name=None):
    """Обновить сотрудника"""
    conn.execute(
        '''UPDATE employees
           SET last_name   = ?,
               first_name  = ?,
               middle_name = ?
           WHERE id = ?''', (last_name, first_name, middle_name, employee_id))
    return True


@with_db_connection()
def delete_employee(conn, employee_id):
    """Удалить сотрудника"""
    # Проверяем, используется ли сотрудник в назначениях
    count = conn.execute('SELECT COUNT(*) as count FROM assignments WHERE employee_id = ?', (employee_id,)).fetchone()[
        'count']
    if count > 0:
        # Если используется, просто открепляем его
        conn.execute('UPDATE assignments SET employee_id = NULL WHERE employee_id = ?', (employee_id,))
    conn.execute('DELETE FROM employees WHERE id = ?', (employee_id,))


# === FREEZE DAYS CRUD ===
@with_db_connection(commit_on_success=False)
def get_all_freeze_days(conn):
    """Получить все дни фриза"""
    days = conn.execute('SELECT date FROM freeze_days ORDER BY date').fetchall()
    return [day['date'] for day in days]


@with_db_connection(commit_on_success=False)
def get_freeze_days_in_period(conn, start_date, end_date):
    """Получить дни фриза в заданном периоде"""
    days = conn.execute(
        'SELECT date FROM freeze_days WHERE date BETWEEN ? AND ? ORDER BY date',
        (start_date, end_date)
    ).fetchall()
    return [day['date'] for day in days]


@with_db_connection(default_return=False, raise_on_error=False)
def add_freeze_day(conn, date_str):
    """Добавить день фриза"""
    conn.execute('INSERT INTO freeze_days (date) VALUES (?)', (date_str,))
    return True


@with_db_connection()
def add_freeze_range(conn, start_date, end_date):
    """Добавить диапазон дней фриза"""
    start = datetime.strptime(start_date, '%Y-%m-%d').date()
    end = datetime.strptime(end_date, '%Y-%m-%d').date()

    added = 0
    current = start
    while current <= end:
        date_str = current.strftime('%Y-%m-%d')
        try:
            conn.execute('INSERT INTO freeze_days (date) VALUES (?)', (date_str,))
            added += 1
        except sqlite3.IntegrityError:
            pass
        current += timedelta(days=1)
    return added


@with_db_connection()
def remove_freeze_day(conn, date_str):
    """Удалить день фриза"""
    conn.execute('DELETE FROM freeze_days WHERE date = ?', (date_str,))


# === TASKS CRUD ===
@with_db_connection(commit_on_success=False)
def get_tasks_by_team(conn, team_id):
    """Получить все задачи команды"""
    return conn.execute(
        '''SELECT id, name, description, criticality
           FROM tasks
           WHERE team_id = ?
           ORDER BY CASE criticality
                        WHEN 'high' THEN 0
                        WHEN 'medium' THEN 1
                        WHEN 'low' THEN 2
                        ELSE 3
                        END''',
        (team_id,)
    ).fetchall()


@with_db_connection(commit_on_success=False)
def task_exists(conn, task_id):
    """Проверить существование задачи"""
    return conn.execute('SELECT 1 FROM tasks WHERE id = ?', (task_id,)).fetchone()


@with_db_connection(commit_on_success=False)
def create_or_update_task(conn, task_id, team_id, name, description, criticality='medium'):
    """Создать задачу"""
    existing = conn.execute('SELECT 1 FROM tasks WHERE id = ?', (task_id,)).fetchone()
    if existing:
        conn.execute(
            '''UPDATE tasks
               SET name        = ?,
                   description = ?,
                   criticality = ?
               WHERE id = ?''',
            (name, description, criticality, task_id)
        )
        conn.commit()
    else:
        cursor = conn.execute(
            'INSERT INTO tasks (team_id, name, description, criticality) VALUES (?, ?, ?, ?)',
            (team_id, name, description, criticality)
        )
        conn.commit()
        task_id = cursor.lastrowid
    return task_id


@with_db_connection()
def delete_task(conn, task_id):
    """Удалить задачу"""
    conn.execute('DELETE FROM tasks WHERE id = ?', (task_id,))


# === ASSIGNMENTS CRUD ===
@with_db_connection(commit_on_success=False)
def get_assignment(conn, task_id, date_str):
    """Получить назначение на задачу на конкретную дату"""
    return conn.execute(
        '''SELECT a.id, a.task_id, a.date, a.block, a.status, a.employee_id, a.comment,
                  e.last_name   as employee_last_name,
                  e.first_name  as employee_first_name,
                  e.middle_name as employee_middle_name
           FROM assignments a
                    LEFT JOIN employees e ON a.employee_id = e.id
           WHERE a.task_id = ?
             AND a.date = ?''',
        (task_id, date_str)
    ).fetchone()


@with_db_connection(commit_on_success=False)
def get_assignments_by_team_in_period(conn, team_id, start_date, end_date):
    """Получить все назначения команды в период"""
    return conn.execute(
        '''SELECT a.id, a.task_id, a.date, a.block, a.status, a.employee_id, a.comment,
                  e.last_name   as employee_last_name,
                  e.first_name  as employee_first_name,
                  e.middle_name as employee_middle_name
           FROM assignments a
                    JOIN tasks t ON a.task_id = t.id
                    LEFT JOIN employees e ON a.employee_id = e.id
           WHERE t.team_id = ?
             AND a.date BETWEEN ? AND ?
           ORDER BY a.date, t.id''',
        (team_id, start_date, end_date)
    ).fetchall()


@with_db_connection()
def create_or_update_assignment(conn, assignment_id, task_id, date_str, block, status, employee_id, comment):
    """Создать или обновить назначение"""
    existing = conn.execute('SELECT 1 FROM assignments WHERE id = ?', (assignment_id,)).fetchone()

    if existing:
        conn.execute(
            '''UPDATE assignments
               SET date        = ?,
                   task_id     = ?,
                   block       = ?,
                   status      = ?,
                   employee_id = ?,
                   comment     = ?
               WHERE id = ?''',
            (date_str, task_id, block, status, employee_id, comment, assignment_id)
        )
    else:
        conn.execute(
            '''INSERT INTO assignments (task_id, date, block, status, employee_id, comment)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (task_id, date_str, block, status, employee_id, comment)
        )


@with_db_connection()
def delete_assignment(conn, assignment_id):
    """Удалить назначение"""
    conn.execute('DELETE FROM assignments WHERE id = ?', (assignment_id,))


# === STATISTICS ===
@with_db_connection(commit_on_success=False)
def get_team_stats(conn, team_id=None):
    """Получить статистику по команде или всем командам"""
    today = date.today().strftime('%Y-%m-%d')

    # Активные задачи (с назначениями статус new или planned)
    where_clause = ''
    params = []
    if team_id:
        where_clause = 'AND t.team_id = ?'
        params.append(team_id)

    # Общее количество активных задач
    tasks_count = conn.execute(
        f'''SELECT COUNT(DISTINCT t.id) as count 
           FROM tasks t 
           JOIN assignments a ON t.id = a.task_id 
           WHERE a.status IN ('new', 'planned') {where_clause}''',
        tuple(params)
    ).fetchone()['count']

    # Распределение по критичности (активные задачи)
    criticality_stats = conn.execute(
        f'''SELECT t.criticality, COUNT(DISTINCT t.id) as count 
           FROM tasks t 
           JOIN assignments a ON t.id = a.task_id 
           WHERE a.status IN ('new', 'planned') {where_clause}
           GROUP BY t.criticality''',
        tuple(params)
    ).fetchall()

    # Распределение по статусам за сегодня
    params_today = []
    if team_id:
        params_today.append(team_id)
    status_today = conn.execute(
        f'''SELECT a.status, COUNT(*) as count 
           FROM assignments a 
           JOIN tasks t ON a.task_id = t.id 
           WHERE a.date = ? AND a.status IN ('new', 'planned', 'rollback', 'success') 
           {f'AND t.team_id = ?' if team_id else ''}
           GROUP BY a.status''',
        tuple([today] + params_today)
    ).fetchall()

    return {
        'total_active': tasks_count,
        'criticality': criticality_stats,
        'status_today': status_today
    }


def get_all_teams_stats():
    """Получить статистику по всем командам"""
    return get_team_stats()


# === Инициализация БД при импорте ===
if not os.path.exists(DB_PATH):
    init_db()
else:
    ensure_schema()
