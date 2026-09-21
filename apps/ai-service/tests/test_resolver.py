"""
tests/test_resolver.py

Test suite for Milestone 5 — Cross-File Resolution.

Coverage
--------
1.  Relative path resolution (./file.js)
2.  Parent directory path resolution (../file.js)
3.  JS extension inference (./auth → auth.js)
4.  JSX extension inference
5.  Directory index.js resolution
6.  Directory index.jsx resolution
7.  Named import → symbol resolution
8.  Default import → symbol resolution
9.  Aliased import → correct original symbol
10. Namespace import → RESOLVED_FILE
11. Side-effect import → RESOLVED_FILE
12. Export list resolution
13. Re-export single level
14. Re-export multi-level chain
15. Missing local module → UNRESOLVED
16. External npm package → EXTERNAL
17. Node.js built-in → EXTERNAL
18. Duplicate symbol names in different files
19. Circular dependency (does not crash)
20. Invalid / escape paths → UNRESOLVED
21. Repository boundary protection
22. Deterministic results
23. Unresolved import fields
24. Resolved symbol identity
25. SymbolId uniqueness across files
26. RepositoryIndex queries
27. ResolutionStatus enum
28. ResolvedRelationship is frozen
29. SymbolId is frozen
30. Empty repository
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

from repository.models import FileInfo
from repository.parser import Position
from repository.relationships import Relationship, RelationshipKind
from repository.resolver import (
    RepositoryIndex,
    ResolvedRelationship,
    ResolutionStatus,
    SymbolId,
    resolve_imports,
    _is_external,
    _is_safe_path,
    _resolve_module_path,
)
from repository.symbols import Symbol, SymbolKind


# ===========================================================================
# Test data factories
# ===========================================================================


def _fi(path: str, ext: str = ".js") -> FileInfo:
    """Create a minimal FileInfo for testing."""
    return FileInfo(path=path, language="javascript", extension=ext, size=100)


def _pos(line: int = 1, col: int = 0) -> Position:
    return Position(line=line, column=col)


def _sym(
    name: str,
    path: str,
    kind: SymbolKind = SymbolKind.FUNCTION,
    line: int = 1,
    parent: str | None = None,
) -> Symbol:
    return Symbol(
        name=name,
        kind=kind,
        path=path,
        start=_pos(line),
        end=_pos(line + 2),
        parent=parent,
    )


def _imp(
    source: str,
    target_name: str,
    module_path: str,
    alias: str | None = None,
    is_default: bool = False,
    is_namespace: bool = False,
    line: int = 1,
) -> Relationship:
    return Relationship(
        kind=RelationshipKind.IMPORTS,
        source_path=source,
        source_position=_pos(line),
        target_name=target_name,
        module_path=module_path,
        alias=alias,
        is_default=is_default,
        is_namespace=is_namespace,
    )


def _exp(
    source: str,
    target_name: str,
    module_path: str | None = None,
    alias: str | None = None,
    is_default: bool = False,
    is_namespace: bool = False,
) -> Relationship:
    return Relationship(
        kind=RelationshipKind.EXPORTS,
        source_path=source,
        source_position=_pos(),
        target_name=target_name,
        module_path=module_path,
        alias=alias,
        is_default=is_default,
        is_namespace=is_namespace,
    )


def resolve(
    files: list[FileInfo],
    symbols: list[Symbol],
    rels: list[Relationship],
) -> list[ResolvedRelationship]:
    return resolve_imports(files, symbols, rels)


def first_resolved(results: list[ResolvedRelationship]) -> ResolvedRelationship:
    assert len(results) == 1, f"Expected 1 result, got {len(results)}"
    return results[0]


# ===========================================================================
# 1. Relative path resolution (./file.js)
# ===========================================================================


class TestRelativePathResolution:
    def test_exact_relative_js_path_resolved(self) -> None:
        files = [_fi("src/app.js"), _fi("src/auth.js")]
        symbols = [_sym("login", "src/auth.js")]
        rels = [_imp("src/app.js", "login", "./auth.js"), _exp("src/auth.js", "login")]
        r = first_resolved(resolve(files, symbols, rels))
        assert r.target_path == "src/auth.js"

    def test_relative_path_resolved_status(self) -> None:
        files = [_fi("src/app.js"), _fi("src/auth.js")]
        symbols = [_sym("login", "src/auth.js")]
        rels = [_imp("src/app.js", "login", "./auth.js"), _exp("src/auth.js", "login")]
        r = first_resolved(resolve(files, symbols, rels))
        assert r.status == ResolutionStatus.RESOLVED

    def test_nested_relative_path(self) -> None:
        files = [_fi("src/app.js"), _fi("src/utils/helper.js")]
        symbols = [_sym("helper", "src/utils/helper.js")]
        rels = [
            _imp("src/app.js", "helper", "./utils/helper.js"),
            _exp("src/utils/helper.js", "helper"),
        ]
        r = first_resolved(resolve(files, symbols, rels))
        assert r.target_path == "src/utils/helper.js"
        assert r.status == ResolutionStatus.RESOLVED


# ===========================================================================
# 2. Parent directory path resolution (../file.js)
# ===========================================================================


class TestParentDirectoryResolution:
    def test_parent_relative_path_resolved(self) -> None:
        files = [_fi("src/views/page.js"), _fi("src/auth.js")]
        symbols = [_sym("login", "src/auth.js")]
        rels = [
            _imp("src/views/page.js", "login", "../auth.js"),
            _exp("src/auth.js", "login"),
        ]
        r = first_resolved(resolve(files, symbols, rels))
        assert r.target_path == "src/auth.js"

    def test_multiple_parent_hops(self) -> None:
        files = [_fi("a/b/c/app.js"), _fi("a/util.js")]
        symbols = [_sym("util", "a/util.js")]
        rels = [
            _imp("a/b/c/app.js", "util", "../../util.js"),
            _exp("a/util.js", "util"),
        ]
        r = first_resolved(resolve(files, symbols, rels))
        assert r.target_path == "a/util.js"


# ===========================================================================
# 3. JS extension inference
# ===========================================================================


class TestJsExtensionInference:
    def test_bare_name_resolves_to_js(self) -> None:
        files = [_fi("src/app.js"), _fi("src/auth.js")]
        symbols = [_sym("login", "src/auth.js")]
        rels = [
            _imp("src/app.js", "login", "./auth"),  # no .js
            _exp("src/auth.js", "login"),
        ]
        r = first_resolved(resolve(files, symbols, rels))
        assert r.target_path == "src/auth.js"
        assert r.status == ResolutionStatus.RESOLVED

    def test_extension_inference_target_path(self) -> None:
        files = [_fi("src/app.js"), _fi("src/helper.js")]
        rels = [_imp("src/app.js", "", "./helper")]
        r = first_resolved(resolve(files, [], rels))
        assert r.target_path == "src/helper.js"


# ===========================================================================
# 4. JSX extension inference
# ===========================================================================


class TestJsxExtensionInference:
    def test_bare_name_resolves_to_jsx(self) -> None:
        files = [_fi("src/app.js"), _fi("src/Button.jsx", ".jsx")]
        symbols = [_sym("Button", "src/Button.jsx", SymbolKind.CLASS)]
        rels = [
            _imp("src/app.js", "Button", "./Button", is_default=True),
            _exp("src/Button.jsx", "Button", is_default=True),
        ]
        r = first_resolved(resolve(files, symbols, rels))
        assert r.target_path == "src/Button.jsx"


# ===========================================================================
# 5. Directory index.js resolution
# ===========================================================================


class TestIndexJsResolution:
    def test_directory_resolves_to_index_js(self) -> None:
        files = [_fi("src/app.js"), _fi("src/services/index.js")]
        symbols = [_sym("process", "src/services/index.js")]
        rels = [
            _imp("src/app.js", "process", "./services"),
            _exp("src/services/index.js", "process"),
        ]
        r = first_resolved(resolve(files, symbols, rels))
        assert r.target_path == "src/services/index.js"
        assert r.status == ResolutionStatus.RESOLVED

    def test_directory_index_symbol_resolved(self) -> None:
        files = [_fi("src/app.js"), _fi("src/db/index.js")]
        symbols = [_sym("connect", "src/db/index.js")]
        rels = [
            _imp("src/app.js", "connect", "./db"),
            _exp("src/db/index.js", "connect"),
        ]
        r = first_resolved(resolve(files, symbols, rels))
        assert r.target_symbol_id is not None
        assert r.target_symbol_id.name == "connect"


# ===========================================================================
# 6. Directory index.jsx resolution
# ===========================================================================


class TestIndexJsxResolution:
    def test_directory_resolves_to_index_jsx(self) -> None:
        files = [_fi("src/app.js"), _fi("src/components/index.jsx", ".jsx")]
        symbols = [_sym("Button", "src/components/index.jsx")]
        rels = [
            _imp("src/app.js", "Button", "./components"),
            _exp("src/components/index.jsx", "Button"),
        ]
        r = first_resolved(resolve(files, symbols, rels))
        assert r.target_path == "src/components/index.jsx"


# ===========================================================================
# 7. Named import → symbol resolution
# ===========================================================================


class TestNamedImportResolution:
    def test_named_import_resolved_to_symbol(self) -> None:
        files = [_fi("src/app.js"), _fi("src/auth.js")]
        symbols = [_sym("login", "src/auth.js")]
        rels = [_imp("src/app.js", "login", "./auth.js"), _exp("src/auth.js", "login")]
        r = first_resolved(resolve(files, symbols, rels))
        assert r.status == ResolutionStatus.RESOLVED
        assert r.target_symbol_id is not None
        assert r.target_symbol_id.name == "login"
        assert r.target_symbol_id.path == "src/auth.js"

    def test_named_import_missing_symbol_resolved_file(self) -> None:
        """File found but symbol not declared — RESOLVED_FILE."""
        files = [_fi("src/app.js"), _fi("src/auth.js")]
        rels = [_imp("src/app.js", "login", "./auth.js")]  # no symbol in auth.js
        r = first_resolved(resolve(files, [], rels))
        assert r.status == ResolutionStatus.RESOLVED_FILE
        assert r.target_path == "src/auth.js"
        assert r.target_symbol_id is None

    def test_multiple_named_imports_all_resolved(self) -> None:
        files = [_fi("src/app.js"), _fi("src/auth.js")]
        symbols = [_sym("login", "src/auth.js", line=1), _sym("logout", "src/auth.js", line=5)]
        rels = [
            _imp("src/app.js", "login", "./auth.js"),
            _imp("src/app.js", "logout", "./auth.js"),
            _exp("src/auth.js", "login"),
            _exp("src/auth.js", "logout"),
        ]
        results = resolve(files, symbols, rels)
        assert len(results) == 2
        assert all(r.status == ResolutionStatus.RESOLVED for r in results)
        names = {r.target_symbol_id.name for r in results if r.target_symbol_id}
        assert names == {"login", "logout"}

    def test_named_import_prefers_top_level_symbol(self) -> None:
        """When same name exists at multiple scopes, prefer parent=None."""
        files = [_fi("src/app.js"), _fi("src/auth.js")]
        nested_sym = Symbol(
            name="login",
            kind=SymbolKind.FUNCTION,
            path="src/auth.js",
            start=_pos(10),
            end=_pos(12),
            parent="outer",  # NOT top-level
        )
        top_sym = _sym("login", "src/auth.js", line=3)  # top-level (parent=None)
        rels = [_imp("src/app.js", "login", "./auth.js"), _exp("src/auth.js", "login")]
        r = first_resolved(resolve(files, [nested_sym, top_sym], rels))
        assert r.target_symbol_id is not None
        assert r.target_symbol_id.line == 3  # top-level symbol


# ===========================================================================
# 8. Default import → symbol resolution
# ===========================================================================


class TestDefaultImportResolution:
    def test_default_function_export_resolved(self) -> None:
        files = [_fi("src/app.js"), _fi("src/auth.js")]
        symbols = [_sym("login", "src/auth.js")]
        rels = [
            _imp("src/app.js", "login", "./auth.js", is_default=True),
            _exp("src/auth.js", "login", is_default=True),
        ]
        r = first_resolved(resolve(files, symbols, rels))
        assert r.status == ResolutionStatus.RESOLVED
        assert r.target_symbol_id.name == "login"

    def test_default_class_export_resolved(self) -> None:
        files = [_fi("src/app.js"), _fi("src/UserService.js")]
        symbols = [_sym("UserService", "src/UserService.js", SymbolKind.CLASS, line=2)]
        rels = [
            _imp("src/app.js", "UserService", "./UserService.js", is_default=True),
            _exp("src/UserService.js", "UserService", is_default=True),
        ]
        r = first_resolved(resolve(files, symbols, rels))
        assert r.status == ResolutionStatus.RESOLVED
        assert r.target_symbol_id.name == "UserService"

    def test_default_import_no_default_export_resolved_file(self) -> None:
        """File has no default export declaration → RESOLVED_FILE."""
        files = [_fi("src/app.js"), _fi("src/auth.js")]
        # auth.js has a symbol but no is_default=True export relationship
        symbols = [_sym("login", "src/auth.js")]
        rels = [_imp("src/app.js", "App", "./auth.js", is_default=True)]
        r = first_resolved(resolve(files, symbols, rels))
        assert r.status == ResolutionStatus.RESOLVED_FILE
        assert r.target_path == "src/auth.js"
        assert r.target_symbol_id is None

    def test_default_import_file_correct(self) -> None:
        files = [_fi("src/app.js"), _fi("src/index.js")]
        symbols = [_sym("App", "src/index.js", SymbolKind.CLASS)]
        rels = [
            _imp("src/app.js", "App", "./index.js", is_default=True),
            _exp("src/index.js", "App", is_default=True),
        ]
        r = first_resolved(resolve(files, symbols, rels))
        assert r.target_path == "src/index.js"


# ===========================================================================
# 9. Aliased import → correct original symbol
# ===========================================================================


class TestAliasedImportResolution:
    def test_aliased_import_resolves_by_original_name(self) -> None:
        """import { login as authenticate } → resolves to 'login', not 'authenticate'."""
        files = [_fi("src/app.js"), _fi("src/auth.js")]
        symbols = [_sym("login", "src/auth.js")]
        rels = [
            _imp("src/app.js", "login", "./auth.js", alias="authenticate"),
            _exp("src/auth.js", "login"),
        ]
        r = first_resolved(resolve(files, symbols, rels))
        assert r.status == ResolutionStatus.RESOLVED
        assert r.target_symbol_id.name == "login"

    def test_aliased_import_does_not_search_alias_name(self) -> None:
        """The resolver must NOT look for the alias 'authenticate' in auth.js."""
        files = [_fi("src/app.js"), _fi("src/auth.js")]
        # Only 'authenticate' exists in auth.js, but the import asks for 'login'
        symbols = [_sym("authenticate", "src/auth.js")]
        rels = [
            _imp("src/app.js", "login", "./auth.js", alias="authenticate"),
            _exp("src/auth.js", "authenticate"),
        ]
        r = first_resolved(resolve(files, symbols, rels))
        # Should be RESOLVED_FILE: target is "login" but only "authenticate" exists
        assert r.status == ResolutionStatus.RESOLVED_FILE

    def test_aliased_import_notes_mention_alias(self) -> None:
        files = [_fi("src/app.js"), _fi("src/auth.js")]
        symbols = [_sym("login", "src/auth.js")]
        rels = [
            _imp("src/app.js", "login", "./auth.js", alias="l"),
            _exp("src/auth.js", "login"),
        ]
        r = first_resolved(resolve(files, symbols, rels))
        assert r.notes is not None
        assert "l" in r.notes


# ===========================================================================
# 10. Namespace import → RESOLVED_FILE
# ===========================================================================


class TestNamespaceImportResolution:
    def test_namespace_import_status_resolved_file(self) -> None:
        files = [_fi("src/app.js"), _fi("src/utils.js")]
        symbols = [_sym("helper", "src/utils.js")]
        rels = [_imp("src/app.js", "utils", "./utils.js", is_namespace=True)]
        r = first_resolved(resolve(files, symbols, rels))
        assert r.status == ResolutionStatus.RESOLVED_FILE

    def test_namespace_import_target_path_set(self) -> None:
        files = [_fi("src/app.js"), _fi("src/utils.js")]
        rels = [_imp("src/app.js", "utils", "./utils.js", is_namespace=True)]
        r = first_resolved(resolve(files, [], rels))
        assert r.target_path == "src/utils.js"

    def test_namespace_import_no_symbol_id(self) -> None:
        files = [_fi("src/app.js"), _fi("src/utils.js")]
        rels = [_imp("src/app.js", "ns", "./utils.js", is_namespace=True)]
        r = first_resolved(resolve(files, [], rels))
        assert r.target_symbol_id is None


# ===========================================================================
# 11. Side-effect import → RESOLVED_FILE
# ===========================================================================


class TestSideEffectImportResolution:
    def test_side_effect_resolved_file_status(self) -> None:
        files = [_fi("src/app.js"), _fi("src/polyfill.js")]
        rels = [_imp("src/app.js", "", "./polyfill.js")]
        r = first_resolved(resolve(files, [], rels))
        assert r.status == ResolutionStatus.RESOLVED_FILE

    def test_side_effect_target_path_set(self) -> None:
        files = [_fi("src/app.js"), _fi("src/polyfill.js")]
        rels = [_imp("src/app.js", "", "./polyfill.js")]
        r = first_resolved(resolve(files, [], rels))
        assert r.target_path == "src/polyfill.js"

    def test_side_effect_no_symbol_id(self) -> None:
        files = [_fi("src/app.js"), _fi("src/init.js")]
        rels = [_imp("src/app.js", "", "./init.js")]
        r = first_resolved(resolve(files, [], rels))
        assert r.target_symbol_id is None


# ===========================================================================
# 12. Export list resolution
# ===========================================================================


class TestExportListResolution:
    def test_export_list_symbol_resolved(self) -> None:
        """export { login } in auth.js → import { login } in app.js resolves."""
        files = [_fi("src/app.js"), _fi("src/auth.js")]
        symbols = [_sym("login", "src/auth.js")]
        rels = [
            _imp("src/app.js", "login", "./auth.js"),
            _exp("src/auth.js", "login"),  # export list item
        ]
        r = first_resolved(resolve(files, symbols, rels))
        assert r.status == ResolutionStatus.RESOLVED
        assert r.target_symbol_id.name == "login"

    def test_aliased_export_list_resolves_local_name(self) -> None:
        """export { login as signIn } → import { login } resolves to login symbol."""
        files = [_fi("src/app.js"), _fi("src/auth.js")]
        symbols = [_sym("login", "src/auth.js")]
        rels = [
            _imp("src/app.js", "login", "./auth.js"),
            _exp("src/auth.js", "login", alias="signIn"),
        ]
        r = first_resolved(resolve(files, symbols, rels))
        assert r.status == ResolutionStatus.RESOLVED


# ===========================================================================
# 13. Re-export — single level
# ===========================================================================


class TestSingleLevelReexport:
    def test_reexport_chain_resolved(self) -> None:
        """
        index.js re-exports from auth.js.
        app.js imports from index.js → should find login in auth.js.
        """
        files = [_fi("src/app.js"), _fi("src/index.js"), _fi("src/auth.js")]
        symbols = [_sym("login", "src/auth.js")]
        rels = [
            _imp("src/app.js", "login", "./index.js"),
            # index.js: export { login } from "./auth.js"
            _exp("src/index.js", "login"),         # named export (EXPORTS from M4)
            _exp("src/index.js", "*", module_path="./auth.js", is_namespace=True),  # re-export marker
            _exp("src/auth.js", "login"),
        ]
        r = first_resolved(resolve(files, symbols, rels))
        assert r.status == ResolutionStatus.RESOLVED
        assert r.target_symbol_id.path == "src/auth.js"
        assert r.target_symbol_id.name == "login"

    def test_reexport_target_file_correct(self) -> None:
        files = [_fi("src/app.js"), _fi("src/index.js"), _fi("src/auth.js")]
        symbols = [_sym("logout", "src/auth.js")]
        rels = [
            _imp("src/app.js", "logout", "./index.js"),
            _exp("src/index.js", "logout"),
            _exp("src/index.js", "*", module_path="./auth.js", is_namespace=True),
            _exp("src/auth.js", "logout"),
        ]
        r = first_resolved(resolve(files, symbols, rels))
        assert r.target_path == "src/index.js"  # direct target is index.js


# ===========================================================================
# 14. Re-export — multi-level chain
# ===========================================================================


class TestMultiLevelReexport:
    def test_two_hop_reexport(self) -> None:
        """app.js → index.js → lib.js → auth.js::login"""
        files = [
            _fi("src/app.js"),
            _fi("src/index.js"),
            _fi("src/lib.js"),
            _fi("src/auth.js"),
        ]
        symbols = [_sym("login", "src/auth.js")]
        rels = [
            _imp("src/app.js", "login", "./index.js"),
            _exp("src/index.js", "login"),
            _exp("src/index.js", "*", module_path="./lib.js", is_namespace=True),
            _exp("src/lib.js", "login"),
            _exp("src/lib.js", "*", module_path="./auth.js", is_namespace=True),
            _exp("src/auth.js", "login"),
        ]
        r = first_resolved(resolve(files, symbols, rels))
        assert r.status == ResolutionStatus.RESOLVED
        assert r.target_symbol_id.path == "src/auth.js"


# ===========================================================================
# 15. Missing local module → UNRESOLVED
# ===========================================================================


class TestMissingLocalModule:
    def test_missing_file_unresolved(self) -> None:
        files = [_fi("src/app.js")]  # auth.js NOT in index
        rels = [_imp("src/app.js", "login", "./auth.js")]
        r = first_resolved(resolve(files, [], rels))
        assert r.status == ResolutionStatus.UNRESOLVED

    def test_unresolved_no_target_path(self) -> None:
        files = [_fi("src/app.js")]
        rels = [_imp("src/app.js", "fn", "./missing.js")]
        r = first_resolved(resolve(files, [], rels))
        assert r.target_path is None
        assert r.target_symbol_id is None

    def test_unresolved_notes_include_module(self) -> None:
        files = [_fi("src/app.js")]
        rels = [_imp("src/app.js", "fn", "./ghost.js")]
        r = first_resolved(resolve(files, [], rels))
        assert r.notes is not None
        assert "ghost.js" in r.notes


# ===========================================================================
# 16. External npm package → EXTERNAL
# ===========================================================================


class TestExternalNpmPackage:
    def test_react_is_external(self) -> None:
        rels = [_imp("src/app.js", "React", "react", is_default=True)]
        r = first_resolved(resolve([], [], rels))
        assert r.status == ResolutionStatus.EXTERNAL

    def test_express_is_external(self) -> None:
        rels = [_imp("src/app.js", "express", "express", is_default=True)]
        r = first_resolved(resolve([], [], rels))
        assert r.status == ResolutionStatus.EXTERNAL

    def test_lodash_is_external(self) -> None:
        rels = [_imp("src/app.js", "_", "lodash", is_default=True)]
        r = first_resolved(resolve([], [], rels))
        assert r.status == ResolutionStatus.EXTERNAL

    def test_external_no_target_path(self) -> None:
        rels = [_imp("src/app.js", "axios", "axios", is_default=True)]
        r = first_resolved(resolve([], [], rels))
        assert r.target_path is None
        assert r.target_symbol_id is None

    def test_external_notes_present(self) -> None:
        rels = [_imp("src/app.js", "React", "react", is_default=True)]
        r = first_resolved(resolve([], [], rels))
        assert r.notes is not None
        assert "react" in r.notes


# ===========================================================================
# 17. Node.js built-in → EXTERNAL
# ===========================================================================


class TestNodeBuiltins:
    def test_fs_is_external(self) -> None:
        rels = [_imp("src/app.js", "fs", "fs", is_default=True)]
        r = first_resolved(resolve([], [], rels))
        assert r.status == ResolutionStatus.EXTERNAL

    def test_path_builtin_is_external(self) -> None:
        rels = [_imp("src/app.js", "path", "path", is_default=True)]
        r = first_resolved(resolve([], [], rels))
        assert r.status == ResolutionStatus.EXTERNAL

    def test_node_protocol_is_external(self) -> None:
        """node:fs style imports."""
        rels = [_imp("src/app.js", "fs", "node:fs")]
        r = first_resolved(resolve([], [], rels))
        assert r.status == ResolutionStatus.EXTERNAL


# ===========================================================================
# 18. Duplicate symbol names in different files
# ===========================================================================


class TestDuplicateSymbolNames:
    def test_same_name_different_files_resolved_independently(self) -> None:
        files = [_fi("src/app.js"), _fi("src/auth.js"), _fi("src/admin.js")]
        symbols = [
            _sym("login", "src/auth.js", line=3),
            _sym("login", "src/admin.js", line=7),
        ]
        rels = [
            _imp("src/app.js", "login", "./auth.js"),
            _imp("src/app.js", "login", "./admin.js"),
            _exp("src/auth.js", "login"),
            _exp("src/admin.js", "login"),
        ]
        results = resolve(files, symbols, rels)
        assert len(results) == 2
        assert all(r.status == ResolutionStatus.RESOLVED for r in results)
        symbol_ids = {r.target_symbol_id for r in results}
        # Both resolved but to DIFFERENT SymbolIds
        assert len(symbol_ids) == 2

    def test_symbol_id_includes_path_for_disambiguation(self) -> None:
        """Two login() symbols must have different SymbolIds because paths differ."""
        files = [_fi("src/app.js"), _fi("src/auth.js"), _fi("src/admin.js")]
        symbols = [
            _sym("login", "src/auth.js", line=3),
            _sym("login", "src/admin.js", line=3),  # same line, different file
        ]
        rels = [
            _imp("src/app.js", "login", "./auth.js"),
            _imp("src/app.js", "login", "./admin.js"),
            _exp("src/auth.js", "login"),
            _exp("src/admin.js", "login"),
        ]
        results = resolve(files, symbols, rels)
        id_paths = {r.target_symbol_id.path for r in results if r.target_symbol_id}
        assert "src/auth.js" in id_paths
        assert "src/admin.js" in id_paths

    def test_resolution_uses_file_context_not_just_name(self) -> None:
        """Importing from auth.js should only resolve to auth.js::login."""
        files = [_fi("src/app.js"), _fi("src/auth.js"), _fi("src/admin.js")]
        auth_login = _sym("login", "src/auth.js", line=1)
        admin_login = _sym("login", "src/admin.js", line=1)
        rels = [
            _imp("src/app.js", "login", "./auth.js"),
            _exp("src/auth.js", "login"),
            _exp("src/admin.js", "login"),
        ]
        results = resolve(files, [auth_login, admin_login], rels)
        assert len(results) == 1
        assert results[0].target_symbol_id.path == "src/auth.js"


# ===========================================================================
# 19. Circular dependencies
# ===========================================================================


class TestCircularDependencies:
    def test_circular_does_not_crash(self) -> None:
        """a.js imports from b.js; b.js imports from a.js — should not crash."""
        files = [_fi("src/a.js"), _fi("src/b.js")]
        symbols = []
        rels = [
            _imp("src/a.js", "x", "./b.js"),
            _imp("src/b.js", "y", "./a.js"),
        ]
        result = resolve(files, symbols, rels)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_circular_reexport_terminates(self) -> None:
        """Circular re-export chain must terminate without infinite recursion."""
        files = [_fi("src/a.js"), _fi("src/b.js"), _fi("src/app.js")]
        rels = [
            _imp("src/app.js", "login", "./a.js"),
            _exp("src/a.js", "login"),
            _exp("src/a.js", "*", module_path="./b.js", is_namespace=True),
            _exp("src/b.js", "login"),
            _exp("src/b.js", "*", module_path="./a.js", is_namespace=True),  # cycle!
        ]
        result = resolve(files, [], rels)
        assert isinstance(result, list)  # did not crash

    def test_circular_result_has_status(self) -> None:
        """Even a circular case must produce a valid ResolutionStatus."""
        files = [_fi("src/a.js"), _fi("src/b.js")]
        rels = [_imp("src/a.js", "x", "./b.js"), _imp("src/b.js", "y", "./a.js")]
        results = resolve(files, [], rels)
        for r in results:
            assert isinstance(r.status, ResolutionStatus)


# ===========================================================================
# 20. Invalid / escape paths → UNRESOLVED
# ===========================================================================


class TestInvalidPaths:
    def test_repo_escape_path_unresolved(self) -> None:
        """../../etc/passwd should be rejected as UNRESOLVED."""
        files = [_fi("src/app.js")]
        rels = [_imp("src/app.js", "x", "../../etc/passwd")]
        r = first_resolved(resolve(files, [], rels))
        assert r.status == ResolutionStatus.UNRESOLVED

    def test_triple_dot_dot_escape_unresolved(self) -> None:
        files = [_fi("src/app.js")]
        rels = [_imp("src/app.js", "x", "../../../outside")]
        r = first_resolved(resolve(files, [], rels))
        assert r.status == ResolutionStatus.UNRESOLVED

    def test_escape_path_no_target(self) -> None:
        files = [_fi("src/app.js")]
        rels = [_imp("src/app.js", "x", "../../escape")]
        r = first_resolved(resolve(files, [], rels))
        assert r.target_path is None


# ===========================================================================
# 21. Repository boundary protection
# ===========================================================================


class TestRepositoryBoundary:
    def test_is_safe_path_rejects_escape(self) -> None:
        assert _is_safe_path("../outside") is False
        assert _is_safe_path("../../etc") is False

    def test_is_safe_path_allows_normal(self) -> None:
        assert _is_safe_path("src/auth.js") is True
        assert _is_safe_path("lib/util.js") is True
        assert _is_safe_path("index.js") is True

    def test_resolve_module_path_rejects_escape(self) -> None:
        files = {"src/app.js": _fi("src/app.js")}
        result = _resolve_module_path("src/app.js", "../../../escape", files)
        assert result is None


# ===========================================================================
# 22. Deterministic results
# ===========================================================================


class TestDeterministicResults:
    def test_same_input_same_output(self) -> None:
        files = [_fi("src/app.js"), _fi("src/auth.js")]
        symbols = [_sym("login", "src/auth.js")]
        rels = [
            _imp("src/app.js", "login", "./auth.js"),
            _imp("src/app.js", "logout", "./auth.js"),
        ]
        first = resolve(files, symbols, rels)
        second = resolve(files, symbols, rels)
        assert first == second

    def test_sorted_by_source_path(self) -> None:
        files = [_fi("src/app.js"), _fi("src/auth.js"), _fi("src/b.js")]
        symbols = [_sym("x", "src/auth.js"), _sym("y", "src/auth.js")]
        rels = [
            _imp("src/b.js", "y", "./auth.js", line=2),
            _imp("src/app.js", "x", "./auth.js", line=1),
        ]
        results = resolve(files, symbols, rels)
        paths = [r.source_relationship.source_path for r in results]
        assert paths == sorted(paths)


# ===========================================================================
# 23. Unresolved import fields
# ===========================================================================


class TestUnresolvedFields:
    def test_unresolved_fields(self) -> None:
        files = [_fi("src/app.js")]
        rels = [_imp("src/app.js", "fn", "./missing.js")]
        r = first_resolved(resolve(files, [], rels))
        assert r.status == ResolutionStatus.UNRESOLVED
        assert r.target_path is None
        assert r.target_symbol_id is None
        assert r.source_relationship is not None

    def test_external_fields(self) -> None:
        rels = [_imp("src/app.js", "React", "react", is_default=True)]
        r = first_resolved(resolve([], [], rels))
        assert r.status == ResolutionStatus.EXTERNAL
        assert r.target_path is None
        assert r.target_symbol_id is None


# ===========================================================================
# 24. Resolved symbol identity
# ===========================================================================


class TestResolvedSymbolIdentity:
    def test_symbol_id_path_matches_file(self) -> None:
        files = [_fi("src/app.js"), _fi("src/auth.js")]
        symbols = [_sym("login", "src/auth.js")]
        rels = [_imp("src/app.js", "login", "./auth.js"), _exp("src/auth.js", "login")]
        r = first_resolved(resolve(files, symbols, rels))
        assert r.target_symbol_id.path == "src/auth.js"

    def test_symbol_id_name_matches_symbol(self) -> None:
        files = [_fi("src/app.js"), _fi("src/auth.js")]
        symbols = [_sym("doLogin", "src/auth.js")]
        rels = [_imp("src/app.js", "doLogin", "./auth.js"), _exp("src/auth.js", "doLogin")]
        r = first_resolved(resolve(files, symbols, rels))
        assert r.target_symbol_id.name == "doLogin"

    def test_symbol_id_position_matches_source(self) -> None:
        files = [_fi("src/app.js"), _fi("src/auth.js")]
        symbols = [_sym("login", "src/auth.js", line=5)]
        rels = [_imp("src/app.js", "login", "./auth.js"), _exp("src/auth.js", "login")]
        r = first_resolved(resolve(files, symbols, rels))
        assert r.target_symbol_id.line == 5


# ===========================================================================
# 25. SymbolId uniqueness across files
# ===========================================================================


class TestSymbolIdUniqueness:
    def test_different_file_same_name_different_id(self) -> None:
        id1 = SymbolId(path="src/auth.js", name="login", line=1, column=0)
        id2 = SymbolId(path="src/admin.js", name="login", line=1, column=0)
        assert id1 != id2

    def test_same_file_same_name_same_position_same_id(self) -> None:
        id1 = SymbolId(path="src/auth.js", name="login", line=3, column=0)
        id2 = SymbolId(path="src/auth.js", name="login", line=3, column=0)
        assert id1 == id2

    def test_same_file_same_name_different_line_different_id(self) -> None:
        id1 = SymbolId(path="src/auth.js", name="login", line=1, column=0)
        id2 = SymbolId(path="src/auth.js", name="login", line=5, column=0)
        assert id1 != id2


# ===========================================================================
# 26. RepositoryIndex queries
# ===========================================================================


class TestRepositoryIndex:
    def _make_index(self) -> RepositoryIndex:
        files = [_fi("src/auth.js"), _fi("src/app.js")]
        symbols = [_sym("login", "src/auth.js"), _sym("logout", "src/auth.js")]
        rels = [
            _exp("src/auth.js", "login"),
            _imp("src/app.js", "login", "./auth.js"),
        ]
        return RepositoryIndex(files, symbols, rels)

    def test_has_file_true(self) -> None:
        idx = self._make_index()
        assert idx.has_file("src/auth.js") is True

    def test_has_file_false(self) -> None:
        idx = self._make_index()
        assert idx.has_file("src/missing.js") is False

    def test_get_symbols_for_file(self) -> None:
        idx = self._make_index()
        syms = idx.get_symbols_for_file("src/auth.js")
        assert len(syms) == 2

    def test_get_symbols_by_name(self) -> None:
        idx = self._make_index()
        syms = idx.get_symbols_by_name("src/auth.js", "login")
        assert len(syms) == 1
        assert syms[0].name == "login"

    def test_get_symbols_by_name_not_found(self) -> None:
        idx = self._make_index()
        assert idx.get_symbols_by_name("src/auth.js", "nonexistent") == []

    def test_get_exports(self) -> None:
        idx = self._make_index()
        exports = idx.get_exports("src/auth.js")
        assert len(exports) == 1


# ===========================================================================
# 27. ResolutionStatus enum
# ===========================================================================


class TestResolutionStatusEnum:
    def test_resolved_value(self) -> None:
        assert ResolutionStatus.RESOLVED.value == "resolved"

    def test_resolved_file_value(self) -> None:
        assert ResolutionStatus.RESOLVED_FILE.value == "resolved_file"

    def test_external_value(self) -> None:
        assert ResolutionStatus.EXTERNAL.value == "external"

    def test_unresolved_value(self) -> None:
        assert ResolutionStatus.UNRESOLVED.value == "unresolved"

    def test_status_is_str(self) -> None:
        assert isinstance(ResolutionStatus.RESOLVED, str)


# ===========================================================================
# 28. ResolvedRelationship is frozen
# ===========================================================================


class TestResolvedRelationshipImmutability:
    def test_frozen_dataclass(self) -> None:
        files = [_fi("src/app.js"), _fi("src/auth.js")]
        symbols = [_sym("login", "src/auth.js")]
        rels = [_imp("src/app.js", "login", "./auth.js"), _exp("src/auth.js", "login")]
        r = first_resolved(resolve(files, symbols, rels))
        with pytest.raises((AttributeError, TypeError)):
            r.status = ResolutionStatus.UNRESOLVED  # type: ignore[misc]

    def test_all_fields_present(self) -> None:
        rels = [_imp("src/app.js", "React", "react", is_default=True)]
        r = first_resolved(resolve([], [], rels))
        assert hasattr(r, "source_relationship")
        assert hasattr(r, "status")
        assert hasattr(r, "target_path")
        assert hasattr(r, "target_symbol_id")
        assert hasattr(r, "notes")


# ===========================================================================
# 29. SymbolId is frozen
# ===========================================================================


class TestSymbolIdImmutability:
    def test_symbol_id_frozen(self) -> None:
        sid = SymbolId(path="src/auth.js", name="login", line=1, column=0)
        with pytest.raises((AttributeError, TypeError)):
            sid.name = "hacked"  # type: ignore[misc]

    def test_symbol_id_hashable(self) -> None:
        sid = SymbolId(path="src/auth.js", name="login", line=1, column=0)
        s = {sid}
        assert sid in s


# ===========================================================================
# 30. Empty repository
# ===========================================================================


class TestEmptyRepository:
    def test_no_files_external_imports(self) -> None:
        rels = [_imp("src/app.js", "React", "react", is_default=True)]
        results = resolve([], [], rels)
        assert len(results) == 1
        assert results[0].status == ResolutionStatus.EXTERNAL

    def test_no_files_local_imports_unresolved(self) -> None:
        rels = [_imp("src/app.js", "login", "./auth.js")]
        results = resolve([], [], rels)
        assert len(results) == 1
        assert results[0].status == ResolutionStatus.UNRESOLVED

    def test_no_relationships_empty_result(self) -> None:
        files = [_fi("src/app.js")]
        results = resolve(files, [], [])
        assert results == []

    def test_only_export_relationships_ignored(self) -> None:
        """resolve_imports only processes IMPORTS — exports are ignored."""
        files = [_fi("src/auth.js")]
        rels = [_exp("src/auth.js", "login")]
        results = resolve(files, [_sym("login", "src/auth.js")], rels)
        assert results == []
