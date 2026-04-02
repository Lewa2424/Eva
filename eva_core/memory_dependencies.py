"""
eva_core/memory_dependencies.py

MemoryDependenciesMixin — операции памяти для зависимостей между модулями.
"""

from __future__ import annotations

from typing import Optional

from psycopg2.extras import RealDictCursor


class MemoryDependenciesMixin:
    def save_dependency(
        self,
        from_module_name: str,
        to_module_name: str,
        kind: str = "import",
    ) -> int:
        """
        Сохраняет связь между модулями.
        Saves a dependency between modules.
        """
        from_module_name = (from_module_name or "").strip()
        to_module_name = (to_module_name or "").strip()
        kind = (kind or "import").strip().lower()

        if not from_module_name or not to_module_name:
            raise ValueError("from_module_name and to_module_name are required")
        if kind not in ("import", "call", "other"):
            raise ValueError(f"kind must be one of: 'import', 'call', 'other', got: {kind}")

        from_module = self.get_module_by_name(from_module_name)
        to_module = self.get_module_by_name(to_module_name)

        if not from_module:
            raise ValueError(f"Module not found: {from_module_name}")
        if not to_module:
            raise ValueError(f"Module not found: {to_module_name}")

        from_module_id = from_module["id"]
        to_module_id = to_module["id"]

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

            cur.execute(
                """
                INSERT INTO dependencies (from_module_id, to_module_id, kind)
                VALUES (%s, %s, %s)
                RETURNING id;
                """,
                (from_module_id, to_module_id, kind),
            )
            self._conn.commit()
            return int(cur.fetchone()["id"])

    def replace_module_dependencies(
        self,
        module_name: str,
        target_module_names: list[str],
        kind: str = "import",
    ) -> int:
        """
        Полностью заменяет зависимости одного типа для модуля.
        Replaces dependencies of one kind for a module.
        """
        module_name = (module_name or "").strip()
        kind = (kind or "import").strip().lower()

        if not module_name:
            raise ValueError("module_name is required")
        if kind not in ("import", "call", "other"):
            raise ValueError(f"kind must be one of: 'import', 'call', 'other', got: {kind}")

        source_module = self.get_module_by_name(module_name)
        if not source_module:
            raise ValueError(f"Module not found: {module_name}")

        target_module_names = [name.strip() for name in target_module_names if name and name.strip()]
        target_module_names = sorted(set(target_module_names))

        with self._conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM dependencies
                WHERE from_module_id = %s AND kind = %s;
                """,
                (source_module["id"], kind),
            )

        created_count = 0
        for target_module_name in target_module_names:
            if target_module_name == module_name:
                continue
            self.save_dependency(module_name, target_module_name, kind=kind)
            created_count += 1

        return created_count

    def delete_dependencies_for_module(self, module_name: str) -> int:
        """
        Удаляет все зависимости модуля.
        Deletes all dependencies for a module.
        """
        module_name = (module_name or "").strip()
        if not module_name:
            return 0

        module = self.get_module_by_name(module_name)
        if not module:
            return 0

        module_id = module["id"]

        with self._conn.cursor() as cur:
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
        Returns dependencies for a module.
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
