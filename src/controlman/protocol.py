from typing import Protocol as _Protocol, runtime_checkable as _runtime_checkable
from pathlib import Path as _Path


@_runtime_checkable
class Git(_Protocol):
    """Protocol for the Git API interface required by ControlMan."""

    @property
    def repo_path(self) -> _Path:
        """Path to the root of the Git repository."""
        ...

    def file_at_hash(self, path: str | _Path, commit_hash: str) -> str | None:
        """Read the contents of a file at a given commit hash."""
        ...
