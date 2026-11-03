"""
repository/relationships.py

Deterministic relationship extraction from JavaScript source code.
Milestone 4 — extracts raw structural facts for future CodeGraph construction.

Cross-file resolution is explicitly deferred to Milestone 5.

Public API
----------
extract_relationships(path, language, source) -> list[Relationship]
    Parse *source* and return a deterministically-sorted flat list of
    ``Relationship`` objects found in the file.

Supported relationship kinds
-----------------------------
IMPORTS    — this file imports a symbol or module
EXPORTS    — this file exports a symbol
CALLS      — an identifier is called as a function
REFERENCES — an identifier is used as a value (not a call, not a declaration)

Supported languages (Milestone 4)
-----------------------------------
- javascript (.js / .jsx)

Design principles
-----------------
1.  Pure Tree-sitter AST traversal — no regex.
2.  Each Relationship is a raw, file-local fact.
3.  Cross-file edges (e.g. resolving "./auth.js" → the actual auth.js symbols)
    are intentionally NOT performed here.
4.  Results are deterministically sorted by source position, then target_name.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from typing import Iterator

from .parser import Position, UnsupportedLanguageError

# ---------------------------------------------------------------------------
# Relationship kinds
# ---------------------------------------------------------------------------


class RelationshipKind(str, Enum):
    """Semantic category of an extracted relationship."""

    IMPORTS = "imports"
    EXPORTS = "exports"
    CALLS = "calls"
    REFERENCES = "references"


# ---------------------------------------------------------------------------
# Immutable Relationship model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Relationship:
    """
    An immutable, file-local structural relationship.

    Each instance captures a single directional fact observable from static
    analysis of a single file.  Cross-file resolution (mapping module paths
    to actual files/symbols) is deferred to Milestone 5.

    Attributes
    ----------
    kind:
        The semantic category of this relationship.
    source_path:
        Repository-relative POSIX path of the file that contains this
        relationship.  Example: ``"src/auth/login.js"``
    source_position:
        Source location (1-indexed line, 0-indexed column) where this
        relationship appears in the file.
    target_name:
        The primary name involved in the relationship:
          - IMPORTS:    the imported symbol name (or ``"*"`` for namespace, or
                        ``""`` for side-effect-only imports)
          - EXPORTS:    the exported symbol name
          - CALLS:      the callee name (e.g. ``"login"`` or ``"util.format"``)
          - REFERENCES: the referenced identifier name
    module_path:
        For IMPORTS only: the raw module specifier string as written in
        the source (e.g. ``"./auth.js"``, ``"react"``).  ``None`` for all
        other relationship kinds.
    alias:
        For IMPORTS: the local binding name when it differs from the
        original name (e.g. ``import { login as l }`` → alias ``"l"``).
        For EXPORTS: the public name when it differs (``export { x as y }``
        → alias ``"y"``).
        ``None`` when there is no renaming.
    is_default:
        ``True`` for default imports (``import Foo from "..."``), default
        exports (``export default ...``), and ``False`` otherwise.
    is_namespace:
        ``True`` only for namespace imports (``import * as ns from "..."``).
    """

    kind: RelationshipKind
    source_path: str
    source_position: Position
    target_name: str
    module_path: str | None
    alias: str | None
    is_default: bool
    is_namespace: bool


# ---------------------------------------------------------------------------
# Supported languages
# ---------------------------------------------------------------------------

_SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"javascript"})

# ---------------------------------------------------------------------------
# Tree-sitter parser cache (independent of parser.py cache — same grammar)
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
    """Convert a ``tree_sitter.Point`` → 1-indexed ``Position``."""
    return Position(line=point.row + 1, column=point.column)  # type: ignore[attr-defined]


def _text(node: object | None) -> str | None:
    """Decode a node's ``.text`` bytes, or return ``None``."""
    if node is None:
        return None
    raw: bytes | None = node.text  # type: ignore[attr-defined]
    return raw.decode("utf-8") if raw else None


def _field(node: object, name: str) -> object | None:
    """Return ``node.child_by_field_name(name)`` or ``None``."""
    return node.child_by_field_name(name)  # type: ignore[attr-defined]


def _children_of_type(node: object, *types: str) -> list[object]:
    """Return all direct children whose ``.type`` is in *types*."""
    return [c for c in node.children if c.type in types]  # type: ignore[attr-defined]


def _has_anonymous_child(node: object, text: str) -> bool:
    """Return True if *node* has an anonymous child with the given text."""
    return any(
        not c.is_named and _text(c) == text  # type: ignore[attr-defined]
        for c in node.children  # type: ignore[attr-defined]
    )


def _module_path_from_string_node(str_node: object) -> str:
    """
    Extract the raw module path from a Tree-sitter ``string`` node.

    The ``string_fragment`` named child holds the actual text content
    (without quotes).
    """
    for child in str_node.children:  # type: ignore[attr-defined]
        if child.type == "string_fragment":  # type: ignore[attr-defined]
            return _text(child) or ""
    # Fallback: decode full text and strip one layer of quotes
    raw = _text(str_node) or ""
    return raw.strip('"').strip("'")


# ---------------------------------------------------------------------------
# IMPORT extraction
# ---------------------------------------------------------------------------


def _handle_import_statement(
    node: object,
    path: str,
) -> list[Relationship]:
    """
    Extract IMPORTS relationships from an ``import_statement`` node.

    Handles:
    - ``import foo from "./mod.js"``          → default import
    - ``import { a, b as c } from "./mod.js"``→ named imports (with optional alias)
    - ``import * as ns from "./mod.js"``      → namespace import
    - ``import "./side.js"``                  → side-effect import (no binding)
    """
    # --- Module path --------------------------------------------------------
    source_node = _field(node, "source")
    if source_node is None:
        # Fallback: find the string node among children
        strings = _children_of_type(node, "string")
        source_node = strings[-1] if strings else None
    if source_node is None:
        return []
    module_path = _module_path_from_string_node(source_node)

    results: list[Relationship] = []

    # --- Import clause (may be absent for side-effect imports) --------------
    clauses = _children_of_type(node, "import_clause")
    if not clauses:
        # Side-effect import: ``import "./startup.js"``
        results.append(
            Relationship(
                kind=RelationshipKind.IMPORTS,
                source_path=path,
                source_position=_pos(node.start_point),  # type: ignore[attr-defined]
                target_name="",  # no binding
                module_path=module_path,
                alias=None,
                is_default=False,
                is_namespace=False,
            )
        )
        return results

    clause = clauses[0]

    for child in clause.children:  # type: ignore[attr-defined]
        child_type: str = child.type  # type: ignore[attr-defined]

        if child_type == "identifier":
            # Default import: ``import foo from "..."``
            name = _text(child) or ""
            results.append(
                Relationship(
                    kind=RelationshipKind.IMPORTS,
                    source_path=path,
                    source_position=_pos(child.start_point),  # type: ignore[attr-defined]
                    target_name=name,
                    module_path=module_path,
                    alias=None,
                    is_default=True,
                    is_namespace=False,
                )
            )

        elif child_type == "named_imports":
            # Named imports: ``import { a, b as c } from "..."``
            for spec in _children_of_type(child, "import_specifier"):
                name_node = _field(spec, "name")
                alias_node = _field(spec, "alias")
                name = _text(name_node) or ""
                alias = _text(alias_node)
                results.append(
                    Relationship(
                        kind=RelationshipKind.IMPORTS,
                        source_path=path,
                        source_position=_pos(spec.start_point),  # type: ignore[attr-defined]
                        target_name=name,
                        module_path=module_path,
                        alias=alias,
                        is_default=False,
                        is_namespace=False,
                    )
                )

        elif child_type == "namespace_import":
            # Namespace import: ``import * as ns from "..."``
            ns_id = next(
                (c for c in child.children if c.type == "identifier"),  # type: ignore[attr-defined]
                None,
            )
            name = _text(ns_id) or "*"
            results.append(
                Relationship(
                    kind=RelationshipKind.IMPORTS,
                    source_path=path,
                    source_position=_pos(child.start_point),  # type: ignore[attr-defined]
                    target_name=name,
                    module_path=module_path,
                    alias=None,
                    is_default=False,
                    is_namespace=True,
                )
            )

    return results


# ---------------------------------------------------------------------------
# EXPORT extraction
# ---------------------------------------------------------------------------


def _handle_export_statement(
    node: object,
    path: str,
) -> list[Relationship]:
    """
    Extract EXPORTS relationships from an ``export_statement`` node.

    Handles:
    - ``export function foo() {}``      → named export of declaration
    - ``export const X = 1``            → named export of declaration
    - ``export default UserService``    → default export of identifier
    - ``export { a, b as c }``          → export list
    - ``export * from "./mod.js"``      → re-export (target_name = "*")
    """
    results: list[Relationship] = []
    is_default = _has_anonymous_child(node, "default")

    if is_default:
        # ``export default <identifier/expression>``
        # Find the identifier or expression being exported
        for child in node.children:  # type: ignore[attr-defined]
            if child.is_named and child.type not in (  # type: ignore[attr-defined]
                "export_clause",
                "function_declaration",
                "class_declaration",
                "lexical_declaration",
                "variable_declaration",
            ):
                name = _text(child) or ""
                if name and name != "default":
                    results.append(
                        Relationship(
                            kind=RelationshipKind.EXPORTS,
                            source_path=path,
                            source_position=_pos(child.start_point),  # type: ignore[attr-defined]
                            target_name=name,
                            module_path=None,
                            alias=None,
                            is_default=True,
                            is_namespace=False,
                        )
                    )
        # Also handle ``export default function foo(){}`` or ``class Foo{}``
        for child in node.children:  # type: ignore[attr-defined]
            ct: str = child.type  # type: ignore[attr-defined]
            if ct in ("function_declaration", "class_declaration"):
                name_node = _field(child, "name")
                name = _text(name_node) or ""
                if name:
                    results.append(
                        Relationship(
                            kind=RelationshipKind.EXPORTS,
                            source_path=path,
                            source_position=_pos(child.start_point),  # type: ignore[attr-defined]
                            target_name=name,
                            module_path=None,
                            alias=None,
                            is_default=True,
                            is_namespace=False,
                        )
                    )
        return results

    # Non-default exports
    for child in node.children:  # type: ignore[attr-defined]
        ct: str = child.type  # type: ignore[attr-defined]

        if ct == "export_clause":
            # ``export { a, b as c }``
            for spec in _children_of_type(child, "export_specifier"):
                name_node = _field(spec, "name")
                alias_node = _field(spec, "alias")
                name = _text(name_node) or ""
                alias = _text(alias_node)
                results.append(
                    Relationship(
                        kind=RelationshipKind.EXPORTS,
                        source_path=path,
                        source_position=_pos(spec.start_point),  # type: ignore[attr-defined]
                        target_name=name,
                        module_path=None,
                        alias=alias,
                        is_default=False,
                        is_namespace=False,
                    )
                )

        elif ct == "function_declaration":
            # ``export function foo() {}``
            name_node = _field(child, "name")
            name = _text(name_node) or ""
            if name:
                results.append(
                    Relationship(
                        kind=RelationshipKind.EXPORTS,
                        source_path=path,
                        source_position=_pos(child.start_point),  # type: ignore[attr-defined]
                        target_name=name,
                        module_path=None,
                        alias=None,
                        is_default=False,
                        is_namespace=False,
                    )
                )

        elif ct == "class_declaration":
            # ``export class Foo {}``
            name_node = _field(child, "name")
            name = _text(name_node) or ""
            if name:
                results.append(
                    Relationship(
                        kind=RelationshipKind.EXPORTS,
                        source_path=path,
                        source_position=_pos(child.start_point),  # type: ignore[attr-defined]
                        target_name=name,
                        module_path=None,
                        alias=None,
                        is_default=False,
                        is_namespace=False,
                    )
                )

        elif ct in ("lexical_declaration", "variable_declaration"):
            # ``export const X = 1``  or  ``export let x = ...``
            for vc in _children_of_type(child, "variable_declarator"):
                name_node = _field(vc, "name")
                if name_node is None or name_node.type != "identifier":  # type: ignore[attr-defined]
                    continue
                name = _text(name_node) or ""
                if name:
                    results.append(
                        Relationship(
                            kind=RelationshipKind.EXPORTS,
                            source_path=path,
                            source_position=_pos(vc.start_point),  # type: ignore[attr-defined]
                            target_name=name,
                            module_path=None,
                            alias=None,
                            is_default=False,
                            is_namespace=False,
                        )
                    )

        elif ct == "string":
            # ``export * from "./mod.js"`` — re-export with a source
            module_path = _module_path_from_string_node(child)
            results.append(
                Relationship(
                    kind=RelationshipKind.EXPORTS,
                    source_path=path,
                    source_position=_pos(node.start_point),  # type: ignore[attr-defined]
                    target_name="*",
                    module_path=module_path,
                    alias=None,
                    is_default=False,
                    is_namespace=True,
                )
            )

    return results


# ---------------------------------------------------------------------------
# CALLS and REFERENCES extraction
# ---------------------------------------------------------------------------

# Node types that introduce new declaration scopes (we track these so that
# we don't confuse an identifier *declaring* something with one *referencing*
# something).
_DECLARATION_TYPES: frozenset[str] = frozenset(
    {
        "function_declaration",
        "class_declaration",
        "method_definition",
        "lexical_declaration",
        "variable_declaration",
        "variable_declarator",  # name field = declaration; value field = expression
        "import_statement",
        "export_statement",
        "formal_parameters",
        "import_clause",
        "export_clause",
    }
)


def _walk_for_calls_and_refs(
    node: object,
    path: str,
    *,
    inside_declaration: bool = False,
    inside_call_callee: bool = False,
) -> list[Relationship]:
    """
    Recursively walk *node* collecting CALLS and REFERENCES.

    Rules
    -----
    - A ``call_expression``'s callee (``function`` field) produces a CALLS
      relationship.
    - An ``identifier`` in value / expression position (not declaring a new
      name, not the callee of a call_expression) produces a REFERENCES
      relationship.
    - We do NOT recurse into import/export statements (handled separately).
    - We do NOT recurse into the ``name`` field of declarations.
    """
    results: list[Relationship] = []
    nt: str = node.type  # type: ignore[attr-defined]

    # Skip import/export — handled by their own extractors
    if nt in ("import_statement", "export_statement"):
        return results

    if nt == "call_expression":
        callee = _field(node, "function")
        args = _field(node, "arguments")

        # --- Emit a CALLS relationship for the callee ---
        if callee is not None:
            callee_name = _callee_name(callee)
            if callee_name == "require":
                # CommonJS: ``require("./mod")`` is recorded as a module-level
                # import (no symbol binding, like a side-effect import) so the
                # resolver can link the two files.
                req_path = _require_module_path(args)
                if req_path is not None:
                    results.append(
                        Relationship(
                            kind=RelationshipKind.IMPORTS,
                            source_path=path,
                            source_position=_pos(node.start_point),  # type: ignore[attr-defined]
                            target_name="",
                            module_path=req_path,
                            alias=None,
                            is_default=False,
                            is_namespace=False,
                        )
                    )
            if callee_name:
                results.append(
                    Relationship(
                        kind=RelationshipKind.CALLS,
                        source_path=path,
                        source_position=_pos(callee.start_point),  # type: ignore[attr-defined]
                        target_name=callee_name,
                        module_path=None,
                        alias=None,
                        is_default=False,
                        is_namespace=False,
                    )
                )
            # Recurse into callee sub-expressions (e.g. chained calls)
            # but mark them as "inside_call_callee" to avoid double-counting
            results.extend(
                _walk_for_calls_and_refs(
                    callee, path, inside_call_callee=True
                )
            )

        # Recurse into arguments for nested calls/references
        if args is not None:
            results.extend(
                _walk_for_calls_and_refs(args, path)
            )
        return results

    if nt == "identifier" and not inside_declaration and not inside_call_callee:
        # Identifier in value position → REFERENCES
        name = _text(node)
        if name:
            results.append(
                Relationship(
                    kind=RelationshipKind.REFERENCES,
                    source_path=path,
                    source_position=_pos(node.start_point),  # type: ignore[attr-defined]
                    target_name=name,
                    module_path=None,
                    alias=None,
                    is_default=False,
                    is_namespace=False,
                )
            )
        return results

    # Generic recursion — decide whether children are in declaration context
    if nt in _DECLARATION_TYPES:
        # Children of declaration nodes need careful treatment:
        # - The "name" / binding identifier is in declaration position
        # - The "value" / "body" is in expression position (can have refs/calls)
        if nt == "variable_declarator":
            # name field → declaration position (skip)
            # value field → expression position (recurse without declaration flag)
            value_child = _field(node, "value")
            if value_child is not None:
                results.extend(
                    _walk_for_calls_and_refs(value_child, path)
                )
        elif nt in ("function_declaration", "method_definition"):
            # parameters → declaration scope (skip); body → expression scope
            body = _field(node, "body")
            if body is not None:
                results.extend(
                    _walk_for_calls_and_refs(body, path)
                )
        elif nt == "class_declaration":
            body = _field(node, "body")
            if body is not None:
                results.extend(
                    _walk_for_calls_and_refs(body, path)
                )
        elif nt in ("lexical_declaration", "variable_declaration"):
            # Recurse into variable_declarator nodes (each has its own name/value handling)
            for c in node.children:  # type: ignore[attr-defined]
                if c.type == "variable_declarator":  # type: ignore[attr-defined]
                    results.extend(
                        _walk_for_calls_and_refs(c, path)  # NOT inside_declaration
                    )
        # For import/export and other declaration types: skip children
        return results

    # Default: recurse into all children
    for child in node.children:  # type: ignore[attr-defined]
        results.extend(
            _walk_for_calls_and_refs(child, path, inside_declaration=inside_declaration)
        )
    return results


def _require_module_path(args: object | None) -> str | None:
    """Return the string literal passed to ``require(...)``, or ``None``.

    Only a single plain string argument counts; dynamic expressions such as
    ``require(name)`` or template strings are not statically resolvable.
    """
    if args is None:
        return None
    named = [c for c in args.children if c.is_named]  # type: ignore[attr-defined]
    if len(named) != 1 or named[0].type != "string":  # type: ignore[attr-defined]
        return None
    module_path = _module_path_from_string_node(named[0])
    return module_path or None


def _callee_name(callee: object) -> str | None:
    """
    Derive a human-readable callee name from a call_expression's function node.

    - ``identifier``       → ``"foo"``
    - ``member_expression``→ ``"obj.method"``
    - Other types          → ``None`` (chained calls, dynamic callees, etc.)
    """
    ct: str = callee.type  # type: ignore[attr-defined]
    if ct == "identifier":
        return _text(callee)
    if ct == "member_expression":
        obj = _field(callee, "object")
        prop = _field(callee, "property")
        obj_text = _text(obj) or "?"
        prop_text = _text(prop) or "?"
        return f"{obj_text}.{prop_text}"
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_relationships(
    path: str,
    language: str,
    source: bytes | str,
) -> list[Relationship]:
    """
    Extract structural relationships from *source* using Tree-sitter.

    The returned list is sorted deterministically by source position
    (line ascending, then column ascending, then target_name ascending).

    Parameters
    ----------
    path:
        Repository-relative POSIX path (used in ``Relationship.source_path``).
    language:
        Language name matching scanner conventions (e.g. ``"javascript"``).
    source:
        Raw file content as ``bytes`` or ``str`` (auto-encoded to UTF-8).

    Returns
    -------
    list[Relationship]
        Flat, sorted list of relationships.

    Raises
    ------
    UnsupportedLanguageError
        If *language* is not yet supported by the relationship extractor.
    """
    if language not in _SUPPORTED_LANGUAGES:
        raise UnsupportedLanguageError(language)

    if isinstance(source, str):
        source = source.encode("utf-8")

    parser = _get_js_parser()
    tree = parser.parse(source)  # type: ignore[attr-defined]
    root = tree.root_node  # type: ignore[attr-defined]

    results: list[Relationship] = []

    # Walk top-level statements
    for child in root.children:  # type: ignore[attr-defined]
        ct: str = child.type  # type: ignore[attr-defined]

        if ct == "import_statement":
            results.extend(_handle_import_statement(child, path))

        elif ct == "export_statement":
            results.extend(_handle_export_statement(child, path))

        else:
            # For all other statements: scan for calls and references
            results.extend(_walk_for_calls_and_refs(child, path))

    # Deterministic sort: position first, target_name as tiebreaker
    results.sort(key=lambda r: (r.source_position.line, r.source_position.column, r.target_name))
    return results
