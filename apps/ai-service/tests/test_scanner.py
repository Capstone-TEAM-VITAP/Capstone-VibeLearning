"""
tests/test_scanner.py

Test suite for Milestone 1 — Repository Scanner + Language Detection.

Tests
-----
A. Supported files are detected with correct languages.
B. Unsupported extensions are ignored.
C. Ignored directories are skipped.
D. Nested directories work and paths are correct.
E. Returned paths use POSIX '/' separators.
F. Results are deterministically sorted.
G. FileNotFoundError on a non-existent path.
H. NotADirectoryError when path points to a file.
"""

import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Make sure the project's src/ package is importable when running pytest
# from the ai-service root (i.e. without installing the package).
# ---------------------------------------------------------------------------
_SRC = Path(__file__).parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from repository.models import FileInfo
from repository.scanner import detect_language, scan_repository


# ===========================================================================
# Helpers
# ===========================================================================

def _touch(path: Path, content: bytes = b"") -> None:
    """Create *path* and any missing parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _paths(files: list[FileInfo]) -> list[str]:
    """Extract just the POSIX path strings from a FileInfo list."""
    return [f.path for f in files]


# ===========================================================================
# A — Supported files are detected with correct languages
# ===========================================================================

class TestSupportedFiles:
    def test_all_supported_files_detected(self, tmp_path: Path) -> None:
        fixtures = {
            "src/app.js": "javascript",
            "src/main.py": "python",
            "src/User.java": "java",
            "src/auth.ts": "typescript",
            "src/Login.jsx": "javascript",
            "README.md": "markdown",
        }
        for rel, _ in fixtures.items():
            _touch(tmp_path / rel)

        result = scan_repository(tmp_path)
        result_map = {f.path: f.language for f in result}

        for rel, expected_lang in fixtures.items():
            posix = rel  # already uses '/'
            assert posix in result_map, f"Expected {posix!r} in results"
            assert result_map[posix] == expected_lang, (
                f"{posix}: expected language {expected_lang!r}, "
                f"got {result_map[posix]!r}"
            )

    def test_file_info_fields_populated(self, tmp_path: Path) -> None:
        """FileInfo.extension and FileInfo.size are correctly set."""
        target = tmp_path / "src" / "app.js"
        _touch(target, content=b"console.log('hello');")

        result = scan_repository(tmp_path)
        assert len(result) == 1

        fi = result[0]
        assert fi.path == "src/app.js"
        assert fi.language == "javascript"
        assert fi.extension == ".js"
        assert fi.size == len(b"console.log('hello');")

    def test_tsx_detected_as_typescript(self, tmp_path: Path) -> None:
        _touch(tmp_path / "Component.tsx")
        result = scan_repository(tmp_path)
        assert any(f.language == "typescript" for f in result)

    def test_css_and_scss_detected(self, tmp_path: Path) -> None:
        _touch(tmp_path / "styles.css")
        _touch(tmp_path / "theme.scss")
        result = scan_repository(tmp_path)
        langs = {f.extension: f.language for f in result}
        assert langs[".css"] == "css"
        assert langs[".scss"] == "scss"

    def test_html_and_json_detected(self, tmp_path: Path) -> None:
        _touch(tmp_path / "index.html")
        _touch(tmp_path / "package.json")
        result = scan_repository(tmp_path)
        langs = {f.extension: f.language for f in result}
        assert langs[".html"] == "html"
        assert langs[".json"] == "json"


# ===========================================================================
# B — Unsupported files are ignored
# ===========================================================================

class TestUnsupportedFiles:
    def test_unknown_extensions_not_returned(self, tmp_path: Path) -> None:
        _touch(tmp_path / "image.png")
        _touch(tmp_path / "archive.zip")
        _touch(tmp_path / "random.xyz")
        _touch(tmp_path / "noextension")

        result = scan_repository(tmp_path)
        assert result == [], f"Expected empty list, got {result}"

    def test_mixed_supported_unsupported(self, tmp_path: Path) -> None:
        _touch(tmp_path / "app.js")
        _touch(tmp_path / "logo.png")
        _touch(tmp_path / "data.csv")

        result = scan_repository(tmp_path)
        assert len(result) == 1
        assert result[0].path == "app.js"


# ===========================================================================
# C — Ignored directories are skipped
# ===========================================================================

class TestIgnoredDirectories:
    _IGNORED_CASES = [
        "node_modules/package/index.js",
        ".git/config.js",
        "dist/bundle.js",
        "build/output.js",
        "coverage/report.js",
        "__pycache__/cache.py",
        ".venv/test.py",
        ".next/server/page.js",
        ".turbo/cache.js",
        ".cache/query.js",
        "venv/lib.py",
    ]

    def test_ignored_dirs_not_returned(self, tmp_path: Path) -> None:
        for rel in self._IGNORED_CASES:
            _touch(tmp_path / rel)

        result = scan_repository(tmp_path)
        assert result == [], (
            f"Expected empty results but got: {_paths(result)}"
        )

    def test_ignored_dir_alongside_valid_files(self, tmp_path: Path) -> None:
        """Valid files outside ignored dirs must still be returned."""
        _touch(tmp_path / "src" / "app.js")
        _touch(tmp_path / "node_modules" / "lib" / "index.js")

        result = scan_repository(tmp_path)
        assert _paths(result) == ["src/app.js"]

    def test_dir_name_with_ignored_substring_not_filtered(
        self, tmp_path: Path
    ) -> None:
        """
        A directory whose name *contains* an ignored name as a substring
        (e.g. "node_modules_backup") must NOT be filtered out.
        """
        _touch(tmp_path / "node_modules_backup" / "index.js")

        result = scan_repository(tmp_path)
        assert _paths(result) == ["node_modules_backup/index.js"]

    def test_ds_store_ignored(self, tmp_path: Path) -> None:
        """
        .DS_Store has no supported extension, so it's dropped at the language
        step anyway — but the ignore rule should also catch it.
        """
        _touch(tmp_path / ".DS_Store")
        result = scan_repository(tmp_path)
        assert result == []


# ===========================================================================
# D — Nested directories work
# ===========================================================================

class TestNestedDirectories:
    def test_deeply_nested_file(self, tmp_path: Path) -> None:
        _touch(tmp_path / "src" / "auth" / "services" / "authService.js")

        result = scan_repository(tmp_path)
        assert len(result) == 1
        assert result[0].path == "src/auth/services/authService.js"

    def test_multiple_nesting_levels(self, tmp_path: Path) -> None:
        paths = [
            "a/b/c/d/deep.py",
            "x/y/z/shallow.js",
        ]
        for p in paths:
            _touch(tmp_path / p)

        result = scan_repository(tmp_path)
        assert set(_paths(result)) == set(paths)


# ===========================================================================
# E — Paths use POSIX separators
# ===========================================================================

class TestPosixPaths:
    def test_no_backslashes_in_paths(self, tmp_path: Path) -> None:
        _touch(tmp_path / "src" / "auth" / "login.ts")

        result = scan_repository(tmp_path)
        for fi in result:
            assert "\\" not in fi.path, (
                f"Backslash found in path: {fi.path!r}"
            )

    def test_posix_separator_present(self, tmp_path: Path) -> None:
        _touch(tmp_path / "a" / "b" / "c.js")

        result = scan_repository(tmp_path)
        assert result[0].path == "a/b/c.js"


# ===========================================================================
# F — Results are deterministic (sorted by path)
# ===========================================================================

class TestDeterministicOrder:
    def test_sorted_by_path(self, tmp_path: Path) -> None:
        # Create files in a shuffled order; scanner must return them sorted.
        files = [
            "z_last.js",
            "a_first.py",
            "m_middle.ts",
            "src/nested.md",
        ]
        for f in files:
            _touch(tmp_path / f)

        result = scan_repository(tmp_path)
        returned_paths = _paths(result)
        assert returned_paths == sorted(returned_paths), (
            f"Results not sorted: {returned_paths}"
        )

    def test_repeated_scans_are_identical(self, tmp_path: Path) -> None:
        for name in ["c.js", "a.py", "b.ts"]:
            _touch(tmp_path / name)

        first = scan_repository(tmp_path)
        second = scan_repository(tmp_path)
        assert first == second


# ===========================================================================
# G — Invalid repository path
# ===========================================================================

class TestInvalidPath:
    def test_nonexistent_path_raises_file_not_found(
        self, tmp_path: Path
    ) -> None:
        missing = tmp_path / "does_not_exist"
        with pytest.raises(FileNotFoundError):
            scan_repository(missing)

    def test_nonexistent_deep_path(self, tmp_path: Path) -> None:
        deep_missing = tmp_path / "a" / "b" / "c"
        with pytest.raises(FileNotFoundError):
            scan_repository(deep_missing)


# ===========================================================================
# H — Path points to a file instead of a directory
# ===========================================================================

class TestNotADirectory:
    def test_file_path_raises_not_a_directory(self, tmp_path: Path) -> None:
        file_path = tmp_path / "actual_file.py"
        _touch(file_path)
        with pytest.raises(NotADirectoryError):
            scan_repository(file_path)


# ===========================================================================
# detect_language unit tests
# ===========================================================================

class TestDetectLanguage:
    @pytest.mark.parametrize(
        "filename,expected",
        [
            ("app.js", "javascript"),
            ("App.JSX", "javascript"),   # case-insensitive
            ("index.ts", "typescript"),
            ("Page.TSX", "typescript"),
            ("main.py", "python"),
            ("Main.PY", "python"),
            ("Main.java", "java"),
            ("data.json", "json"),
            ("README.md", "markdown"),
            ("styles.css", "css"),
            ("theme.scss", "scss"),
            ("index.html", "html"),
        ],
    )
    def test_known_extensions(self, filename: str, expected: str) -> None:
        result = detect_language(Path(filename))
        assert result == expected, (
            f"detect_language({filename!r}) -> {result!r}, expected {expected!r}"
        )

    @pytest.mark.parametrize(
        "filename",
        ["image.png", "archive.zip", "data.csv", "noextension", ".hidden"],
    )
    def test_unknown_extensions_return_none(self, filename: str) -> None:
        result = detect_language(Path(filename))
        assert result is None, (
            f"detect_language({filename!r}) should be None, got {result!r}"
        )
