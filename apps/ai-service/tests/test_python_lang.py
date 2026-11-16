"""Python support: symbols, relationships and import resolution."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from repository.models import FileInfo  # noqa: E402
from repository.relationships import RelationshipKind, extract_relationships  # noqa: E402
from repository.resolver import ResolutionStatus, resolve_imports  # noqa: E402
from repository.symbols import SymbolKind, extract_symbols  # noqa: E402

SRC = '''
import os
import a.b as ab
from . import sibling
from ..pkg.mod import thing as t, other
from x import *
MAX_SIZE = 10
counter = 0

@decorator
async def top(a):
    def inner():
        return helper(a)
    return inner

class Service(Base):
    LIMIT = 3
    def run(self):
        return self.go() or top(1)
'''


def _syms():
    return extract_symbols("app/svc.py", "python", SRC)


def test_symbol_kinds_and_parents():
    by = {s.name: s for s in _syms()}
    assert by["top"].kind == SymbolKind.FUNCTION and by["top"].parent is None
    assert by["inner"].kind == SymbolKind.FUNCTION and by["inner"].parent == "top"
    assert by["Service"].kind == SymbolKind.CLASS
    assert by["run"].kind == SymbolKind.METHOD and by["run"].parent == "Service"
    assert by["MAX_SIZE"].kind == SymbolKind.CONSTANT
    assert by["counter"].kind == SymbolKind.VARIABLE
    assert "LIMIT" not in by  # class attributes are not extracted


def test_decorated_definition_starts_at_def_line():
    top = next(s for s in _syms() if s.name == "top")
    assert SRC.splitlines()[top.start.line - 1].lstrip().startswith("async def top")


def test_imports_extracted_with_module_paths():
    rels = [r for r in extract_relationships("app/svc.py", "python", SRC) if r.kind == RelationshipKind.IMPORTS]
    got = {(r.target_name, r.module_path) for r in rels}
    assert ("os", "os") in got
    assert ("ab", "a.b") in got
    assert ("sibling", ".") in got
    assert ("thing", "..pkg.mod") in got and ("other", "..pkg.mod") in got
    assert ("*", "x") in got
    alias = next(r for r in rels if r.target_name == "thing")
    assert alias.alias == "t"


def test_calls_extracted():
    calls = {r.target_name for r in extract_relationships("app/svc.py", "python", SRC) if r.kind == RelationshipKind.CALLS}
    assert {"helper", "self.go", "top"} <= calls


def test_syntax_error_does_not_raise():
    assert isinstance(extract_symbols("x.py", "python", "def (:\n"), list)


def _resolve(files, sources):
    infos = [FileInfo(path=p, extension=".py", language="python", size=1) for p in files]
    syms, rels = [], []
    for p, src in sources.items():
        syms += extract_symbols(p, "python", src)
        rels += extract_relationships(p, "python", src)
    return resolve_imports(infos, syms, rels)


def test_resolves_relative_absolute_and_external():
    files = ["pkg/__init__.py", "pkg/a.py", "pkg/b.py", "pkg/sub/c.py", "main.py"]
    res = _resolve(
        files,
        {
            "pkg/a.py": "from .b import helper\nfrom . import b\nfrom .sub.c import deep\nimport requests\n",
            "pkg/b.py": "def helper():\n    pass\n",
            "pkg/sub/c.py": "def deep():\n    pass\n",
            "main.py": "import pkg.a\nfrom pkg.b import helper\n",
        },
    )
    by = {(r.source_relationship.source_path, r.source_relationship.target_name): r for r in res}
    assert by[("pkg/a.py", "helper")].status == ResolutionStatus.RESOLVED
    assert by[("pkg/a.py", "helper")].target_path == "pkg/b.py"
    assert by[("pkg/a.py", "b")].target_path == "pkg/b.py"  # submodule import
    assert by[("pkg/a.py", "deep")].target_path == "pkg/sub/c.py"
    assert by[("pkg/a.py", "requests")].status == ResolutionStatus.EXTERNAL
    assert by[("main.py", "pkg")].target_path == "pkg/a.py"
    assert by[("main.py", "helper")].target_path == "pkg/b.py"


def test_src_layout_ancestor_roots():
    files = ["svc/src/repo/x.py", "svc/src/repo/y.py", "svc/src/app.py"]
    res = _resolve(
        files,
        {"svc/src/app.py": "from repo.x import f\n", "svc/src/repo/x.py": "def f():\n    pass\n", "svc/src/repo/y.py": ""},
    )
    assert res[0].target_path == "svc/src/repo/x.py"


def test_unresolved_relative_import():
    res = _resolve(["a.py"], {"a.py": "from .missing import q\n"})
    assert res[0].status == ResolutionStatus.UNRESOLVED
