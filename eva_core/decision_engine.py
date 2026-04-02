"""
eva_core/decision_engine.py

DecisionEngine — центральный координатор Евы 2.0.
Отвечает за цикл работы: цель -> план -> действие -> проверка -> вывод -> урок.

На уровне MVP здесь будет только "скелет" интерфейса (точки входа),
чтобы остальные модули подключались через понятные "синапсы".
"""

from __future__ import annotations

from eva_core.memory_manager import MemoryManager


# DecisionEngine
# Назначение: "скелет мозга" — минимальная версия координатора Евы (MVP).
# Делает: принимает MemoryManager в конструкторе, метод run_once(goal: str) сохраняет цель как задачу в БД.
class DecisionEngine:
    def __init__(self, memory: MemoryManager) -> None:
        self._mem = memory

    def run_once(self, goal: str) -> int:
        """
        Сохраняет цель как задачу в БД.
        
        Returns:
            task_id (int): идентификатор созданной задачи.
        """
        goal = (goal or "").strip()
        if not goal:
            raise ValueError("goal is empty")

        task_id = self._mem.save_task(goal=goal, status="new", source="user")
        return task_id
