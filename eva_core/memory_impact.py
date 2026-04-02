"""
eva_core/memory_impact.py

MemoryImpactMixin — операции памяти для оценки влияния изменений.
MemoryImpactMixin — memory operations for change impact analysis.
"""

from __future__ import annotations

from psycopg2.extras import Json, RealDictCursor


class MemoryImpactMixin:
    """
    Работает с таблицами влияния изменений и нужными выборками графа.
    Works with impact tables and the graph reads needed for analysis.
    """

    def list_entity_relations(self) -> list[dict]:
        """
        Возвращает все связи вызовов между сущностями.
        Returns all call relations between code entities.
        """
        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT er.id,
                       er.source_module_id,
                       er.target_module_id,
                       er.from_entity_id,
                       er.to_entity_id,
                       er.relation_type,
                       er.call_line,
                       er.call_expr
                FROM entity_relations er
                ORDER BY er.id ASC;
                """
            )
            return cur.fetchall()

    def list_dependencies(self, kind: str | None = None) -> list[dict]:
        """
        Возвращает все зависимости модулей.
        Returns all module dependencies.
        """
        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            if kind:
                cur.execute(
                    """
                    SELECT id, from_module_id, to_module_id, kind
                    FROM dependencies
                    WHERE kind = %s
                    ORDER BY id ASC;
                    """,
                    (kind,),
                )
            else:
                cur.execute(
                    """
                    SELECT id, from_module_id, to_module_id, kind
                    FROM dependencies
                    ORDER BY id ASC;
                    """
                )
            return cur.fetchall()

    def replace_all_entity_impacts(self, impacts: list[dict]) -> int:
        """
        Полностью заменяет сохранённые entity-level impacts.
        Replaces stored entity-level impacts.
        """
        with self._conn.cursor() as cur:
            cur.execute("DELETE FROM entity_impacts;")
            created_count = 0
            for impact in impacts:
                cur.execute(
                    """
                    INSERT INTO entity_impacts (
                        source_entity_id, impacted_entity_id, source_module_id, impacted_module_id,
                        min_distance, is_direct
                    )
                    VALUES (%s, %s, %s, %s, %s, %s);
                    """,
                    (
                        int(impact["source_entity_id"]),
                        int(impact["impacted_entity_id"]),
                        int(impact["source_module_id"]),
                        int(impact["impacted_module_id"]),
                        int(impact["min_distance"]),
                        bool(impact["is_direct"]),
                    ),
                )
                created_count += 1

            self._conn.commit()
            return created_count

    def replace_all_module_impacts(self, impacts: list[dict]) -> int:
        """
        Полностью заменяет сохранённые module-level impacts.
        Replaces stored module-level impacts.
        """
        with self._conn.cursor() as cur:
            cur.execute("DELETE FROM module_impacts;")
            created_count = 0
            for impact in impacts:
                cur.execute(
                    """
                    INSERT INTO module_impacts (
                        source_module_id, impacted_module_id, min_distance, is_direct, via_kinds
                    )
                    VALUES (%s, %s, %s, %s, %s);
                    """,
                    (
                        int(impact["source_module_id"]),
                        int(impact["impacted_module_id"]),
                        int(impact["min_distance"]),
                        bool(impact["is_direct"]),
                        Json(impact.get("via_kinds") or []),
                    ),
                )
                created_count += 1

            self._conn.commit()
            return created_count

    def get_entity_impacts(self, module_name: str, qualname: str) -> list[dict]:
        """
        Возвращает сохранённое влияние для сущности.
        Returns persisted impact rows for an entity.
        """
        module_name = (module_name or "").strip()
        qualname = (qualname or "").strip()
        if not module_name or not qualname:
            return []

        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT ie.min_distance,
                       ie.is_direct,
                       ms.name AS source_module_name,
                       es.qualname AS source_entity_qualname,
                       mi.name AS impacted_module_name,
                       ei.qualname AS impacted_entity_qualname
                FROM entity_impacts ie
                JOIN code_entities es ON ie.source_entity_id = es.id
                JOIN modules ms ON ie.source_module_id = ms.id
                JOIN code_entities ei ON ie.impacted_entity_id = ei.id
                JOIN modules mi ON ie.impacted_module_id = mi.id
                WHERE ms.name = %s
                  AND es.qualname = %s
                ORDER BY ie.min_distance ASC, mi.name ASC, ei.qualname ASC;
                """,
                (module_name, qualname),
            )
            return cur.fetchall()

    def get_module_impacts(self, module_name: str) -> list[dict]:
        """
        Возвращает сохранённое влияние для модуля.
        Returns persisted impact rows for a module.
        """
        module_name = (module_name or "").strip()
        if not module_name:
            return []

        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT im.min_distance,
                       im.is_direct,
                       im.via_kinds,
                       ms.name AS source_module_name,
                       mi.name AS impacted_module_name
                FROM module_impacts im
                JOIN modules ms ON im.source_module_id = ms.id
                JOIN modules mi ON im.impacted_module_id = mi.id
                WHERE ms.name = %s
                ORDER BY im.min_distance ASC, mi.name ASC;
                """,
                (module_name,),
            )
            return cur.fetchall()
