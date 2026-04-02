"""
main.py

Минимальная точка входа (MVP):
- загрузить .env
- создать MemoryManager
- проверить подключение к БД (ping / SELECT 1)
"""

from __future__ import annotations

import os
import sys
from dotenv import load_dotenv
from eva_core.decision_engine import DecisionEngine
from eva_core.memory_manager import MemoryManager
from eva_core.self_monitor import SelfMonitor


# main()
# Назначение: минимальная точка входа Евы (MVP) — проверить, что .env прочитан и БД доступна.
# Делает: load_dotenv() → создаёт MemoryManager (POSTGRES_DSN) → mm.ping() (SELECT 1) → печатает DB ping: OK/FAIL → закрывает соединение.
def main() -> int:
    # 1) Загружаем переменные окружения из .env (если файл существует).
    load_dotenv()
    dsn = (os.getenv("POSTGRES_DSN") or "").strip()
    print(f"POSTGRES_DSN: {'SET' if dsn else 'NOT SET'}")

    # 2) Создаём MemoryManager (подключается к PostgreSQL по POSTGRES_DSN).
    try:
        mm = MemoryManager()
    except Exception as e:  # noqa: BLE001 - MVP: показать ошибку конфигурации/подключения
        print(f"[ERROR] MemoryManager init failed: {e}")
        return 1

    # Временная проверка записи/чтения в БД через DecisionEngine.
    engine = DecisionEngine(mm)
    task_id = engine.run_once("тестовая цель")
    print(f"DecisionEngine task_id: {task_id}")

    # Временная проверка SelfMonitor: сканирование проекта.
    monitor = SelfMonitor(mm)
    monitor.scan()
    print("SelfMonitor: DONE")

    # 3) Проверяем подключение к БД простым запросом.
    try:
        ok = bool(mm.ping())
        print(f"DB ping: {'OK' if ok else 'FAIL'}")
        return 0 if ok else 2
    except Exception as e:  # noqa: BLE001 - MVP: показать ошибку пинга
        print(f"[ERROR] DB ping failed: {e}")
        return 2
    finally:
        mm.close()


if __name__ == "__main__":
    raise SystemExit(main())

    # touch