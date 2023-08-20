from typing import Literal
import sys

from repodynamics.ansi import SGR


class Logger:

    def __init__(
        self,
        output: Literal["console", "github"] = "console",
        color: tuple[int, int, int] = (0, 162, 255)
    ):
        self.output = output
        self.color = color
        self.in_section: bool = False
        return

    def section(self, title: str):
        if self.output == "github":
            if self.in_section:
                print("::endgroup::")
            print(f"::group::{SGR.style('bold', self.color)}{title}")
            self.in_section = True
        return

    def end_section(self):
        if self.output == "github":
            if self.in_section:
                print("::endgroup::")
            self.in_section = False
        return

    def log(
        self,
        message: str,
        level: Literal["success", "debug", "info", "attention", "warning", "error"] = "info"
    ):
        if self.output in ("console", "github"):
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

    def warning(self, message: str):
        self.log(message, level="warning")
        return

    def attention(self, message: str):
        self.log(message, level="attention")
        return
