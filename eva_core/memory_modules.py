"""
eva_core/memory_modules.py

MemoryModulesMixin — операции памяти для модулей, AST-снимков и импортов.
"""

from __future__ import annotations

from typing import Optional

from psycopg2.extras import Json, RealDictCursor


class MemoryModulesMixin:
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
        Сохраняет или обновляет модуль в мета-карте.
        Saves or updates a module in the code map.
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
                    status, meta, content_hash, updated_at, last_seen_at, ast_synced_at, calls_synced_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, NULL, NULL)
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
                    last_seen_at = CURRENT_TIMESTAMP,
                    ast_synced_at = NULL,
                    calls_synced_at = NULL
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

    def get_module_by_name(self, name: str) -> Optional[dict]:
        """
        Возвращает модуль по имени.
        Returns a module by name.
        """
        name = (name or "").strip()
        if not name:
            return None

        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, name, description, file_path, start_line, end_line, metrics, status, meta,
                       content_hash, created_at, updated_at, last_seen_at, ast_synced_at, calls_synced_at
                FROM modules
                WHERE name = %s;
                """,
                (name,),
            )
            return cur.fetchone()

    def list_modules(self) -> list[dict]:
        """
        Возвращает список всех модулей.
        Returns all modules from the code map.
        """
        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, name, file_path, status, content_hash, last_seen_at, ast_synced_at, calls_synced_at
                FROM modules
                ORDER BY file_path ASC;
                """
            )
            return cur.fetchall()

    def update_module_last_seen(self, name: str) -> None:
        """
        Обновляет только время последнего обнаружения модуля.
        Updates only the module last-seen timestamp.
        """
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

    def get_module_imports(self, module_name: str) -> list[dict]:
        """
        Возвращает импорты модуля.
        Returns stored imports for a module.
        """
        module_name = (module_name or "").strip()
        if not module_name:
            return []

        module = self.get_module_by_name(module_name)
        if not module:
            return []

        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT import_type, imported_module, imported_name, alias_name, is_relative, relative_level
                FROM module_imports
                WHERE module_id = %s
                ORDER BY id ASC;
                """,
                (module["id"],),
            )
            return cur.fetchall()

    def replace_module_ast_snapshot(
        self,
        module_name: str,
        entities: list[dict],
        imports: list[dict],
    ) -> None:
        """
        Полностью заменяет AST-снимок модуля.
        Replaces the full AST snapshot of a module.
        """
        module_name = (module_name or "").strip()
        if not module_name:
            raise ValueError("module_name is required")

        module = self.get_module_by_name(module_name)
        if not module:
            raise ValueError(f"Module not found: {module_name}")

        module_id = int(module["id"])

        with self._conn.cursor() as cur:
            cur.execute("DELETE FROM module_imports WHERE module_id = %s;", (module_id,))
            cur.execute("DELETE FROM code_entities WHERE module_id = %s;", (module_id,))

            for entity in entities:
                cur.execute(
                    """
                    INSERT INTO code_entities (
                        module_id, entity_type, name, qualname, parent_qualname,
                        start_line, end_line, decorators, docstring
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """,
                    (
                        module_id,
                        entity.get("entity_type"),
                        entity.get("name"),
                        entity.get("qualname"),
                        entity.get("parent_qualname"),
                        entity.get("start_line"),
                        entity.get("end_line"),
                        Json(entity.get("decorators") or []),
                        entity.get("docstring"),
                    ),
                )

            for import_item in imports:
                cur.execute(
                    """
                    INSERT INTO module_imports (
                        module_id, import_type, imported_module, imported_name,
                        alias_name, is_relative, relative_level
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                    """,
                    (
                        module_id,
                        import_item.get("import_type"),
                        import_item.get("imported_module"),
                        import_item.get("imported_name"),
                        import_item.get("alias_name"),
                        bool(import_item.get("is_relative", False)),
                        int(import_item.get("relative_level", 0)),
                    ),
                )

            cur.execute(
                """
                UPDATE modules
                SET ast_synced_at = CURRENT_TIMESTAMP
                WHERE id = %s;
                """,
                (module_id,),
            )

            self._conn.commit()
