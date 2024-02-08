class ControlManException(Exception):
    """Base class for all exceptions raised by ControlMan."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)
        return


class ControlManContentException(ControlManException):
    """Base class for all exceptions related to the user repository's control center contents."""

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
