"""
eva_core/state_comparator.py

StateComparator - compares the previous and current project states.
StateComparator - сравнивает предыдущее и текущее состояние проекта.
"""

from __future__ import annotations

from eva_core.memory_manager import MemoryManager


class StateComparator:
    """
    Persists state snapshots and before/after metric diffs.
    Сохраняет снимки состояния и дельты метрик до/после.
    """

    def __init__(self, memory: MemoryManager) -> None:
        """
        Stores the shared memory facade.
        Сохраняет общий фасад памяти.
        """
        self._mem = memory

    def sync(self, reason: str = "scan") -> dict[str, int]:
        """
        Creates a new state snapshot and compares it with the previous one.
        Создаёт новый снимок состояния и сравнивает его с предыдущим.
        """
        totals = self._mem.collect_state_totals()
        current_snapshot_id = self._mem.create_state_snapshot(reason=reason, totals=totals)

        current_entity_rows = self._mem.list_current_entity_metric_rows()
        current_module_rows = self._mem.list_current_module_metric_rows()

        self._mem.save_entity_metric_snapshots(current_snapshot_id, current_entity_rows)
        self._mem.save_module_metric_snapshots(current_snapshot_id, current_module_rows)

        previous_snapshot = self._mem.get_previous_state_snapshot(current_snapshot_id)
        if not previous_snapshot:
            return {
                "snapshot_id": current_snapshot_id,
                "comparison_id": 0,
                "entity_diffs": 0,
                "module_diffs": 0,
            }

        previous_entity_rows = self._mem.list_entity_metric_snapshot_rows(int(previous_snapshot["id"]))
        previous_module_rows = self._mem.list_module_metric_snapshot_rows(int(previous_snapshot["id"]))

        entity_diffs = self._build_entity_diffs(previous_entity_rows, current_entity_rows)
        module_diffs = self._build_module_diffs(previous_module_rows, current_module_rows)

        comparison_id = self._mem.create_state_comparison(
            from_snapshot_id=int(previous_snapshot["id"]),
            to_snapshot_id=current_snapshot_id,
            changed_entities_count=len(entity_diffs),
            changed_modules_count=len(module_diffs),
        )

        return {
            "snapshot_id": current_snapshot_id,
            "comparison_id": comparison_id,
            "entity_diffs": self._mem.replace_entity_metric_diffs(comparison_id, entity_diffs),
            "module_diffs": self._mem.replace_module_metric_diffs(comparison_id, module_diffs),
        }

    def _build_entity_diffs(self, previous_rows: list[dict], current_rows: list[dict]) -> list[dict]:
        """
        Builds entity-level diffs between two snapshots.
        Строит дельты по сущностям между двумя снимками.
        """
        previous_index = {
            (str(row["module_name"]), str(row["entity_qualname"])): row
            for row in previous_rows
        }
        current_index = {
            (str(row["module_name"]), str(row["entity_qualname"])): row
            for row in current_rows
        }

        diffs: list[dict] = []
        for key in sorted(set(previous_index) | set(current_index)):
            old_row = previous_index.get(key)
            new_row = current_index.get(key)
            diff = self._entity_diff_from_rows(old_row, new_row)
            if diff:
                diffs.append(diff)
        return diffs

    def _build_module_diffs(self, previous_rows: list[dict], current_rows: list[dict]) -> list[dict]:
        """
        Builds module-level diffs between two snapshots.
        Строит дельты по модулям между двумя снимками.
        """
        previous_index = {str(row["module_name"]): row for row in previous_rows}
        current_index = {str(row["module_name"]): row for row in current_rows}

        diffs: list[dict] = []
        for module_name in sorted(set(previous_index) | set(current_index)):
            old_row = previous_index.get(module_name)
            new_row = current_index.get(module_name)
            diff = self._module_diff_from_rows(old_row, new_row)
            if diff:
                diffs.append(diff)
        return diffs

    def _entity_diff_from_rows(self, old_row: dict | None, new_row: dict | None) -> dict | None:
        """
        Converts a pair of entity rows into one diff row.
        Преобразует пару entity-строк в одну строку дельты.
        """
        if old_row is None and new_row is None:
            return None

        source_row = new_row or old_row
        module_name = str(source_row["module_name"])
        entity_qualname = str(source_row["entity_qualname"])
        entity_type = str(source_row["entity_type"])

        old_direct = int(old_row["direct_entity_impact_count"]) if old_row else 0
        new_direct = int(new_row["direct_entity_impact_count"]) if new_row else 0
        old_indirect = int(old_row["indirect_entity_impact_count"]) if old_row else 0
        new_indirect = int(new_row["indirect_entity_impact_count"]) if new_row else 0
        old_incoming = int(old_row["incoming_call_count"]) if old_row else 0
        new_incoming = int(new_row["incoming_call_count"]) if new_row else 0
        old_criticality = float(old_row["criticality_score"]) if old_row else 0.0
        new_criticality = float(new_row["criticality_score"]) if new_row else 0.0
        old_fragility = float(old_row["fragility_score"]) if old_row else 0.0
        new_fragility = float(new_row["fragility_score"]) if new_row else 0.0

        is_added = old_row is None and new_row is not None
        is_removed = old_row is not None and new_row is None

        delta_direct = new_direct - old_direct
        delta_indirect = new_indirect - old_indirect
        delta_incoming = new_incoming - old_incoming
        delta_criticality = round(new_criticality - old_criticality, 2)
        delta_fragility = round(new_fragility - old_fragility, 2)

        if not any(
            (
                is_added,
                is_removed,
                delta_direct,
                delta_indirect,
                delta_incoming,
                delta_criticality,
                delta_fragility,
            )
        ):
            return None

        return {
            "module_name": module_name,
            "entity_qualname": entity_qualname,
            "entity_type": entity_type,
            "is_added": is_added,
            "is_removed": is_removed,
            "old_direct_entity_impact_count": old_direct,
            "new_direct_entity_impact_count": new_direct,
            "delta_direct_entity_impact_count": delta_direct,
            "old_indirect_entity_impact_count": old_indirect,
            "new_indirect_entity_impact_count": new_indirect,
            "delta_indirect_entity_impact_count": delta_indirect,
            "old_incoming_call_count": old_incoming,
            "new_incoming_call_count": new_incoming,
            "delta_incoming_call_count": delta_incoming,
            "old_criticality_score": round(old_criticality, 2),
            "new_criticality_score": round(new_criticality, 2),
            "delta_criticality_score": delta_criticality,
            "old_fragility_score": round(old_fragility, 2),
            "new_fragility_score": round(new_fragility, 2),
            "delta_fragility_score": delta_fragility,
        }

    def _module_diff_from_rows(self, old_row: dict | None, new_row: dict | None) -> dict | None:
        """
        Converts a pair of module rows into one diff row.
        Преобразует пару module-строк в одну строку дельты.
        """
        if old_row is None and new_row is None:
            return None

        source_row = new_row or old_row
        module_name = str(source_row["module_name"])

        old_direct = int(old_row["direct_module_impact_count"]) if old_row else 0
        new_direct = int(new_row["direct_module_impact_count"]) if new_row else 0
        old_indirect = int(old_row["indirect_module_impact_count"]) if old_row else 0
        new_indirect = int(new_row["indirect_module_impact_count"]) if new_row else 0
        old_incoming = int(old_row["incoming_dependency_count"]) if old_row else 0
        new_incoming = int(new_row["incoming_dependency_count"]) if new_row else 0
        old_criticality = float(old_row["criticality_score"]) if old_row else 0.0
        new_criticality = float(new_row["criticality_score"]) if new_row else 0.0
        old_fragility = float(old_row["fragility_score"]) if old_row else 0.0
        new_fragility = float(new_row["fragility_score"]) if new_row else 0.0

        is_added = old_row is None and new_row is not None
        is_removed = old_row is not None and new_row is None

        delta_direct = new_direct - old_direct
        delta_indirect = new_indirect - old_indirect
        delta_incoming = new_incoming - old_incoming
        delta_criticality = round(new_criticality - old_criticality, 2)
        delta_fragility = round(new_fragility - old_fragility, 2)

        if not any(
            (
                is_added,
                is_removed,
                delta_direct,
                delta_indirect,
                delta_incoming,
                delta_criticality,
                delta_fragility,
            )
        ):
            return None

        return {
            "module_name": module_name,
            "is_added": is_added,
            "is_removed": is_removed,
            "old_direct_module_impact_count": old_direct,
            "new_direct_module_impact_count": new_direct,
            "delta_direct_module_impact_count": delta_direct,
            "old_indirect_module_impact_count": old_indirect,
            "new_indirect_module_impact_count": new_indirect,
            "delta_indirect_module_impact_count": delta_indirect,
            "old_incoming_dependency_count": old_incoming,
            "new_incoming_dependency_count": new_incoming,
            "delta_incoming_dependency_count": delta_incoming,
            "old_criticality_score": round(old_criticality, 2),
            "new_criticality_score": round(new_criticality, 2),
            "delta_criticality_score": delta_criticality,
            "old_fragility_score": round(old_fragility, 2),
            "new_fragility_score": round(new_fragility, 2),
            "delta_fragility_score": delta_fragility,
        }
