"""Generate millions of deterministic SQLite rows for UI and API load testing.

The regular ``seed_demo_data.py`` remains the small human-friendly demo seed.
This script uses batched SQL inserts and creates isolated entities whose names
start with ``LOADTEST``.

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
SEGMENT_NAME = "LOADTEST segment"
ADMIN_LOGIN = "load_admin"
ADMIN_PASSWORD = "password123"
CRITICALITIES = ("low", "medium", "high")
TASK_STATUSES = ("new", "new", "new", "new", "done", "cancelled")
ASSIGNMENT_STATUSES = ("new", "planned", "success", "rollback", "cancelled")
BLOCKS = ("Analysis", "Development", "Review", "Release", None)


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


def ensure_reference_data(conn: sqlite3.Connection) -> tuple[int, int]:
    conn.execute("INSERT OR IGNORE INTO segments(name) VALUES (?)", (SEGMENT_NAME,))
    segment_id = conn.execute("SELECT id FROM segments WHERE name = ?", (SEGMENT_NAME,)).fetchone()[0]

    admin = conn.execute("SELECT id FROM users WHERE login = ?", (ADMIN_LOGIN,)).fetchone()
    if admin is None:
        cursor = conn.execute(
            """
            INSERT INTO users(last_name, first_name, middle_name, password_hash, role, login, is_assignee)
            VALUES (?, ?, ?, ?, 'admin', ?, 0)
            """,
            ("Load", "Administrator", None, auth.hash_password(ADMIN_PASSWORD), ADMIN_LOGIN),
        )
        admin_id = cursor.lastrowid
    else:
        admin_id = admin[0]
    conn.commit()
    return segment_id, admin_id


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


def task_row(task_id: int, team_id: int, segment_id: int, team_position: int) -> tuple:
    criticality = CRITICALITIES[task_id % len(CRITICALITIES)]
    status = TASK_STATUSES[task_id % len(TASK_STATUSES)]
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
    )


def assignment_rows(first_assignment_id: int, task_ids: list[int], per_task: int, today: date):
    assignment_id = first_assignment_id
    for task_id in task_ids:
        for number in range(per_task):
            # 17 is coprime with 730, so dates stay unique for up to 730 rows per task.
            offset = ((task_id + number * 17) % 730) - 365
            assignment_date = (today + timedelta(days=offset)).isoformat()
            status = ASSIGNMENT_STATUSES[(task_id + number) % len(ASSIGNMENT_STATUSES)]
            time_spent = f"{(task_id + number) % 9:02d}:{((task_id + number) * 7) % 60:02d}" if status in ("success", "rollback") else None
            yield (
                assignment_id,
                task_id,
                assignment_date,
                BLOCKS[(task_id + number) % len(BLOCKS)],
                status,
                None,
                f"Load-test assignment {assignment_id}" if assignment_id % 5 == 0 else None,
                0,
                time_spent,
                0,
            )
            assignment_id += 1


def seed_rows(
    conn: sqlite3.Connection,
    team_ids: list[int],
    segment_id: int,
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
            team_positions[team_id] += 1
            tasks.append(task_row(task_id, team_id, segment_id, team_positions[team_id]))
            previous_task = previous_task_by_team.get(team_id)
            if dependency_every and previous_task is not None and (global_offset + 1) % dependency_every == 0:
                dependencies.append((task_id, previous_task))
            previous_task_by_team[team_id] = task_id

        conn.execute("BEGIN")
        try:
            conn.executemany(
                """
                INSERT INTO tasks(id, team_id, segment_id, name, description, criticality, priority, task_status, is_deleted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                tasks,
            )
            if assignments_per_task:
                conn.executemany(
                    """
                    INSERT INTO assignments(id, task_id, date, block, status, user_id, comment, is_psi, time_spent, is_deleted)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    assignment_rows(next_assignment_id + inserted_assignments, batch_task_ids, assignments_per_task, today),
                )
                inserted_assignments += current_size * assignments_per_task
            if dependencies:
                conn.executemany(
                    "INSERT INTO task_dependencies(task_id, depends_on_task_id) VALUES (?, ?)",
                    dependencies,
                )
                inserted_dependencies += len(dependencies)
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
        segment_id, _admin_id = ensure_reference_data(conn)
        team_ids = create_teams(conn, args.teams)
        tasks, assignments, dependencies = seed_rows(
            conn,
            team_ids,
            segment_id,
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
    print(f"UI login: {ADMIN_LOGIN} / {ADMIN_PASSWORD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
