"""Generate millions of deterministic SQLite rows for UI and API load testing.

The regular ``seed_demo_data.py`` remains the small human-friendly demo seed.
This script uses batched SQL inserts and creates isolated entities whose names
start with ``LOADTEST``. Along with volume it creates the full reference-data
graph: segments, blocks, templates, team access, users of every role, freeze
days, all task/assignment/PSI statuses, histories and dependencies.

Default volume: 1,000,000 tasks, 2,000,000 assignments and about 100,000
dependencies across 50 teams.

Examples:
    python seed_large_demo_data.py --yes
    python seed_large_demo_data.py --tasks 2000000 --assignments-per-task 3 --yes
    python seed_large_demo_data.py --replace --yes
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import auth
from db.sqlite import SQLiteBackend

TEAM_PREFIX = "LOADTEST"
ADMIN_LOGIN = "load_admin"
ADMIN_PASSWORD = "password123"
CRITICALITIES = ("low", "medium", "high")
TASK_STATUSES = ("new", "done", "cancelled")
PSI_STATUSES = ("not_required", "passed", "not_required", "required")
ASSIGNMENT_STATUSES = ("new", "planned", "success", "rollback", "cancelled")
BLOCKS = ("LOAD_ANALYSIS", "LOAD_DEVELOPMENT", "LOAD_REVIEW", "LOAD_RELEASE")
SEGMENTS = ("LOADTEST core", "LOADTEST integrations", "LOADTEST channels")
TEMPLATE_SUFFIXES = ("standard", "fast")


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return parsed


def non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be zero or greater")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("database.db"), help="SQLite database path")
    parser.add_argument("--teams", type=positive_int, default=50, help="number of load-test teams")
    parser.add_argument("--tasks", type=positive_int, default=1_000_000, help="total task count")
    parser.add_argument(
        "--assignments-per-task",
        type=non_negative_int,
        default=2,
        help="assignments per task (0..730, each uses a unique date)",
    )
    parser.add_argument("--batch-size", type=positive_int, default=10_000, help="tasks per committed batch")
    parser.add_argument(
        "--dependency-every",
        type=non_negative_int,
        default=10,
        help="add one dependency for every Nth task; 0 disables dependencies",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="delete entities created by an earlier large seed before inserting",
    )
    parser.add_argument("--yes", action="store_true", help="skip the interactive size confirmation")
    args = parser.parse_args()
    if args.assignments_per_task > 730:
        parser.error("--assignments-per-task cannot exceed 730 because dates must be unique per task")
    return args


def format_count(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def connect_database(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA cache_size = -200000")
    SQLiteBackend().init_schema(conn)
    conn.commit()
    return conn


def existing_seed_team_count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM teams WHERE name LIKE ?", (f"{TEAM_PREFIX} team %",)).fetchone()[0]


def remove_existing_seed(conn: sqlite3.Connection) -> None:
    started = time.monotonic()
    team_count = existing_seed_team_count(conn)
    if not team_count:
        return
    print(f"Deleting the previous large seed ({team_count} teams and their dependent rows)...")
    conn.execute("DELETE FROM teams WHERE name LIKE ?", (f"{TEAM_PREFIX} team %",))
    conn.commit()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    print(f"Previous seed deleted in {time.monotonic() - started:.1f}s")


def ensure_reference_data(conn: sqlite3.Connection) -> tuple[list[int], list[int], list[int]]:
    for name in SEGMENTS:
        conn.execute("INSERT OR IGNORE INTO segments(name) VALUES (?)", (name,))
    segment_ids = [
        conn.execute("SELECT id FROM segments WHERE name = ?", (name,)).fetchone()[0]
        for name in SEGMENTS
    ]
    for name in BLOCKS:
        conn.execute("INSERT OR IGNORE INTO blocks(name) VALUES (?)", (name,))
    block_ids = {
        name: conn.execute("SELECT id FROM blocks WHERE name = ?", (name,)).fetchone()[0]
        for name in BLOCKS
    }

    template_ids = []
    for segment_name, segment_id in zip(SEGMENTS, segment_ids):
        for suffix in TEMPLATE_SUFFIXES:
            template_name = f"{TEAM_PREFIX} {segment_name.removeprefix('LOADTEST ')} {suffix}"
            conn.execute(
                "INSERT OR IGNORE INTO block_templates(name, segment_id) VALUES (?, ?)",
                (template_name, segment_id),
            )
            template_id = conn.execute(
                "SELECT id FROM block_templates WHERE name = ?", (template_name,)
            ).fetchone()[0]
            template_ids.append(template_id)
            names = BLOCKS[:2] if suffix == "fast" else BLOCKS
            conn.executemany(
                "INSERT OR IGNORE INTO template_blocks(template_id, block_id, schedule_offset) VALUES (?, ?, ?)",
                ((template_id, block_ids[name], index) for index, name in enumerate(names)),
            )

    password_hash = auth.hash_password(ADMIN_PASSWORD)
    user_specs = (
        ("Load", "Administrator", "admin", ADMIN_LOGIN, 0),
        ("Load", "Editor", "editor", "load_editor", 1),
        ("Load", "Executor", "user", "load_user", 1),
        ("Load", "Observer", "user", "load_observer", 0),
    )
    for last_name, first_name, role, login, is_assignee in user_specs:
        conn.execute(
            """INSERT INTO users
               (last_name, first_name, password_hash, role, login, is_assignee)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(login) DO UPDATE SET
                   last_name = excluded.last_name,
                   first_name = excluded.first_name,
                   password_hash = excluded.password_hash,
                   role = excluded.role,
                   is_assignee = excluded.is_assignee""",
            (last_name, first_name, password_hash, role, login, is_assignee),
        )
    user_ids = [
        conn.execute("SELECT id FROM users WHERE login = ?", (spec[3],)).fetchone()[0]
        for spec in user_specs
    ]
    conn.commit()
    return segment_ids, template_ids, user_ids


def create_teams(conn: sqlite3.Connection, count: int) -> list[int]:
    conn.executemany(
        "INSERT INTO teams(name) VALUES (?)",
        ((f"{TEAM_PREFIX} team {number:04d}",) for number in range(1, count + 1)),
    )
    conn.commit()
    return [
        row[0]
        for row in conn.execute(
            "SELECT id FROM teams WHERE name LIKE ? ORDER BY name",
            (f"{TEAM_PREFIX} team %",),
        )
    ]


def configure_teams_and_users(
    conn: sqlite3.Connection, team_ids: list[int], template_ids: list[int], user_ids: list[int]
) -> None:
    conn.executemany(
        "INSERT OR IGNORE INTO team_templates(team_id, template_id) VALUES (?, ?)",
        ((team_id, template_id) for team_id in team_ids for template_id in template_ids),
    )
    conn.executemany(
        "INSERT OR IGNORE INTO team_blocks(team_id, block_name, schedule_offset) VALUES (?, ?, ?)",
        ((team_id, block, index) for team_id in team_ids for index, block in enumerate(BLOCKS)),
    )
    # Admin has global access. Editor and executor see all teams, observer sees
    # only half of them and cannot be selected as assignee.
    editor_id, executor_id, observer_id = user_ids[1:]
    conn.executemany(
        "INSERT OR IGNORE INTO user_team_access(user_id, team_id) VALUES (?, ?)",
        [(editor_id, team_id) for team_id in team_ids]
        + [(executor_id, team_id) for team_id in team_ids]
        + [(observer_id, team_id) for team_id in team_ids[1::2]],
    )
    for offset in (-7, -1, 0, 1, 7, 30):
        conn.execute(
            "INSERT OR IGNORE INTO freeze_days(date) VALUES (?)",
            ((date.today() + timedelta(days=offset)).isoformat(),),
        )
    conn.commit()


def task_row(task_id: int, team_id: int, segment_id: int, template_id: int, team_position: int) -> tuple:
    criticality = CRITICALITIES[task_id % len(CRITICALITIES)]
    status = TASK_STATUSES[task_id % len(TASK_STATUSES)]
    psi_status = PSI_STATUSES[task_id % len(PSI_STATUSES)]
    is_deleted = int(task_id % 997 == 0)
    completion_template_id = template_id if psi_status != "required" and task_id % 10 == 0 else None
    completed_at = date.today().isoformat() if status in ("done", "cancelled") else None
    description = None
    if task_id % 4 == 0:
        description = f"Synthetic load record {task_id}; https://example.test/load/{task_id}"
    return (
        task_id,
        team_id,
        segment_id,
        f"{TEAM_PREFIX} task {task_id:09d} API UI performance scenario {task_id % 1000:03d}",
        description,
        criticality,
        team_position * 1000,
        status,
        psi_status,
        completed_at,
        completion_template_id,
        is_deleted,
    )


def assignment_rows(
    first_assignment_id: int, task_ids: list[int], per_task: int, today: date, assignee_ids: list[int]
):
    assignment_id = first_assignment_id
    for task_id in task_ids:
        psi_status = PSI_STATUSES[task_id % len(PSI_STATUSES)]
        task_deleted = task_id % 997 == 0
        completion_ready = psi_status != "required" and task_id % 10 == 0 and per_task >= 2
        for number in range(per_task):
            # 17 is coprime with 730, so dates stay unique for up to 730 rows per task.
            offset = ((task_id + number * 17) % 730) - 365
            assignment_date = (today + timedelta(days=offset)).isoformat()
            status = "success" if completion_ready and number < 2 else ASSIGNMENT_STATUSES[(task_id + number) % len(ASSIGNMENT_STATUSES)]
            time_spent = f"{(task_id + number) % 9:02d}:{((task_id + number) * 7) % 60:02d}" if status in ("success", "rollback") else None
            yield (
                assignment_id,
                task_id,
                assignment_date,
                BLOCKS[number] if completion_ready and number < 2 else BLOCKS[(task_id + number) % len(BLOCKS)],
                status,
                assignee_ids[(task_id + number) % len(assignee_ids)],
                f"Load-test assignment {assignment_id}" if assignment_id % 5 == 0 else None,
                0,
                time_spent,
                int(psi_status == "required" or task_deleted),
            )
            assignment_id += 1


def seed_rows(
    conn: sqlite3.Connection,
    team_ids: list[int],
    segment_ids: list[int],
    template_ids: list[int],
    user_ids: list[int],
    task_count: int,
    assignments_per_task: int,
    dependency_every: int,
    batch_size: int,
) -> tuple[int, int, int]:
    next_task_id = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM tasks").fetchone()[0]
    next_assignment_id = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM assignments").fetchone()[0]
    team_positions = {team_id: 0 for team_id in team_ids}
    previous_task_by_team: dict[int, int] = {}
    inserted_assignments = 0
    inserted_dependencies = 0
    started = time.monotonic()
    today = date.today()

    for batch_offset in range(0, task_count, batch_size):
        current_size = min(batch_size, task_count - batch_offset)
        batch_task_ids = list(range(next_task_id + batch_offset, next_task_id + batch_offset + current_size))
        tasks = []
        dependencies = []
        for global_offset, task_id in enumerate(batch_task_ids, start=batch_offset):
            team_id = team_ids[global_offset % len(team_ids)]
            segment_index = global_offset % len(segment_ids)
            team_positions[team_id] += 1
            # Fast template has two required blocks, so the default two assignments
            # can form a guaranteed completion-suggestion scenario.
            template_id = template_ids[segment_index * len(TEMPLATE_SUFFIXES) + 1]
            tasks.append(task_row(
                task_id, team_id, segment_ids[segment_index], template_id, team_positions[team_id]
            ))
            previous_task = previous_task_by_team.get(team_id)
            if dependency_every and previous_task is not None and (global_offset + 1) % dependency_every == 0:
                dependencies.append((task_id, previous_task))
            previous_task_by_team[team_id] = task_id

        conn.execute("BEGIN")
        try:
            conn.executemany(
                """
                INSERT INTO tasks
                    (id, team_id, segment_id, name, description, criticality, priority, task_status,
                     psi_status, completed_at, completion_template_id, is_deleted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tasks,
            )
            if assignments_per_task:
                conn.executemany(
                    """
                    INSERT INTO assignments(id, task_id, date, block, status, user_id, comment, is_psi, time_spent, is_deleted)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    assignment_rows(
                        next_assignment_id + inserted_assignments,
                        batch_task_ids,
                        assignments_per_task,
                        today,
                        user_ids[1:3],
                    ),
                )
                inserted_assignments += current_size * assignments_per_task
            if dependencies:
                conn.executemany(
                    "INSERT INTO task_dependencies(task_id, depends_on_task_id) VALUES (?, ?)",
                    dependencies,
                )
                inserted_dependencies += len(dependencies)
            conn.executemany(
                """INSERT INTO task_history
                   (task_id, action, field_name, old_value, new_value, changed_by_user_id)
                   VALUES (?, 'create', NULL, NULL, ?, ?)""",
                ((task_id, f'{TEAM_PREFIX} seeded task', user_ids[1]) for task_id in batch_task_ids if task_id % 100 == 0),
            )
            if assignments_per_task:
                first_id = next_assignment_id + inserted_assignments - current_size * assignments_per_task
                last_id = next_assignment_id + inserted_assignments
                history_ids = range(first_id, last_id, 250)
                conn.executemany(
                    """INSERT INTO assignment_history
                       (assignment_id, task_id, date, action, new_value, changed_by_user_id)
                       SELECT id, task_id, date, 'create', ?, ? FROM assignments WHERE id = ?""",
                    ((f'{TEAM_PREFIX} seeded assignment', user_ids[1], assignment_id) for assignment_id in history_ids),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        completed = batch_offset + current_size
        elapsed = time.monotonic() - started
        rate = completed / elapsed if elapsed else 0
        print(
            f"Tasks: {format_count(completed)}/{format_count(task_count)} "
            f"({completed / task_count:6.2%}), {format_count(int(rate))}/s",
            flush=True,
        )

    return task_count, inserted_assignments, inserted_dependencies


def main() -> int:
    args = parse_args()
    total_assignments = args.tasks * args.assignments_per_task
    approximate_dependencies = args.tasks // args.dependency_every if args.dependency_every else 0
    approximate_total = args.teams + args.tasks + total_assignments + approximate_dependencies

    print(f"Database: {args.database.resolve()}")
    print(
        "Planned rows: "
        f"teams={format_count(args.teams)}, tasks={format_count(args.tasks)}, "
        f"assignments={format_count(total_assignments)}, dependencies≈{format_count(approximate_dependencies)}, "
        f"total≈{format_count(approximate_total)}"
    )
    if not args.yes:
        answer = input("Continue? Type 'yes': ").strip().lower()
        if answer != "yes":
            print("Cancelled")
            return 1

    conn = connect_database(args.database)
    started = time.monotonic()
    try:
        existing = existing_seed_team_count(conn)
        if existing and not args.replace:
            raise RuntimeError(
                f"Found {existing} existing {TEAM_PREFIX} teams. "
                "Use --replace to remove the previous large seed first."
            )
        if args.replace:
            remove_existing_seed(conn)
        segment_ids, template_ids, user_ids = ensure_reference_data(conn)
        team_ids = create_teams(conn, args.teams)
        configure_teams_and_users(conn, team_ids, template_ids, user_ids)
        tasks, assignments, dependencies = seed_rows(
            conn,
            team_ids,
            segment_ids,
            template_ids,
            user_ids,
            args.tasks,
            args.assignments_per_task,
            args.dependency_every,
            args.batch_size,
        )
        conn.execute("PRAGMA optimize")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except Exception:
        print("Large seed stopped. Already committed batches can be removed with --replace.", file=sys.stderr)
        raise
    finally:
        conn.close()

    elapsed = time.monotonic() - started
    print(
        f"Done in {elapsed:.1f}s: teams={format_count(len(team_ids))}, tasks={format_count(tasks)}, "
        f"assignments={format_count(assignments)}, dependencies={format_count(dependencies)}"
    )
    print(f"UI logins (password {ADMIN_PASSWORD}): {ADMIN_LOGIN}, load_editor, load_user, load_observer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
