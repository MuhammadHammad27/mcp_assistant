"""SQLite locally, PostgreSQL in hosted deployments, for Agency Operations."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "agency.db"
VALID_PRIORITIES = {"low", "medium", "high", "urgent"}
VALID_STATUSES = {"todo", "in_progress", "blocked", "done"}


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class AgencyStore:
    """Persists demo data locally with SQLite or in hosted Postgres via DATABASE_URL."""

    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH, database_url: str | None = None):
        self.database_url = (database_url or os.getenv("DATABASE_URL", "")).strip()
        self.uses_postgres = self.database_url.startswith(("postgres://", "postgresql://"))
        self.db_path = Path(db_path)

    def _sql(self, query: str) -> str:
        return query.replace("?", "%s") if self.uses_postgres else query

    @contextmanager
    def connection(self) -> Iterator[Any]:
        if self.uses_postgres:
            from psycopg import connect
            from psycopg.rows import dict_row

            conn = connect(self.database_url, row_factory=dict_row)
        else:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        if self.uses_postgres:
            schema = """
                CREATE TABLE IF NOT EXISTS projects (
                    id BIGSERIAL PRIMARY KEY,
                    client_name TEXT NOT NULL,
                    name TEXT NOT NULL,
                    brief TEXT NOT NULL,
                    plan_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    id BIGSERIAL PRIMARY KEY,
                    project_id BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    priority TEXT NOT NULL DEFAULT 'medium',
                    status TEXT NOT NULL DEFAULT 'todo',
                    due_date TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS proposals (
                    id BIGSERIAL PRIMARY KEY,
                    project_id BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS activity_log (
                    id BIGSERIAL PRIMARY KEY,
                    action TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id BIGINT,
                    detail TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
            """
        else:
            schema = """
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_name TEXT NOT NULL,
                    name TEXT NOT NULL,
                    brief TEXT NOT NULL,
                    plan_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    priority TEXT NOT NULL DEFAULT 'medium',
                    status TEXT NOT NULL DEFAULT 'todo',
                    due_date TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS proposals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS activity_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id INTEGER,
                    detail TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
            """
        with self.connection() as conn:
            for statement in schema.split(";"):
                if statement.strip():
                    conn.execute(statement)

    def _insert_id(self, conn: Any, query: str, values: tuple[Any, ...]) -> int:
        if self.uses_postgres:
            row = conn.execute(self._sql(query) + " RETURNING id", values).fetchone()
            return int(row["id"])
        cursor = conn.execute(query, values)
        return int(cursor.lastrowid)

    def _log(self, conn: Any, action: str, entity_type: str, entity_id: int | None, detail: dict[str, Any]) -> None:
        conn.execute(
            self._sql("INSERT INTO activity_log (action, entity_type, entity_id, detail, created_at) VALUES (?, ?, ?, ?, ?)"),
            (action, entity_type, entity_id, json.dumps(detail), utc_now()),
        )

    @staticmethod
    def _project(row: Any) -> dict[str, Any]:
        project = dict(row)
        project["plan"] = json.loads(project.pop("plan_json"))
        return project

    def create_project(self, client_name: str, name: str, brief: str, plan: dict[str, Any]) -> dict[str, Any]:
        if not client_name.strip() or not name.strip() or not brief.strip():
            raise ValueError("client_name, name, and brief are required")
        with self.connection() as conn:
            project_id = self._insert_id(
                conn,
                "INSERT INTO projects (client_name, name, brief, plan_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (client_name.strip(), name.strip(), brief.strip(), json.dumps(plan), utc_now()),
            )
            self._log(conn, "created", "project", project_id, {"name": name.strip(), "client_name": client_name.strip()})
        return self.get_project(project_id)

    def get_project(self, project_id: int) -> dict[str, Any]:
        with self.connection() as conn:
            row = conn.execute(self._sql("SELECT * FROM projects WHERE id = ?"), (project_id,)).fetchone()
        if row is None:
            raise ValueError(f"Project {project_id} was not found")
        return self._project(row)

    def list_projects(self) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute("SELECT * FROM projects ORDER BY id DESC").fetchall()
        return [self._project(row) for row in rows]

    def create_tasks(self, project_id: int, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self.get_project(project_id)
        if not tasks:
            raise ValueError("Provide at least one task")
        created: list[int] = []
        with self.connection() as conn:
            for task in tasks:
                title = str(task.get("title", "")).strip()
                if not title:
                    raise ValueError("Every task needs a title")
                priority = str(task.get("priority", "medium")).lower()
                if priority not in VALID_PRIORITIES:
                    raise ValueError(f"priority must be one of: {', '.join(sorted(VALID_PRIORITIES))}")
                status = str(task.get("status", "todo")).lower()
                if status not in VALID_STATUSES:
                    raise ValueError(f"status must be one of: {', '.join(sorted(VALID_STATUSES))}")
                task_id = self._insert_id(
                    conn,
                    "INSERT INTO tasks (project_id, title, description, priority, status, due_date, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (project_id, title, str(task.get("description", "")).strip(), priority, status, task.get("due_date") or None, utc_now()),
                )
                self._log(conn, "created", "task", task_id, {"project_id": project_id, "title": title, "priority": priority})
                created.append(task_id)
        return [self.get_task(task_id) for task_id in created]

    def get_task(self, task_id: int) -> dict[str, Any]:
        with self.connection() as conn:
            row = conn.execute(self._sql("SELECT * FROM tasks WHERE id = ?"), (task_id,)).fetchone()
        if row is None:
            raise ValueError(f"Task {task_id} was not found")
        return dict(row)

    def update_task_status(self, task_id: int, status: str) -> dict[str, Any]:
        normalized_status = status.lower().strip()
        if normalized_status not in VALID_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(sorted(VALID_STATUSES))}")
        with self.connection() as conn:
            task = conn.execute(self._sql("SELECT * FROM tasks WHERE id = ?"), (task_id,)).fetchone()
            if task is None:
                raise ValueError(f"Task {task_id} was not found")
            conn.execute(self._sql("UPDATE tasks SET status = ? WHERE id = ?"), (normalized_status, task_id))
            self._log(conn, "updated", "task", task_id, {"project_id": task["project_id"], "title": task["title"], "status": normalized_status})
        return self.get_task(task_id)

    def list_tasks(self, project_id: int | None = None, status: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM tasks"
        values: list[Any] = []
        clauses = []
        if project_id is not None:
            clauses.append("project_id = ?")
            values.append(project_id)
        if status and status != "all":
            if status not in VALID_STATUSES:
                raise ValueError(f"status must be one of: all, {', '.join(sorted(VALID_STATUSES))}")
            clauses.append("status = ?")
            values.append(status)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY CASE priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END, id DESC"
        with self.connection() as conn:
            rows = conn.execute(self._sql(query), values).fetchall()
        return [dict(row) for row in rows]

    def save_proposal(self, project_id: int, content: str) -> dict[str, Any]:
        self.get_project(project_id)
        if not content.strip():
            raise ValueError("Proposal content is required")
        with self.connection() as conn:
            proposal_id = self._insert_id(
                conn,
                "INSERT INTO proposals (project_id, content, created_at) VALUES (?, ?, ?)",
                (project_id, content.strip(), utc_now()),
            )
            self._log(conn, "created", "proposal", proposal_id, {"project_id": project_id})
        return {"id": proposal_id, "project_id": project_id, "content": content.strip()}

    def get_proposal(self, proposal_id: int) -> dict[str, Any]:
        with self.connection() as conn:
            row = conn.execute(self._sql("SELECT * FROM proposals WHERE id = ?"), (proposal_id,)).fetchone()
        if row is None:
            raise ValueError(f"Proposal {proposal_id} was not found")
        return dict(row)

    def dashboard(self) -> dict[str, Any]:
        with self.connection() as conn:
            projects = conn.execute("SELECT COUNT(*) AS total FROM projects").fetchone()["total"]
            task_rows = conn.execute("SELECT status, COUNT(*) AS total FROM tasks GROUP BY status").fetchall()
            activity_rows = conn.execute("SELECT * FROM activity_log ORDER BY id DESC LIMIT 20").fetchall()
        counts = {status: 0 for status in VALID_STATUSES}
        counts.update({row["status"]: row["total"] for row in task_rows})
        return {"project_count": projects, "task_counts": counts, "recent_activity": [dict(row) for row in activity_rows]}
