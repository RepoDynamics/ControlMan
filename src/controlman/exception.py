
class ControlManException(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        return


class ControlManSchemaError(ControlManException):
    def __init__(self, path: str,  message: str):
        super().__init__(message)
        self.path = path
        return
