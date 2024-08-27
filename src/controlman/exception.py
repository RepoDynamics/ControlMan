"""Exceptions raised by ControlMan."""

from pathlib import Path as _Path
from typing import Type as _Type

from markitup import html as _html, doc as _doc







class ControlManRepositoryError(ControlManException):
    """Exception raised when issues are encountered with the Git(Hub) repository."""

    def __init__(self, msg: str, repo_path: str | _Path):
        super().__init__(f"An error occurred with the repository at '{repo_path}': {msg}")
        self.repo_path = repo_path
        return


class ControlManWebsiteError(ControlManException):
    """Exception raised when issues are encountered with the website."""

    def __init__(self, msg: str):
        super().__init__(f"An error occurred with the website: {msg}")
        return


class ControlManSchemaValidationError(ControlManException):
    """Exception raised when a control center file is invalid against its schema."""

    def __init__(self, msg: str, key: str | None = None):
        intro = "Control center data is not valid" + (f" at '{key}'" if key else "")
        super().__init__(f"{intro}: {msg}")
        self.key = key
        return


class ControlManFileReadError(ControlManException):
    """Exception raised when a file cannot be read."""

    def __init__(self, path: str | _Path | None = None, data: str | None = None, msg: str | None = None):
        msg = msg or "Please check the error details below and fix the issue."
        content = f' File content:\n{data}\n' if data else ''
        source = f"at '{path}'" if path else 'from string data'
        super().__init__(f"Failed to read file {source}. {msg}{content}")
        self.path = path
        self.data = data
        return


class ControlManFileDataTypeError(ControlManFileReadError):
    """Exception raised when a control center file's data is of an unexpected type."""

    def __init__(
        self,
        expected_type: _Type[dict | list],
        path: str | _Path | None = None,
        data: str | None = None,
        msg: str | None = None,
    ):
        super().__init__(
            path=path,
            data=data,
            msg=msg or f"Expected data type '{expected_type.__name__}' but got '{type(data).__name__}'."
        )
        self.expected_type = expected_type
        return


