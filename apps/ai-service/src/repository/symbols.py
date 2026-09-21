"""
repository/symbols.py

Deterministic symbol extraction from JavaScript source code.
Milestone 3 — builds on top of the Tree-sitter parser infrastructure.

Public API
----------
extract_symbols(path, language, source) -> list[Symbol]
    Parse *source* and return a deterministically-sorted flat list of
    ``Symbol`` objects found in the file.

Supported languages (Milestone 3)
----------------------------------
- javascript (.js / .jsx)

Symbol hierarchy
----------------
Parent–child relationships are encoded via the ``Symbol.parent`` field,
which holds the *name* of the immediately enclosing named symbol (or
``None`` for top-level declarations).  The full chain can be reconstructed
by following parent references:

    UserService       parent=None
    login             parent="UserService"

Extraction rules
----------------
Symbols ARE extracted from:
  - function_declaration            → FUNCTION
  - function_expression (named)     → FUNCTION  (const f = function() {})
  - arrow_function (named binding)  → FUNCTION  (const f = () => {})
  - class_declaration               → CLASS
  - method_definition               → METHOD
  - lexical_declaration "const"     → CONSTANT  (unless value is callable)
  - lexical_declaration "let"       → VARIABLE  (unless value is callable)
  - variable_declaration "var"      → VARIABLE  (unless value is callable)
  - export_statement wrappers       → delegates to the inner declaration

Symbols are NOT extracted from:
  - Anonymous functions / arrows used as callbacks or arguments
  - Punctuation, keywords, string literals, comments
  - Destructuring patterns (excluded for M3 simplicity)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from functools import lru_cache

from .parser import Position, UnsupportedLanguageError

# ---------------------------------------------------------------------------
# Symbol kinds
# ---------------------------------------------------------------------------


class SymbolKind(str, Enum):
    """Semantic category of an extracted symbol."""

    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    VARIABLE = "variable"
    CONSTANT = "constant"


# ---------------------------------------------------------------------------
# Immutable Symbol model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Symbol:
    """
    An immutable representation of a named code symbol.

    Attributes
    ----------
    name:
        The identifier text of this symbol as it appears in source.
        Example: ``"UserService"``
    kind:
        Semantic category of the symbol.
    path:
        Repository-relative POSIX path of the containing file.
        Example: ``"src/auth/userService.js"``
    start:
        Position of the first character of the symbol's declaration.
    end:
        Position of the character after the last character.
    parent:
        Name of the immediately enclosing named symbol, or ``None`` if
        this symbol is declared at the top level (or at module scope).
        Examples: ``None``, ``"UserService"``, ``"login"``
    """

    name: str
    kind: SymbolKind
    path: str
    start: Position
    end: Position
    parent: str | None


# ---------------------------------------------------------------------------
# Supported languages
# ---------------------------------------------------------------------------

_SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"javascript"})

# ---------------------------------------------------------------------------
# Tree-sitter parser (independent cache — shares nothing with parser.py
# internals but uses the same grammar, so results are identical)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=None)
def _get_js_parser() -> object:  # returns tree_sitter.Parser
    import tree_sitter_javascript as tsjs
    from tree_sitter import Language, Parser  # type: ignore[import]

    return Parser(Language(tsjs.language()))


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def _pos(point: object) -> Position:
    """Convert a ``tree_sitter.Point`` → ``Position`` (1-indexed line)."""
    return Position(line=point.row + 1, column=point.column)  # type: ignore[attr-defined]


def _field(node: object, field_name: str) -> object | None:
    """Return ``node.child_by_field_name(field_name)`` or ``None``."""
    return node.child_by_field_name(field_name)  # type: ignore[attr-defined]


def _node_text(node: object) -> str | None:
    """Decode a node's ``.text`` bytes to a ``str``, or return ``None``."""
    raw: bytes | None = node.text  # type: ignore[attr-defined]
    return raw.decode("utf-8") if raw else None


# ---------------------------------------------------------------------------
# Core extraction logic
# ---------------------------------------------------------------------------

# Node types whose values, when assigned to a named binding, produce a
# FUNCTION symbol rather than a VARIABLE / CONSTANT symbol.
_CALLABLE_TYPES: frozenset[str] = frozenset(
    {"arrow_function", "function_expression"}
)

# Statement types that introduce a new block; we recurse into them to find
# nested declarations without descending into arbitrary expression contexts.
_BLOCK_STATEMENT_TYPES: frozenset[str] = frozenset(
    {
        "if_statement",
        "else_clause",
        "for_statement",
        "for_in_statement",
        "while_statement",
        "do_statement",
        "try_statement",
        "catch_clause",
        "finally_clause",
        "with_statement",
        "labeled_statement",
        "switch_statement",
        "switch_case",
        "switch_default",
    }
)


def _extract_statements(
    nodes: list[object],
    path: str,
    parent_name: str | None,
) -> list[Symbol]:
    """Visit a sequence of statement nodes and collect symbols."""
    results: list[Symbol] = []
    for node in nodes:
        results.extend(_extract_statement(node, path, parent_name))
    return results


def _extract_statement(
    node: object,
    path: str,
    parent_name: str | None,
) -> list[Symbol]:
    """
    Extract symbols from a single statement node.

    Only *declaration* nodes are harvested; expression-context nodes
    (callbacks, IIFE, etc.) are silently ignored.
    """
    nt: str = node.type  # type: ignore[attr-defined]

    if nt == "function_declaration":
        return _handle_function_declaration(node, path, parent_name)

    if nt == "class_declaration":
        return _handle_class_declaration(node, path, parent_name)

    if nt in ("lexical_declaration",):
        return _handle_lexical_declaration(node, path, parent_name)

    if nt == "variable_declaration":
        return _handle_variable_declaration(node, path, parent_name)

    if nt == "export_statement":
        return _handle_export_statement(node, path, parent_name)

    if nt == "statement_block":
        # Recurse into a bare block (e.g., function body, if branch)
        return _extract_statements(
            node.children, path, parent_name  # type: ignore[attr-defined]
        )

    if nt in _BLOCK_STATEMENT_TYPES:
        # Recurse into the child blocks of control-flow statements
        results: list[Symbol] = []
        for child in node.children:  # type: ignore[attr-defined]
            if child.type == "statement_block" or child.type in _BLOCK_STATEMENT_TYPES:
                results.extend(_extract_statement(child, path, parent_name))
        return results

    if nt == "expression_statement":
        return _handle_expression_statement(node, path, parent_name)

    return []


# ---------------------------------------------------------------------------
# Declaration handlers
# ---------------------------------------------------------------------------


def _handle_function_declaration(
    node: object,
    path: str,
    parent_name: str | None,
) -> list[Symbol]:
    """
    Extract a FUNCTION symbol from a ``function_declaration`` node.

    Recurses into the body to collect nested declarations.
    """
    name_node = _field(node, "name")
    if name_node is None:
        return []
    name = _node_text(name_node)
    if not name:
        return []

    sym = Symbol(
        name=name,
        kind=SymbolKind.FUNCTION,
        path=path,
        start=_pos(node.start_point),  # type: ignore[attr-defined]
        end=_pos(node.end_point),  # type: ignore[attr-defined]
        parent=parent_name,
    )
    results: list[Symbol] = [sym]

    body = _field(node, "body")
    if body is not None:
        results.extend(
            _extract_statements(body.children, path, name)  # type: ignore[attr-defined]
        )
    return results


def _handle_class_declaration(
    node: object,
    path: str,
    parent_name: str | None,
) -> list[Symbol]:
    """
    Extract a CLASS symbol and its METHOD symbols from a
    ``class_declaration`` node.
    """
    name_node = _field(node, "name")
    if name_node is None:
        return []
    name = _node_text(name_node)
    if not name:
        return []

    sym = Symbol(
        name=name,
        kind=SymbolKind.CLASS,
        path=path,
        start=_pos(node.start_point),  # type: ignore[attr-defined]
        end=_pos(node.end_point),  # type: ignore[attr-defined]
        parent=parent_name,
    )
    results: list[Symbol] = [sym]

    body = _field(node, "body")
    if body is not None:
        for child in body.children:  # type: ignore[attr-defined]
            if child.type == "method_definition":
                results.extend(_handle_method_definition(child, path, name))
    return results


def _handle_method_definition(
    node: object,
    path: str,
    class_name: str,
) -> list[Symbol]:
    """
    Extract a METHOD symbol from a ``method_definition`` node.

    Recurses into the method body for nested declarations.
    """
    name_node = _field(node, "name")
    if name_node is None:
        return []
    name = _node_text(name_node)
    if not name:
        return []

    sym = Symbol(
        name=name,
        kind=SymbolKind.METHOD,
        path=path,
        start=_pos(node.start_point),  # type: ignore[attr-defined]
        end=_pos(node.end_point),  # type: ignore[attr-defined]
        parent=class_name,
    )
    results: list[Symbol] = [sym]

    body = _field(node, "body")
    if body is not None:
        results.extend(
            _extract_statements(body.children, path, name)  # type: ignore[attr-defined]
        )
    return results


def _handle_lexical_declaration(
    node: object,
    path: str,
    parent_name: str | None,
) -> list[Symbol]:
    """
    Extract symbols from a ``lexical_declaration`` (``const`` / ``let``).

    - ``const`` → CONSTANT (or FUNCTION if the value is callable)
    - ``let``   → VARIABLE (or FUNCTION if the value is callable)
    """
    # The first child is the keyword: 'const' or 'let'
    children: list[object] = node.children  # type: ignore[attr-defined]
    decl_kind = children[0].type if children else "let"  # type: ignore[attr-defined]

    results: list[Symbol] = []
    for child in children:
        if child.type == "variable_declarator":  # type: ignore[attr-defined]
            results.extend(
                _handle_variable_declarator(child, path, parent_name, decl_kind)
            )
    return results


def _handle_variable_declaration(
    node: object,
    path: str,
    parent_name: str | None,
) -> list[Symbol]:
    """
    Extract symbols from a ``variable_declaration`` (``var``).

    All bindings produce VARIABLE symbols (or FUNCTION if callable value).
    """
    results: list[Symbol] = []
    for child in node.children:  # type: ignore[attr-defined]
        if child.type == "variable_declarator":  # type: ignore[attr-defined]
            results.extend(
                _handle_variable_declarator(child, path, parent_name, "var")
            )
    return results


def _handle_variable_declarator(
    node: object,
    path: str,
    parent_name: str | None,
    decl_kind: str,
) -> list[Symbol]:
    """
    Extract a symbol from a ``variable_declarator`` node.

    - If the right-hand side is a function/arrow → FUNCTION symbol.
    - Otherwise → CONSTANT or VARIABLE depending on *decl_kind*.
    - Destructuring patterns (object/array) are skipped (no simple name).
    """
    name_node = _field(node, "name")
    # Skip destructuring patterns (array_pattern, object_pattern, etc.)
    if name_node is None or name_node.type != "identifier":  # type: ignore[attr-defined]
        return []
    name = _node_text(name_node)
    if not name:
        return []

    value_node = _field(node, "value")
    value_type: str = value_node.type if value_node is not None else ""  # type: ignore[attr-defined]

    if value_type in _CALLABLE_TYPES:
        # Named function expression or named arrow function
        sym = Symbol(
            name=name,
            kind=SymbolKind.FUNCTION,
            path=path,
            start=_pos(node.start_point),  # type: ignore[attr-defined]
            end=_pos(node.end_point),  # type: ignore[attr-defined]
            parent=parent_name,
        )
        results: list[Symbol] = [sym]

        # Recurse into a block body (concise arrow bodies are not blocks
        # and contain no declarations, so we check the type first).
        body = _field(value_node, "body")
        if body is not None and body.type == "statement_block":  # type: ignore[attr-defined]
            results.extend(
                _extract_statements(body.children, path, name)  # type: ignore[attr-defined]
            )
        return results

    else:
        kind = SymbolKind.CONSTANT if decl_kind == "const" else SymbolKind.VARIABLE
        return [
            Symbol(
                name=name,
                kind=kind,
                path=path,
                start=_pos(node.start_point),  # type: ignore[attr-defined]
                end=_pos(node.end_point),  # type: ignore[attr-defined]
                parent=parent_name,
            )
        ]


def _handle_export_statement(
    node: object,
    path: str,
    parent_name: str | None,
) -> list[Symbol]:
    """
    Delegate symbol extraction to the declaration inside an
    ``export_statement``.

    Named and default exports of declarations are handled; bare
    ``export { x }`` re-exports are ignored (no new symbol is defined).
    """
    results: list[Symbol] = []
    for child in node.children:  # type: ignore[attr-defined]
        child_type: str = child.type  # type: ignore[attr-defined]
        if child_type in (
            "function_declaration",
            "class_declaration",
            "lexical_declaration",
            "variable_declaration",
        ):
            results.extend(_extract_statement(child, path, parent_name))
    return results


def _handle_expression_statement(
    node: object,
    path: str,
    parent_name: str | None,
) -> list[Symbol]:
    """
    Extract symbols from CommonJS export assignments in expression_statement nodes.

    Handles:
    - ``exports.myFunc = async (req, res) => ...``
    - ``module.exports.myFunc = function(...) ...``
    - ``exports.MyClass = class ...``
    """
    results: list[Symbol] = []
    for child in node.children:  # type: ignore[attr-defined]
        if child.type != "assignment_expression":  # type: ignore[attr-defined]
            continue
        left = _field(child, "left")
        right = _field(child, "right")
        if left is None or right is None:
            continue

        name: str | None = None
        if left.type == "member_expression":  # type: ignore[attr-defined]
            obj = _field(left, "object")
            prop = _field(left, "property")
            if obj is not None and prop is not None:
                obj_text = _node_text(obj)
                prop_text = _node_text(prop)
                if obj_text in ("exports", "module.exports"):
                    name = prop_text

        if not name:
            continue

        right_type: str = right.type  # type: ignore[attr-defined]
        if right_type in _CALLABLE_TYPES:
            sym = Symbol(
                name=name,
                kind=SymbolKind.FUNCTION,
                path=path,
                start=_pos(child.start_point),  # type: ignore[attr-defined]
                end=_pos(child.end_point),  # type: ignore[attr-defined]
                parent=parent_name,
            )
            results.append(sym)
            body = _field(right, "body")
            if body is not None and body.type == "statement_block":  # type: ignore[attr-defined]
                results.extend(_extract_statements(body.children, path, name))  # type: ignore[attr-defined]
        elif right_type == "class":
            sym = Symbol(
                name=name,
                kind=SymbolKind.CLASS,
                path=path,
                start=_pos(child.start_point),  # type: ignore[attr-defined]
                end=_pos(child.end_point),  # type: ignore[attr-defined]
                parent=parent_name,
            )
            results.append(sym)
            body = _field(right, "body")
            if body is not None:
                results.extend(_extract_statements(body.children, path, name))  # type: ignore[attr-defined]

    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_symbols(
    path: str,
    language: str,
    source: bytes | str,
) -> list[Symbol]:
    """
    Extract code symbols from *source* using Tree-sitter.

    The returned list is sorted deterministically by source position
    (line ascending, then column ascending, then name ascending for
    ties at the same position).

    Parameters
    ----------
    path:
        Repository-relative POSIX path (used to populate ``Symbol.path``).
    language:
        Language name matching scanner conventions (e.g. ``"javascript"``).
    source:
        Raw file content as ``bytes`` or ``str`` (auto-encoded to UTF-8).

    Returns
    -------
    list[Symbol]
        Flat, sorted list of symbols.  Parent–child relationships are
        encoded via ``Symbol.parent``.

    Raises
    ------
    UnsupportedLanguageError
        If *language* is not yet supported by the symbol extractor.
    """
    if language not in _SUPPORTED_LANGUAGES:
        raise UnsupportedLanguageError(language)

    if isinstance(source, str):
        source = source.encode("utf-8")

    parser = _get_js_parser()
    tree = parser.parse(source)  # type: ignore[attr-defined]
    root = tree.root_node  # type: ignore[attr-defined]

    # Walk all top-level statements; each handler recurses as needed.
    symbols = _extract_statements(
        root.children,  # type: ignore[attr-defined]
        path=path,
        parent_name=None,
    )

    # Deterministic ordering: source position first, name as tiebreaker.
    symbols.sort(key=lambda s: (s.start.line, s.start.column, s.name))
    return symbols
