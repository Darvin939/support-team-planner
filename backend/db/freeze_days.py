from datetime import datetime, timedelta

from backend.db.connection import backend as _backend, with_db_connection


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
        f'SELECT date FROM freeze_days WHERE date BETWEEN {_backend.placeholder} AND {_backend.placeholder} ORDER BY date',
        (start_date, end_date)
    ).fetchall()
    return [day['date'] for day in days]


@with_db_connection(write=True)
def add_freeze_day(conn, date_str):
    """Добавить день фриза"""
    cursor = conn.execute(
        f'INSERT INTO freeze_days (date) VALUES ({_backend.placeholder})' + _backend.conflict_ignore(('date',)),
        (date_str,),
    )
    return cursor.rowcount > 0


@with_db_connection(write=True)
def add_freeze_range(conn, start_date, end_date):
    """Добавить диапазон дней фриза"""
    start = datetime.strptime(start_date, '%Y-%m-%d').date()
    end = datetime.strptime(end_date, '%Y-%m-%d').date()

    added = 0
    current = start
    while current <= end:
        date_str = current.strftime('%Y-%m-%d')
        cursor = conn.execute(
            f'INSERT INTO freeze_days (date) VALUES ({_backend.placeholder})' + _backend.conflict_ignore(('date',)),
            (date_str,),
        )
        added += cursor.rowcount
        current += timedelta(days=1)
    return added


@with_db_connection(write=True)
def remove_freeze_day(conn, date_str):
    """Удалить день фриза"""
    conn.execute(f'DELETE FROM freeze_days WHERE date = {_backend.placeholder}', (date_str,))


@with_db_connection(write=True)
def delete_freeze_days_by_month(conn, year, month):
    prefix = f"{year}-{month:02d}-%"
    conn.execute(f"DELETE FROM freeze_days WHERE date LIKE {_backend.placeholder}", (prefix,))


@with_db_connection(write=True)
def set_freeze_days_for_month(conn, year, month, days):
    prefix = f"{year}-{month:02d}-%"
    conn.execute(f"DELETE FROM freeze_days WHERE date LIKE {_backend.placeholder}", (prefix,))
    for day in days:
        date_str = f"{year}-{month:02d}-{day:02d}"
        conn.execute(f"INSERT INTO freeze_days (date) VALUES ({_backend.placeholder}){_backend.conflict_ignore(('date',))}", (date_str,))
