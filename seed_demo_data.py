"""Наполняет свежую database.db объёмными воспроизводимыми демо-данными.

Создаёт 50 команд, 3 сегмента и соответствующие шаблоны блоков, 60
пользователей разных ролей с доступами к командам, от 1 до 50 работ на
команду и назначения в диапазоне +/- 2 недели от текущего дня.

Запуск: python seed_demo_data.py
"""
import random
from datetime import date, timedelta

import auth
import db


RANDOM_SEED = 42
TEAM_COUNT = 50
USER_COUNT = 60
TODAY = date.today()

SEGMENT_TEMPLATES = {
    'ФЛ': ('ЕФС ФЛ', ['GF', *[f'Б{i}' for i in range(1, 13)]]),
    'Сотрудники': ('ЕФС Сотр', ['SB', 'GF', 'BF']),
    'ППРБ': ('ППРБ', ['SK', 'MG']),
}

VERBS = [
    'Обновление', 'Исправление', 'Доработка', 'Оптимизация', 'Внедрение',
    'Синхронизация', 'Миграция', 'Рефакторинг', 'Настройка', 'Проверка',
    'Отключение', 'Включение', 'Расширение', 'Перенос', 'Согласование',
]
OBJECTS = [
    'модуля авторизации', 'расчёта комиссии', 'базы клиентов', 'отчёта по операциям',
    'запросов к БД', 'API партнёра', 'уведомлений оператора', 'лимитов переводов',
    'формы заявки', 'справочников', 'интерфейса оператора', 'шаблонов писем',
    'кэша сессий', 'логирования ошибок', 'фоновых заданий', 'валидации реквизитов',
    'интеграции с CRM', 'экспорта в 1С', 'мобильного приложения', 'личного кабинета',
]
DETAILS = [
    'после смены тарифной политики', 'по итогам ретроспективы релиза',
    'в рамках квартального плана', 'по заявке от службы поддержки',
    'после инцидента на проде', 'для повышения отказоустойчивости',
    'после аудита безопасности', 'для соответствия новым регламентам',
]
COMMENTS = [
    None, None, '', 'Ожидает подтверждения', 'Требуется согласование',
    'Плановое обновление', 'Проверить мониторинг после установки',
    'Инструкция: https://wiki.example.com/release/runbook',
]
LAST_NAMES = [
    'Иванов', 'Петрова', 'Сидоров', 'Кузнецова', 'Смирнов', 'Новикова',
    'Морозов', 'Волкова', 'Соколова', 'Лебедев', 'Козлов', 'Орлова',
    'Макаров', 'Захарова', 'Фёдоров', 'Михайлова', 'Беляев', 'Тарасова',
]
FIRST_NAMES = [
    'Иван', 'Мария', 'Алексей', 'Ольга', 'Дмитрий', 'Екатерина',
    'Сергей', 'Анна', 'Николай', 'Елена', 'Андрей', 'Наталья',
]
MIDDLE_NAMES = [
    'Иванович', 'Сергеевна', 'Алексеевич', 'Дмитриевна', 'Андреевич',
    'Павловна', 'Игоревич', 'Олеговна', None,
]


def day(offset):
    return (TODAY + timedelta(days=offset)).isoformat()


def random_name(number, segment_name):
    base = f'{random.choice(VERBS)} {random.choice(OBJECTS)}'
    style = random.choice(['short', 'short', 'detail', 'link'])
    if style == 'detail':
        base += f' {random.choice(DETAILS)}'
    elif style == 'link':
        base += f' (https://jira.example.com/browse/DEMO-{1000 + number})'
    return f'[{segment_name}] {base} №{number}'


def random_description(team_name):
    return random.choice([
        None,
        '',
        'Стандартная доработка.',
        f'Демо-работа команды «{team_name}».',
        'Необходимо провести анализ, согласовать окно и проверить метрики после релиза.',
        'Подробности: https://wiki.example.com/release и https://tracker.example.com/demo.',
    ])


def create_segments_and_templates():
    segment_ids = {name: db.create_segment(name) for name in SEGMENT_TEMPLATES}
    block_names = list(dict.fromkeys(
        block for _, blocks in SEGMENT_TEMPLATES.values() for block in blocks
    ))
    block_ids = {name: db.create_block(name) for name in block_names}

    template_ids = {}
    for segment_name, (template_name, blocks) in SEGMENT_TEMPLATES.items():
        entries = [
            {'block_id': block_ids[block], 'shift_days': index}
            for index, block in enumerate(blocks)
        ]
        template_ids[segment_name] = db.create_template(
            template_name, segment_ids[segment_name], entries,
        )
    return segment_ids, block_ids, template_ids


def create_teams(template_ids):
    all_template_ids = list(template_ids.values())
    return {
        f'Команда поддержки {number:02d}': db.create_team(
            f'Команда поддержки {number:02d}', all_template_ids,
        )
        for number in range(1, TEAM_COUNT + 1)
    }


def create_users(team_ids):
    """Создаёт пользователей и возвращает исполнителей по каждой команде."""
    teams = list(team_ids.values())
    password_hash = auth.hash_password('password123')
    fixed_users = [
        ('Иванов', 'Иван', 'Иванович', 'editor', 'ivanov', True),
        ('Петрова', 'Мария', 'Сергеевна', 'user', 'petrova', True),
    ]
    users = []

    for number in range(1, USER_COUNT + 1):
        if number <= len(fixed_users):
            last, first, middle, role, login, is_assignee = fixed_users[number - 1]
        else:
            last = random.choice(LAST_NAMES)
            first = random.choice(FIRST_NAMES)
            middle = random.choice(MIDDLE_NAMES)
            if number == USER_COUNT:
                role = 'admin'  # гарантируем наличие всех трёх ролей
            else:
                # Первые 50 записей остаются user/editor: так каждая команда ниже
                # гарантированно получает хотя бы одного реального исполнителя.
                role_pool = ['user', 'editor'] if number <= TEAM_COUNT else ['user', 'editor', 'admin']
                weights = [75, 25] if number <= TEAM_COUNT else [70, 25, 5]
                role = random.choices(role_pool, weights=weights, k=1)[0]
            login = f'demo{number:02d}'
            is_assignee = role != 'admin' and (number <= TEAM_COUNT or random.random() < 0.9)

        # Администраторы имеют глобальный доступ; остальные получают 1-8 команд.
        if role == 'admin':
            allowed_teams = None
        else:
            required_team = teams[(number - 1) % len(teams)]
            extra_teams = random.sample(
                [team_id for team_id in teams if team_id != required_team],
                random.randint(0, 7),
            )
            allowed_teams = [required_team, *extra_teams]
        user_id = db.create_user(
            last, first, middle, password_hash, role, login, is_assignee, allowed_teams,
        )
        users.append({
            'id': user_id, 'login': login, 'role': role,
            'is_assignee': is_assignee, 'teams': set(allowed_teams or teams),
        })

    assignees_by_team = {
        team_id: [u['id'] for u in users if u['is_assignee'] and team_id in u['teams']]
        for team_id in teams
    }
    return users, assignees_by_team


def assignment_status(task_status, offset):
    if task_status == 'done':
        return random.choice(['success', 'success', 'rollback', 'cancelled'])
    if task_status == 'cancelled':
        return 'cancelled'
    if offset > 0:
        return random.choice(['new', 'planned', 'cancelled'])
    return random.choice(['new', 'planned', 'success', 'rollback', 'cancelled'])


def create_tasks_and_assignments(team_ids, segment_ids, assignees_by_team):
    total_tasks = total_assignments = total_dependencies = 0
    global_task_number = 0
    segment_names = list(SEGMENT_TEMPLATES)

    for team_name, team_id in team_ids.items():
        team_tasks = []
        # Независимое случайное число работ для каждой команды: 1..50.
        for _ in range(random.randint(1, 50)):
            global_task_number += 1
            segment_name = random.choice(segment_names)
            task_id = db.create_or_update_task(
                None,
                team_id,
                random_name(global_task_number, segment_name),
                random_description(team_name),
                criticality=random.choice(['high', 'medium', 'low']),
                segment_id=segment_ids[segment_name],
            )
            team_tasks.append(task_id)
            total_tasks += 1

            task_status = random.choices(
                ['new', 'done', 'cancelled'], weights=[78, 14, 8], k=1,
            )[0]
            if task_status != 'new':
                db.update_task_status(task_id, task_status)

            # От нуля до восьми назначений, даты уникальны в пределах работы.
            offsets = random.sample(range(-14, 15), random.randint(0, 8))
            for offset in offsets:
                status = assignment_status(task_status, offset)
                time_spent = None
                if status in ('success', 'rollback') and random.random() < 0.8:
                    minutes = random.choice([30, 60, 90, 120, 180, 240, 360, 480])
                    time_spent = f'{minutes // 60:02d}:{minutes % 60:02d}'

                blocks = SEGMENT_TEMPLATES[segment_name][1]
                db.create_or_update_assignment(
                    None,
                    task_id,
                    day(offset),
                    random.choice([*blocks, None]),
                    status,
                    random.choice([*assignees_by_team[team_id], None]),
                    random.choice(COMMENTS),
                    time_spent=time_spent,
                )
                total_assignments += 1

        # Зависимости направлены только назад, поэтому циклы невозможны.
        for index, task_id in enumerate(team_tasks[1:], start=1):
            if random.random() < 0.35:
                dependencies = random.sample(
                    team_tasks[:index], random.randint(1, min(3, index)),
                )
                db.set_task_dependencies(task_id, dependencies)
                total_dependencies += len(dependencies)

    return total_tasks, total_assignments, total_dependencies


def main():
    random.seed(RANDOM_SEED)
    print(f'Сегодня: {TODAY.isoformat()}; seed: {RANDOM_SEED}')
    # create_user намеренно не коммитит самостоятельно (HTTP-запрос коммитится
    # middleware). Скрипту также нужно общее соединение на весь запуск.
    conn = db.get_db_connection()
    token = db.set_request_connection(conn)
    try:
        segment_ids, block_ids, template_ids = create_segments_and_templates()
        team_ids = create_teams(template_ids)
        users, assignees_by_team = create_users(team_ids)
        tasks, assignments, dependencies = create_tasks_and_assignments(
            team_ids, segment_ids, assignees_by_team,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        db.clear_request_connection(token)
        conn.close()

    roles = {role: sum(u['role'] == role for u in users) for role in ('user', 'editor', 'admin')}
    print(f'Сегменты: {len(segment_ids)}, блоки: {len(block_ids)}, шаблоны: {len(template_ids)}')
    print(f'Команды: {len(team_ids)}, пользователи: {len(users)} ({roles})')
    print(f'Работы: {tasks}, назначения: {assignments}, зависимости: {dependencies}')
    print('Пароль демо-пользователей: password123')


if __name__ == '__main__':
    main()
