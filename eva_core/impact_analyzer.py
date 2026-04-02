"""
eva_core/impact_analyzer.py

ImpactAnalyzer — анализирует и сохраняет влияние изменений на сущности и модули.
ImpactAnalyzer — analyzes and persists the impact of changes on entities and modules.
"""

from __future__ import annotations

from collections import deque

from eva_core.memory_manager import MemoryManager


class ImpactAnalyzer:
    """
    Строит слой оценки влияния на основе связей вызовов и зависимостей модулей.
    Builds an impact layer based on call relations and module dependencies.
    """

    def __init__(self, memory: MemoryManager) -> None:
        self._mem = memory

    def sync_all(self, max_depth: int = 2) -> dict[str, int]:
        """
        Полностью пересобирает entity-level и module-level impacts.
        Rebuilds entity-level and module-level impacts.
        """
        entities = self._mem.list_code_entities()
        relations = self._mem.list_entity_relations()
        dependencies = self._mem.list_dependencies()

        entity_impacts = self._build_entity_impacts(entities, relations, max_depth=max_depth)
        module_impacts = self._build_module_impacts(dependencies, max_depth=max_depth)

        return {
            "entity_impacts": self._mem.replace_all_entity_impacts(entity_impacts),
            "module_impacts": self._mem.replace_all_module_impacts(module_impacts),
        }

    def analyze_entity(self, module_name: str, qualname: str) -> dict[str, list[dict]]:
        """
        Возвращает сохранённый отчёт влияния для сущности.
        Returns the persisted impact report for an entity.
        """
        return {
            "entity_impacts": self._mem.get_entity_impacts(module_name, qualname),
            "module_impacts": self._mem.get_module_impacts(module_name),
        }

    def _build_entity_impacts(self, entities: list[dict], relations: list[dict], max_depth: int) -> list[dict]:
        entity_by_id = {int(entity["id"]): entity for entity in entities}
        reverse_graph: dict[int, list[int]] = {}

        for relation in relations:
            target_entity_id = int(relation["to_entity_id"])
            source_entity_id = int(relation["from_entity_id"])
            reverse_graph.setdefault(target_entity_id, []).append(source_entity_id)

        impacts_by_pair: dict[tuple[int, int], dict] = {}
        for entity in entities:
            source_entity_id = int(entity["id"])
            source_module_id = int(entity["module_id"])
            distances = self._traverse_reverse_graph(source_entity_id, reverse_graph, max_depth=max_depth)

            for impacted_entity_id, distance in sorted(distances.items(), key=lambda item: (item[1], item[0])):
                impacted_entity = entity_by_id.get(impacted_entity_id)
                if not impacted_entity:
                    continue

                pair = (source_entity_id, impacted_entity_id)
                saved = impacts_by_pair.get(pair)
                if saved and int(saved["min_distance"]) <= int(distance):
                    continue

                impacts_by_pair[pair] = {
                    "source_entity_id": source_entity_id,
                    "impacted_entity_id": impacted_entity_id,
                    "source_module_id": source_module_id,
                    "impacted_module_id": int(impacted_entity["module_id"]),
                    "min_distance": distance,
                    "is_direct": distance == 1,
                }

        return [
            impacts_by_pair[pair]
            for pair in sorted(impacts_by_pair, key=lambda item: (item[0], item[1]))
        ]

    def _build_module_impacts(self, dependencies: list[dict], max_depth: int) -> list[dict]:
        reverse_graph: dict[int, list[tuple[int, str]]] = {}

        for dependency in dependencies:
            target_module_id = int(dependency["to_module_id"])
            source_module_id = int(dependency["from_module_id"])
            reverse_graph.setdefault(target_module_id, []).append((source_module_id, str(dependency["kind"])))

        impacts_by_pair: dict[tuple[int, int], dict] = {}
        module_ids = sorted(
            {
                int(dependency["from_module_id"])
                for dependency in dependencies
            }
            | {
                int(dependency["to_module_id"])
                for dependency in dependencies
            }
        )

        for source_module_id in module_ids:
            discovered = self._traverse_reverse_module_graph(source_module_id, reverse_graph, max_depth=max_depth)
            for impacted_module_id, payload in sorted(discovered.items(), key=lambda item: (item[1]["distance"], item[0])):
                pair = (source_module_id, impacted_module_id)
                saved = impacts_by_pair.get(pair)
                next_distance = int(payload["distance"])
                next_kinds = sorted(payload["via_kinds"])

                if saved and int(saved["min_distance"]) < next_distance:
                    continue

                if saved and int(saved["min_distance"]) == next_distance:
                    merged_kinds = sorted(set(saved["via_kinds"]) | set(next_kinds))
                    saved["via_kinds"] = merged_kinds
                    continue

                impacts_by_pair[pair] = {
                    "source_module_id": source_module_id,
                    "impacted_module_id": impacted_module_id,
                    "min_distance": next_distance,
                    "is_direct": next_distance == 1,
                    "via_kinds": next_kinds,
                }

        return [
            impacts_by_pair[pair]
            for pair in sorted(impacts_by_pair, key=lambda item: (item[0], item[1]))
        ]

    def _traverse_reverse_graph(self, start_id: int, reverse_graph: dict[int, list[int]], max_depth: int) -> dict[int, int]:
        discovered: dict[int, int] = {}
        queue: deque[tuple[int, int]] = deque([(start_id, 0)])

        while queue:
            current_id, depth = queue.popleft()
            if depth >= max_depth:
                continue

            for next_id in reverse_graph.get(current_id, []):
                next_depth = depth + 1
                saved_depth = discovered.get(next_id)
                if saved_depth is not None and saved_depth <= next_depth:
                    continue

                discovered[next_id] = next_depth
                queue.append((next_id, next_depth))

        discovered.pop(start_id, None)
        return discovered

    def _traverse_reverse_module_graph(
        self,
        start_id: int,
        reverse_graph: dict[int, list[tuple[int, str]]],
        max_depth: int,
    ) -> dict[int, dict]:
        discovered: dict[int, dict] = {}
        queue: deque[tuple[int, int]] = deque([(start_id, 0)])

        while queue:
            current_id, depth = queue.popleft()
            if depth >= max_depth:
                continue

            for next_id, dependency_kind in reverse_graph.get(current_id, []):
                next_depth = depth + 1
                payload = discovered.get(next_id)

                if payload is None or int(payload["distance"]) > next_depth:
                    discovered[next_id] = {
                        "distance": next_depth,
                        "via_kinds": {dependency_kind},
                    }
                    queue.append((next_id, next_depth))
                    continue

                if int(payload["distance"]) == next_depth:
                    payload["via_kinds"].add(dependency_kind)

        discovered.pop(start_id, None)
        return discovered
