"""
eva_core/self_monitor.py

SelfMonitor — модуль самонаблюдения Евы 2.0.
Отвечает за сканирование кодовой базы и построение мета-карты кода.

На уровне MVP здесь будет только "скелет" интерфейса (точки входа),
чтобы остальные модули подключались через понятные "синапсы".
"""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path, PurePosixPath

from eva_core.call_map_builder import build_call_relations
from eva_core.criticality_analyzer import CriticalityAnalyzer
from eva_core.impact_analyzer import ImpactAnalyzer
from eva_core.memory_manager import MemoryManager
from eva_core.state_comparator import StateComparator


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

    def _file_path_to_module_path(self, file_path: str) -> str:
        """Преобразует путь файла проекта в dotted-путь модуля Python."""
        path = PurePosixPath(file_path.replace("\\", "/"))
        if path.name == "__init__.py":
            return ".".join(path.parent.parts)
        return ".".join(path.with_suffix("").parts)

    def _file_path_to_package_path(self, file_path: str) -> str:
        """Возвращает dotted-путь пакета, внутри которого находится модуль."""
        path = PurePosixPath(file_path.replace("\\", "/"))
        if path.name == "__init__.py":
            return ".".join(path.parent.parts)
        return ".".join(path.parent.parts)

    def _node_to_text(self, node: ast.AST) -> str:
        """Преобразует AST-узел в краткий текст."""
        try:
            return ast.unparse(node)
        except Exception:
            return ast.dump(node, annotate_fields=False)

    def _parse_file(self, file_path: Path) -> tuple[list[dict], list[dict]]:
        """
        Разбирает Python-файл через AST и извлекает:
        - сущности кода (функции, методы, классы);
        - импорты.
        """
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))

        entities: list[dict] = []
        imports: list[dict] = []

        def visit_body(body: list[ast.stmt], parent_qualname: str | None = None, in_class: bool = False) -> None:
            for node in body:
                if isinstance(node, ast.ClassDef):
                    qualname = f"{parent_qualname}.{node.name}" if parent_qualname else node.name
                    entities.append(
                        {
                            "entity_type": "class",
                            "name": node.name,
                            "qualname": qualname,
                            "parent_qualname": parent_qualname,
                            "start_line": getattr(node, "lineno", None),
                            "end_line": getattr(node, "end_lineno", None),
                            "decorators": [self._node_to_text(item) for item in node.decorator_list],
                            "docstring": ast.get_docstring(node),
                        }
                    )
                    visit_body(node.body, parent_qualname=qualname, in_class=True)
                    continue

                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if in_class:
                        entity_type = "async_method" if isinstance(node, ast.AsyncFunctionDef) else "method"
                    else:
                        entity_type = "async_function" if isinstance(node, ast.AsyncFunctionDef) else "function"

                    qualname = f"{parent_qualname}.{node.name}" if parent_qualname else node.name
                    entities.append(
                        {
                            "entity_type": entity_type,
                            "name": node.name,
                            "qualname": qualname,
                            "parent_qualname": parent_qualname,
                            "start_line": getattr(node, "lineno", None),
                            "end_line": getattr(node, "end_lineno", None),
                            "decorators": [self._node_to_text(item) for item in node.decorator_list],
                            "docstring": ast.get_docstring(node),
                        }
                    )
                    visit_body(node.body, parent_qualname=qualname, in_class=False)
                    continue

                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(
                            {
                                "import_type": "import",
                                "imported_module": alias.name,
                                "imported_name": None,
                                "alias_name": alias.asname,
                                "is_relative": False,
                                "relative_level": 0,
                            }
                        )
                    continue

                if isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        imports.append(
                            {
                                "import_type": "from",
                                "imported_module": node.module,
                                "imported_name": alias.name,
                                "alias_name": alias.asname,
                                "is_relative": bool(node.level),
                                "relative_level": int(node.level or 0),
                            }
                        )
                    continue

        visit_body(tree.body)
        return entities, imports

    def _build_module_index(self) -> dict[str, str]:
        """
        Строит индекс вида:
        dotted import path -> имя модуля в мета-карте (фактически file_path).
        """
        module_index: dict[str, str] = {}
        for module in self._mem.list_modules():
            module_name = str(module["name"])
            dotted_path = self._file_path_to_module_path(module_name)
            if dotted_path:
                module_index[dotted_path] = module_name
        return module_index

    def _build_entity_index(self) -> dict:
        """
        Строит индексы сущностей для разрешения простых внутренних вызовов.
        Builds entity indexes to resolve simple internal calls.
        """
        by_module: dict[str, dict[str, dict]] = {}
        top_level: dict[str, dict[str, dict]] = {}
        members: dict[str, dict[str, dict[str, dict]]] = {}

        for entity in self._mem.list_code_entities():
            module_name = str(entity["module_name"])
            qualname = str(entity["qualname"])
            entity_name = str(entity["name"])
            parent_qualname = entity.get("parent_qualname")

            by_module.setdefault(module_name, {})[qualname] = entity
            if parent_qualname:
                parent_name = str(parent_qualname)
                parent_entity = by_module[module_name].get(parent_name)
                if parent_entity and str(parent_entity.get("entity_type")) == "class":
                    members.setdefault(module_name, {}).setdefault(parent_name, {})[entity_name] = entity
            else:
                top_level.setdefault(module_name, {})[entity_name] = entity

        return {
            "by_module": by_module,
            "top_level": top_level,
            "members": members,
        }

    def _resolve_import_target(
        self,
        current_module_name: str,
        import_item: dict,
        module_index: dict[str, str],
    ) -> str | None:
        """
        Разрешает импорт в конкретный внутренний модуль проекта.
        Возвращает имя модуля из мета-карты или None, если импорт внешний.
        """
        import_type = str(import_item.get("import_type") or "").strip()
        imported_module = str(import_item.get("imported_module") or "").strip()
        imported_name = str(import_item.get("imported_name") or "").strip()
        is_relative = bool(import_item.get("is_relative", False))
        relative_level = int(import_item.get("relative_level", 0))

        full_module = imported_module
        if is_relative:
            current_package = self._file_path_to_package_path(current_module_name)
            package_parts = [part for part in current_package.split(".") if part]
            cut = max(relative_level - 1, 0)
            if cut > len(package_parts):
                base_parts: list[str] = []
            else:
                base_parts = package_parts[: len(package_parts) - cut]
            extra_parts = [part for part in imported_module.split(".") if part]
            full_module = ".".join(base_parts + extra_parts)

        if import_type == "import":
            return module_index.get(full_module)

        if import_type != "from":
            return None

        candidates: list[str] = []
        if full_module and imported_name and imported_name != "*":
            candidates.append(f"{full_module}.{imported_name}")
        if full_module:
            candidates.append(full_module)
        elif imported_name and imported_name != "*":
            candidates.append(imported_name)

        for candidate in candidates:
            target_module = module_index.get(candidate)
            if target_module:
                return target_module

        return None

    def _sync_import_dependencies(self) -> None:
        """
        Полностью пересобирает import-зависимости между внутренними модулями проекта
        на основе уже сохранённых AST-импортов.
        """
        module_index = self._build_module_index()

        for module in self._mem.list_modules():
            module_name = str(module["name"])
            imports = self._mem.get_module_imports(module_name)

            targets: list[str] = []
            for import_item in imports:
                target_module = self._resolve_import_target(module_name, import_item, module_index)
                if target_module:
                    targets.append(target_module)

            self._mem.replace_module_dependencies(module_name, targets, kind="import")

    def _sync_call_relations(self, module_names: set[str]) -> None:
        """
        Пересобирает связи вызовов для модулей, которым нужна синхронизация.
        Rebuilds call relations for modules that need synchronization.
        """
        if not module_names:
            return

        project_root = Path(__file__).parent.parent
        module_index = self._build_module_index()
        entity_index = self._build_entity_index()

        for module_name in sorted(module_names):
            file_path = project_root / Path(module_name)
            if not file_path.exists():
                self._mem.replace_module_entity_relations(module_name, [])
                continue

            raw_relations = build_call_relations(
                file_path=file_path,
                module_name=module_name,
                module_dotted_path=self._file_path_to_module_path(module_name),
                package_dotted_path=self._file_path_to_package_path(module_name),
                entity_index=entity_index,
                module_index=module_index,
            )

            module_entities = entity_index["by_module"].get(module_name, {})
            resolved_relations: list[dict] = []
            for relation in raw_relations:
                from_entity = module_entities.get(str(relation["from_qualname"]))
                target_module_name = str(relation["to_module_name"])
                target_entities = entity_index["by_module"].get(target_module_name, {})
                to_entity = target_entities.get(str(relation["to_qualname"]))
                target_module = self._mem.get_module_by_name(target_module_name)
                if not from_entity or not to_entity or not target_module:
                    continue

                resolved_relations.append(
                    {
                        "from_entity_id": int(from_entity["id"]),
                        "to_entity_id": int(to_entity["id"]),
                        "target_module_id": int(target_module["id"]),
                        "target_module_name": target_module_name,
                        "relation_type": relation.get("relation_type") or "call",
                        "call_line": relation.get("call_line"),
                        "call_expr": relation.get("call_expr"),
                    }
                )

            self._mem.replace_module_entity_relations(module_name, resolved_relations)

    def scan(self) -> None:
        """
        Сканирует проект и строит мета-карту кода (модули и зависимости).
        Минимальное "зрение": находит все .py файлы и сохраняет их в таблицу modules.
        """
        # Определяем корень проекта (относительно eva_core/self_monitor.py это parent.parent)
        project_root = Path(__file__).parent.parent

        # Находим все .py файлы рекурсивно
        skip_dirs = {".venv", "venv", "__pycache__", ".git", "site-packages"}
        modules_needing_call_sync: set[str] = set()

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
                ast_synced = existing.get("ast_synced_at") is not None
                calls_synced = existing.get("calls_synced_at") is not None
                if saved_hash == content_hash and ast_synced and calls_synced:
                    # Файл не изменился и AST уже синхронизирован - обновляем только last_seen_at
                    self._mem.update_module_last_seen(name)
                elif saved_hash == content_hash and not ast_synced:
                    # Файл не изменился, но AST-снимка ещё нет - делаем первичный разбор
                    entities, imports = self._parse_file(py_file)
                    self._mem.update_module_last_seen(name)
                    self._mem.replace_module_ast_snapshot(name, entities, imports)
                    modules_needing_call_sync.add(name)
                elif saved_hash == content_hash and not calls_synced:
                    self._mem.update_module_last_seen(name)
                    modules_needing_call_sync.add(name)
                else:
                    # Файл изменился - пересчитываем AST-снимок и обновляем запись
                    entities, imports = self._parse_file(py_file)
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
                    self._mem.replace_module_ast_snapshot(name, entities, imports)
                    modules_needing_call_sync.add(name)
            else:
                # Файл новый - создаём запись и сохраняем AST-снимок
                entities, imports = self._parse_file(py_file)
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
                self._mem.replace_module_ast_snapshot(name, entities, imports)
                modules_needing_call_sync.add(name)

        self._sync_import_dependencies()
        self._sync_call_relations(modules_needing_call_sync)
        ImpactAnalyzer(self._mem).sync_all(max_depth=2)
        CriticalityAnalyzer(self._mem).sync_all()
        StateComparator(self._mem).sync(reason="scan")

