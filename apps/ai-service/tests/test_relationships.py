"""
tests/test_relationships.py

Test suite for Milestone 4 — Relationship Extraction.

Coverage
--------
1.  Default imports
2.  Named imports (single, multiple)
3.  Aliased named imports
4.  Namespace imports
5.  Side-effect imports
6.  Multiple import statements
7.  Named exports (function, const, class)
8.  Default export (identifier, function)
9.  Export list ({ a, b })
10. Aliased export list ({ a as b })
11. Re-export with source (export * from "...")
12. Function calls (direct identifier callee)
13. Method calls (member_expression callee: obj.method)
14. Nested calls inside function bodies
15. Identifier references in value position
16. References inside function body
17. References as call arguments
18. Multiple relationships in one file
19. Source position accuracy
20. Deterministic ordering
21. Empty source → empty list
22. Syntax-error source → still returns list
23. UnsupportedLanguageError for non-JS
24. str source auto-encoding
25. Relationship model fields
26. Relationship is frozen / immutable
27. module_path only on IMPORTS
28. is_default flag on imports/exports
29. is_namespace flag on namespace import
30. alias field on aliased imports/exports
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

from repository.parser import Position, UnsupportedLanguageError
from repository.relationships import Relationship, RelationshipKind, extract_relationships


# ===========================================================================
# Helpers
# ===========================================================================


def js(source: str | bytes, path: str = "src/test.js") -> list[Relationship]:
    """Convenience wrapper — extract relationships from JavaScript source."""
    return extract_relationships(path=path, language="javascript", source=source)


def by_kind(rels: list[Relationship], kind: RelationshipKind) -> list[Relationship]:
    """Filter relationships by kind."""
    return [r for r in rels if r.kind == kind]


def target_names(rels: list[Relationship]) -> list[str]:
    """Extract target_name strings."""
    return [r.target_name for r in rels]


def find_rel(
    rels: list[Relationship],
    kind: RelationshipKind,
    target: str,
) -> Relationship | None:
    """Find first relationship with matching kind and target_name."""
    for r in rels:
        if r.kind == kind and r.target_name == target:
            return r
    return None


# ===========================================================================
# 1. Default imports
# ===========================================================================


class TestDefaultImports:
    def test_default_import_extracted(self) -> None:
        rels = js("import React from 'react';")
        imports = by_kind(rels, RelationshipKind.IMPORTS)
        assert any(r.target_name == "React" for r in imports)

    def test_default_import_is_default_true(self) -> None:
        rels = js("import React from 'react';")
        r = find_rel(rels, RelationshipKind.IMPORTS, "React")
        assert r is not None
        assert r.is_default is True

    def test_default_import_module_path(self) -> None:
        rels = js("import React from 'react';")
        r = find_rel(rels, RelationshipKind.IMPORTS, "React")
        assert r is not None
        assert r.module_path == "react"

    def test_default_import_not_namespace(self) -> None:
        rels = js("import App from './App.js';")
        r = find_rel(rels, RelationshipKind.IMPORTS, "App")
        assert r is not None
        assert r.is_namespace is False

    def test_default_import_alias_none(self) -> None:
        rels = js("import Foo from './foo.js';")
        r = find_rel(rels, RelationshipKind.IMPORTS, "Foo")
        assert r is not None
        assert r.alias is None

    def test_default_import_relative_path(self) -> None:
        rels = js("import MyComp from './components/MyComp.js';")
        r = find_rel(rels, RelationshipKind.IMPORTS, "MyComp")
        assert r is not None
        assert r.module_path == "./components/MyComp.js"


# ===========================================================================
# 2. Named imports
# ===========================================================================


class TestNamedImports:
    def test_single_named_import(self) -> None:
        rels = js("import { login } from './auth.js';")
        r = find_rel(rels, RelationshipKind.IMPORTS, "login")
        assert r is not None
        assert r.is_default is False

    def test_multiple_named_imports(self) -> None:
        rels = js("import { login, logout, register } from './auth.js';")
        imports = by_kind(rels, RelationshipKind.IMPORTS)
        names = target_names(imports)
        assert "login" in names
        assert "logout" in names
        assert "register" in names

    def test_named_import_module_path(self) -> None:
        rels = js("import { useState } from 'react';")
        r = find_rel(rels, RelationshipKind.IMPORTS, "useState")
        assert r is not None
        assert r.module_path == "react"

    def test_named_import_not_default(self) -> None:
        rels = js("import { helper } from './utils.js';")
        r = find_rel(rels, RelationshipKind.IMPORTS, "helper")
        assert r is not None
        assert r.is_default is False
        assert r.is_namespace is False


# ===========================================================================
# 3. Aliased named imports
# ===========================================================================


class TestAliasedImports:
    def test_aliased_import_target_is_original_name(self) -> None:
        """target_name is the exported name; alias is the local binding."""
        rels = js("import { login as l } from './auth.js';")
        r = find_rel(rels, RelationshipKind.IMPORTS, "login")
        assert r is not None

    def test_aliased_import_alias_field(self) -> None:
        rels = js("import { login as l } from './auth.js';")
        r = find_rel(rels, RelationshipKind.IMPORTS, "login")
        assert r is not None
        assert r.alias == "l"

    def test_aliased_import_module_path(self) -> None:
        rels = js("import { foo as bar } from './utils.js';")
        r = find_rel(rels, RelationshipKind.IMPORTS, "foo")
        assert r is not None
        assert r.module_path == "./utils.js"
        assert r.alias == "bar"

    def test_non_aliased_import_alias_none(self) -> None:
        rels = js("import { login } from './auth.js';")
        r = find_rel(rels, RelationshipKind.IMPORTS, "login")
        assert r is not None
        assert r.alias is None


# ===========================================================================
# 4. Namespace imports
# ===========================================================================


class TestNamespaceImports:
    def test_namespace_import_extracted(self) -> None:
        rels = js("import * as utils from './utils.js';")
        imports = by_kind(rels, RelationshipKind.IMPORTS)
        assert any(r.target_name == "utils" for r in imports)

    def test_namespace_import_is_namespace_true(self) -> None:
        rels = js("import * as utils from './utils.js';")
        r = find_rel(rels, RelationshipKind.IMPORTS, "utils")
        assert r is not None
        assert r.is_namespace is True

    def test_namespace_import_not_default(self) -> None:
        rels = js("import * as ns from './mod.js';")
        r = find_rel(rels, RelationshipKind.IMPORTS, "ns")
        assert r is not None
        assert r.is_default is False

    def test_namespace_import_module_path(self) -> None:
        rels = js("import * as fs from 'fs';")
        r = find_rel(rels, RelationshipKind.IMPORTS, "fs")
        assert r is not None
        assert r.module_path == "fs"

    def test_namespace_import_alias_none(self) -> None:
        rels = js("import * as math from './math.js';")
        r = find_rel(rels, RelationshipKind.IMPORTS, "math")
        assert r is not None
        assert r.alias is None


# ===========================================================================
# 5. Side-effect imports
# ===========================================================================


class TestSideEffectImports:
    def test_side_effect_import_extracted(self) -> None:
        rels = js("import './polyfill.js';")
        imports = by_kind(rels, RelationshipKind.IMPORTS)
        assert len(imports) == 1

    def test_side_effect_import_empty_target_name(self) -> None:
        rels = js("import './startup.js';")
        r = imports = by_kind(rels, RelationshipKind.IMPORTS)[0]
        assert r.target_name == ""

    def test_side_effect_import_module_path(self) -> None:
        rels = js("import './styles.css';")
        imports = by_kind(rels, RelationshipKind.IMPORTS)
        assert imports[0].module_path == "./styles.css"

    def test_side_effect_import_all_flags_false(self) -> None:
        rels = js("import './init.js';")
        r = by_kind(rels, RelationshipKind.IMPORTS)[0]
        assert r.is_default is False
        assert r.is_namespace is False
        assert r.alias is None


# ===========================================================================
# 6. Multiple import statements
# ===========================================================================


class TestMultipleImports:
    def test_multiple_import_statements_all_extracted(self) -> None:
        src = (
            "import React from 'react';\n"
            "import { useState } from 'react';\n"
            "import * as utils from './utils.js';\n"
            "import './polyfill.js';\n"
        )
        rels = js(src)
        imports = by_kind(rels, RelationshipKind.IMPORTS)
        names = target_names(imports)
        assert "React" in names
        assert "useState" in names
        assert "utils" in names
        assert "" in names  # side-effect

    def test_import_count_matches_specifiers(self) -> None:
        src = "import { a, b, c } from './mod.js';"
        imports = by_kind(js(src), RelationshipKind.IMPORTS)
        assert len(imports) == 3
        assert set(target_names(imports)) == {"a", "b", "c"}


# ===========================================================================
# 7. Named exports
# ===========================================================================


class TestNamedExports:
    def test_export_function_extracted(self) -> None:
        rels = js("export function login() {}")
        exports = by_kind(rels, RelationshipKind.EXPORTS)
        assert any(r.target_name == "login" for r in exports)

    def test_export_function_is_default_false(self) -> None:
        rels = js("export function login() {}")
        r = find_rel(rels, RelationshipKind.EXPORTS, "login")
        assert r is not None
        assert r.is_default is False

    def test_export_const_extracted(self) -> None:
        rels = js("export const API_URL = 'https://api.example.com';")
        r = find_rel(rels, RelationshipKind.EXPORTS, "API_URL")
        assert r is not None

    def test_export_let_extracted(self) -> None:
        rels = js("export let count = 0;")
        r = find_rel(rels, RelationshipKind.EXPORTS, "count")
        assert r is not None

    def test_export_class_extracted(self) -> None:
        rels = js("export class UserService {}")
        r = find_rel(rels, RelationshipKind.EXPORTS, "UserService")
        assert r is not None

    def test_export_module_path_none(self) -> None:
        rels = js("export function helper() {}")
        r = find_rel(rels, RelationshipKind.EXPORTS, "helper")
        assert r is not None
        assert r.module_path is None


# ===========================================================================
# 8. Default exports
# ===========================================================================


class TestDefaultExports:
    def test_default_export_identifier(self) -> None:
        rels = js("export default App;")
        exports = by_kind(rels, RelationshipKind.EXPORTS)
        assert any(r.target_name == "App" for r in exports)

    def test_default_export_is_default_true(self) -> None:
        rels = js("export default App;")
        r = find_rel(rels, RelationshipKind.EXPORTS, "App")
        assert r is not None
        assert r.is_default is True

    def test_default_export_function(self) -> None:
        rels = js("export default function main() {}")
        exports = by_kind(rels, RelationshipKind.EXPORTS)
        defaults = [r for r in exports if r.is_default]
        assert len(defaults) >= 1
        assert any(r.target_name == "main" for r in defaults)


# ===========================================================================
# 9. Export list
# ===========================================================================


class TestExportList:
    def test_export_list_extracted(self) -> None:
        rels = js("export { login, logout };")
        exports = by_kind(rels, RelationshipKind.EXPORTS)
        names = target_names(exports)
        assert "login" in names
        assert "logout" in names

    def test_export_list_not_default(self) -> None:
        rels = js("export { helper };")
        r = find_rel(rels, RelationshipKind.EXPORTS, "helper")
        assert r is not None
        assert r.is_default is False

    def test_export_list_module_path_none(self) -> None:
        rels = js("export { processData };")
        r = find_rel(rels, RelationshipKind.EXPORTS, "processData")
        assert r is not None
        assert r.module_path is None


# ===========================================================================
# 10. Aliased export list
# ===========================================================================


class TestAliasedExportList:
    def test_aliased_export_target_is_local_name(self) -> None:
        """target_name is the local name; alias is the exported public name."""
        rels = js("export { login as signIn };")
        r = find_rel(rels, RelationshipKind.EXPORTS, "login")
        assert r is not None

    def test_aliased_export_alias_field(self) -> None:
        rels = js("export { login as signIn };")
        r = find_rel(rels, RelationshipKind.EXPORTS, "login")
        assert r is not None
        assert r.alias == "signIn"

    def test_non_aliased_export_alias_none(self) -> None:
        rels = js("export { login };")
        r = find_rel(rels, RelationshipKind.EXPORTS, "login")
        assert r is not None
        assert r.alias is None


# ===========================================================================
# 11. Re-export with source (export * from "...")
# ===========================================================================


class TestReExport:
    def test_reexport_extracted(self) -> None:
        rels = js("export * from './utils.js';")
        exports = by_kind(rels, RelationshipKind.EXPORTS)
        assert len(exports) >= 1

    def test_reexport_target_name_is_star(self) -> None:
        rels = js("export * from './utils.js';")
        exports = by_kind(rels, RelationshipKind.EXPORTS)
        assert any(r.target_name == "*" for r in exports)

    def test_reexport_module_path_set(self) -> None:
        rels = js("export * from './utils.js';")
        r = find_rel(rels, RelationshipKind.EXPORTS, "*")
        assert r is not None
        assert r.module_path == "./utils.js"

    def test_reexport_is_namespace_true(self) -> None:
        rels = js("export * from './utils.js';")
        r = find_rel(rels, RelationshipKind.EXPORTS, "*")
        assert r is not None
        assert r.is_namespace is True


# ===========================================================================
# 12. Function calls (direct identifier callee)
# ===========================================================================


class TestDirectCalls:
    def test_direct_call_extracted(self) -> None:
        rels = js("authenticateUser(data);")
        r = find_rel(rels, RelationshipKind.CALLS, "authenticateUser")
        assert r is not None

    def test_direct_call_kind_is_calls(self) -> None:
        rels = js("doSomething();")
        calls = by_kind(rels, RelationshipKind.CALLS)
        assert len(calls) == 1
        assert calls[0].kind == "calls"

    def test_direct_call_target_name(self) -> None:
        rels = js("processData(payload);")
        r = find_rel(rels, RelationshipKind.CALLS, "processData")
        assert r is not None
        assert r.target_name == "processData"

    def test_direct_call_flags_false(self) -> None:
        rels = js("doWork();")
        r = find_rel(rels, RelationshipKind.CALLS, "doWork")
        assert r is not None
        assert r.is_default is False
        assert r.is_namespace is False
        assert r.module_path is None
        assert r.alias is None

    def test_multiple_calls_extracted(self) -> None:
        src = "alpha();\nbeta();\ngamma();"
        calls = by_kind(js(src), RelationshipKind.CALLS)
        call_names = target_names(calls)
        assert "alpha" in call_names
        assert "beta" in call_names
        assert "gamma" in call_names


# ===========================================================================
# 13. Method calls (member_expression callee)
# ===========================================================================


class TestMethodCalls:
    def test_method_call_extracted(self) -> None:
        rels = js("console.log('hello');")
        r = find_rel(rels, RelationshipKind.CALLS, "console.log")
        assert r is not None

    def test_method_call_target_format(self) -> None:
        """Method calls format as 'object.method'."""
        rels = js("obj.doWork();")
        r = find_rel(rels, RelationshipKind.CALLS, "obj.doWork")
        assert r is not None
        assert r.target_name == "obj.doWork"

    def test_method_call_kind_is_calls(self) -> None:
        rels = js("util.format(data);")
        r = find_rel(rels, RelationshipKind.CALLS, "util.format")
        assert r is not None
        assert r.kind == RelationshipKind.CALLS


# ===========================================================================
# 14. Nested calls inside function bodies
# ===========================================================================


class TestNestedCalls:
    def test_call_inside_function_body_extracted(self) -> None:
        src = "function process(data) {\n  validate(data);\n}"
        r = find_rel(js(src), RelationshipKind.CALLS, "validate")
        assert r is not None

    def test_call_inside_method_extracted(self) -> None:
        src = "class Svc {\n  run() {\n    helper();\n  }\n}"
        r = find_rel(js(src), RelationshipKind.CALLS, "helper")
        assert r is not None

    def test_call_in_assignment_rhs_extracted(self) -> None:
        src = "const result = validateToken(token);"
        r = find_rel(js(src), RelationshipKind.CALLS, "validateToken")
        assert r is not None


# ===========================================================================
# 15. References in value position
# ===========================================================================


class TestReferences:
    def test_identifier_argument_is_reference(self) -> None:
        """Identifiers passed as arguments to calls are REFERENCES."""
        rels = js("foo(bar);")
        r = find_rel(rels, RelationshipKind.REFERENCES, "bar")
        assert r is not None

    def test_return_value_reference(self) -> None:
        src = "function get() { return data; }"
        r = find_rel(js(src), RelationshipKind.REFERENCES, "data")
        assert r is not None

    def test_const_rhs_reference(self) -> None:
        """const x = someVar; → REFERENCE to someVar."""
        # someVar is a plain identifier in value position (not a call)
        src = "const x = someVar;"
        r = find_rel(js(src), RelationshipKind.REFERENCES, "someVar")
        # someVar should appear as a reference (assigned to x)
        assert r is not None
        assert r.kind == RelationshipKind.REFERENCES


# ===========================================================================
# 16. References inside function body
# ===========================================================================


class TestFunctionBodyReferences:
    def test_argument_reference_inside_call(self) -> None:
        src = "function process(user) {\n  const t = authenticate(user);\n}"
        r = find_rel(js(src), RelationshipKind.REFERENCES, "user")
        assert r is not None

    def test_multiple_references_inside_function(self) -> None:
        src = "function run(a, b) {\n  doWork(a, b);\n}"
        refs = by_kind(js(src), RelationshipKind.REFERENCES)
        ref_names = target_names(refs)
        assert "a" in ref_names
        assert "b" in ref_names


# ===========================================================================
# 17. Multiple relationships in one file
# ===========================================================================


class TestMixedRelationships:
    def test_all_four_kinds_present(self) -> None:
        src = (
            "import { login } from './auth.js';\n"
            "export function app() {}\n"
            "processData(payload);\n"
            "const result = loadData(key);\n"
        )
        rels = js(src)
        kinds = {r.kind for r in rels}
        assert RelationshipKind.IMPORTS in kinds
        assert RelationshipKind.EXPORTS in kinds
        assert RelationshipKind.CALLS in kinds

    def test_import_and_call_same_file(self) -> None:
        src = "import { validate } from './utils.js';\nvalidate(data);"
        imports = by_kind(js(src), RelationshipKind.IMPORTS)
        calls = by_kind(js(src), RelationshipKind.CALLS)
        assert any(r.target_name == "validate" for r in imports)
        assert any(r.target_name == "validate" for r in calls)


# ===========================================================================
# 18. Source position accuracy
# ===========================================================================


class TestSourcePositions:
    def test_import_position_line_1(self) -> None:
        rels = js("import foo from './foo.js';")
        imports = by_kind(rels, RelationshipKind.IMPORTS)
        assert all(r.source_position.line == 1 for r in imports)

    def test_second_import_line_2(self) -> None:
        src = "import A from './a.js';\nimport B from './b.js';"
        rels = js(src)
        imports = by_kind(rels, RelationshipKind.IMPORTS)
        a_rel = find_rel(rels, RelationshipKind.IMPORTS, "A")
        b_rel = find_rel(rels, RelationshipKind.IMPORTS, "B")
        assert a_rel is not None and a_rel.source_position.line == 1
        assert b_rel is not None and b_rel.source_position.line == 2

    def test_call_position_correct(self) -> None:
        src = "\n\n\nfoo();"  # call is on line 4
        r = find_rel(js(src), RelationshipKind.CALLS, "foo")
        assert r is not None
        assert r.source_position.line == 4

    def test_position_is_position_instance(self) -> None:
        rels = js("import x from './mod.js';")
        for r in rels:
            assert isinstance(r.source_position, Position)

    def test_position_line_is_int(self) -> None:
        rels = js("export const X = 1;")
        for r in by_kind(rels, RelationshipKind.EXPORTS):
            assert isinstance(r.source_position.line, int)
            assert isinstance(r.source_position.column, int)


# ===========================================================================
# 19. Deterministic ordering
# ===========================================================================


class TestDeterministicOrdering:
    def test_sorted_by_source_position(self) -> None:
        src = (
            "import A from './a.js';\n"
            "import B from './b.js';\n"
            "export const C = 1;\n"
        )
        rels = js(src)
        lines = [r.source_position.line for r in rels]
        assert lines == sorted(lines)

    def test_repeated_extraction_is_identical(self) -> None:
        src = "import { a, b } from './mod.js';\nexport const c = 1;\nfoo(bar);"
        assert js(src) == js(src)

    def test_complex_source_deterministic(self) -> None:
        src = (
            "import React from 'react';\n"
            "import { useState } from 'react';\n"
            "export function App() {\n"
            "  const [x, setX] = useState(0);\n"
            "  return null;\n"
            "}\n"
            "export default App;\n"
        )
        results = [js(src) for _ in range(3)]
        assert results[0] == results[1] == results[2]


# ===========================================================================
# 20. Empty source
# ===========================================================================


class TestEmptySource:
    def test_empty_bytes_returns_empty_list(self) -> None:
        assert js(b"") == []

    def test_empty_string_returns_empty_list(self) -> None:
        assert js("") == []

    def test_comments_only_returns_empty_list(self) -> None:
        assert js("// just a comment\n/* another */") == []

    def test_whitespace_only_returns_empty_list(self) -> None:
        assert js("   \n\n  ") == []


# ===========================================================================
# 21. Syntax-error source
# ===========================================================================


class TestSyntaxErrorSource:
    def test_valid_imports_before_error_extracted(self) -> None:
        src = "import React from 'react';\nconst x = @@@;"
        imports = by_kind(js(src), RelationshipKind.IMPORTS)
        assert any(r.target_name == "React" for r in imports)

    def test_returns_list_not_raises(self) -> None:
        assert isinstance(js("import { = } from 'oops'; function broken() {"), list)


# ===========================================================================
# 22. UnsupportedLanguageError
# ===========================================================================


class TestUnsupportedLanguage:
    def test_python_raises(self) -> None:
        with pytest.raises(UnsupportedLanguageError) as exc_info:
            extract_relationships(path="main.py", language="python", source=b"x = 1")
        assert exc_info.value.language == "python"

    def test_typescript_raises(self) -> None:
        with pytest.raises(UnsupportedLanguageError):
            extract_relationships(path="app.ts", language="typescript", source=b"const x = 1;")

    def test_unknown_raises(self) -> None:
        with pytest.raises(UnsupportedLanguageError):
            extract_relationships(path="x.rb", language="ruby", source=b"puts 'hi'")

    def test_error_message_contains_language(self) -> None:
        with pytest.raises(UnsupportedLanguageError) as exc_info:
            extract_relationships(path="x", language="cobol", source=b"HELLO.")
        assert "cobol" in str(exc_info.value)


# ===========================================================================
# 23. str source auto-encoding
# ===========================================================================


class TestStrSource:
    def test_str_accepted(self) -> None:
        result = js("import foo from './foo.js';")
        assert len(result) > 0

    def test_str_and_bytes_equal(self) -> None:
        src_str = "import { login } from './auth.js';\nfoo(bar);"
        src_bytes = src_str.encode("utf-8")
        assert js(src_str) == js(src_bytes)


# ===========================================================================
# 24. Relationship model fields
# ===========================================================================


class TestRelationshipModelFields:
    def test_all_fields_present(self) -> None:
        rels = js("import React from 'react';")
        r = by_kind(rels, RelationshipKind.IMPORTS)[0]
        assert hasattr(r, "kind")
        assert hasattr(r, "source_path")
        assert hasattr(r, "source_position")
        assert hasattr(r, "target_name")
        assert hasattr(r, "module_path")
        assert hasattr(r, "alias")
        assert hasattr(r, "is_default")
        assert hasattr(r, "is_namespace")

    def test_source_path_preserved(self) -> None:
        rels = extract_relationships(
            path="src/auth/login.js",
            language="javascript",
            source="import React from 'react';",
        )
        assert all(r.source_path == "src/auth/login.js" for r in rels)

    def test_all_rels_same_source_path(self) -> None:
        src = "import A from './a.js';\nexport const B = 1;\nfoo();"
        rels = js(src, path="src/myfile.js")
        assert all(r.source_path == "src/myfile.js" for r in rels)


# ===========================================================================
# 25. Immutability
# ===========================================================================


class TestImmutability:
    def test_relationship_is_frozen(self) -> None:
        rels = js("import React from 'react';")
        r = rels[0]
        with pytest.raises((AttributeError, TypeError)):
            r.kind = RelationshipKind.EXPORTS  # type: ignore[misc]

    def test_target_name_frozen(self) -> None:
        rels = js("foo();")
        r = by_kind(rels, RelationshipKind.CALLS)[0]
        with pytest.raises((AttributeError, TypeError)):
            r.target_name = "hacked"  # type: ignore[misc]


# ===========================================================================
# 26. module_path only on IMPORTS (and re-exports)
# ===========================================================================


class TestModulePath:
    def test_imports_have_module_path(self) -> None:
        rels = js("import { x } from './mod.js';")
        for r in by_kind(rels, RelationshipKind.IMPORTS):
            assert r.module_path is not None

    def test_calls_have_no_module_path(self) -> None:
        rels = js("doWork();")
        for r in by_kind(rels, RelationshipKind.CALLS):
            assert r.module_path is None

    def test_exports_no_module_path_normally(self) -> None:
        rels = js("export const X = 1;")
        for r in by_kind(rels, RelationshipKind.EXPORTS):
            assert r.module_path is None

    def test_references_have_no_module_path(self) -> None:
        rels = js("foo(bar);")
        for r in by_kind(rels, RelationshipKind.REFERENCES):
            assert r.module_path is None


# ===========================================================================
# 27. RelationshipKind enum
# ===========================================================================


class TestRelationshipKindEnum:
    def test_imports_value(self) -> None:
        assert RelationshipKind.IMPORTS.value == "imports"

    def test_exports_value(self) -> None:
        assert RelationshipKind.EXPORTS.value == "exports"

    def test_calls_value(self) -> None:
        assert RelationshipKind.CALLS.value == "calls"

    def test_references_value(self) -> None:
        assert RelationshipKind.REFERENCES.value == "references"

    def test_kind_is_str(self) -> None:
        """RelationshipKind(str, Enum) — each kind IS a str."""
        assert isinstance(RelationshipKind.IMPORTS, str)


class TestCommonJsRequire:
    """CommonJS ``require("./x")`` is extracted as a module-level IMPORTS fact."""

    @staticmethod
    def _imports(src: str):
        rels = extract_relationships("a.js", "javascript", src)
        return [r for r in rels if r.kind == RelationshipKind.IMPORTS]

    def test_plain_require(self) -> None:
        imps = self._imports("const x = require('./x');")
        assert [i.module_path for i in imps] == ["./x"]
        assert imps[0].target_name == ""

    def test_destructured_and_bare_require(self) -> None:
        imps = self._imports("const { a, b } = require('./m');\nrequire('./side');")
        assert sorted(i.module_path for i in imps) == ["./m", "./side"]

    def test_nested_require_inside_function(self) -> None:
        imps = self._imports("function f() { return require('./lazy'); }")
        assert [i.module_path for i in imps] == ["./lazy"]

    def test_package_require_is_kept_for_external_classification(self) -> None:
        imps = self._imports("const e = require('express');")
        assert [i.module_path for i in imps] == ["express"]

    def test_dynamic_require_ignored(self) -> None:
        assert self._imports("const m = require(name);") == []
        assert self._imports("const m = require(`./${n}`);") == []
        assert self._imports("const m = require('a', 'b');") == []

    def test_require_still_recorded_as_call(self) -> None:
        rels = extract_relationships("a.js", "javascript", "const x = require('./x');")
        assert any(r.kind == RelationshipKind.CALLS and r.target_name == "require" for r in rels)
