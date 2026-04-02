"""
eva_core/memory_metrics.py

MemoryMetricsMixin — операции памяти для метрик критичности и хрупкости.
MemoryMetricsMixin — memory operations for criticality and fragility metrics.
"""

from __future__ import annotations

from psycopg2.extras import RealDictCursor


class MemoryMetricsMixin:
    """
    Работает с таблицами метрик сущностей и модулей.
    Works with entity and module metric tables.
    """

    def replace_all_entity_metrics(self, metrics: list[dict]) -> int:
        """
        Полностью заменяет сохранённые entity-level metrics.
        Replaces stored entity-level metrics.
        """
        with self._conn.cursor() as cur:
            cur.execute("DELETE FROM entity_metrics;")
            created_count = 0
            for metric in metrics:
                cur.execute(
                    """
                    INSERT INTO entity_metrics (
                        entity_id, module_id, direct_entity_impact_count, indirect_entity_impact_count,
                        incoming_call_count, criticality_score, fragility_score
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                    """,
                    (
                        int(metric["entity_id"]),
                        int(metric["module_id"]),
                        int(metric["direct_entity_impact_count"]),
                        int(metric["indirect_entity_impact_count"]),
                        int(metric["incoming_call_count"]),
                        float(metric["criticality_score"]),
                        float(metric["fragility_score"]),
                    ),
                )
                created_count += 1

            self._conn.commit()
            return created_count

    def replace_all_module_metrics(self, metrics: list[dict]) -> int:
        """
        Полностью заменяет сохранённые module-level metrics.
        Replaces stored module-level metrics.
        """
        with self._conn.cursor() as cur:
            cur.execute("DELETE FROM module_metrics;")
            created_count = 0
            for metric in metrics:
                cur.execute(
                    """
                    INSERT INTO module_metrics (
                        module_id, direct_module_impact_count, indirect_module_impact_count,
                        incoming_dependency_count, criticality_score, fragility_score
                    )
                    VALUES (%s, %s, %s, %s, %s, %s);
                    """,
                    (
                        int(metric["module_id"]),
                        int(metric["direct_module_impact_count"]),
                        int(metric["indirect_module_impact_count"]),
                        int(metric["incoming_dependency_count"]),
                        float(metric["criticality_score"]),
                        float(metric["fragility_score"]),
                    ),
                )
                created_count += 1

            self._conn.commit()
            return created_count

    def get_top_entity_metrics(self, limit: int = 10) -> list[dict]:
        """
        Возвращает самые критичные сущности.
        Returns the most critical entities.
        """
        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT m.name AS module_name,
                       e.qualname,
                       em.direct_entity_impact_count,
                       em.indirect_entity_impact_count,
                       em.incoming_call_count,
                       em.criticality_score,
                       em.fragility_score
                FROM entity_metrics em
                JOIN code_entities e ON em.entity_id = e.id
                JOIN modules m ON em.module_id = m.id
                ORDER BY em.criticality_score DESC, em.fragility_score DESC, m.name ASC, e.qualname ASC
                LIMIT %s;
                """,
                (int(limit),),
            )
            return cur.fetchall()

    def get_top_module_metrics(self, limit: int = 10) -> list[dict]:
        """
        Возвращает самые критичные модули.
        Returns the most critical modules.
        """
        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT m.name AS module_name,
                       mm.direct_module_impact_count,
                       mm.indirect_module_impact_count,
                       mm.incoming_dependency_count,
                       mm.criticality_score,
                       mm.fragility_score
                FROM module_metrics mm
                JOIN modules m ON mm.module_id = m.id
                ORDER BY mm.criticality_score DESC, mm.fragility_score DESC, m.name ASC
                LIMIT %s;
                """,
                (int(limit),),
            )
            return cur.fetchall()
