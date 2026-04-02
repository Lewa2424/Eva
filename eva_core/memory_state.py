"""
eva_core/memory_state.py

MemoryStateMixin — операции памяти для снимков состояний и сравнений до/после.
MemoryStateMixin — memory operations for state snapshots and before/after comparisons.
"""

from __future__ import annotations

from psycopg2.extras import RealDictCursor


class MemoryStateMixin:
    """
    Работает со снимками состояния и сохранёнными дельтами.
    Works with state snapshots and persisted diffs.
    """

    def collect_state_totals(self) -> dict:
        """
        Собирает агрегированные размеры текущего состояния проекта.
        Collects aggregate sizes of the current project state.
        """
        totals: dict[str, int] = {}
        with self._conn.cursor() as cur:
            for key, table_name in (
                ("total_modules", "modules"),
                ("total_entities", "code_entities"),
                ("total_dependencies", "dependencies"),
                ("total_entity_relations", "entity_relations"),
                ("total_entity_impacts", "entity_impacts"),
                ("total_module_impacts", "module_impacts"),
                ("total_entity_metrics", "entity_metrics"),
                ("total_module_metrics", "module_metrics"),
            ):
                cur.execute(f"SELECT COUNT(*) FROM {table_name};")
                totals[key] = int(cur.fetchone()[0])
        return totals

    def create_state_snapshot(self, reason: str, totals: dict) -> int:
        """
        Создаёт запись снимка состояния.
        Creates a state snapshot row.
        """
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO state_snapshots (
                    reason, total_modules, total_entities, total_dependencies, total_entity_relations,
                    total_entity_impacts, total_module_impacts, total_entity_metrics, total_module_metrics
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    reason,
                    int(totals.get("total_modules", 0)),
                    int(totals.get("total_entities", 0)),
                    int(totals.get("total_dependencies", 0)),
                    int(totals.get("total_entity_relations", 0)),
                    int(totals.get("total_entity_impacts", 0)),
                    int(totals.get("total_module_impacts", 0)),
                    int(totals.get("total_entity_metrics", 0)),
                    int(totals.get("total_module_metrics", 0)),
                ),
            )
            snapshot_id = int(cur.fetchone()[0])
            self._conn.commit()
            return snapshot_id

    def get_previous_state_snapshot(self, current_snapshot_id: int) -> dict | None:
        """
        Возвращает предыдущий снимок перед текущим.
        Returns the snapshot that precedes the current one.
        """
        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, reason, total_modules, total_entities, total_dependencies,
                       total_entity_relations, total_entity_impacts, total_module_impacts,
                       total_entity_metrics, total_module_metrics, created_at
                FROM state_snapshots
                WHERE id < %s
                ORDER BY id DESC
                LIMIT 1;
                """,
                (int(current_snapshot_id),),
            )
            return cur.fetchone()

    def list_current_entity_metric_rows(self) -> list[dict]:
        """
        Возвращает текущие метрики сущностей в стабильном ключе module_name + qualname.
        Returns current entity metrics using the stable key module_name + qualname.
        """
        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT m.name AS module_name,
                       e.qualname AS entity_qualname,
                       e.entity_type,
                       em.direct_entity_impact_count,
                       em.indirect_entity_impact_count,
                       em.incoming_call_count,
                       em.criticality_score,
                       em.fragility_score
                FROM entity_metrics em
                JOIN code_entities e ON em.entity_id = e.id
                JOIN modules m ON em.module_id = m.id
                ORDER BY m.name ASC, e.qualname ASC;
                """
            )
            return cur.fetchall()

    def list_current_module_metric_rows(self) -> list[dict]:
        """
        Возвращает текущие метрики модулей.
        Returns current module metrics.
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
                ORDER BY m.name ASC;
                """
            )
            return cur.fetchall()

    def save_entity_metric_snapshots(self, snapshot_id: int, rows: list[dict]) -> int:
        """
        Сохраняет entity-level snapshot для указанного состояния.
        Persists an entity-level snapshot for the given state.
        """
        with self._conn.cursor() as cur:
            created_count = 0
            for row in rows:
                cur.execute(
                    """
                    INSERT INTO entity_metric_snapshots (
                        snapshot_id, module_name, entity_qualname, entity_type,
                        direct_entity_impact_count, indirect_entity_impact_count,
                        incoming_call_count, criticality_score, fragility_score
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """,
                    (
                        int(snapshot_id),
                        str(row["module_name"]),
                        str(row["entity_qualname"]),
                        str(row["entity_type"]),
                        int(row["direct_entity_impact_count"]),
                        int(row["indirect_entity_impact_count"]),
                        int(row["incoming_call_count"]),
                        float(row["criticality_score"]),
                        float(row["fragility_score"]),
                    ),
                )
                created_count += 1
            self._conn.commit()
            return created_count

    def save_module_metric_snapshots(self, snapshot_id: int, rows: list[dict]) -> int:
        """
        Сохраняет module-level snapshot для указанного состояния.
        Persists a module-level snapshot for the given state.
        """
        with self._conn.cursor() as cur:
            created_count = 0
            for row in rows:
                cur.execute(
                    """
                    INSERT INTO module_metric_snapshots (
                        snapshot_id, module_name, direct_module_impact_count,
                        indirect_module_impact_count, incoming_dependency_count,
                        criticality_score, fragility_score
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                    """,
                    (
                        int(snapshot_id),
                        str(row["module_name"]),
                        int(row["direct_module_impact_count"]),
                        int(row["indirect_module_impact_count"]),
                        int(row["incoming_dependency_count"]),
                        float(row["criticality_score"]),
                        float(row["fragility_score"]),
                    ),
                )
                created_count += 1
            self._conn.commit()
            return created_count

    def list_entity_metric_snapshot_rows(self, snapshot_id: int) -> list[dict]:
        """
        Возвращает entity-level snapshot по snapshot_id.
        Returns entity-level snapshot rows by snapshot_id.
        """
        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT module_name, entity_qualname, entity_type,
                       direct_entity_impact_count, indirect_entity_impact_count,
                       incoming_call_count, criticality_score, fragility_score
                FROM entity_metric_snapshots
                WHERE snapshot_id = %s
                ORDER BY module_name ASC, entity_qualname ASC;
                """,
                (int(snapshot_id),),
            )
            return cur.fetchall()

    def list_module_metric_snapshot_rows(self, snapshot_id: int) -> list[dict]:
        """
        Возвращает module-level snapshot по snapshot_id.
        Returns module-level snapshot rows by snapshot_id.
        """
        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT module_name, direct_module_impact_count, indirect_module_impact_count,
                       incoming_dependency_count, criticality_score, fragility_score
                FROM module_metric_snapshots
                WHERE snapshot_id = %s
                ORDER BY module_name ASC;
                """,
                (int(snapshot_id),),
            )
            return cur.fetchall()

    def create_state_comparison(self, from_snapshot_id: int, to_snapshot_id: int, changed_entities_count: int, changed_modules_count: int) -> int:
        """
        Создаёт запись сравнения двух состояний.
        Creates a comparison row between two states.
        """
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO state_comparisons (
                    from_snapshot_id, to_snapshot_id, changed_entities_count, changed_modules_count
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (from_snapshot_id, to_snapshot_id) DO UPDATE
                SET changed_entities_count = EXCLUDED.changed_entities_count,
                    changed_modules_count = EXCLUDED.changed_modules_count,
                    created_at = CURRENT_TIMESTAMP
                RETURNING id;
                """,
                (
                    int(from_snapshot_id),
                    int(to_snapshot_id),
                    int(changed_entities_count),
                    int(changed_modules_count),
                ),
            )
            comparison_id = int(cur.fetchone()[0])
            self._conn.commit()
            return comparison_id

    def replace_entity_metric_diffs(self, comparison_id: int, rows: list[dict]) -> int:
        """
        Полностью заменяет entity-level diffs для сравнения.
        Replaces entity-level diffs for a comparison.
        """
        with self._conn.cursor() as cur:
            cur.execute("DELETE FROM entity_metric_diffs WHERE comparison_id = %s;", (int(comparison_id),))
            created_count = 0
            for row in rows:
                cur.execute(
                    """
                    INSERT INTO entity_metric_diffs (
                        comparison_id, module_name, entity_qualname, entity_type, is_added, is_removed,
                        old_direct_entity_impact_count, new_direct_entity_impact_count, delta_direct_entity_impact_count,
                        old_indirect_entity_impact_count, new_indirect_entity_impact_count, delta_indirect_entity_impact_count,
                        old_incoming_call_count, new_incoming_call_count, delta_incoming_call_count,
                        old_criticality_score, new_criticality_score, delta_criticality_score,
                        old_fragility_score, new_fragility_score, delta_fragility_score
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """,
                    (
                        int(comparison_id),
                        str(row["module_name"]),
                        str(row["entity_qualname"]),
                        str(row["entity_type"]),
                        bool(row["is_added"]),
                        bool(row["is_removed"]),
                        int(row["old_direct_entity_impact_count"]),
                        int(row["new_direct_entity_impact_count"]),
                        int(row["delta_direct_entity_impact_count"]),
                        int(row["old_indirect_entity_impact_count"]),
                        int(row["new_indirect_entity_impact_count"]),
                        int(row["delta_indirect_entity_impact_count"]),
                        int(row["old_incoming_call_count"]),
                        int(row["new_incoming_call_count"]),
                        int(row["delta_incoming_call_count"]),
                        float(row["old_criticality_score"]),
                        float(row["new_criticality_score"]),
                        float(row["delta_criticality_score"]),
                        float(row["old_fragility_score"]),
                        float(row["new_fragility_score"]),
                        float(row["delta_fragility_score"]),
                    ),
                )
                created_count += 1
            self._conn.commit()
            return created_count

    def replace_module_metric_diffs(self, comparison_id: int, rows: list[dict]) -> int:
        """
        Полностью заменяет module-level diffs для сравнения.
        Replaces module-level diffs for a comparison.
        """
        with self._conn.cursor() as cur:
            cur.execute("DELETE FROM module_metric_diffs WHERE comparison_id = %s;", (int(comparison_id),))
            created_count = 0
            for row in rows:
                cur.execute(
                    """
                    INSERT INTO module_metric_diffs (
                        comparison_id, module_name, is_added, is_removed,
                        old_direct_module_impact_count, new_direct_module_impact_count, delta_direct_module_impact_count,
                        old_indirect_module_impact_count, new_indirect_module_impact_count, delta_indirect_module_impact_count,
                        old_incoming_dependency_count, new_incoming_dependency_count, delta_incoming_dependency_count,
                        old_criticality_score, new_criticality_score, delta_criticality_score,
                        old_fragility_score, new_fragility_score, delta_fragility_score
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """,
                    (
                        int(comparison_id),
                        str(row["module_name"]),
                        bool(row["is_added"]),
                        bool(row["is_removed"]),
                        int(row["old_direct_module_impact_count"]),
                        int(row["new_direct_module_impact_count"]),
                        int(row["delta_direct_module_impact_count"]),
                        int(row["old_indirect_module_impact_count"]),
                        int(row["new_indirect_module_impact_count"]),
                        int(row["delta_indirect_module_impact_count"]),
                        int(row["old_incoming_dependency_count"]),
                        int(row["new_incoming_dependency_count"]),
                        int(row["delta_incoming_dependency_count"]),
                        float(row["old_criticality_score"]),
                        float(row["new_criticality_score"]),
                        float(row["delta_criticality_score"]),
                        float(row["old_fragility_score"]),
                        float(row["new_fragility_score"]),
                        float(row["delta_fragility_score"]),
                    ),
                )
                created_count += 1
            self._conn.commit()
            return created_count

    def get_latest_state_comparison(self) -> dict | None:
        """
        Возвращает последнее сохранённое сравнение состояний.
        Returns the latest persisted state comparison.
        """
        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT sc.id,
                       sc.from_snapshot_id,
                       sc.to_snapshot_id,
                       sc.changed_entities_count,
                       sc.changed_modules_count,
                       sc.created_at
                FROM state_comparisons sc
                ORDER BY sc.id DESC
                LIMIT 1;
                """
            )
            return cur.fetchone()

    def get_top_entity_metric_diffs(self, limit: int = 10) -> list[dict]:
        """
        Возвращает самые заметные изменения метрик сущностей.
        Returns the most notable entity metric changes.
        """
        latest = self.get_latest_state_comparison()
        if not latest:
            return []

        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT module_name,
                       entity_qualname,
                       entity_type,
                       is_added,
                       is_removed,
                       old_criticality_score,
                       new_criticality_score,
                       delta_criticality_score,
                       old_fragility_score,
                       new_fragility_score,
                       delta_fragility_score
                FROM entity_metric_diffs
                WHERE comparison_id = %s
                ORDER BY ABS(delta_criticality_score) DESC, module_name ASC, entity_qualname ASC
                LIMIT %s;
                """,
                (int(latest["id"]), int(limit)),
            )
            return cur.fetchall()

    def get_top_module_metric_diffs(self, limit: int = 10) -> list[dict]:
        """
        Возвращает самые заметные изменения метрик модулей.
        Returns the most notable module metric changes.
        """
        latest = self.get_latest_state_comparison()
        if not latest:
            return []

        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT module_name,
                       is_added,
                       is_removed,
                       old_criticality_score,
                       new_criticality_score,
                       delta_criticality_score,
                       old_fragility_score,
                       new_fragility_score,
                       delta_fragility_score
                FROM module_metric_diffs
                WHERE comparison_id = %s
                ORDER BY ABS(delta_criticality_score) DESC, module_name ASC
                LIMIT %s;
                """,
                (int(latest["id"]), int(limit)),
            )
            return cur.fetchall()
