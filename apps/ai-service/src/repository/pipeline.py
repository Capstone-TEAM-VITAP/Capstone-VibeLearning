"""
repository/pipeline.py

Repository Intelligence Orchestration Pipeline — Milestone 1–8 Integration.

Runs the complete M1–M8 repository-intelligence pipeline deterministically
on a local repository path to produce an immutable CodeGraph and Graph IR.

Pipeline steps:
1. Validate repository path exists and is a directory.
2. Scan repository for supported, non-ignored files (M1).
3. Read and parse supported source files with Tree-sitter (M2).
4. Extract symbols from parsed source (M3).
5. Extract structural relationships (M4).
6. Resolve cross-file imports and module bindings (M5).
7. Detect architectural roles and patterns (M6).
8. Construct unified in-memory CodeGraph (M7).
9. Convert CodeGraph to standard Graph IR format (M8).
10. Return immutable RepositoryAnalysisResult.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .architecture import RepositoryArchitecture, classify_repository
from .graph import CodeGraph, GraphValidationError, build_code_graph
from .graph_ir import graph_to_ir
from .models import FileInfo
from .parser import UnsupportedLanguageError, parse_source
from .relationships import Relationship, extract_relationships
from .resolver import ResolvedRelationship, resolve_imports
from .scanner import scan_repository
from .symbols import Symbol, extract_symbols

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class RepositoryAnalysisError(ValueError):
    """Raised when repository analysis fails or receives invalid input."""


# ---------------------------------------------------------------------------
# Result Model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RepositoryAnalysisResult:
    """
    Immutable container holding the complete output of repository analysis.

    Attributes:
        repository_name: Name of the analyzed repository.
        files: Discovered repository files as FileInfo objects.
        symbols: Extracted symbols across all files.
        relationships: Extracted structural relationships across all files.
        resolved_relationships: Cross-file resolved relationships.
        architecture: Repository-level architectural classification.
        graph: Fully-assembled in-memory CodeGraph.
        ir: Serialized Graph IR dictionary strictly conforming to schema.
    """

    repository_name: str
    files: tuple[FileInfo, ...]
    symbols: tuple[Symbol, ...]
    relationships: tuple[Relationship, ...]
    resolved_relationships: tuple[ResolvedRelationship, ...]
    architecture: RepositoryArchitecture
    graph: CodeGraph
    ir: dict[str, Any]


# ---------------------------------------------------------------------------
# Main Pipeline Function
# ---------------------------------------------------------------------------


def analyze_repository(
    repository_path: str | Path,
    *,
    repo_name: str | None = None,
) -> RepositoryAnalysisResult:
    """
    Orchestrate full M1–M8 static analysis on a local repository.

    Parameters
    ----------
    repository_path:
        Path to the repository root directory on the local filesystem.
    repo_name:
        Optional explicit name for the repository. If not provided,
        derived from Path(repository_path).name.

    Returns
    -------
    RepositoryAnalysisResult
        Immutable analysis result containing all discovered files, symbols,
        relationships, architectural classifications, CodeGraph, and Graph IR.

    Raises
    ------
    RepositoryAnalysisError
        If repository_path is invalid, does not exist, is not a directory,
        or if unrecoverable pipeline errors occur.
    """
    if repository_path is None:
        raise RepositoryAnalysisError("Repository path must not be None")

    if not isinstance(repository_path, (str, Path)):
        raise RepositoryAnalysisError(
            f"Invalid repository path type: {type(repository_path).__name__}"
        )

    path_obj = Path(repository_path)

    # Validate repository path existence and directory type
    if not path_obj.exists():
        raise RepositoryAnalysisError(f"Repository path does not exist: {path_obj}")

    if not path_obj.is_dir():
        raise RepositoryAnalysisError(f"Repository path is not a directory: {path_obj}")

    # Resolve root path safely
    try:
        resolved_root = path_obj.resolve()
    except OSError as err:
        raise RepositoryAnalysisError(f"Failed to resolve repository path: {err}") from err

    # Determine repository name
    if repo_name is not None and str(repo_name).strip():
        final_repo_name = str(repo_name)
    else:
        derived = path_obj.name
        if derived:
            final_repo_name = derived
        else:
            final_repo_name = resolved_root.name if resolved_root.name else "root"

    # Step 1: Scan repository for files (M1)
    try:
        files_list = scan_repository(resolved_root)
    except (FileNotFoundError, NotADirectoryError, OSError) as err:
        raise RepositoryAnalysisError(f"Repository scan failed: {err}") from err

    # Step 2: Read, parse, and extract symbols & relationships (M2, M3, M4)
    all_symbols: list[Symbol] = []
    all_relationships: list[Relationship] = []

    for file_info in files_list:
        file_full_path = (resolved_root / file_info.path).resolve()

        # Security check: never follow files outside repository_path
        try:
            file_full_path.relative_to(resolved_root)
        except ValueError:
            logger.warning("Skipping file outside repository root: %s", file_info.path)
            continue

        # Safely read source file
        try:
            source_bytes = file_full_path.read_bytes()
        except OSError as err:
            logger.warning("Skipping unreadable file %s: %s", file_info.path, err)
            continue

        # Parse source (M2) — if supported language
        try:
            parse_source(file_info.path, file_info.language, source_bytes)
        except UnsupportedLanguageError:
            # Language not supported by AST parser; continue without AST extraction
            continue
        except Exception as err:
            logger.warning("Parser error on file %s: %s", file_info.path, err)
            continue

        # Extract symbols (M3)
        try:
            file_symbols = extract_symbols(file_info.path, file_info.language, source_bytes)
            all_symbols.extend(file_symbols)
        except UnsupportedLanguageError:
            pass
        except Exception as err:
            logger.warning("Symbol extraction error on file %s: %s", file_info.path, err)

        # Extract relationships (M4)
        try:
            file_relationships = extract_relationships(
                file_info.path, file_info.language, source_bytes
            )
            all_relationships.extend(file_relationships)
        except UnsupportedLanguageError:
            pass
        except Exception as err:
            logger.warning("Relationship extraction error on file %s: %s", file_info.path, err)

    # Ensure deterministic ordering for all symbols and relationships
    all_symbols.sort(key=lambda s: (s.path, s.start.line, s.start.column, s.name))
    all_relationships.sort(
        key=lambda r: (
            r.source_path,
            r.source_position.line,
            r.source_position.column,
            r.target_name,
        )
    )

    # Step 3: Resolve cross-file relationships (M5)
    try:
        resolved_relationships = resolve_imports(
            files=files_list,
            symbols=all_symbols,
            relationships=all_relationships,
        )
    except Exception as err:
        raise RepositoryAnalysisError(f"Cross-file resolution failed: {err}") from err

    # Step 4: Detect architecture (M6)
    try:
        architecture = classify_repository(
            files=files_list,
            symbols=all_symbols,
            relationships=all_relationships,
            resolved=resolved_relationships,
        )
    except Exception as err:
        raise RepositoryAnalysisError(f"Architecture classification failed: {err}") from err

    # Step 5: Build unified CodeGraph (M7)
    try:
        graph = build_code_graph(
            files=files_list,
            symbols=all_symbols,
            relationships=all_relationships,
            resolved_relationships=resolved_relationships,
            architecture=architecture,
            repo_name=final_repo_name,
        )
    except GraphValidationError as err:
        raise RepositoryAnalysisError(f"CodeGraph construction validation failed: {err}") from err
    except Exception as err:
        raise RepositoryAnalysisError(f"CodeGraph construction failed: {err}") from err

    # Step 6: Convert CodeGraph to standard IR (M8)
    try:
        ir = graph_to_ir(graph)
    except Exception as err:
        raise RepositoryAnalysisError(f"Graph IR generation failed: {err}") from err

    return RepositoryAnalysisResult(
        repository_name=final_repo_name,
        files=tuple(files_list),
        symbols=tuple(all_symbols),
        relationships=tuple(all_relationships),
        resolved_relationships=tuple(resolved_relationships),
        architecture=architecture,
        graph=graph,
        ir=ir,
    )
