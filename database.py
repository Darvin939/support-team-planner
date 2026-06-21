import os
import sqlite3
from datetime import datetime, date, timedelta

DB_PATH = 'database.db'


def get_db_connection():
    """Получить соединение с базой данных"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Инициализация базы данных"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Создание таблиц
    # @formatter:off
    cursor.executescript('''
        CREATE TABLE if NOT EXISTS teams (
            id INTEGER PRIMARY key autoincrement,
            name text NOT NULL UNIQUE
        );

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
    conn.commit()
    conn.close()


# === TEAMS CRUD ===

def get_all_teams():
    """Получить все команды"""
    conn = get_db_connection()
    teams = conn.execute('SELECT * FROM teams ORDER BY name').fetchall()
    conn.close()
    return teams


def get_team_by_id(team_id):
    """Получить команду по ID"""
    conn = get_db_connection()
    team = conn.execute('SELECT * FROM teams WHERE id = ?', (team_id,)).fetchone()
    conn.close()
    return team


def create_team(name):
    """Создать команду"""
    conn = get_db_connection()
    cursor = conn.execute('INSERT INTO teams (name) VALUES (?)', (name,))
    conn.commit()
    team_id = cursor.lastrowid
    conn.close()
    return team_id


def update_team(team_id, name):
    """Обновить команду"""
    conn = get_db_connection()
    conn.execute('UPDATE teams SET name = ? WHERE id = ?', (name, team_id))
    conn.commit()
    conn.close()


def delete_team(team_id):
    """Удалить команду"""
    conn = get_db_connection()
    conn.execute('DELETE FROM teams WHERE id = ?', (team_id,))
    conn.commit()
    conn.close()


# === EMPLOYEES CRUD ===

def get_all_employees():
    """Получить всех сотрудников"""
    conn = get_db_connection()
    employees = conn.execute('SELECT * FROM employees ORDER BY last_name, first_name, middle_name').fetchall()
    conn.close()
    return [dict(emp) for emp in employees]


def create_employee(last_name, first_name, middle_name=None):
    """Создать сотрудника"""
    conn = get_db_connection()
    cursor = conn.execute(
        '''INSERT INTO employees (last_name, first_name, middle_name)
           VALUES (?, ?, ?)''',
        (last_name, first_name, middle_name))
    conn.commit()
    employee_id = cursor.lastrowid
    conn.close()
    return employee_id


def update_employee(employee_id, last_name, first_name, middle_name=None):
    """Обновить сотрудника"""
    conn = get_db_connection()
    conn.execute(
        '''UPDATE employees
           SET last_name = ?, first_name = ?, middle_name = ?
           WHERE id = ?''', (last_name, first_name, middle_name, employee_id))
    conn.commit()
    conn.close()


def delete_employee(employee_id):
    """Удалить сотрудника"""
    conn = get_db_connection()
    # Проверяем, используется ли сотрудник в назначениях
    count = conn.execute('SELECT COUNT(*) as count FROM assignments WHERE employee_id = ?', (employee_id,)).fetchone()[
        'count']
    if count > 0:
        # Если используется, просто открепляем его
        conn.execute('UPDATE assignments SET employee_id = NULL WHERE employee_id = ?', (employee_id,))
    conn.execute('DELETE FROM employees WHERE id = ?', (employee_id,))
    conn.commit()
    conn.close()


# === FREEZE DAYS CRUD ===

def get_all_freeze_days():
    """Получить все дни фриза"""
    conn = get_db_connection()
    days = conn.execute('SELECT date FROM freeze_days ORDER BY date').fetchall()
    conn.close()
    return [day['date'] for day in days]


def add_freeze_day(date_str):
    """Добавить день фриза"""
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO freeze_days (date) VALUES (?)', (date_str,))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def add_freeze_range(start_date, end_date):
    """Добавить диапазон дней фриза"""
    start = datetime.strptime(start_date, '%Y-%m-%d').date()
    end = datetime.strptime(end_date, '%Y-%m-%d').date()

    conn = get_db_connection()
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
    conn.commit()
    conn.close()
    return added


def remove_freeze_day(date_str):
    """Удалить день фриза"""
    conn = get_db_connection()
    conn.execute('DELETE FROM freeze_days WHERE date = ?', (date_str,))
    conn.commit()
    conn.close()


def is_freeze_day(date_str):
    """Проверить, является ли день днем фриза"""
    conn = get_db_connection()
    result = conn.execute('SELECT 1 FROM freeze_days WHERE date = ?', (date_str,)).fetchone()
    conn.close()
    return result is not None


# === TASKS CRUD ===

def get_tasks_by_team(team_id):
    """Получить все задачи команды"""
    conn = get_db_connection()
    tasks = conn.execute(
        '''SELECT *
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
    conn.close()
    return tasks


def get_task_by_id(task_id):
    """Получить задачу по ID"""
    conn = get_db_connection()
    task = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    conn.close()
    return task


def create_or_update_task(task_id, team_id, name, description, criticality='medium'):
    """Создать задачу"""
    conn = get_db_connection()
    existing = conn.execute('SELECT 1 FROM tasks WHERE id = ?', (task_id,)).fetchone()
    if existing:
        conn.execute(
            '''UPDATE tasks
               SET name = ?,
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
    conn.close()
    return task_id


def delete_task(task_id):
    """Удалить задачу"""
    conn = get_db_connection()
    conn.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
    conn.commit()
    conn.close()


# === ASSIGNMENTS CRUD ===

def get_assignment(task_id, date_str):
    """Получить назначение на задачу на конкретную дату"""
    conn = get_db_connection()
    assignment = conn.execute(
        '''SELECT a.*,
                  e.last_name   as employee_last_name,
                  e.first_name  as employee_first_name,
                  e.middle_name as employee_middle_name
           FROM assignments a
                    LEFT JOIN employees e ON a.employee_id = e.id
           WHERE a.task_id = ?
             AND a.date = ?''',
        (task_id, date_str)
    ).fetchone()
    conn.close()
    return assignment


def get_assignments_by_team_in_period(team_id, start_date, end_date):
    """Получить все назначения команды в период"""
    conn = get_db_connection()
    assignments = conn.execute(
        '''SELECT a.*,
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
    conn.close()
    return assignments


def get_assignments_by_team(team_id):
    """Получить все назначения команды"""
    conn = get_db_connection()
    assignments = conn.execute(
        '''SELECT a.*,
                  e.last_name   as employee_last_name,
                  e.first_name  as employee_first_name,
                  e.middle_name as employee_middle_name
           FROM assignments a
                    JOIN tasks t ON a.task_id = t.id
                    LEFT JOIN employees e ON a.employee_id = e.id
           WHERE t.team_id = ?
           ORDER BY a.date, t.id''',
        (team_id,)
    ).fetchall()
    conn.close()
    return assignments


def create_or_update_assignment(assignment_id, task_id, date_str, block, status, employee_id, comment):
    """Создать или обновить назначение"""
    conn = get_db_connection()
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
    conn.commit()
    conn.close()


def delete_assignment(assignment_id):
    """Удалить назначение"""
    conn = get_db_connection()
    conn.execute('DELETE FROM assignments WHERE id = ?', (assignment_id,))
    conn.commit()
    conn.close()


# === STATISTICS ===

def get_team_stats(team_id=None):
    """Получить статистику по команде или всем командам"""
    conn = get_db_connection()
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

    conn.close()
    return {
        'total_active': tasks_count,
        'criticality': criticality_stats,
        'status_today': status_today
    }


def get_daily_stats(team_id, start_date, end_date):
    """Получить статистику по дням в периоде"""
    conn = get_db_connection()
    stats = conn.execute(
        '''SELECT a.date, a.status, COUNT(*) as count
           FROM assignments a
               JOIN tasks t
           ON a.task_id = t.id
           WHERE t.team_id = ? AND a.date BETWEEN ? AND ?
           GROUP BY a.date, a.status
           ORDER BY a.date''',
        (team_id, start_date, end_date)
    ).fetchall()
    conn.close()
    return stats


def get_all_teams_stats():
    """Получить статистику по всем командам"""
    return get_team_stats()


# === Инициализация БД при импорте ===
if not os.path.exists(DB_PATH):
    init_db()
