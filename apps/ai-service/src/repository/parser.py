"""
repository/parser.py

Tree-sitter based AST parser — Milestone 2.

Responsibilities
----------------
- Receive a file path + raw source bytes and a language name.
- Parse the source deterministically using Tree-sitter.
- Convert the Tree-sitter tree into an immutable internal representation
  (``ParseResult``) that is independent of the Tree-sitter object model.
- Detect and surface syntax errors via ``ParseResult.has_errors``.
- Expose source positions using 1-indexed lines (human convention) and
  0-indexed columns (editor convention).

Supported languages (Milestone 2)
----------------------------------
- javascript  (.js / .jsx)

Public API
----------
parse_source(path, language, source) -> ParseResult
    Parse *source* and return a ``ParseResult``.
    Raises ``UnsupportedLanguageError`` for unrecognised language names.

Internal models (immutable, frozen dataclasses)
-----------------------------------------------
Position   – a single location in source (line 1-indexed, column 0-indexed)
ASTNode    – a node in the AST tree
ParseResult – top-level parse output
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class UnsupportedLanguageError(ValueError):
    """Raised when *language* has no registered Tree-sitter grammar."""

    def __init__(self, language: str) -> None:
        super().__init__(
            f"Tree-sitter parsing is not supported for language: {language!r}. "
            f"Supported: {sorted(_LANGUAGE_LOADERS)}"
        )
        self.language = language


# ---------------------------------------------------------------------------
# Immutable AST models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Position:
    """
    A single point in source code.

    Attributes
    ----------
    line:
        1-indexed line number (row 0 in Tree-sitter → line 1 here).
    column:
        0-indexed column number (matches Tree-sitter convention).
    """

    line: int
    column: int


@dataclass(frozen=True)
class ASTNode:
    """
    An immutable representation of a single Tree-sitter syntax node.

    Attributes
    ----------
    type:
        The Tree-sitter node type string, e.g. ``"function_declaration"``.
    start:
        Position of the first character of this node.
    end:
        Position of the character *after* the last character of this node.
    is_named:
        ``True`` for named nodes (semantically meaningful syntax), ``False``
        for anonymous nodes (punctuation, keywords treated as literals).
    children:
        Ordered tuple of all child nodes (named *and* anonymous).
    """

    type: str
    start: Position
    end: Position
    is_named: bool
    children: tuple[ASTNode, ...]


@dataclass(frozen=True)
class ParseResult:
    """
    The complete result of parsing a single source file.

    Attributes
    ----------
    path:
        Repository-relative POSIX path of the parsed file.
        Example: ``"src/auth/login.js"``
    language:
        Language name used for parsing.  Example: ``"javascript"``
    root:
        Root ``ASTNode`` of the parse tree.
    has_errors:
        ``True`` if the Tree-sitter parser inserted any ERROR or MISSING
        nodes, indicating the source contains syntax errors.
    """

    path: str
    language: str
    root: ASTNode
    has_errors: bool


# ---------------------------------------------------------------------------
# Language registry
# ---------------------------------------------------------------------------
# Each entry maps a language name (matching scanner.py conventions) to a
# zero-argument callable that returns a tree_sitter.Language object.
# New languages can be added here without touching any other code.
# The callable is intentionally lazy: the import only happens on first use.
# ---------------------------------------------------------------------------

def _load_javascript() -> object:  # returns tree_sitter.Language
    import tree_sitter_javascript as tsjs
    from tree_sitter import Language  # type: ignore[import]
    return Language(tsjs.language())


_LANGUAGE_LOADERS: dict[str, object] = {
    "javascript": _load_javascript,
}


@lru_cache(maxsize=None)
def _get_ts_language(language: str) -> object:
    """
    Load and cache the Tree-sitter Language object for *language*.

    The result is cached at module level so each grammar is compiled /
    loaded exactly once per process.

    Raises
    ------
    UnsupportedLanguageError
        If *language* is not in the registry.
    """
    loader = _LANGUAGE_LOADERS.get(language)
    if loader is None:
        raise UnsupportedLanguageError(language)
    return loader()  # type: ignore[operator]


@lru_cache(maxsize=None)
def _get_parser(language: str) -> object:  # returns tree_sitter.Parser
    """
    Build and cache a ``tree_sitter.Parser`` configured for *language*.

    Parsers are stateless between ``parse()`` calls and safe to reuse.
    """
    from tree_sitter import Parser  # type: ignore[import]
    ts_language = _get_ts_language(language)
    return Parser(ts_language)


# ---------------------------------------------------------------------------
# Tree conversion
# ---------------------------------------------------------------------------


def _ts_point_to_position(point: object) -> Position:
    """Convert a ``tree_sitter.Point`` to our ``Position`` model.

    Tree-sitter rows are 0-indexed; we expose 1-indexed lines.
    Columns remain 0-indexed.
    """
    return Position(line=point.row + 1, column=point.column)  # type: ignore[attr-defined]


def _convert_node(ts_node: object) -> ASTNode:
    """
    Recursively convert a Tree-sitter node into an immutable ``ASTNode``.

    All children (named and anonymous) are preserved in order, mirroring
    the exact structure Tree-sitter produces for deterministic output.
    """
    children = tuple(_convert_node(child) for child in ts_node.children)  # type: ignore[attr-defined]
    return ASTNode(
        type=ts_node.type,  # type: ignore[attr-defined]
        start=_ts_point_to_position(ts_node.start_point),  # type: ignore[attr-defined]
        end=_ts_point_to_position(ts_node.end_point),  # type: ignore[attr-defined]
        is_named=ts_node.is_named,  # type: ignore[attr-defined]
        children=children,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_source(
    path: str,
    language: str,
    source: bytes | str,
) -> ParseResult:
    """
    Parse *source* using Tree-sitter and return an immutable ``ParseResult``.

    Parameters
    ----------
    path:
        Repository-relative POSIX path of the file being parsed.
        Used only for labelling the result; the file is not read from disk.
    language:
        Language name as returned by ``scanner.detect_language()``.
        Example: ``"javascript"``
    source:
        Raw file content as ``bytes`` (UTF-8) or ``str`` (auto-encoded).

    Returns
    -------
    ParseResult
        Immutable parse result including the full AST and error flag.

    Raises
    ------
    UnsupportedLanguageError
        If *language* is not supported.
    """
    if isinstance(source, str):
        source = source.encode("utf-8")

    parser = _get_parser(language)
    tree = parser.parse(source)  # type: ignore[attr-defined]

    root_ts = tree.root_node  # type: ignore[attr-defined]
    root_node = _convert_node(root_ts)

    return ParseResult(
        path=path,
        language=language,
        root=root_node,
        has_errors=root_ts.has_error,
    )
