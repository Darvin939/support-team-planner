"""
Одноразовый скрипт наполнения свежей database.db демо-данными:
3 команды (в одной — 20+ задач), сегменты, блоки, шаблоны блоков, пользователи,
случайные зависимости между задачами, задачи со случайными именами/описаниями
(короткие/длинные/со ссылками) и назначения в разных статусах в периоде
+/- неделя от сегодняшнего дня.

Запуск: python seed_demo_data.py
"""
import random
from datetime import date, timedelta

import auth
import db

random.seed(42)

TODAY = date.today()


def d(offset):
    return (TODAY + timedelta(days=offset)).isoformat()


# === Генерация случайных имён/описаний задач ===

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
    'системы уведомлений', 'модуля отчётности', 'процесса согласования', 'справочника тарифов',
]
DETAILS = [
    'после смены тарифной политики', 'по итогам ретроспективы релиза', 'в рамках квартального плана',
    'по заявке от службы поддержки', 'после инцидента на проде', 'для повышения отказоустойчивости',
    'в связи с изменением требований комплаенс', 'по результатам нагрузочного тестирования',
    'после аудита безопасности', 'для соответствия новым регламентам',
]
LINKS = [
    'https://jira.example.com/browse/SUP-{n}',
    'https://wiki.example.com/pages/task-{n}',
    'https://confluence.example.com/display/SUP/TASK-{n}',
    'https://github.example.com/support-team/tasks/issues/{n}',
    'https://tracker.example.com/tickets/{n}',
]
LONG_FILLER = [
    'Необходимо провести анализ текущей реализации и выявить узкие места.',
    'Требуется согласование с командой безопасности перед выкладкой в прод.',
    'Изменения затрагивают несколько смежных систем, требуется дополнительное регрессионное тестирование.',
    'После внедрения нужно обновить документацию и уведомить смежные команды.',
    'В случае отката необходимо предусмотреть план восстановления данных.',
    'Затронуты клиенты сегмента B2B, важно минимизировать простой сервиса.',
    'Работа выполняется поэтапно: подготовка, тестирование на стенде, выкладка на прод.',
    'Ожидается влияние на производительность, требуется мониторинг метрик после релиза.',
]


def random_name(i):
    verb = random.choice(VERBS)
    obj = random.choice(OBJECTS)
    short = f'{verb} {obj}'
    style = random.choice(['short', 'short', 'long', 'link'])
    if style == 'short':
        return f'{short} №{i}'
    if style == 'long':
        detail = random.choice(DETAILS)
        return f'{short} {detail} №{i}'
    ticket = random.choice(LINKS).format(n=1000 + i)
    return f'{short} (см. {ticket}) №{i}'


def random_description(team_name):
    style = random.choice(['short', 'long', 'link', 'link'])
    if style == 'short':
        return random.choice([
            'Срочная правка, без деталей.', 'См. задачу в трекере.', 'Стандартная доработка.',
            f'Демо-задача для команды «{team_name}».',
        ])
    if style == 'long':
        sentences = random.sample(LONG_FILLER, k=random.randint(3, 5))
        intro = f'Демо-задача для команды «{team_name}».'
        return ' '.join([intro] + sentences)
    n_links = random.randint(1, 2)
    links = [random.choice(LINKS).format(n=random.randint(1000, 9999)) for _ in range(n_links)]
    return f'Подробности и обсуждение: {", ".join(links)}.'


def main():
    print(f'Сегодня: {TODAY.isoformat()}')

    # === Сегменты ===
    segment_names = ['Розница', 'Корпоративные клиенты', 'Онлайн-банк']
    segment_ids = {name: db.create_segment(name) for name in segment_names}
    print('Сегменты:', segment_ids)

    # === Блоки ===
    block_names = ['ГФ', 'Б1', 'Б2', 'ПРОД', 'ГИС']
    block_ids = {name: db.create_block(name) for name in block_names}
    print('Блоки:', block_ids)

    # === Шаблоны блоков (привязаны к сегменту) ===
    templates = [
        ('Стандартный релиз', 'Розница', [
            ('ГФ', -2), ('Б1', 0), ('Б2', 1), ('ПРОД', 3),
        ]),
        ('Ускоренный релиз', 'Онлайн-банк', [
            ('ГФ', -1), ('ПРОД', 1),
        ]),
        ('Корпоративный релиз', 'Корпоративные клиенты', [
            ('ГФ', -3), ('Б1', -1), ('ГИС', 0), ('ПРОД', 2),
        ]),
    ]
    template_ids = {}
    for name, segment_name, entries in templates:
        entries_payload = [{'block_id': block_ids[b], 'shift_days': off} for b, off in entries]
        tmpl_id = db.create_template(name, segment_ids[segment_name], entries_payload)
        template_ids[name] = tmpl_id
    print('Шаблоны:', template_ids)

    # === Команды (3 шт), каждой назначаем 1-2 шаблона ===
    teams = [
        ('Поддержка Розницы', ['Стандартный релиз']),
        ('Поддержка Онлайн-банка', ['Ускоренный релиз', 'Стандартный релиз']),
        ('Поддержка Корпоративных клиентов', ['Корпоративный релиз']),
    ]
    team_ids = {}
    for name, tmpl_names in teams:
        tids = [template_ids[t] for t in tmpl_names]
        team_ids[name] = db.create_team(name, tids)
    print('Команды:', team_ids)

    # === Пользователи ===
    users_data = [
        ('Иванов', 'Иван', 'Иванович', 'editor', 'ivanov', True),
        ('Петрова', 'Мария', 'Сергеевна', 'user', 'petrova', True),
        ('Сидоров', 'Алексей', 'Викторович', 'user', 'sidorov', True),
        ('Кузнецова', 'Ольга', 'Дмитриевна', 'user', 'kuznetsova', True),
        ('Смирнов', 'Дмитрий', 'Андреевич', 'editor', 'smirnov', True),
        ('Новикова', 'Екатерина', 'Павловна', 'user', 'novikova', True),
        ('Морозов', 'Сергей', 'Игоревич', 'admin', 'morozov', False),
    ]
    user_ids = {}
    for last, first, middle, role, login, is_assignee in users_data:
        uid = db.create_user(last, first, middle, auth.hash_password('password123'), role, login, is_assignee)
        user_ids[login] = uid
    print('Пользователи:', user_ids)

    assignee_pool = [uid for login, uid in user_ids.items()
                      if any(u[5] for u in users_data if u[4] == login)]

    # === Задачи и назначения ===
    task_status_pool = ['new', 'new', 'new', 'new', 'done', 'cancelled']
    assignment_status_pool = ['new', 'planned', 'planned', 'success', 'success', 'rollback']
    criticalities = ['high', 'medium', 'low']

    team_segment_map = {
        'Поддержка Розницы': 'Розница',
        'Поддержка Онлайн-банка': 'Онлайн-банк',
        'Поддержка Корпоративных клиентов': 'Корпоративные клиенты',
    }
    team_blocks_map = {
        'Поддержка Розницы': ['ГФ', 'Б1', 'Б2', 'ПРОД'],
        'Поддержка Онлайн-банка': ['ГФ', 'ПРОД'],
        'Поддержка Корпоративных клиентов': ['ГФ', 'Б1', 'ГИС', 'ПРОД'],
    }
    # Розница получает 20+ задач, остальные — поменьше, для разнообразия
    task_counts_map = {
        'Поддержка Розницы': 24,
        'Поддержка Онлайн-банка': 9,
        'Поддержка Корпоративных клиентов': 11,
    }

    day_offsets = list(range(-7, 8))

    total_tasks = 0
    total_assignments = 0
    total_deps = 0

    for team_name, team_id in team_ids.items():
        segment_id = segment_ids[team_segment_map[team_name]]
        blocks_for_team = team_blocks_map[team_name]
        n_tasks = task_counts_map[team_name]

        team_task_ids = []

        for i in range(n_tasks):
            name = random_name(i + 1)
            description = random_description(team_name)
            criticality = criticalities[i % len(criticalities)]

            task_id = db.create_or_update_task(
                None, team_id, name, description,
                criticality=criticality, segment_id=segment_id,
            )
            total_tasks += 1
            team_task_ids.append(task_id)

            task_status = task_status_pool[i % len(task_status_pool)]
            if task_status != 'new':
                db.update_task_status(task_id, task_status)

            # Число назначений на задачу: 1-3
            n_assignments = random.choice([1, 1, 2, 2, 3])
            used_dates = set()
            for _ in range(n_assignments):
                offset = random.choice(day_offsets)
                # избегаем дублей по (task_id, date) — уникальный индекс в БД
                attempts = 0
                while offset in used_dates and attempts < 10:
                    offset = random.choice(day_offsets)
                    attempts += 1
                if offset in used_dates:
                    continue
                used_dates.add(offset)

                date_str = d(offset)
                block = random.choice(blocks_for_team)
                user_id = random.choice(assignee_pool)
                comment = random.choice([
                    None, 'Ожидает подтверждения', 'Требуется согласование', 'Плановое обновление',
                ])

                if task_status in ('done', 'cancelled'):
                    status = random.choice(['success', 'rollback'])
                elif offset > 0:
                    status = random.choice(['new', 'planned'])
                else:
                    status = random.choice(assignment_status_pool)

                time_spent = None
                if status in ('success', 'rollback'):
                    time_spent = f'{random.choice([1, 2, 3, 4, 6, 8])}ч'

                db.create_or_update_assignment(
                    None, task_id, date_str, block, status, user_id, comment,
                    time_spent=time_spent,
                )
                total_assignments += 1

        # === Случайные зависимости между задачами команды ===
        # Каждая задача может зависеть только от уже созданных ранее задач той же команды —
        # порядок создания сам по себе гарантирует отсутствие циклов.
        for idx, task_id in enumerate(team_task_ids):
            if idx == 0:
                continue
            if random.random() < 0.45:
                n_deps = random.randint(1, min(3, idx))
                deps = random.sample(team_task_ids[:idx], n_deps)
                db.set_task_dependencies(task_id, deps)
                total_deps += len(deps)

    print(f'Создано задач: {total_tasks}, назначений: {total_assignments}, зависимостей: {total_deps}')


if __name__ == '__main__':
    main()
