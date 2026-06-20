from datetime import date, timedelta

from flask import Flask, render_template, request, jsonify, redirect, url_for

import database as db

app = Flask(__name__)


# === Роуты ===
@app.route('/')
def index():
    """Главная страница со статистикой"""
    teams = db.get_all_teams()
    stats = db.get_all_teams_stats()

    # Преобразование критичности для отображения
    criticality_data = {}
    for item in stats['criticality']:
        criticality_data[item['criticality']] = item['count']

    # Статусы сегодня
    status_data = {}
    for item in stats['status_today']:
        status_data[item['status']] = item['count']

    # Все статусы для заполнения нулями
    all_statuses = ['new', 'planned', 'rollback', 'success']
    status_counts = {}
    for s in all_statuses:
        status_counts[s] = status_data.get(s, 0)

    return render_template('index.html',
                           teams=teams,
                           total_active=stats['total_active'],
                           criticality_data=criticality_data,
                           status_counts=status_counts)


@app.route('/planning/<int:team_id>')
def planning(team_id):
    """Страница планирования команды"""
    team = db.get_team_by_id(team_id)
    if not team:
        return redirect(url_for('index'))

    tasks = db.get_tasks_by_team(team_id)
    employees = db.get_all_employees()
    freeze_days = db.get_all_freeze_days()

    # Период по умолчанию
    today = date.today()
    start_date = today - timedelta(days=7)
    end_date = today + timedelta(days=30)

    return render_template('planning.html',
                           team=team,
                           tasks=tasks,
                           employees=employees,
                           freeze_days=freeze_days,
                           start_date=start_date.strftime('%Y-%m-%d'),
                           end_date=end_date.strftime('%Y-%m-%d'))


@app.route('/api/assignments/<int:team_id>')
def get_assignments_api(team_id):
    """API для получения назначений команды"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if start_date and end_date:
        assignments = db.get_assignments_by_team_in_period(team_id, start_date, end_date)
    else:
        assignments = db.get_assignments_by_team(team_id)

    # Преобразование для JSON
    result = []
    for a in assignments:
        result.append({
            'id': a['id'],
            'task_id': a['task_id'],
            'date': a['date'],
            'block': a['block'],
            'status': a['status'],
            'employee_id': a['employee_id'],
            'employee_name': a['employee_name'] if a['employee_name'] else '',
            'comment': a['comment'],
            'task_description': a['task_description'],
            'criticality': a['criticality']
        })

    return jsonify(result)


@app.route('/api/tasks/<int:team_id>')
def get_tasks_api(team_id):
    """API для получения задач команды"""
    tasks = db.get_tasks_by_team(team_id)
    result = []
    for t in tasks:
        result.append({
            'id': t['id'],
            'description': t['description'],
            'criticality': t['criticality']
        })
    return jsonify(result)


@app.route('/api/assignment/<int:task_id>', methods=['GET'])
def get_assignment_api(task_id):
    """API для получения конкретного назначения"""
    date_str = request.args.get('date')
    if not date_str:
        return jsonify({'error': 'Date required'}), 400

    assignment = db.get_assignment(task_id, date_str)
    if assignment:
        result = {
            'id': assignment['id'],
            'task_id': assignment['task_id'],
            'date': assignment['date'],
            'block': assignment['block'],
            'status': assignment['status'],
            'employee_id': assignment['employee_id'],
            'employee_name': assignment['employee_name'] if assignment['employee_name'] else '',
            'comment': assignment['comment']
        }
    else:
        result = None

    return jsonify(result)


@app.route('/api/assignment', methods=['POST'])
def save_assignment_api():
    """API для сохранения назначения"""
    data = request.get_json()
    assignment_id = data.get('assignment_id')
    task_id = data.get('task_id')
    date_str = data.get('date')
    block = data.get('block', '')
    status = data.get('status', 'new')
    employee_id = data.get('employee_id')
    comment = data.get('comment', '')

    if not task_id:
        return jsonify({'error': 'Task ID required'}), 400

    # Проверяем существование задачи
    task = db.get_task_by_id(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    # Сохраняем
    db.create_or_update_assignment(assignment_id, task_id, date_str, block, status, employee_id, comment)
    return jsonify({'success': True})


@app.route('/api/assignment/<int:assignment_id>', methods=['DELETE'])
def delete_assignment_api(assignment_id):
    """API для удаления назначения"""
    db.delete_assignment(assignment_id)
    return jsonify({'success': True})


@app.route('/api/task', methods=['POST'])
def save_task_api():
    """API для сохранения задачи"""
    data = request.get_json()
    task_id = data.get('task_id')
    team_id = data.get('team_id')
    description = data.get('description')
    criticality = data.get('criticality', 'medium')

    if not team_id or not description:
        return jsonify({'error': 'Team ID and description required'}), 400

    task_id = db.create_or_update_task(task_id, team_id, description, criticality)
    return jsonify({'id': task_id, 'success': True})


@app.route('/api/task/<int:task_id>', methods=['DELETE'])
def delete_task_api(task_id):
    """API для удаления задачи"""
    db.delete_task(task_id)
    return jsonify({'success': True})


# === API для настроек ===

@app.route('/api/teams', methods=['GET'])
def get_teams_api():
    """Получить все команды"""
    teams = db.get_all_teams()
    result = [{'id': t['id'], 'name': t['name']} for t in teams]
    return jsonify(result)


@app.route('/api/teams', methods=['POST'])
def create_team_api():
    """Создать команду"""
    data = request.get_json()
    name = data.get('name')
    if not name:
        return jsonify({'error': 'Name required'}), 400

    try:
        team_id = db.create_team(name)
        return jsonify({'id': team_id, 'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/teams/<int:team_id>', methods=['PUT'])
def update_team_api(team_id):
    """Обновить команду"""
    data = request.get_json()
    name = data.get('name')
    if not name:
        return jsonify({'error': 'Name required'}), 400

    try:
        db.update_team(team_id, name)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/teams/<int:team_id>', methods=['DELETE'])
def delete_team_api(team_id):
    """Удалить команду"""
    db.delete_team(team_id)
    return jsonify({'success': True})


@app.route('/api/employees', methods=['GET'])
def get_employees_api():
    """Получить всех сотрудников"""
    employees = db.get_all_employees()
    result = [{'id': e['id'], 'full_name': e['full_name']} for e in employees]
    return jsonify(result)


@app.route('/api/employees', methods=['POST'])
def create_employee_api():
    """Создать сотрудника"""
    data = request.get_json()
    full_name = data.get('full_name')
    if not full_name:
        return jsonify({'error': 'Full name required'}), 400

    employee_id = db.create_employee(full_name)
    return jsonify({'id': employee_id, 'success': True})


@app.route('/api/employees/<int:employee_id>', methods=['PUT'])
def update_employee_api(employee_id):
    """Обновить сотрудника"""
    data = request.get_json()
    full_name = data.get('full_name')
    if not full_name:
        return jsonify({'error': 'Full name required'}), 400

    db.update_employee(employee_id, full_name)
    return jsonify({'success': True})


@app.route('/api/employees/<int:employee_id>', methods=['DELETE'])
def delete_employee_api(employee_id):
    """Удалить сотрудника"""
    db.delete_employee(employee_id)
    return jsonify({'success': True})


@app.route('/api/freeze-days', methods=['GET'])
def get_freeze_days_api():
    """Получить все дни фриза"""
    days = db.get_all_freeze_days()
    return jsonify(days)


@app.route('/api/freeze-days', methods=['POST'])
def add_freeze_day_api():
    """Добавить день фриза"""
    data = request.get_json()
    date_str = data.get('date')
    start_date = data.get('start_date')
    end_date = data.get('end_date')

    if date_str:
        # Добавление одной даты
        success = db.add_freeze_day(date_str)
        return jsonify({'success': success})
    elif start_date and end_date:
        # Добавление диапазона
        count = db.add_freeze_range(start_date, end_date)
        return jsonify({'success': True, 'count': count})
    else:
        return jsonify({'error': 'Date or range required'}), 400


@app.route('/api/freeze-days/<path:date_str>', methods=['DELETE'])
def delete_freeze_day_api(date_str):
    """Удалить день фриза"""
    db.remove_freeze_day(date_str)
    return jsonify({'success': True})


# === Страницы настроек и статистики ===

@app.route('/settings')
def settings_page():
    """Страница настроек"""
    teams = db.get_all_teams()
    employees = db.get_all_employees()
    freeze_days = db.get_all_freeze_days()

    return render_template('settings.html',
                           teams=teams,
                           employees=employees,
                           freeze_days=freeze_days)


@app.route('/statistics')
def statistics_page():
    """Страница статистики"""
    teams = db.get_all_teams()
    return render_template('statistics.html',
                           teams=teams)


@app.route('/api/statistics/<int:team_id>')
def get_statistics_api(team_id):
    """API для получения статистики по команде"""
    if team_id == 0:  # Все команды
        stats = db.get_all_teams_stats()
    else:
        stats = db.get_team_stats(team_id)

    # Преобразование критичности
    criticality_data = {}
    for item in stats['criticality']:
        criticality_data[item['criticality']] = item['count']

    # Статусы сегодня
    status_data = {}
    for item in stats['status_today']:
        status_data[item['status']] = item['count']

    all_statuses = ['new', 'planned', 'rollback', 'success']
    status_counts = {}
    for s in all_statuses:
        status_counts[s] = status_data.get(s, 0)

    return jsonify({
        'total_active': stats['total_active'],
        'criticality': criticality_data,
        'status_today': status_counts
    })


@app.route('/api/daily-stats/<int:team_id>')
def get_daily_stats_api(team_id):
    """API для получения ежедневной статистики"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if not start_date or not end_date:
        return jsonify({'error': 'Date range required'}), 400

    if team_id == 0:
        # Для всех команд - получаем статистику по каждой
        teams = db.get_all_teams()
        result = {}
        for team in teams:
            stats = db.get_daily_stats(team['id'], start_date, end_date)
            result[team['name']] = [dict(s) for s in stats]
        return jsonify(result)
    else:
        stats = db.get_daily_stats(team_id, start_date, end_date)
        return jsonify([dict(s) for s in stats])


if __name__ == '__main__':
    app.run(debug=True, port=5000)
