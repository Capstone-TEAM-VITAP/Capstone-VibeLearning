"""
repository/models.py

Immutable data models for the Repository Intelligence module.
Milestone 1: File metadata only.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FileInfo:
    """
    Represents a single file discovered inside a repository.

    Attributes:
        path:      Repository-relative path using POSIX '/' separators.
                   Example: "src/auth/Login.jsx"
        language:  Detected programming/markup language.
                   Example: "javascript"
        extension: File extension including the leading dot, lower-cased.
                   Example: ".jsx"
        size:      File size in bytes.
    """

    path: str
    language: str
    extension: str
    size: int
