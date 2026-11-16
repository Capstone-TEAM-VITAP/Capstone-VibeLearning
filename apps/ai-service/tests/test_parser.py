"""
tests/test_parser.py

Test suite for Milestone 2 — Tree-sitter AST Parser.

Coverage
--------
1.  valid JavaScript — basic parse succeeds
2.  empty source — parses without error
3.  single-line comment
4.  multi-line comment
5.  string literals (single, double, template)
6.  function declarations
7.  arrow functions
8.  classes (with methods)
9.  nested syntax (function inside class inside module)
10. import statements
11. export statements (named, default)
12. syntax errors → has_errors == True
13. source positions — start/end lines and columns
14. determinism — identical source produces identical ParseResult
15. unsupported language → UnsupportedLanguageError
16. str source auto-encoded to UTF-8
17. ParseResult fields are correctly populated
18. ASTNode.is_named distinguishes named vs anonymous nodes
19. root node type is "program" for JavaScript
20. empty source root node has no children / correct positions
"""

import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Make src/ importable when running pytest from the ai-service root.
# ---------------------------------------------------------------------------
_SRC = Path(__file__).parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from repository.parser import (
    ASTNode,
    ParseResult,
    Position,
    UnsupportedLanguageError,
    parse_source,
)


# ===========================================================================
# Helpers
# ===========================================================================

def js(source: str | bytes, path: str = "src/test.js") -> ParseResult:
    """Convenience wrapper — parse JavaScript source."""
    return parse_source(path=path, language="javascript", source=source)


def _find_nodes(node: ASTNode, node_type: str) -> list[ASTNode]:
    """Recursively collect all nodes whose type matches *node_type*."""
    results: list[ASTNode] = []
    if node.type == node_type:
        results.append(node)
    for child in node.children:
        results.extend(_find_nodes(child, node_type))
    return results


# ===========================================================================
# 1. Valid JavaScript — basic parse succeeds
# ===========================================================================

class TestValidJavaScript:
    def test_simple_statement_returns_parse_result(self) -> None:
        result = js("console.log('hello');")
        assert isinstance(result, ParseResult)

    def test_has_errors_false_for_valid_source(self) -> None:
        result = js("const x = 42;")
        assert result.has_errors is False

    def test_root_is_ast_node(self) -> None:
        result = js("let y = true;")
        assert isinstance(result.root, ASTNode)

    def test_path_preserved(self) -> None:
        result = parse_source(
            path="src/auth/login.js",
            language="javascript",
            source=b"const x = 1;",
        )
        assert result.path == "src/auth/login.js"

    def test_language_preserved(self) -> None:
        result = js("const x = 1;")
        assert result.language == "javascript"


# ===========================================================================
# 2. Empty source
# ===========================================================================

class TestEmptySource:
    def test_empty_bytes_parses_without_error(self) -> None:
        result = js(b"")
        assert result.has_errors is False

    def test_empty_string_parses_without_error(self) -> None:
        result = js("")
        assert result.has_errors is False

    def test_empty_root_type_is_program(self) -> None:
        result = js(b"")
        assert result.root.type == "program"

    def test_empty_root_starts_at_line_1(self) -> None:
        result = js(b"")
        assert result.root.start.line == 1
        assert result.root.start.column == 0


# ===========================================================================
# 3. Root node type
# ===========================================================================

class TestRootNodeType:
    def test_js_root_is_program(self) -> None:
        """Tree-sitter JavaScript grammar always uses 'program' as root."""
        result = js("const x = 1;")
        assert result.root.type == "program"

    def test_root_children_non_empty_for_non_empty_source(self) -> None:
        result = js("const x = 1;")
        assert len(result.root.children) > 0


# ===========================================================================
# 4. Comments
# ===========================================================================

class TestComments:
    def test_single_line_comment(self) -> None:
        result = js("// this is a comment\nconst x = 1;")
        assert result.has_errors is False

    def test_multi_line_comment(self) -> None:
        result = js("/* block\n   comment */\nconst y = 2;")
        assert result.has_errors is False

    def test_comment_nodes_present_in_tree(self) -> None:
        result = js("// hello\nconst x = 1;")
        comments = _find_nodes(result.root, "comment")
        assert len(comments) >= 1


# ===========================================================================
# 5. String literals
# ===========================================================================

class TestStringLiterals:
    def test_single_quoted_string(self) -> None:
        result = js("const s = 'hello';")
        assert result.has_errors is False

    def test_double_quoted_string(self) -> None:
        result = js('const s = "hello";')
        assert result.has_errors is False

    def test_template_literal(self) -> None:
        result = js("const s = `hello ${name}`;")
        assert result.has_errors is False


# ===========================================================================
# 6. Function declarations
# ===========================================================================

class TestFunctions:
    def test_function_declaration(self) -> None:
        src = "function greet(name) { return 'Hi ' + name; }"
        result = js(src)
        assert result.has_errors is False
        fns = _find_nodes(result.root, "function_declaration")
        assert len(fns) == 1

    def test_function_expression(self) -> None:
        src = "const greet = function(name) { return name; };"
        result = js(src)
        assert result.has_errors is False

    def test_function_node_is_named(self) -> None:
        src = "function foo() {}"
        result = js(src)
        fns = _find_nodes(result.root, "function_declaration")
        assert fns[0].is_named is True


# ===========================================================================
# 7. Arrow functions
# ===========================================================================

class TestArrowFunctions:
    def test_concise_arrow_function(self) -> None:
        src = "const double = x => x * 2;"
        result = js(src)
        assert result.has_errors is False

    def test_block_arrow_function(self) -> None:
        src = "const add = (a, b) => { return a + b; };"
        result = js(src)
        assert result.has_errors is False

    def test_arrow_function_node_present(self) -> None:
        src = "const fn = () => 42;"
        result = js(src)
        arrows = _find_nodes(result.root, "arrow_function")
        assert len(arrows) >= 1


# ===========================================================================
# 8. Classes
# ===========================================================================

class TestClasses:
    def test_basic_class(self) -> None:
        src = "class Animal { constructor(name) { this.name = name; } }"
        result = js(src)
        assert result.has_errors is False

    def test_class_with_method(self) -> None:
        src = """
class Dog extends Animal {
    bark() { return 'woof'; }
}
"""
        result = js(src)
        assert result.has_errors is False

    def test_class_node_present(self) -> None:
        src = "class Foo {}"
        result = js(src)
        classes = _find_nodes(result.root, "class_declaration")
        assert len(classes) == 1


# ===========================================================================
# 9. Nested syntax
# ===========================================================================

class TestNestedSyntax:
    def test_deeply_nested_structure(self) -> None:
        src = """
class Service {
    process(data) {
        return data.map(item => {
            if (item.active) {
                return item.value;
            }
            return null;
        });
    }
}
"""
        result = js(src)
        assert result.has_errors is False

    def test_nested_functions(self) -> None:
        src = """
function outer() {
    function inner() {
        return 42;
    }
    return inner();
}
"""
        result = js(src)
        assert result.has_errors is False
        fns = _find_nodes(result.root, "function_declaration")
        assert len(fns) == 2


# ===========================================================================
# 10. Import statements
# ===========================================================================

class TestImports:
    def test_default_import(self) -> None:
        src = "import React from 'react';"
        result = js(src)
        assert result.has_errors is False

    def test_named_import(self) -> None:
        src = "import { useState, useEffect } from 'react';"
        result = js(src)
        assert result.has_errors is False

    def test_namespace_import(self) -> None:
        src = "import * as fs from 'fs';"
        result = js(src)
        assert result.has_errors is False

    def test_import_node_present(self) -> None:
        src = "import React from 'react';"
        result = js(src)
        imports = _find_nodes(result.root, "import_statement")
        assert len(imports) == 1


# ===========================================================================
# 11. Export statements
# ===========================================================================

class TestExports:
    def test_named_export(self) -> None:
        src = "export const PI = 3.14;"
        result = js(src)
        assert result.has_errors is False

    def test_default_export(self) -> None:
        src = "export default function App() { return null; }"
        result = js(src)
        assert result.has_errors is False

    def test_export_node_present(self) -> None:
        src = "export const x = 1;"
        result = js(src)
        exports = _find_nodes(result.root, "export_statement")
        assert len(exports) == 1


# ===========================================================================
# 12. Syntax errors
# ===========================================================================

class TestSyntaxErrors:
    def test_unclosed_brace_has_errors(self) -> None:
        result = js("function broken() {")
        assert result.has_errors is True

    def test_invalid_token_has_errors(self) -> None:
        result = js("const x = @@@;")
        assert result.has_errors is True

    def test_missing_semicolon_may_still_parse(self) -> None:
        """
        JavaScript ASI (automatic semicolon insertion) means missing
        semicolons are usually NOT parse errors — just verify it doesn't
        crash and returns a ParseResult.
        """
        result = js("const x = 1\nconst y = 2")
        assert isinstance(result, ParseResult)

    def test_has_errors_true_produces_valid_parse_result(self) -> None:
        """Even when has_errors is True, we still get a valid ParseResult."""
        result = js("((((")
        assert isinstance(result, ParseResult)
        assert result.has_errors is True
        assert isinstance(result.root, ASTNode)


# ===========================================================================
# 13. Source positions
# ===========================================================================

class TestSourcePositions:
    def test_root_starts_at_line_1_column_0(self) -> None:
        result = js("const x = 1;")
        assert result.root.start.line == 1
        assert result.root.start.column == 0

    def test_multiline_end_position(self) -> None:
        src = "const a = 1;\nconst b = 2;\nconst c = 3;"
        result = js(src)
        # Root must end at or after line 3
        assert result.root.end.line >= 3

    def test_second_line_statement_starts_at_line_2(self) -> None:
        src = "const a = 1;\nconst b = 2;"
        result = js(src)
        # Root has two lexical_declaration children
        named_children = [c for c in result.root.children if c.is_named]
        assert len(named_children) == 2
        # Second declaration must start on line 2
        assert named_children[1].start.line == 2

    def test_column_0_for_line_start(self) -> None:
        src = "function foo() {}\nfunction bar() {}"
        result = js(src)
        fns = _find_nodes(result.root, "function_declaration")
        assert fns[0].start.column == 0
        assert fns[1].start.column == 0

    def test_indented_node_has_nonzero_column(self) -> None:
        src = "class Foo {\n  bar() {}\n}"
        result = js(src)
        # method_definition inside the class body is indented
        methods = _find_nodes(result.root, "method_definition")
        assert len(methods) >= 1
        assert methods[0].start.column > 0

    def test_position_is_position_instance(self) -> None:
        result = js("const x = 1;")
        assert isinstance(result.root.start, Position)
        assert isinstance(result.root.end, Position)

    def test_position_line_is_int(self) -> None:
        result = js("const x = 1;")
        assert isinstance(result.root.start.line, int)
        assert isinstance(result.root.start.column, int)


# ===========================================================================
# 14. Determinism
# ===========================================================================

class TestDeterminism:
    def test_same_source_same_result(self) -> None:
        src = "function hello() { return 42; }"
        first = js(src)
        second = js(src)
        assert first == second

    def test_same_source_same_root_type(self) -> None:
        src = "const x = [1, 2, 3];"
        assert js(src).root.type == js(src).root.type

    def test_same_source_same_error_status(self) -> None:
        src = "function broken() {"
        assert js(src).has_errors == js(src).has_errors

    def test_complex_source_deterministic(self) -> None:
        src = """
import React, { useState } from 'react';

class Counter extends React.Component {
    constructor(props) {
        super(props);
        this.state = { count: 0 };
    }
    increment = () => this.setState(s => ({ count: s.count + 1 }));
    render() {
        return null;
    }
}

export default Counter;
"""
        results = [js(src) for _ in range(3)]
        assert results[0] == results[1] == results[2]


# ===========================================================================
# 15. Unsupported language
# ===========================================================================

class TestUnsupportedLanguage:
    def test_java_raises_unsupported(self) -> None:
        with pytest.raises(UnsupportedLanguageError) as exc_info:
            parse_source(path="Main.java", language="java", source=b"class A {}")
        assert exc_info.value.language == "java"

    def test_typescript_raises_unsupported(self) -> None:
        with pytest.raises(UnsupportedLanguageError) as exc_info:
            parse_source(
                path="app.ts",
                language="typescript",
                source=b"const x: number = 1;",
            )
        assert exc_info.value.language == "typescript"

    def test_unknown_raises_unsupported(self) -> None:
        with pytest.raises(UnsupportedLanguageError):
            parse_source(path="foo.xyz", language="cobol", source=b"HELLO.")

    def test_error_message_contains_language(self) -> None:
        with pytest.raises(UnsupportedLanguageError) as exc_info:
            parse_source(path="x.rb", language="ruby", source=b"puts 'hi'")
        assert "ruby" in str(exc_info.value)


# ===========================================================================
# 16. str source auto-encoding
# ===========================================================================

class TestStrSource:
    def test_str_source_accepted(self) -> None:
        result = js("const x = 'héllo';")
        assert isinstance(result, ParseResult)
        assert result.has_errors is False

    def test_str_and_bytes_produce_same_result(self) -> None:
        source_str = "function foo() { return 1; }"
        source_bytes = source_str.encode("utf-8")
        r_str = js(source_str)
        r_bytes = js(source_bytes)
        assert r_str == r_bytes


# ===========================================================================
# 17. ASTNode.is_named
# ===========================================================================

class TestIsNamed:
    def test_program_node_is_named(self) -> None:
        result = js("const x = 1;")
        assert result.root.is_named is True

    def test_anonymous_punctuation_not_named(self) -> None:
        """
        Leaf tokens like '(' ')' '{' '}' are anonymous nodes (is_named=False).
        Verify at least one such node exists inside a function declaration.
        """
        result = js("function foo() {}")
        all_nodes: list[ASTNode] = []

        def collect(node: ASTNode) -> None:
            all_nodes.append(node)
            for c in node.children:
                collect(c)

        collect(result.root)
        anonymous_nodes = [n for n in all_nodes if not n.is_named]
        assert len(anonymous_nodes) > 0


# ===========================================================================
# 18. ParseResult is frozen / immutable
# ===========================================================================

class TestImmutability:
    def test_parse_result_is_frozen(self) -> None:
        result = js("const x = 1;")
        with pytest.raises((AttributeError, TypeError)):
            result.has_errors = True  # type: ignore[misc]

    def test_ast_node_is_frozen(self) -> None:
        result = js("const x = 1;")
        with pytest.raises((AttributeError, TypeError)):
            result.root.type = "hacked"  # type: ignore[misc]

    def test_position_is_frozen(self) -> None:
        result = js("const x = 1;")
        with pytest.raises((AttributeError, TypeError)):
            result.root.start.line = 999  # type: ignore[misc]
