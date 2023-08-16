from typing import Literal
import sys

from repodynamics.ansi import SGR


class Logger:

    def __init__(
        self,
        output: Literal["console", "github"] = "console",
        color: tuple[int, int, int] = (0, 162, 255)
    ):
        self._output = output
        self._color = color
        self._in_section: bool = False
        return

    def section(self, title: str):
        if self._output == "github":
            if self._in_section:
                print("::endgroup::")
            print(f"::group::{SGR.style('bold', self._color)}{title}")
            self._in_section = True
        return

    def log(self, message: str, level: Literal["success", "debug", "info", "warning", "error"] = "info"):
        if self._output in ("console", "github"):
            print(SGR.format(message, level))
        return

    def info(self, message: str):
        self.log(message, level="info")
        return

    def debug(self, message: str):
        self.log(message, level="debug")
        return

    def success(self, message: str):
        self.log(message, level="success")
        return

    def error(self, message: str):
        self.log(message, level="error")
        sys.exit(1)


