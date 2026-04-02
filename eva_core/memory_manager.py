"""
eva_core/memory_manager.py

MemoryManager — долговременная память Евы 2.0 (PostgreSQL).
Единая точка доступа к данным: задачи, планы, версии кода, тесты, рефлексия.
"""

from __future__ import annotations

import os
from typing import Any, Optional

import psycopg2
from psycopg2.extras import Json, RealDictCursor
from dotenv import load_dotenv


class MemoryManager:
    def __init__(self) -> None:
        load_dotenv()
        dsn = (os.getenv("POSTGRES_DSN") or "").strip()
        if not dsn:
            raise RuntimeError("POSTGRES_DSN is not set. Add it to .env")

        self._conn = psycopg2.connect(dsn)
        self._conn.autocommit = True

    def close(self) -> None:
        """Закрывает соединение с БД."""
        if getattr(self, "_conn", None):
            self._conn.close()

    def ping(self) -> bool:
        """Проверяет, что соединение с БД живое."""
        with self._conn.cursor() as cur:
            cur.execute("SELECT 1;")
            return cur.fetchone() == (1,)

    # -------------------------
    # Контекст для принятия решений
    # -------------------------

    def get_context_for_goal(self, goal: str, limit: int = 10) -> dict:
        """
        Возвращает контекст для цели:
        - последние задачи
        - последние планы по ним
        - последние рефлексии по ним
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
        Возвращает информацию о модуле:
        - последняя версия кода
        - количество версий
        - последняя дата изменения
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
        Возвращает последние неуспешные результаты тестов по указанному модулю.
        Связь идёт через code_versions (module_name) -> test_results(code_version_id).
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

    # -------------------------
    # Запись результатов и опыта
    # -------------------------

    def save_task(self, goal: str, status: str = "new", source: str = "user", meta: Optional[dict] = None) -> int:
        """Создаёт задачу и возвращает её id."""
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tasks (goal, status, source, meta)
                VALUES (%s, %s, %s, %s)
                RETURNING id;
                """,
                (goal, status, source, psycopg2.extras.Json(meta) if meta is not None else None),
            )
            return int(cur.fetchone()[0])

    def update_task_status(self, task_id: int, status: str) -> None:
        """Обновляет статус задачи."""
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
        """Сохраняет план по задаче и возвращает id плана."""
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO plans (task_id, plan_text, meta)
                VALUES (%s, %s, %s)
                RETURNING id;
                """,
                (task_id, plan_text, psycopg2.extras.Json(meta) if meta is not None else None),
            )
            return int(cur.fetchone()[0])

    def save_code_version(
        self,
        module_name: str,
        code_text: str,
        status: str = "draft",
        meta: Optional[dict] = None,
    ) -> int:
        """Сохраняет версию кода и возвращает id версии."""
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO code_versions (module_name, status, code_text, meta)
                VALUES (%s, %s, %s, %s)
                RETURNING id;
                """,
                (module_name, status, code_text, psycopg2.extras.Json(meta) if meta is not None else None),
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
        """Сохраняет результат тестов и возвращает id записи."""
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
                    psycopg2.extras.Json(meta) if meta is not None else None,
                ),
            )
            return int(cur.fetchone()[0])

    def save_reflection(self, task_id: int, reflection: str, meta: Optional[dict] = None) -> int:
        """Сохраняет рефлексию и возвращает id записи."""
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO reflections (task_id, reflection, meta)
                VALUES (%s, %s, %s)
                RETURNING id;
                """,
                (task_id, reflection, psycopg2.extras.Json(meta) if meta is not None else None),
            )
            return int(cur.fetchone()[0])

    def save_module(
        self,
        name: str,
        file_path: str,
        description: Optional[str] = None,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
        metrics: Optional[dict] = None,
        status: str = "unknown",
        meta: Optional[dict] = None,
        content_hash: Optional[str] = None,
    ) -> int:
        """
        Вставляет или обновляет запись в таблице modules по name (name уникальный).
        Возвращает id модуля.
        """
        name = (name or "").strip()
        file_path = (file_path or "").strip()
        if not name or not file_path:
            raise ValueError("name and file_path are required")

        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO modules (
                    name, file_path, description, start_line, end_line, metrics,
                    status, meta, content_hash, updated_at, last_seen_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT (name) DO UPDATE
                SET file_path = EXCLUDED.file_path,
                    description = EXCLUDED.description,
                    start_line = EXCLUDED.start_line,
                    end_line = EXCLUDED.end_line,
                    metrics = EXCLUDED.metrics,
                    status = EXCLUDED.status,
                    meta = EXCLUDED.meta,
                    content_hash = EXCLUDED.content_hash,
                    updated_at = CURRENT_TIMESTAMP,
                    last_seen_at = CURRENT_TIMESTAMP
                RETURNING id;
                """,
                (
                    name,
                    file_path,
                    description,
                    start_line,
                    end_line,
                    Json(metrics) if metrics is not None else None,
                    status,
                    Json(meta) if meta is not None else None,
                    content_hash,
                ),
            )
            self._conn.commit()
            return int(cur.fetchone()[0])

    # -------------------------
    # Минимальное чтение (для проверки)
    # -------------------------

    def get_task(self, task_id: int) -> Optional[dict]:
        """Возвращает задачу по id (или None)."""
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

    def get_module_by_name(self, name: str) -> Optional[dict]:
        """Возвращает модуль по name (или None)."""
        name = (name or "").strip()
        if not name:
            return None

        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, name, description, file_path, start_line, end_line, metrics, status, meta,
                       content_hash, created_at, updated_at, last_seen_at
                FROM modules
                WHERE name = %s;
                """,
                (name,),
            )
            return cur.fetchone()

    def update_module_last_seen(self, name: str) -> None:
        """Обновляет только last_seen_at для модуля по name."""
        name = (name or "").strip()
        if not name:
            return

        with self._conn.cursor() as cur:
            cur.execute(
                """
                UPDATE modules
                SET last_seen_at = CURRENT_TIMESTAMP
                WHERE name = %s;
                """,
                (name,),
            )
            self._conn.commit()

    # -------------------------
    # Работа с зависимостями (dependencies)
    # -------------------------

    def save_dependency(
        self,
        from_module_name: str,
        to_module_name: str,
        kind: str = "import",
    ) -> int:
        """
        Сохраняет связь между модулями (зависимость).

        Args:
            from_module_name: Имя модуля, который зависит (например, "eva_core/decision_engine.py").
            to_module_name: Имя модуля, от которого зависит (например, "eva_core/memory_manager.py").
            kind: Тип связи: "import", "call", "other" (по умолчанию "import").

        Returns:
            id созданной зависимости.

        Raises:
            ValueError: Если модуль не найден или kind некорректный.
        """
        from_module_name = (from_module_name or "").strip()
        to_module_name = (to_module_name or "").strip()
        kind = (kind or "import").strip().lower()

        if not from_module_name or not to_module_name:
            raise ValueError("from_module_name and to_module_name are required")

        if kind not in ("import", "call", "other"):
            raise ValueError(f"kind must be one of: 'import', 'call', 'other', got: {kind}")

        # Получаем id модулей по именам
        from_module = self.get_module_by_name(from_module_name)
        to_module = self.get_module_by_name(to_module_name)

        if not from_module:
            raise ValueError(f"Module not found: {from_module_name}")
        if not to_module:
            raise ValueError(f"Module not found: {to_module_name}")

        from_module_id = from_module["id"]
        to_module_id = to_module["id"]

        # Если связь уже существует (благодаря UNIQUE constraint), просто возвращаем существующую
        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id FROM dependencies
                WHERE from_module_id = %s AND to_module_id = %s AND kind = %s;
                """,
                (from_module_id, to_module_id, kind),
            )
            existing = cur.fetchone()
            if existing:
                return int(existing["id"])

            # Создаём новую связь
            cur.execute(
                """
                INSERT INTO dependencies (from_module_id, to_module_id, kind)
                VALUES (%s, %s, %s)
                RETURNING id;
                """,
                (from_module_id, to_module_id, kind),
            )
            self._conn.commit()
            return int(cur.fetchone()[0])

    def delete_dependencies_for_module(self, module_name: str) -> int:
        """
        Удаляет все зависимости для указанного модуля (и входящие, и исходящие).

        Используется перед обновлением мета-карты модуля: сначала удаляем старые связи,
        потом добавляем новые.

        Args:
            module_name: Имя модуля.

        Returns:
            Количество удалённых зависимостей.
        """
        module_name = (module_name or "").strip()
        if not module_name:
            return 0

        module = self.get_module_by_name(module_name)
        if not module:
            return 0

        module_id = module["id"]

        with self._conn.cursor() as cur:
            # Удаляем все зависимости, где модуль является источником или целью
            cur.execute(
                """
                DELETE FROM dependencies
                WHERE from_module_id = %s OR to_module_id = %s;
                """,
                (module_id, module_id),
            )
            deleted_count = cur.rowcount
            self._conn.commit()
            return deleted_count

    def get_dependents(self, module_name: str, kind: Optional[str] = None) -> list[dict]:
        """
        Возвращает зависимости модуля.

        Args:
            module_name: Имя модуля.
            kind: Фильтр по типу связи (опционально): "import", "call", "other".
                  Если None, возвращает все типы.

        Returns:
            Список зависимостей, каждая запись содержит:
            - from_module_name: откуда идёт зависимость
            - to_module_name: куда идёт зависимость
            - kind: тип связи
            - id: id зависимости
        """
        module_name = (module_name or "").strip()
        if not module_name:
            return []

        module = self.get_module_by_name(module_name)
        if not module:
            return []

        module_id = module["id"]

        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            if kind:
                # Фильтр по типу связи
                cur.execute(
                    """
                    SELECT d.id, d.kind,
                           m_from.name AS from_module_name,
                           m_to.name AS to_module_name
                    FROM dependencies d
                    JOIN modules m_from ON d.from_module_id = m_from.id
                    JOIN modules m_to ON d.to_module_id = m_to.id
                    WHERE (d.from_module_id = %s OR d.to_module_id = %s)
                      AND d.kind = %s
                    ORDER BY d.created_at DESC;
                    """,
                    (module_id, module_id, kind),
                )
            else:
                # Все типы связей
                cur.execute(
                    """
                    SELECT d.id, d.kind,
                           m_from.name AS from_module_name,
                           m_to.name AS to_module_name
                    FROM dependencies d
                    JOIN modules m_from ON d.from_module_id = m_from.id
                    JOIN modules m_to ON d.to_module_id = m_to.id
                    WHERE d.from_module_id = %s OR d.to_module_id = %s
                    ORDER BY d.created_at DESC;
                    """,
                    (module_id, module_id),
                )

            return cur.fetchall()


