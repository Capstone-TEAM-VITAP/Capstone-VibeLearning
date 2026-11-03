"""
repository/python_lang.py

Python support for the static-analysis pipeline: symbol and relationship
extraction with Tree-sitter, mirroring what the JavaScript extractors produce
so that the existing resolver, architecture classifier and graph builder can
consume the results unchanged.

Symbols
-------
- ``def`` / ``async def``  → FUNCTION (module level or nested), METHOD (directly in a class)
- ``class``                → CLASS
- module-level ``NAME = …`` → CONSTANT if NAME is UPPER_CASE, otherwise VARIABLE

Relationships
-------------
- ``import a.b [as c]``            → IMPORTS, namespace import, ``module_path="a.b"``
- ``from x import y [as z]``       → IMPORTS, ``module_path="x"`` (leading dots kept for relative imports)
- ``from x import *``              → IMPORTS, ``target_name="*"``, namespace import
- calls ``f(…)`` / ``obj.m(…)``    → CALLS (``"f"`` / ``"obj.m"``)

REFERENCES and EXPORTS (``__all__``) are not extracted for Python.
"""

from __future__ import annotations

from functools import lru_cache

from .parser import Position
from .relationships import Relationship, RelationshipKind
from .symbols import Symbol, SymbolKind


@lru_cache(maxsize=None)
def get_python_parser() -> object:  # returns tree_sitter.Parser
    import tree_sitter_python as tspy
    from tree_sitter import Language, Parser  # type: ignore[import]

    return Parser(Language(tspy.language()))


def load_python_language() -> object:  # returns tree_sitter.Language
    import tree_sitter_python as tspy
    from tree_sitter import Language  # type: ignore[import]

    return Language(tspy.language())


def _pos(point: object) -> Position:
    return Position(line=point.row + 1, column=point.column)  # type: ignore[attr-defined]


def _text(node: object | None) -> str:
    if node is None:
        return ""
    raw = node.text  # type: ignore[attr-defined]
    return raw.decode("utf-8") if raw else ""


# Statement containers whose bodies may hold further definitions.
_BLOCK_PARENTS = frozenset(
    {
        "if_statement",
        "elif_clause",
        "else_clause",
        "try_statement",
        "except_clause",
        "finally_clause",
        "with_statement",
        "for_statement",
        "while_statement",
        "match_statement",
        "case_clause",
        "block",
    }
)


# ---------------------------------------------------------------------------
# Symbols
# ---------------------------------------------------------------------------


def _definition_of(node: object) -> object | None:
    """Unwrap ``decorated_definition`` to the inner function/class definition."""
    if node.type == "decorated_definition":  # type: ignore[attr-defined]
        return node.child_by_field_name("definition")  # type: ignore[attr-defined]
    return node


def _walk_definitions(
    node: object,
    path: str,
    parent: str | None,
    parent_kind: str | None,
    out: list[Symbol],
) -> None:
    for child in node.children:  # type: ignore[attr-defined]
        ct = child.type  # type: ignore[attr-defined]
        target = _definition_of(child) if ct == "decorated_definition" else child
        if target is None:
            continue
        tt = target.type  # type: ignore[attr-defined]

        if tt == "function_definition":
            name = _text(target.child_by_field_name("name"))
            if name:
                kind = SymbolKind.METHOD if parent_kind == "class" else SymbolKind.FUNCTION
                out.append(
                    Symbol(
                        name=name,
                        kind=kind,
                        path=path,
                        start=_pos(target.start_point),  # type: ignore[attr-defined]
                        end=_pos(target.end_point),  # type: ignore[attr-defined]
                        parent=parent,
                    )
                )
                body = target.child_by_field_name("body")
                if body is not None:
                    _walk_definitions(body, path, name, "function", out)

        elif tt == "class_definition":
            name = _text(target.child_by_field_name("name"))
            if name:
                out.append(
                    Symbol(
                        name=name,
                        kind=SymbolKind.CLASS,
                        path=path,
                        start=_pos(target.start_point),  # type: ignore[attr-defined]
                        end=_pos(target.end_point),  # type: ignore[attr-defined]
                        parent=parent,
                    )
                )
                body = target.child_by_field_name("body")
                if body is not None:
                    _walk_definitions(body, path, name, "class", out)

        elif ct == "expression_statement" and parent is None:
            assign = next((c for c in child.children if c.type == "assignment"), None)  # type: ignore[attr-defined]
            if assign is not None:
                left = assign.child_by_field_name("left")  # type: ignore[attr-defined]
                if left is not None and left.type == "identifier":  # type: ignore[attr-defined]
                    name = _text(left)
                    kind = SymbolKind.CONSTANT if name.isupper() else SymbolKind.VARIABLE
                    out.append(
                        Symbol(
                            name=name,
                            kind=kind,
                            path=path,
                            start=_pos(child.start_point),  # type: ignore[attr-defined]
                            end=_pos(child.end_point),  # type: ignore[attr-defined]
                            parent=None,
                        )
                    )

        elif ct in _BLOCK_PARENTS:
            _walk_definitions(child, path, parent, parent_kind, out)


def extract_python_symbols(path: str, source: bytes | str) -> list[Symbol]:
    """Extract symbols from Python *source*; sorted by position then name."""
    if isinstance(source, str):
        source = source.encode("utf-8")
    root = get_python_parser().parse(source).root_node  # type: ignore[attr-defined]
    out: list[Symbol] = []
    _walk_definitions(root, path, None, None, out)
    out.sort(key=lambda s: (s.start.line, s.start.column, s.name))
    return out


# ---------------------------------------------------------------------------
# Relationships
# ---------------------------------------------------------------------------


def _dotted(node: object) -> str:
    return _text(node).replace(" ", "")


def _import_statement(node: object, path: str) -> list[Relationship]:
    out: list[Relationship] = []
    for child in node.children:  # type: ignore[attr-defined]
        if child.type == "dotted_name":  # type: ignore[attr-defined]
            module = _dotted(child)
            alias = None
            local = module.split(".")[0]
        elif child.type == "aliased_import":  # type: ignore[attr-defined]
            module = _dotted(child.child_by_field_name("name"))  # type: ignore[attr-defined]
            alias = _text(child.child_by_field_name("alias"))  # type: ignore[attr-defined]
            local = alias
        else:
            continue
        out.append(
            Relationship(
                kind=RelationshipKind.IMPORTS,
                source_path=path,
                source_position=_pos(child.start_point),  # type: ignore[attr-defined]
                target_name=local,
                module_path=module,
                alias=alias,
                is_default=False,
                is_namespace=True,
            )
        )
    return out


def _import_from_statement(node: object, path: str) -> list[Relationship]:
    module_node = node.child_by_field_name("module_name")  # type: ignore[attr-defined]
    if module_node is None:
        return []
    module = _dotted(module_node)
    out: list[Relationship] = []
    pos = _pos(node.start_point)  # type: ignore[attr-defined]

    for child in node.children:  # type: ignore[attr-defined]
        ct = child.type  # type: ignore[attr-defined]
        if ct == "wildcard_import":
            out.append(
                Relationship(
                    kind=RelationshipKind.IMPORTS,
                    source_path=path,
                    source_position=pos,
                    target_name="*",
                    module_path=module,
                    alias=None,
                    is_default=False,
                    is_namespace=True,
                )
            )
        elif ct == "aliased_import":
            name = _dotted(child.child_by_field_name("name"))  # type: ignore[attr-defined]
            alias = _text(child.child_by_field_name("alias"))  # type: ignore[attr-defined]
            out.append(
                Relationship(
                    kind=RelationshipKind.IMPORTS,
                    source_path=path,
                    source_position=_pos(child.start_point),  # type: ignore[attr-defined]
                    target_name=name,
                    module_path=module,
                    alias=alias or None,
                    is_default=False,
                    is_namespace=False,
                )
            )
        elif ct == "dotted_name" and child is not module_node and child.start_byte != module_node.start_byte:  # type: ignore[attr-defined]
            out.append(
                Relationship(
                    kind=RelationshipKind.IMPORTS,
                    source_path=path,
                    source_position=_pos(child.start_point),  # type: ignore[attr-defined]
                    target_name=_dotted(child),
                    module_path=module,
                    alias=None,
                    is_default=False,
                    is_namespace=False,
                )
            )
    return out


def _callee_name(callee: object) -> str | None:
    ct = callee.type  # type: ignore[attr-defined]
    if ct == "identifier":
        return _text(callee)
    if ct == "attribute":
        obj = callee.child_by_field_name("object")  # type: ignore[attr-defined]
        attr = callee.child_by_field_name("attribute")  # type: ignore[attr-defined]
        obj_text = _text(obj) if obj is not None and obj.type == "identifier" else "?"  # type: ignore[attr-defined]
        return f"{obj_text}.{_text(attr)}"
    return None


def _walk_calls(node: object, path: str, out: list[Relationship]) -> None:
    if node.type == "call":  # type: ignore[attr-defined]
        callee = node.child_by_field_name("function")  # type: ignore[attr-defined]
        if callee is not None:
            name = _callee_name(callee)
            if name:
                out.append(
                    Relationship(
                        kind=RelationshipKind.CALLS,
                        source_path=path,
                        source_position=_pos(callee.start_point),  # type: ignore[attr-defined]
                        target_name=name,
                        module_path=None,
                        alias=None,
                        is_default=False,
                        is_namespace=False,
                    )
                )
    for child in node.children:  # type: ignore[attr-defined]
        _walk_calls(child, path, out)


def extract_python_relationships(path: str, source: bytes | str) -> list[Relationship]:
    """Extract IMPORTS and CALLS from Python *source*; sorted deterministically."""
    if isinstance(source, str):
        source = source.encode("utf-8")
    root = get_python_parser().parse(source).root_node  # type: ignore[attr-defined]
    out: list[Relationship] = []

    def visit(node: object) -> None:
        for child in node.children:  # type: ignore[attr-defined]
            ct = child.type  # type: ignore[attr-defined]
            if ct == "import_statement":
                out.extend(_import_statement(child, path))
            elif ct == "import_from_statement":
                out.extend(_import_from_statement(child, path))
            else:
                visit(child)

    visit(root)
    _walk_calls(root, path, out)
    out.sort(key=lambda r: (r.source_position.line, r.source_position.column, r.target_name))
    return out
