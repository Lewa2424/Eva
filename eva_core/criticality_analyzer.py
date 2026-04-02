"""
eva_core/criticality_analyzer.py

CriticalityAnalyzer — рассчитывает метрики критичности и хрупкости узлов.
CriticalityAnalyzer — calculates criticality and fragility metrics for nodes.
"""

from __future__ import annotations

from collections import Counter

from eva_core.memory_manager import MemoryManager


class CriticalityAnalyzer:
    """
    Строит метрический слой поверх impact-данных и графа связей.
    Builds a metrics layer on top of impact data and the relation graph.
    """

    def __init__(self, memory: MemoryManager) -> None:
        self._mem = memory

    def sync_all(self) -> dict[str, int]:
        """
        Полностью пересобирает entity-level и module-level metrics.
        Rebuilds entity-level and module-level metrics.
        """
        entities = self._mem.list_code_entities()
        modules = self._mem.list_modules()
        relations = self._mem.list_entity_relations()
        dependencies = self._mem.list_dependencies()

        entity_impacts = self._load_entity_impacts()
        module_impacts = self._load_module_impacts()

        entity_metrics = self._build_entity_metrics(entities, relations, entity_impacts)
        module_metrics = self._build_module_metrics(modules, dependencies, module_impacts)

        return {
            "entity_metrics": self._mem.replace_all_entity_metrics(entity_metrics),
            "module_metrics": self._mem.replace_all_module_metrics(module_metrics),
        }

    def _load_entity_impacts(self) -> list[dict]:
        with self._mem._conn.cursor() as cur:
            cur.execute(
                """
                SELECT source_entity_id, source_module_id, impacted_entity_id, impacted_module_id,
                       min_distance, is_direct
                FROM entity_impacts
                ORDER BY id ASC;
                """
            )
            rows = cur.fetchall()
        return [
            {
                "source_entity_id": int(row[0]),
                "source_module_id": int(row[1]),
                "impacted_entity_id": int(row[2]),
                "impacted_module_id": int(row[3]),
                "min_distance": int(row[4]),
                "is_direct": bool(row[5]),
            }
            for row in rows
        ]

    def _load_module_impacts(self) -> list[dict]:
        with self._mem._conn.cursor() as cur:
            cur.execute(
                """
                SELECT source_module_id, impacted_module_id, min_distance, is_direct
                FROM module_impacts
                ORDER BY id ASC;
                """
            )
            rows = cur.fetchall()
        return [
            {
                "source_module_id": int(row[0]),
                "impacted_module_id": int(row[1]),
                "min_distance": int(row[2]),
                "is_direct": bool(row[3]),
            }
            for row in rows
        ]

    def _build_entity_metrics(
        self,
        entities: list[dict],
        relations: list[dict],
        entity_impacts: list[dict],
    ) -> list[dict]:
        incoming_call_count = Counter(int(relation["to_entity_id"]) for relation in relations)
        impact_counts: dict[int, dict[str, int]] = {}

        for impact in entity_impacts:
            source_entity_id = int(impact["source_entity_id"])
            bucket = impact_counts.setdefault(
                source_entity_id,
                {"direct": 0, "indirect": 0},
            )
            if bool(impact["is_direct"]):
                bucket["direct"] += 1
            else:
                bucket["indirect"] += 1

        metrics: list[dict] = []
        for entity in entities:
            entity_id = int(entity["id"])
            module_id = int(entity["module_id"])
            counts = impact_counts.get(entity_id, {"direct": 0, "indirect": 0})
            direct_count = int(counts["direct"])
            indirect_count = int(counts["indirect"])
            incoming_count = int(incoming_call_count.get(entity_id, 0))

            criticality_score = (direct_count * 3.0) + (indirect_count * 1.0) + (incoming_count * 2.0)
            fragility_score = (direct_count * 2.0) + (indirect_count * 1.0) + (incoming_count * 1.5)

            metrics.append(
                {
                    "entity_id": entity_id,
                    "module_id": module_id,
                    "direct_entity_impact_count": direct_count,
                    "indirect_entity_impact_count": indirect_count,
                    "incoming_call_count": incoming_count,
                    "criticality_score": criticality_score,
                    "fragility_score": fragility_score,
                }
            )

        return metrics

    def _build_module_metrics(
        self,
        modules: list[dict],
        dependencies: list[dict],
        module_impacts: list[dict],
    ) -> list[dict]:
        incoming_dependency_count = Counter(int(dependency["to_module_id"]) for dependency in dependencies)
        impact_counts: dict[int, dict[str, int]] = {}

        for impact in module_impacts:
            source_module_id = int(impact["source_module_id"])
            bucket = impact_counts.setdefault(
                source_module_id,
                {"direct": 0, "indirect": 0},
            )
            if bool(impact["is_direct"]):
                bucket["direct"] += 1
            else:
                bucket["indirect"] += 1

        metrics: list[dict] = []
        for module in modules:
            module_id = int(module["id"])
            counts = impact_counts.get(module_id, {"direct": 0, "indirect": 0})
            direct_count = int(counts["direct"])
            indirect_count = int(counts["indirect"])
            incoming_count = int(incoming_dependency_count.get(module_id, 0))

            criticality_score = (direct_count * 3.0) + (indirect_count * 1.0) + (incoming_count * 2.0)
            fragility_score = (direct_count * 2.0) + (indirect_count * 1.0) + (incoming_count * 1.5)

            metrics.append(
                {
                    "module_id": module_id,
                    "direct_module_impact_count": direct_count,
                    "indirect_module_impact_count": indirect_count,
                    "incoming_dependency_count": incoming_count,
                    "criticality_score": criticality_score,
                    "fragility_score": fragility_score,
                }
            )

        return metrics
