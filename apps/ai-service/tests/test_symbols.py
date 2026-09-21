"""
tests/test_symbols.py

Test suite for Milestone 3 — Symbol Extraction.

Coverage
--------
1.  function declaration → FUNCTION kind
2.  named function expression (const f = function() {}) → FUNCTION
3.  named arrow function (const f = () => {}) → FUNCTION
4.  anonymous function behavior — not extracted
5.  class declaration → CLASS kind
6.  class methods → METHOD kind
7.  multiple functions in one file
8.  nested functions — inner has parent=outer name
9.  variables (let / var) → VARIABLE kind
10. constants (const) → CONSTANT kind
11. nested symbols (class + methods) — method.parent == class name
12. symbol source ranges (start.line, start.column, end.line)
13. symbol file path field
14. symbol kind field values
15. deterministic ordering (sorted by source position)
16. empty source → empty list
17. source with syntax errors — valid symbols still extracted
18. duplicate names in different scopes — both extracted, different parents
19. exported function → FUNCTION (export transparent)
20. exported const → CONSTANT (export transparent)
21. UnsupportedLanguageError for non-JS languages
22. str source auto-encoding
23. Symbol is frozen / immutable
24. parent chain — three levels of nesting
25. var declaration → VARIABLE
26. anonymous arrow as callback — not extracted
27. const with non-callable value → CONSTANT, not FUNCTION
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

from repository.parser import UnsupportedLanguageError
from repository.symbols import Symbol, SymbolKind, extract_symbols


# ===========================================================================
# Helpers
# ===========================================================================


def js(source: str | bytes, path: str = "src/test.js") -> list[Symbol]:
    """Convenience wrapper — extract JavaScript symbols."""
    return extract_symbols(path=path, language="javascript", source=source)


def by_name(symbols: list[Symbol], name: str) -> Symbol:
    """Return the first Symbol with the given name, or raise AssertionError."""
    for s in symbols:
        if s.name == name:
            return s
    raise AssertionError(f"Symbol {name!r} not found in: {[s.name for s in symbols]}")


def names(symbols: list[Symbol]) -> list[str]:
    """Extract just the name strings."""
    return [s.name for s in symbols]


# ===========================================================================
# 1. Function declaration
# ===========================================================================


class TestFunctionDeclaration:
    def test_basic_function_extracted(self) -> None:
        syms = js("function greet(name) { return name; }")
        assert "greet" in names(syms)

    def test_function_kind_is_function(self) -> None:
        syms = js("function greet(name) { return name; }")
        assert by_name(syms, "greet").kind == SymbolKind.FUNCTION

    def test_function_kind_string_value(self) -> None:
        """SymbolKind is a str Enum — value equals its string."""
        syms = js("function greet() {}")
        assert by_name(syms, "greet").kind == "function"

    def test_function_top_level_parent_is_none(self) -> None:
        syms = js("function foo() {}")
        assert by_name(syms, "foo").parent is None

    def test_multiple_function_declarations(self) -> None:
        src = "function alpha() {}\nfunction beta() {}\nfunction gamma() {}"
        syms = js(src)
        assert set(names(syms)) == {"alpha", "beta", "gamma"}


# ===========================================================================
# 2. Named function expression
# ===========================================================================


class TestFunctionExpression:
    def test_named_function_expression_extracted(self) -> None:
        syms = js("const add = function(a, b) { return a + b; };")
        assert "add" in names(syms)

    def test_named_function_expression_is_function_kind(self) -> None:
        syms = js("const add = function(a, b) { return a + b; };")
        assert by_name(syms, "add").kind == SymbolKind.FUNCTION

    def test_named_function_expression_parent_none(self) -> None:
        syms = js("const handler = function() {};")
        assert by_name(syms, "handler").parent is None

    def test_function_expression_with_let(self) -> None:
        """let f = function() {} — still extracted as FUNCTION."""
        syms = js("let handler = function() { return 1; };")
        assert by_name(syms, "handler").kind == SymbolKind.FUNCTION


# ===========================================================================
# 3. Named arrow function
# ===========================================================================


class TestArrowFunction:
    def test_named_arrow_function_extracted(self) -> None:
        syms = js("const double = x => x * 2;")
        assert "double" in names(syms)

    def test_named_arrow_function_is_function_kind(self) -> None:
        syms = js("const double = x => x * 2;")
        assert by_name(syms, "double").kind == SymbolKind.FUNCTION

    def test_block_body_arrow_function_extracted(self) -> None:
        syms = js("const add = (a, b) => { return a + b; };")
        assert "add" in names(syms)

    def test_arrow_function_parent_none(self) -> None:
        syms = js("const fn = () => 42;")
        assert by_name(syms, "fn").parent is None

    def test_arrow_function_with_let(self) -> None:
        syms = js("let transform = data => data.trim();")
        assert by_name(syms, "transform").kind == SymbolKind.FUNCTION


# ===========================================================================
# 4. Anonymous function behavior — NOT extracted
# ===========================================================================


class TestAnonymousFunctions:
    def test_anonymous_callback_not_extracted(self) -> None:
        src = "[1, 2, 3].forEach(function() { console.log('hi'); });"
        syms = js(src)
        assert syms == []

    def test_anonymous_arrow_callback_not_extracted(self) -> None:
        src = "[1, 2, 3].map(x => x * 2);"
        syms = js(src)
        assert syms == []

    def test_iife_not_extracted(self) -> None:
        src = "(function() { console.log('iife'); })();"
        syms = js(src)
        assert syms == []

    def test_const_with_non_callable_not_function(self) -> None:
        """const arr = [1, 2].map(...) — arr is CONSTANT, not FUNCTION."""
        src = "const result = [1, 2].map(x => x * 2);"
        syms = js(src)
        assert len(syms) == 1
        assert by_name(syms, "result").kind == SymbolKind.CONSTANT

    def test_named_binding_in_settimeout_not_extracted(self) -> None:
        """
        setTimeout's callback is anonymous in binding context.
        The surrounding const is a CONSTANT holding the timeout id (number).
        """
        src = "setTimeout(function() { return 1; }, 1000);"
        syms = js(src)
        assert syms == []


# ===========================================================================
# 5. Class declarations
# ===========================================================================


class TestClassDeclarations:
    def test_class_extracted(self) -> None:
        syms = js("class Animal {}")
        assert "Animal" in names(syms)

    def test_class_kind_is_class(self) -> None:
        syms = js("class Animal {}")
        assert by_name(syms, "Animal").kind == SymbolKind.CLASS

    def test_class_kind_string_value(self) -> None:
        syms = js("class Dog {}")
        assert by_name(syms, "Dog").kind == "class"

    def test_class_top_level_parent_none(self) -> None:
        syms = js("class Service {}")
        assert by_name(syms, "Service").parent is None

    def test_class_with_extends(self) -> None:
        syms = js("class Dog extends Animal {}")
        assert "Dog" in names(syms)
        assert by_name(syms, "Dog").kind == SymbolKind.CLASS


# ===========================================================================
# 6. Class methods
# ===========================================================================


class TestClassMethods:
    def test_method_extracted(self) -> None:
        src = "class Svc { login() { return true; } }"
        syms = js(src)
        assert "login" in names(syms)

    def test_method_kind_is_method(self) -> None:
        src = "class Svc { login() { return true; } }"
        syms = js(src)
        assert by_name(syms, "login").kind == SymbolKind.METHOD

    def test_method_kind_string_value(self) -> None:
        src = "class Svc { doWork() {} }"
        syms = js(src)
        assert by_name(syms, "doWork").kind == "method"

    def test_method_parent_is_class_name(self) -> None:
        src = "class UserService { login() {} }"
        syms = js(src)
        assert by_name(syms, "login").parent == "UserService"

    def test_multiple_methods_all_extracted(self) -> None:
        src = "class Dog { bark() {} fetch() {} sit() {} }"
        syms = js(src)
        method_names = {s.name for s in syms if s.kind == SymbolKind.METHOD}
        assert method_names == {"bark", "fetch", "sit"}

    def test_all_methods_have_class_as_parent(self) -> None:
        src = "class Cat { meow() {} purr() {} sleep() {} }"
        syms = js(src)
        methods = [s for s in syms if s.kind == SymbolKind.METHOD]
        assert all(m.parent == "Cat" for m in methods)

    def test_constructor_method_extracted(self) -> None:
        src = "class Box { constructor(value) { this.value = value; } }"
        syms = js(src)
        assert "constructor" in names(syms)
        assert by_name(syms, "constructor").kind == SymbolKind.METHOD


# ===========================================================================
# 7. Multiple functions in one file
# ===========================================================================


class TestMultipleFunctions:
    def test_all_functions_extracted(self) -> None:
        src = "function a() {}\nfunction b() {}\nfunction c() {}"
        syms = js(src)
        assert set(names(syms)) == {"a", "b", "c"}
        assert all(s.kind == SymbolKind.FUNCTION for s in syms)

    def test_mixed_declarations_all_extracted(self) -> None:
        src = (
            "function foo() {}\n"
            "const bar = () => 1;\n"
            "class Baz {}\n"
            "let count = 0;\n"
        )
        syms = js(src)
        assert set(names(syms)) == {"foo", "bar", "Baz", "count"}


# ===========================================================================
# 8. Nested functions
# ===========================================================================


class TestNestedFunctions:
    def test_inner_function_extracted(self) -> None:
        src = "function outer() {\n  function inner() { return 1; }\n}"
        syms = js(src)
        assert "inner" in names(syms)

    def test_inner_function_parent_is_outer(self) -> None:
        src = "function outer() {\n  function inner() { return 1; }\n}"
        syms = js(src)
        assert by_name(syms, "inner").parent == "outer"

    def test_outer_function_parent_is_none(self) -> None:
        src = "function outer() {\n  function inner() { return 1; }\n}"
        syms = js(src)
        assert by_name(syms, "outer").parent is None

    def test_both_outer_and_inner_extracted(self) -> None:
        src = "function outer() {\n  function inner() {}\n}"
        syms = js(src)
        assert set(names(syms)) == {"outer", "inner"}


# ===========================================================================
# 9. Variables (let / var)
# ===========================================================================


class TestVariables:
    def test_let_variable_extracted(self) -> None:
        syms = js("let count = 0;")
        assert "count" in names(syms)

    def test_let_kind_is_variable(self) -> None:
        syms = js("let count = 0;")
        assert by_name(syms, "count").kind == SymbolKind.VARIABLE

    def test_var_variable_extracted(self) -> None:
        syms = js("var score = 100;")
        assert "score" in names(syms)

    def test_var_kind_is_variable(self) -> None:
        syms = js("var score = 100;")
        assert by_name(syms, "score").kind == SymbolKind.VARIABLE

    def test_variable_kind_string_value(self) -> None:
        syms = js("let x = 1;")
        assert by_name(syms, "x").kind == "variable"

    def test_multiple_let_declarations(self) -> None:
        src = "let a = 1;\nlet b = 2;\nlet c = 3;"
        syms = js(src)
        assert set(names(syms)) == {"a", "b", "c"}
        assert all(s.kind == SymbolKind.VARIABLE for s in syms)


# ===========================================================================
# 10. Constants (const)
# ===========================================================================


class TestConstants:
    def test_const_extracted(self) -> None:
        syms = js("const PI = 3.14;")
        assert "PI" in names(syms)

    def test_const_kind_is_constant(self) -> None:
        syms = js("const PI = 3.14;")
        assert by_name(syms, "PI").kind == SymbolKind.CONSTANT

    def test_const_kind_string_value(self) -> None:
        syms = js("const MAX = 100;")
        assert by_name(syms, "MAX").kind == "constant"

    def test_const_parent_is_none(self) -> None:
        syms = js("const PI = 3.14;")
        assert by_name(syms, "PI").parent is None


# ===========================================================================
# 11. Nested symbols (class + methods hierarchy)
# ===========================================================================


class TestNestedSymbols:
    def test_class_and_method_both_present(self) -> None:
        src = "class UserService { login() {} }"
        syms = js(src)
        kinds = {s.name: s.kind for s in syms}
        assert kinds["UserService"] == SymbolKind.CLASS
        assert kinds["login"] == SymbolKind.METHOD

    def test_method_parent_links_to_class(self) -> None:
        src = "class Repo { find() {} save() {} delete() {} }"
        syms = js(src)
        methods = [s for s in syms if s.kind == SymbolKind.METHOD]
        assert all(m.parent == "Repo" for m in methods)
        assert len(methods) == 3

    def test_function_inside_method_parent_is_method(self) -> None:
        src = """
class Svc {
    process() {
        function helper() { return 1; }
    }
}
"""
        syms = js(src)
        helper = by_name(syms, "helper")
        assert helper.parent == "process"

    def test_three_level_hierarchy(self) -> None:
        src = """
function outer() {
    function middle() {
        function inner() {}
    }
}
"""
        syms = js(src)
        assert by_name(syms, "outer").parent is None
        assert by_name(syms, "middle").parent == "outer"
        assert by_name(syms, "inner").parent == "middle"


# ===========================================================================
# 12. Symbol source ranges
# ===========================================================================


class TestSourceRanges:
    def test_function_starts_at_line_1(self) -> None:
        syms = js("function foo() {}")
        assert by_name(syms, "foo").start.line == 1

    def test_function_start_column_zero(self) -> None:
        syms = js("function foo() {}")
        assert by_name(syms, "foo").start.column == 0

    def test_second_declaration_starts_at_line_2(self) -> None:
        src = "function first() {}\nfunction second() {}"
        syms = js(src)
        assert by_name(syms, "second").start.line == 2

    def test_end_line_at_or_after_start_line(self) -> None:
        syms = js("function foo() {\n  return 1;\n}")
        sym = by_name(syms, "foo")
        assert sym.end.line >= sym.start.line

    def test_multiline_function_end_line_gt_start(self) -> None:
        src = "function foo() {\n  const x = 1;\n  return x;\n}"
        syms = js(src)
        sym = by_name(syms, "foo")
        assert sym.end.line > sym.start.line

    def test_indented_method_has_nonzero_column(self) -> None:
        src = "class Foo {\n  bar() {}\n}"
        syms = js(src)
        assert by_name(syms, "bar").start.column > 0

    def test_start_and_end_are_position_instances(self) -> None:
        from repository.parser import Position

        syms = js("function foo() {}")
        sym = by_name(syms, "foo")
        assert isinstance(sym.start, Position)
        assert isinstance(sym.end, Position)


# ===========================================================================
# 13. Symbol file path
# ===========================================================================


class TestSymbolPath:
    def test_path_preserved_in_symbol(self) -> None:
        syms = extract_symbols(
            path="src/auth/login.js",
            language="javascript",
            source="function login() {}",
        )
        assert by_name(syms, "login").path == "src/auth/login.js"

    def test_all_symbols_share_same_path(self) -> None:
        src = "function a() {}\nconst B = 1;\nclass C {}"
        syms = extract_symbols(path="src/module.js", language="javascript", source=src)
        assert all(s.path == "src/module.js" for s in syms)


# ===========================================================================
# 14. Symbol kind field
# ===========================================================================


class TestSymbolKindEnum:
    def test_function_kind_value(self) -> None:
        assert SymbolKind.FUNCTION.value == "function"

    def test_class_kind_value(self) -> None:
        assert SymbolKind.CLASS.value == "class"

    def test_method_kind_value(self) -> None:
        assert SymbolKind.METHOD.value == "method"

    def test_variable_kind_value(self) -> None:
        assert SymbolKind.VARIABLE.value == "variable"

    def test_constant_kind_value(self) -> None:
        assert SymbolKind.CONSTANT.value == "constant"

    def test_kind_is_str(self) -> None:
        """SymbolKind(str, Enum) — each kind IS a str."""
        assert isinstance(SymbolKind.FUNCTION, str)


# ===========================================================================
# 15. Deterministic ordering
# ===========================================================================


class TestDeterministicOrdering:
    def test_symbols_sorted_by_source_position(self) -> None:
        src = "function c() {}\nfunction a() {}\nfunction b() {}"
        syms = js(src)
        lines = [s.start.line for s in syms]
        assert lines == sorted(lines)

    def test_repeated_extraction_is_identical(self) -> None:
        src = "function foo() {}\nconst bar = 1;\nclass Baz {}"
        first = js(src)
        second = js(src)
        assert first == second

    def test_complex_source_deterministic(self) -> None:
        src = """
class Auth {
    login() {}
    logout() {}
}
function helper() {}
const MAX = 100;
"""
        results = [js(src) for _ in range(3)]
        assert results[0] == results[1] == results[2]


# ===========================================================================
# 16. Empty source
# ===========================================================================


class TestEmptySource:
    def test_empty_bytes_returns_empty_list(self) -> None:
        assert js(b"") == []

    def test_empty_string_returns_empty_list(self) -> None:
        assert js("") == []

    def test_whitespace_only_returns_empty_list(self) -> None:
        assert js("   \n\n  \t  ") == []

    def test_comment_only_returns_empty_list(self) -> None:
        assert js("// just a comment\n/* block comment */") == []


# ===========================================================================
# 17. Syntax-error source — valid symbols still extracted
# ===========================================================================


class TestSyntaxErrorSource:
    def test_symbols_before_error_extracted(self) -> None:
        """Valid declarations before a syntax error still yield symbols."""
        src = "function good() {}\nconst x = @@@;"
        syms = js(src)
        # "good" should still be found even though the file has errors
        assert "good" in names(syms)

    def test_returns_list_not_raises(self) -> None:
        """Even broken source must return a list, not raise."""
        result = js("function broken() {")
        assert isinstance(result, list)


# ===========================================================================
# 18. Duplicate names in different scopes
# ===========================================================================


class TestDuplicateNamesInScopes:
    def test_same_name_different_class(self) -> None:
        src = """
class A { foo() {} }
class B { foo() {} }
"""
        syms = js(src)
        foos = [s for s in syms if s.name == "foo"]
        assert len(foos) == 2
        parents = {s.parent for s in foos}
        assert parents == {"A", "B"}

    def test_same_function_name_different_scope(self) -> None:
        src = """
function outer() {
    function helper() {}
}
function standalone() {
    function helper() {}
}
"""
        syms = js(src)
        helpers = [s for s in syms if s.name == "helper"]
        assert len(helpers) == 2
        parents = {s.parent for s in helpers}
        assert parents == {"outer", "standalone"}


# ===========================================================================
# 19–20. Export transparent (function / const)
# ===========================================================================


class TestExportedDeclarations:
    def test_exported_function_extracted(self) -> None:
        syms = js("export function helper() { return 1; }")
        assert "helper" in names(syms)
        assert by_name(syms, "helper").kind == SymbolKind.FUNCTION

    def test_exported_const_extracted(self) -> None:
        syms = js("export const PI = 3.14;")
        assert "PI" in names(syms)
        assert by_name(syms, "PI").kind == SymbolKind.CONSTANT

    def test_exported_class_extracted(self) -> None:
        syms = js("export class Service {}")
        assert "Service" in names(syms)
        assert by_name(syms, "Service").kind == SymbolKind.CLASS

    def test_exported_arrow_extracted(self) -> None:
        syms = js("export const transform = data => data;")
        assert "transform" in names(syms)
        assert by_name(syms, "transform").kind == SymbolKind.FUNCTION


# ===========================================================================
# 21. UnsupportedLanguageError
# ===========================================================================


class TestUnsupportedLanguage:
    def test_python_raises(self) -> None:
        with pytest.raises(UnsupportedLanguageError) as exc_info:
            extract_symbols(path="main.py", language="python", source=b"x = 1")
        assert exc_info.value.language == "python"

    def test_typescript_raises(self) -> None:
        with pytest.raises(UnsupportedLanguageError):
            extract_symbols(path="app.ts", language="typescript", source=b"const x = 1;")

    def test_unknown_raises(self) -> None:
        with pytest.raises(UnsupportedLanguageError):
            extract_symbols(path="foo.rb", language="ruby", source=b"puts 'hi'")

    def test_error_message_contains_language(self) -> None:
        with pytest.raises(UnsupportedLanguageError) as exc_info:
            extract_symbols(path="x", language="cobol", source=b"HELLO.")
        assert "cobol" in str(exc_info.value)


# ===========================================================================
# 22. str source auto-encoding
# ===========================================================================


class TestStrSource:
    def test_str_source_accepted(self) -> None:
        result = js("function foo() {}")
        assert "foo" in names(result)

    def test_str_and_bytes_produce_same_result(self) -> None:
        source_str = "function foo() { return 1; }"
        source_bytes = source_str.encode("utf-8")
        assert js(source_str) == js(source_bytes)


# ===========================================================================
# 23. Immutability
# ===========================================================================


class TestImmutability:
    def test_symbol_is_frozen(self) -> None:
        syms = js("function foo() {}")
        sym = by_name(syms, "foo")
        with pytest.raises((AttributeError, TypeError)):
            sym.name = "hacked"  # type: ignore[misc]

    def test_symbol_kind_frozen(self) -> None:
        syms = js("function foo() {}")
        sym = by_name(syms, "foo")
        with pytest.raises((AttributeError, TypeError)):
            sym.kind = SymbolKind.CLASS  # type: ignore[misc]


# ===========================================================================
# 24. Three-level parent chain
# ===========================================================================


class TestParentChain:
    def test_three_level_chain(self) -> None:
        src = """
function outer() {
    function middle() {
        function inner() {}
    }
}
"""
        syms = js(src)
        assert by_name(syms, "outer").parent is None
        assert by_name(syms, "middle").parent == "outer"
        assert by_name(syms, "inner").parent == "middle"

    def test_class_method_with_nested_const(self) -> None:
        src = """
class Repo {
    find() {
        const query = 'SELECT *';
    }
}
"""
        syms = js(src)
        query = by_name(syms, "query")
        assert query.parent == "find"
        assert query.kind == SymbolKind.CONSTANT


# ===========================================================================
# 25. var declaration → VARIABLE
# ===========================================================================


class TestVarDeclaration:
    def test_var_is_variable_not_constant(self) -> None:
        syms = js("var score = 0;")
        assert by_name(syms, "score").kind == SymbolKind.VARIABLE

    def test_var_function_is_function(self) -> None:
        syms = js("var fn = function() { return 1; };")
        assert by_name(syms, "fn").kind == SymbolKind.FUNCTION


# ===========================================================================
# 26. Arrow as callback — not extracted as a top-level symbol
# ===========================================================================


class TestCallbackArrows:
    def test_map_callback_not_a_symbol(self) -> None:
        src = "const items = [1, 2, 3];\nconst doubled = items.map(x => x * 2);"
        syms = js(src)
        # Only "items" and "doubled" should be extracted (both CONSTANT)
        assert set(names(syms)) == {"items", "doubled"}
        assert all(s.kind == SymbolKind.CONSTANT for s in syms)

    def test_promise_chain_callbacks_not_symbols(self) -> None:
        src = "fetch('/api').then(r => r.json()).catch(e => console.error(e));"
        syms = js(src)
        assert syms == []


# ===========================================================================
# 28. CommonJS exports assignment (exports.fn = ... / module.exports.fn = ...)
# ===========================================================================


class TestCommonJSExportAssignments:
    def test_exports_arrow_function(self) -> None:
        src = "exports.loginUser = async (req, res) => { const user = req.body; res.json(user); };"
        syms = js(src)
        sym = by_name(syms, "loginUser")
        assert sym.kind == SymbolKind.FUNCTION

    def test_exports_function_expression(self) -> None:
        src = "exports.signupUser = function(req, res) { res.send('ok'); };"
        syms = js(src)
        sym = by_name(syms, "signupUser")
        assert sym.kind == SymbolKind.FUNCTION

    def test_module_exports_property_function(self) -> None:
        src = "module.exports.createWorkout = async (req, res) => { return res.status(200).json({}); };"
        syms = js(src)
        sym = by_name(syms, "createWorkout")
        assert sym.kind == SymbolKind.FUNCTION

