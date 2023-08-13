from typing import Literal

class Logger:

    def __init__(self, output: Literal["console"] = "console"):
        self._output = output
        return

    def log(self, message: str, level: Literal["info", "warning", "error"] = "info"):
        if self._output == "console":
            print(message)
        return
