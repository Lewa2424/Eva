"""
eva_core/memory_manager.py

MemoryManager — долговременная память Евы 2.0 (PostgreSQL).
Единая точка доступа к данным: задачи, планы, версии кода, тесты, рефлексия.
"""

from __future__ import annotations

import os

import psycopg2
from dotenv import load_dotenv

from eva_core.memory_metrics import MemoryMetricsMixin
from eva_core.memory_dependencies import MemoryDependenciesMixin
from eva_core.memory_impact import MemoryImpactMixin
from eva_core.memory_modules import MemoryModulesMixin
from eva_core.memory_relations import MemoryRelationsMixin
from eva_core.memory_state import MemoryStateMixin
from eva_core.memory_tasks import MemoryTasksMixin


class MemoryManager(
    MemoryTasksMixin,
    MemoryModulesMixin,
    MemoryDependenciesMixin,
    MemoryRelationsMixin,
    MemoryImpactMixin,
    MemoryMetricsMixin,
    MemoryStateMixin,
):
    """
    Единый фасад памяти проекта.
    Unified facade for project memory operations.
    """

    def __init__(self) -> None:
        """
        Создаёт подключение к PostgreSQL.
        Creates a PostgreSQL connection.
        """
        load_dotenv()
        dsn = (os.getenv("POSTGRES_DSN") or "").strip()
        if not dsn:
            raise RuntimeError("POSTGRES_DSN is not set. Add it to .env")

        self._conn = psycopg2.connect(dsn)
        self._conn.autocommit = True

    def close(self) -> None:
        """
        Закрывает соединение.
        Closes the connection.
        """
        if getattr(self, "_conn", None):
            self._conn.close()

    def ping(self) -> bool:
        """
        Проверяет, что соединение живое.
        Checks that the connection is alive.
        """
        with self._conn.cursor() as cur:
            cur.execute("SELECT 1;")
            return cur.fetchone() == (1,)
