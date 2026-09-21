"""
repository/scanner.py

Repository file scanner — Milestone 1.

Public API
----------
detect_language(path: Path) -> str | None
    Extension-based language detection.  Returns None for unknown types.

scan_repository(root: str | Path) -> list[FileInfo]
    Recursively scans a repository directory and returns a sorted list of
    FileInfo objects for every supported, non-ignored file.
"""

from pathlib import Path

from .ignore import is_ignored_dir, is_ignored_file
from .models import FileInfo

# ---------------------------------------------------------------------------
# Extension → language mapping (case-insensitive; keys must be lower-cased)
# ---------------------------------------------------------------------------
_EXTENSION_LANGUAGE_MAP: dict[str, str] = {
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".py": "python",
    ".java": "java",
    ".json": "json",
    ".md": "markdown",
    ".css": "css",
    ".scss": "scss",
    ".html": "html",
}


def detect_language(path: Path) -> str | None:
    """
    Detect the programming/markup language of a file from its extension.

    The comparison is case-insensitive, so ``.PY``, ``.Py``, and ``.py``
    all resolve to ``"python"``.

    Parameters
    ----------
    path:
        Any ``Path`` object (only the suffix is examined).

    Returns
    -------
    str
        Language name if the extension is recognised.
    None
        If the extension is unknown or the file has no extension.
    """
    ext = path.suffix.lower()
    return _EXTENSION_LANGUAGE_MAP.get(ext)


def scan_repository(root: str | Path) -> list[FileInfo]:
    """
    Recursively scan a repository directory and return file metadata.

    Steps
    -----
    1. Resolve the repository root to an absolute path.
    2. Verify it exists; raise ``FileNotFoundError`` if not.
    3. Verify it is a directory; raise ``NotADirectoryError`` if not.
    4. Walk the directory tree, skipping ignored dirs/files.
    5. Skip files with unsupported extensions.
    6. Build a ``FileInfo`` for each accepted file.
    7. Return the list sorted deterministically by POSIX path.

    Parameters
    ----------
    root:
        Absolute or relative path to the repository root.

    Returns
    -------
    list[FileInfo]
        Sorted list of discovered files.

    Raises
    ------
    FileNotFoundError
        If *root* does not exist.
    NotADirectoryError
        If *root* exists but is not a directory.
    """
    root = Path(root).resolve()

    if not root.exists():
        raise FileNotFoundError(f"Repository path does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Repository path is not a directory: {root}")

    results: list[FileInfo] = []

    for entry in root.rglob("*"):
        if not entry.is_file():
            continue

        # Compute repository-relative path (pure POSIX string)
        relative = entry.relative_to(root)

        # --- Ignore checks ---
        # Check parent directories: relative.parent gives the directory
        # portion; passing the *full* relative path lets is_ignored_dir
        # inspect every component (including the file's own parent dirs).
        if is_ignored_dir(relative):
            continue

        if is_ignored_file(entry.name):
            continue

        # --- Language detection ---
        language = detect_language(entry)
        if language is None:
            continue  # unsupported extension → skip

        extension = entry.suffix.lower()
        size = entry.stat().st_size
        posix_path = relative.as_posix()

        results.append(
            FileInfo(
                path=posix_path,
                language=language,
                extension=extension,
                size=size,
            )
        )

    # Deterministic ordering by repository-relative POSIX path
    results.sort(key=lambda f: f.path)
    return results
