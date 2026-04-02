"""
eva_core/call_map_builder.py

Строит статическую карту вызовов для Python-модуля.
Builds a static call map for a Python module.
"""

from __future__ import annotations

import ast
from pathlib import Path


class _EntityCallVisitor(ast.NodeVisitor):
    def __init__(self, resolver, source_qualname: str, relations: list[dict]) -> None:
        self._resolver = resolver
        self._source_qualname = source_qualname
        self._relations = relations

    def visit_Call(self, node: ast.Call) -> None:
        target = self._resolver.resolve(node.func)
        if target:
            self._relations.append(
                {
                    "from_qualname": self._source_qualname,
                    "to_module_name": target["module_name"],
                    "to_qualname": target["qualname"],
                    "relation_type": "call",
                    "call_line": getattr(node, "lineno", None),
                    "call_expr": self._resolver.node_to_text(node.func),
                }
            )
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return


class _CallResolver:
    def __init__(
        self,
        module_name: str,
        module_dotted_path: str,
        package_dotted_path: str,
        entity_index: dict,
        module_index: dict[str, str],
        import_aliases: dict[str, dict],
        current_class_qualname: str | None,
    ) -> None:
        self._module_name = module_name
        self._module_dotted_path = module_dotted_path
        self._package_dotted_path = package_dotted_path
        self._entity_index = entity_index
        self._module_index = module_index
        self._import_aliases = import_aliases
        self._current_class_qualname = current_class_qualname

    def node_to_text(self, node: ast.AST) -> str:
        """
        Преобразует AST-узел вызова в короткий текст.
        Converts a call AST node to a short text.
        """
        try:
            return ast.unparse(node)
        except Exception:
            return ast.dump(node, annotate_fields=False)

    def _get_top_level_entity(self, module_name: str, entity_name: str) -> dict | None:
        return self._entity_index["top_level"].get(module_name, {}).get(entity_name)

    def _get_class_member(self, module_name: str, class_qualname: str, member_name: str) -> dict | None:
        return self._entity_index["members"].get(module_name, {}).get(class_qualname, {}).get(member_name)

    def _resolve_relative_module(self, imported_module: str, relative_level: int) -> str:
        package_parts = [part for part in self._package_dotted_path.split(".") if part]
        cut = max(relative_level - 1, 0)
        base_parts = package_parts[: len(package_parts) - cut] if cut <= len(package_parts) else []
        extra_parts = [part for part in imported_module.split(".") if part]
        return ".".join(base_parts + extra_parts)

    def resolve(self, func_node: ast.AST) -> dict | None:
        """
        Разрешает вызов в целевую внутреннюю сущность проекта.
        Resolves a call into a target internal project entity.
        """
        if isinstance(func_node, ast.Name):
            local_target = self._get_top_level_entity(self._module_name, func_node.id)
            if local_target:
                return local_target

            alias = self._import_aliases.get(func_node.id)
            if alias and alias.get("kind") == "entity":
                return self._get_top_level_entity(str(alias["target_module_name"]), str(alias["target_entity_name"]))
            return None

        if isinstance(func_node, ast.Attribute) and isinstance(func_node.value, ast.Name):
            base_name = func_node.value.id

            if base_name in {"self", "cls"} and self._current_class_qualname:
                return self._get_class_member(self._module_name, self._current_class_qualname, func_node.attr)

            alias = self._import_aliases.get(base_name)
            if not alias:
                return None

            if alias.get("kind") == "module":
                return self._get_top_level_entity(str(alias["target_module_name"]), func_node.attr)

            if alias.get("kind") == "entity":
                target_module_name = str(alias["target_module_name"])
                target_entity_name = str(alias["target_entity_name"])
                target_entity = self._get_top_level_entity(target_module_name, target_entity_name)
                if target_entity and str(target_entity.get("entity_type")) == "class":
                    return self._get_class_member(target_module_name, str(target_entity["qualname"]), func_node.attr)

        return None


def build_call_relations(
    file_path: Path,
    module_name: str,
    module_dotted_path: str,
    package_dotted_path: str,
    entity_index: dict,
    module_index: dict[str, str],
) -> list[dict]:
    """
    Строит список связей вызовов для одного Python-файла.
    Builds a list of call relations for one Python file.
    """
    source = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(file_path))
    import_aliases = _build_import_aliases(tree, module_dotted_path, package_dotted_path, module_index)
    relations: list[dict] = []

    def visit_body(
        body: list[ast.stmt],
        parent_qualname: str | None = None,
        current_class_qualname: str | None = None,
        in_class: bool = False,
    ) -> None:
        for node in body:
            if isinstance(node, ast.ClassDef):
                class_qualname = f"{parent_qualname}.{node.name}" if parent_qualname else node.name
                visit_body(
                    node.body,
                    parent_qualname=class_qualname,
                    current_class_qualname=class_qualname,
                    in_class=True,
                )
                continue

            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qualname = f"{parent_qualname}.{node.name}" if parent_qualname else node.name
                resolver = _CallResolver(
                    module_name=module_name,
                    module_dotted_path=module_dotted_path,
                    package_dotted_path=package_dotted_path,
                    entity_index=entity_index,
                    module_index=module_index,
                    import_aliases=import_aliases,
                    current_class_qualname=current_class_qualname if in_class else None,
                )
                visitor = _EntityCallVisitor(resolver=resolver, source_qualname=qualname, relations=relations)
                for statement in node.body:
                    visitor.visit(statement)

                visit_body(
                    node.body,
                    parent_qualname=qualname,
                    current_class_qualname=current_class_qualname if in_class else None,
                    in_class=False,
                )

    visit_body(tree.body)
    return relations


def _build_import_aliases(
    tree: ast.Module,
    module_dotted_path: str,
    package_dotted_path: str,
    module_index: dict[str, str],
) -> dict[str, dict]:
    """
    Собирает алиасы импортов, нужные для разрешения простых внутренних вызовов.
    Collects import aliases needed to resolve simple internal calls.
    """
    aliases: dict[str, dict] = {}

    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                target_module_name = module_index.get(alias.name)
                if not target_module_name:
                    continue
                local_name = alias.asname or alias.name.split(".")[-1]
                aliases[local_name] = {
                    "kind": "module",
                    "target_module_name": target_module_name,
                }
            continue

        if not isinstance(node, ast.ImportFrom):
            continue

        imported_module = node.module or ""
        if node.level:
            imported_module = _resolve_relative_module(package_dotted_path, imported_module, int(node.level or 0))

        for alias in node.names:
            if alias.name == "*":
                continue

            local_name = alias.asname or alias.name
            module_candidate = ".".join(part for part in (imported_module, alias.name) if part)
            target_module_name = module_index.get(module_candidate)
            if target_module_name:
                aliases[local_name] = {
                    "kind": "module",
                    "target_module_name": target_module_name,
                }
                continue

            source_module_name = module_index.get(imported_module)
            if not source_module_name:
                continue

            aliases[local_name] = {
                "kind": "entity",
                "target_module_name": source_module_name,
                "target_entity_name": alias.name,
            }

    return aliases


def _resolve_relative_module(package_dotted_path: str, imported_module: str, relative_level: int) -> str:
    """
    Разрешает относительный import в полный dotted-путь.
    Resolves a relative import into a full dotted path.
    """
    package_parts = [part for part in package_dotted_path.split(".") if part]
    cut = max(relative_level - 1, 0)
    base_parts = package_parts[: len(package_parts) - cut] if cut <= len(package_parts) else []
    extra_parts = [part for part in imported_module.split(".") if part]
    return ".".join(base_parts + extra_parts)
