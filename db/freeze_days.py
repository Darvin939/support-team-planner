from datetime import datetime, timedelta

from db.connection import backend as _backend, with_db_connection

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
        except _backend.duplicate_error:
            pass
        current += timedelta(days=1)
    return added


@with_db_connection()
def remove_freeze_day(conn, date_str):
    """Удалить день фриза"""
    conn.execute('DELETE FROM freeze_days WHERE date = ?', (date_str,))


@with_db_connection()
def delete_freeze_days_by_month(conn, year, month):
    prefix = f"{year}-{month:02d}-%"
    conn.execute("DELETE FROM freeze_days WHERE date LIKE ?", (prefix,))


@with_db_connection()
def set_freeze_days_for_month(conn, year, month, days):
    prefix = f"{year}-{month:02d}-%"
    conn.execute("DELETE FROM freeze_days WHERE date LIKE ?", (prefix,))
    for day in days:
        date_str = f"{year}-{month:02d}-{day:02d}"
        conn.execute("INSERT OR IGNORE INTO freeze_days (date) VALUES (?)", (date_str,))
