from typing import Protocol as _Protocol, runtime_checkable as _runtime_checkable
from pathlib import Path as _Path
import re as _re


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

    def get_remotes(self) -> dict[str, dict[str, str]]:
        """Get all remote URLs of the git repository."""
        ...

    def get_remote_repo_name(
        self,
        remote_name: str = "origin",
        remote_purpose: str = "push",
        fallback_name: bool = True,
        fallback_purpose: bool = True,
    ) -> tuple[str, str] | None:
        ...

    def fetch_remote_branches_by_pattern(
        self,
        branch_pattern: _re.Pattern | None = None,
        remote_name: str = "origin",
        exists_ok: bool = False,
        not_fast_forward_ok: bool = False,
    ) -> None:
        ...

    def get_all_branch_names(self) -> tuple[str, list[str]]:
        """Get the name of all branches."""
        ...