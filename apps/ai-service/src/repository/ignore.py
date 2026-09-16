"""
repository/ignore.py

Repository filtering rules for the scanner.

Rules:
  - Ignore well-known non-source directories (node_modules, .git, dist, …).
  - Ignore specific files (.DS_Store).
  - Matching is done against individual path *components*, never as a
    substring of the full path string, to avoid false positives such as
    ignoring "vendor_modules/foo.js" because it contains "node_modules".

Milestone 1 — no regex, no glob patterns, pure component comparison.
"""

from pathlib import Path

# Directory names that should be skipped entirely during traversal.
_IGNORED_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        "node_modules",
        "dist",
        "build",
        "coverage",
        "__pycache__",
        ".venv",
        "venv",
        ".next",
        ".turbo",
        ".cache",
    }
)

# Individual file names that should always be skipped.
_IGNORED_FILES: frozenset[str] = frozenset(
    {
        ".DS_Store",
    }
)


def is_ignored_dir(relative_path: Path) -> bool:
    """
    Return True if *any* component of ``relative_path`` is an ignored
    directory name.

    ``relative_path`` must be a repository-relative path (i.e. already
    stripped of the repository root), so that we compare only directory
    names — not random substrings of absolute paths.

    Examples
    --------
    >>> is_ignored_dir(Path("node_modules/lodash"))
    True
    >>> is_ignored_dir(Path("src/node_modules_helper/utils.js"))
    False  # "node_modules_helper" ≠ "node_modules"
    """
    return any(part in _IGNORED_DIRS for part in relative_path.parts)


def is_ignored_file(name: str) -> bool:
    """
    Return True if the file's base name matches an ignored file name.

    Parameters
    ----------
    name:
        The bare filename (no directory components), e.g. ".DS_Store".
    """
    return name in _IGNORED_FILES
