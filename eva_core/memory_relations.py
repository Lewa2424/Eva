"""
eva_core/memory_relations.py

MemoryRelationsMixin — операции памяти для связей вызовов между сущностями кода.
MemoryRelationsMixin — memory operations for call relations between code entities.
"""

from __future__ import annotations

from psycopg2.extras import RealDictCursor


class MemoryRelationsMixin:
    """
    Работает со связями вызовов между сущностями кода.
    Works with call relations between code entities.
    """

    def list_code_entities(self) -> list[dict]:
        """
        Возвращает все сущности кода с именами модулей.
        Returns all code entities with module names.
        """
        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT e.id,
                       e.module_id,
                       m.name AS module_name,
                       e.entity_type,
                       e.name,
                       e.qualname,
                       e.parent_qualname
                FROM code_entities e
                JOIN modules m ON e.module_id = m.id
                ORDER BY m.name ASC, e.qualname ASC;
                """
            )
            return cur.fetchall()

    def replace_module_entity_relations(self, module_name: str, relations: list[dict]) -> int:
        """
        Полностью заменяет связи вызовов для одного модуля.
        Replaces all call relations for one module.
        """
        module_name = (module_name or "").strip()
        if not module_name:
            raise ValueError("module_name is required")

        source_module = self.get_module_by_name(module_name)
        if not source_module:
            raise ValueError(f"Module not found: {module_name}")

        source_module_id = int(source_module["id"])
        created_count = 0
        target_module_names: set[str] = set()

        with self._conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM entity_relations
                WHERE source_module_id = %s;
                """,
                (source_module_id,),
            )

            for relation in relations:
                from_entity_id = relation.get("from_entity_id")
                to_entity_id = relation.get("to_entity_id")
                target_module_id = relation.get("target_module_id")
                target_module_name = relation.get("target_module_name")

                if not from_entity_id or not to_entity_id or not target_module_id or not target_module_name:
                    continue

                cur.execute(
                    """
                    INSERT INTO entity_relations (
                        source_module_id, target_module_id, from_entity_id, to_entity_id,
                        relation_type, call_line, call_expr
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                    """,
                    (
                        source_module_id,
                        int(target_module_id),
                        int(from_entity_id),
                        int(to_entity_id),
                        relation.get("relation_type") or "call",
                        relation.get("call_line"),
                        relation.get("call_expr"),
                    ),
                )
                target_module_names.add(str(target_module_name))
                created_count += 1

            cur.execute(
                """
                UPDATE modules
                SET calls_synced_at = CURRENT_TIMESTAMP
                WHERE id = %s;
                """,
                (source_module_id,),
            )

            self._conn.commit()

        self.replace_module_dependencies(module_name, sorted(target_module_names), kind="call")
        return created_count

    def get_module_entity_relations(self, module_name: str) -> list[dict]:
        """
        Возвращает связи вызовов для одного модуля.
        Returns call relations for one module.
        """
        module_name = (module_name or "").strip()
        if not module_name:
            return []

        source_module = self.get_module_by_name(module_name)
        if not source_module:
            return []

        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT er.id,
                       er.relation_type,
                       er.call_line,
                       er.call_expr,
                       mf.name AS from_module_name,
                       ef.qualname AS from_entity_qualname,
                       mt.name AS to_module_name,
                       et.qualname AS to_entity_qualname
                FROM entity_relations er
                JOIN modules mf ON er.source_module_id = mf.id
                JOIN modules mt ON er.target_module_id = mt.id
                JOIN code_entities ef ON er.from_entity_id = ef.id
                JOIN code_entities et ON er.to_entity_id = et.id
                WHERE er.source_module_id = %s
                ORDER BY er.call_line ASC, er.id ASC;
                """,
                (int(source_module["id"]),),
            )
            return cur.fetchall()
