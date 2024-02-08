"""Exceptions raised due to issues with the contents of the user repository's control center files."""

from typing import Type as _Type

from controlman.exception._base import ControlManException as _ControlManException


class ControlManContentException(_ControlManException):
    """Base class for all exceptions raised due to issues with
    the contents of the user repository's control center files.
    """

    def __init__(self, message: str):
        super().__init__(message)
        return


class ControlManSchemaValidationError(ControlManContentException):
    """Exception raised when a control center file is invalid against its schema."""

    def __init__(
        self, rel_path: str, file_ext: str, is_dir: bool, has_extension: bool
    ):
        if is_dir:
            intro = f"One of the control center files in '{rel_path}'"
            if has_extension:
                intro += " (or in one of their extensions defined in 'extensions.yaml')"
        else:
            intro = f"The control center file at '{rel_path}.{file_ext}'"
            if has_extension:
                intro += " (or in one of its extensions defined in 'extensions.yaml')"
        message = (
            f"{intro} is invalid against its schema. Please check the error details below and fix the issue."
        )
        super().__init__(message)
        return


class ControlManFileReadError(ControlManContentException):
    """Exception raised when a control center file cannot be read."""

    def __init__(self, relpath_data: str, data: str):
        super().__init__(
            f"Failed to read control center file at '{relpath_data}'. "
            "Please check the error details below and fix the issue."
        )
        self.relpath_data = relpath_data
        self.data = data
        return


class ControlManFileDataTypeError(ControlManContentException):
    """Exception raised when a control center file's data is of an unexpected type."""

    def __init__(self, relpath_data: str, data: str, expected_type: _Type[dict | list]):
        super().__init__(
            f"Control center file at '{relpath_data}' has an unexpected data type; "
            f"expected '{expected_type.__name__}' but got '{type(data).__name__}'. "
            "Please fix the issue."
        )
        self.relpath_data = relpath_data
        self.data = data
        return
