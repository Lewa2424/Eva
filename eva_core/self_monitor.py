"""
eva_core/self_monitor.py

SelfMonitor — модуль самонаблюдения Евы 2.0.
Отвечает за сканирование кодовой базы и построение мета-карты кода.

На уровне MVP здесь будет только "скелет" интерфейса (точки входа),
чтобы остальные модули подключались через понятные "синапсы".
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from eva_core.memory_manager import MemoryManager


# SelfMonitor
# Назначение: "скелет глаз" — минимальная версия модуля самонаблюдения Евы (MVP).
# Делает: принимает MemoryManager в конструкторе, метод scan() будет сканировать проект и строить мета-карту кода.
class SelfMonitor:
    def __init__(self, memory: MemoryManager) -> None:
        self._mem = memory

    def _compute_file_hash(self, file_path: Path) -> str:
        """Читает файл и возвращает SHA256-хэш содержимого."""
        content = file_path.read_bytes()
        return hashlib.sha256(content).hexdigest()

    def scan(self) -> None:
        """
        Сканирует проект и строит мета-карту кода (модули и зависимости).
        Минимальное "зрение": находит все .py файлы и сохраняет их в таблицу modules.
        """
        # Определяем корень проекта (относительно eva_core/self_monitor.py это parent.parent)
        project_root = Path(__file__).parent.parent

        # Находим все .py файлы рекурсивно
        skip_dirs = {".venv", "venv", "__pycache__", ".git", "site-packages"}

        # Сброс "видимости" перед новым сканированием:
        # кто будет найден — получит last_seen_at заново.
        with self._mem._conn.cursor() as cur:
            cur.execute("UPDATE modules SET last_seen_at = NULL;")
            self._mem._conn.commit()

        for py_file in project_root.rglob("*.py"):
            # Получаем относительный путь от корня проекта
            rel_path = py_file.relative_to(project_root)

            # Пропускаем файлы, если путь содержит любой из skip_dirs
            if any(part in skip_dirs for part in rel_path.parts):
                continue

            name = str(rel_path).replace("\\", "/")  # Нормализуем для Windows

            # Считаем отпечаток файла
            content_hash = self._compute_file_hash(py_file)

            # Получаем модуль из БД по name
            existing = self._mem.get_module_by_name(name)

            if existing:
                saved_hash = existing.get("content_hash")
                if saved_hash == content_hash:
                    # Файл не изменился - обновляем только last_seen_at
                    self._mem.update_module_last_seen(name)
                else:
                    # Файл изменился - обновляем запись с новым content_hash
                    self._mem.save_module(
                        name=name,
                        file_path=name,
                        description=None,
                        start_line=None,
                        end_line=None,
                        metrics=None,
                        status="discovered",
                        content_hash=content_hash,
                    )
            else:
                # Файл новый - создаём запись с content_hash
                self._mem.save_module(
                    name=name,
                    file_path=name,
                    description=None,
                    start_line=None,
                    end_line=None,
                    metrics=None,
                    status="discovered",
                    content_hash=content_hash,
                )

