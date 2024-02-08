"""ControlMan base Exception class."""


class ControlManException(Exception):
    """Base class for all exceptions raised by ControlMan."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)
        return
