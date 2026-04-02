"""
eva_core/memory_tasks.py

MemoryTasksMixin — операции памяти для задач, планов, версий кода,
результатов тестов и рефлексии.
"""

from __future__ import annotations

from typing import Any, Optional

from psycopg2.extras import Json, RealDictCursor


class MemoryTasksMixin:
    def get_context_for_goal(self, goal: str, limit: int = 10) -> dict:
        """
        Возвращает контекст для цели.
        Returns context for a goal.
        """
        context: dict[str, Any] = {"goal": goal, "recent_tasks": [], "plans": [], "reflections": []}

        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, goal, status, source, meta, created_at, updated_at
                FROM tasks
                ORDER BY created_at DESC
                LIMIT %s;
                """,
                (limit,),
            )
            tasks = cur.fetchall()
            context["recent_tasks"] = tasks

            task_ids = [t["id"] for t in tasks]
            if task_ids:
                cur.execute(
                    """
                    SELECT id, task_id, plan_text, meta, created_at
                    FROM plans
                    WHERE task_id = ANY(%s)
                    ORDER BY created_at DESC
                    LIMIT %s;
                    """,
                    (task_ids, limit),
                )
                context["plans"] = cur.fetchall()

                cur.execute(
                    """
                    SELECT id, task_id, reflection, meta, created_at
                    FROM reflections
                    WHERE task_id = ANY(%s)
                    ORDER BY created_at DESC
                    LIMIT %s;
                    """,
                    (task_ids, limit),
                )
                context["reflections"] = cur.fetchall()

        return context

    def get_module_info(self, module_name: str) -> dict:
        """
        Возвращает информацию о модуле по версиям кода.
        Returns code-version information for a module.
        """
        module_name = (module_name or "").strip()
        if not module_name:
            return {"module_name": "", "latest": None, "versions_count": 0}

        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, module_name, status, meta, created_at
                FROM code_versions
                WHERE module_name = %s
                ORDER BY created_at DESC
                LIMIT 1;
                """,
                (module_name,),
            )
            latest = cur.fetchone()

            cur.execute(
                """
                SELECT COUNT(*) AS cnt
                FROM code_versions
                WHERE module_name = %s;
                """,
                (module_name,),
            )
            cnt = cur.fetchone()["cnt"]

        return {"module_name": module_name, "latest": latest, "versions_count": cnt}

    def get_recent_errors(self, module_name: str, limit: int = 10) -> list[dict]:
        """
        Возвращает последние ошибки тестов по модулю.
        Returns recent non-passing test results for a module.
        """
        module_name = (module_name or "").strip()
        if not module_name:
            return []

        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT tr.id,
                       tr.task_id,
                       tr.code_version_id,
                       tr.status,
                       tr.output,
                       tr.meta,
                       tr.created_at
                FROM test_results tr
                JOIN code_versions cv ON cv.id = tr.code_version_id
                WHERE cv.module_name = %s
                  AND tr.status <> 'pass'
                ORDER BY tr.created_at DESC
                LIMIT %s;
                """,
                (module_name, limit),
            )
            return cur.fetchall()

    def save_task(self, goal: str, status: str = "new", source: str = "user", meta: Optional[dict] = None) -> int:
        """
        Создаёт задачу.
        Creates a task.
        """
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tasks (goal, status, source, meta)
                VALUES (%s, %s, %s, %s)
                RETURNING id;
                """,
                (goal, status, source, Json(meta) if meta is not None else None),
            )
            return int(cur.fetchone()[0])

    def update_task_status(self, task_id: int, status: str) -> None:
        """
        Обновляет статус задачи.
        Updates task status.
        """
        with self._conn.cursor() as cur:
            cur.execute(
                """
                UPDATE tasks
                SET status = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s;
                """,
                (status, task_id),
            )

    def save_plan(self, task_id: int, plan_text: str, meta: Optional[dict] = None) -> int:
        """
        Сохраняет план по задаче.
        Saves a plan for a task.
        """
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO plans (task_id, plan_text, meta)
                VALUES (%s, %s, %s)
                RETURNING id;
                """,
                (task_id, plan_text, Json(meta) if meta is not None else None),
            )
            return int(cur.fetchone()[0])

    def save_code_version(
        self,
        module_name: str,
        code_text: str,
        status: str = "draft",
        meta: Optional[dict] = None,
    ) -> int:
        """
        Сохраняет версию кода.
        Saves a code version.
        """
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO code_versions (module_name, status, code_text, meta)
                VALUES (%s, %s, %s, %s)
                RETURNING id;
                """,
                (module_name, status, code_text, Json(meta) if meta is not None else None),
            )
            return int(cur.fetchone()[0])

    def save_test_result(
        self,
        task_id: int,
        status: str,
        output: Optional[str] = None,
        code_version_id: Optional[int] = None,
        meta: Optional[dict] = None,
    ) -> int:
        """
        Сохраняет результат теста.
        Saves a test result.
        """
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO test_results (task_id, code_version_id, status, output, meta)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    task_id,
                    code_version_id,
                    status,
                    output,
                    Json(meta) if meta is not None else None,
                ),
            )
            return int(cur.fetchone()[0])

    def save_reflection(self, task_id: int, reflection: str, meta: Optional[dict] = None) -> int:
        """
        Сохраняет рефлексию.
        Saves a reflection record.
        """
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO reflections (task_id, reflection, meta)
                VALUES (%s, %s, %s)
                RETURNING id;
                """,
                (task_id, reflection, Json(meta) if meta is not None else None),
            )
            return int(cur.fetchone()[0])

    def get_task(self, task_id: int) -> Optional[dict]:
        """
        Возвращает задачу по id.
        Returns a task by id.
        """
        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, goal, status, source, meta, created_at, updated_at
                FROM tasks
                WHERE id = %s;
                """,
                (task_id,),
            )
            return cur.fetchone()
