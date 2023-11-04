from typing import Literal, Optional
import sys
import inspect
from pathlib import Path
import datetime
from markitup import sgr, html, md
from ruamel.yaml import YAML


class Logger:
    def __init__(
        self,
        output: Optional[Literal["console", "github"]] = None,
        path_output: str | Path = None,
        color_h1: tuple[int, int, int] = (0, 162, 255),
        color_h2: tuple[int, int, int] = (200, 120, 255),
        color_h3: tuple[int, int, int] = (252, 189, 0),
        color_h4: tuple[int, int, int] = (79, 255, 15),
        color_h5: tuple[int, int, int] = (0, 162, 255),
        color_h6: tuple[int, int, int] = (0, 162, 255),
        color_info: tuple[int, int, int] = (0, 200, 255),
        color_debug: tuple[int, int, int] = (125, 125, 125),
        color_success: tuple[int, int, int] = (0, 200, 0),
        color_error: tuple[int, int, int] = (200, 0, 0),
        color_warning: tuple[int, int, int] = (255, 125, 0),
        color_attention: tuple[int, int, int] = (255, 205, 0),
    ):
        if output and output not in ("console", "github"):
            raise ValueError(f"output must be one of 'console', 'github', or 'file', not {output}")
        self._output = output
        self._color_h1 = color_h1
        self._color_h2 = color_h2
        self._color_h3 = color_h3
        self._color_h4 = color_h4
        self._color_h5 = color_h5
        self._color_h6 = color_h6
        self._color = {
            "info": color_info,
            "debug": color_debug,
            "success": color_success,
            "skip": color_success,
            "error": color_error,
            "warning": color_warning,
            "attention": color_attention,
            "input": color_info,
        }
        self._path_log = None
        if path_output:
            path_output = Path(path_output)
            path_output.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y_%m_%d_%H_%M_%S")
            self._path_log = path_output / f"{timestamp}.md"
            self._path_log.touch()
        self.emoji = {
            "info": "ℹ️",
            "debug": "🐞",
            "success": "✅",
            "skip": "❎",
            "error": "⛔",
            "warning": "❗",
            "attention": "⚠️",
            "input": "📥",
        }
        self._heading_spec = {
            1: {
                "styles": {"text_styles": "bold", "text_color": "black", "background_color": self._color_h1},
                "line_length": 80,
                "spacing": 4,
            },
            2: {
                "styles": {"text_styles": "bold", "text_color": "black", "background_color": self._color_h2},
                "line_length": 65,
            },
            3: {
                "styles": {"text_styles": "bold", "text_color": "black", "background_color": self._color_h3},
                "line_length": 50,
            },
            4: {
                "styles": {"text_color": "black", "background_color": self._color_h4},
                "line_length": 35,
            },
        }
        self._log_console: str = ""
        self._log_file: str = ""
        return

    @property
    def console_log(self):
        return self._log_console

    @property
    def file_log(self):
        return self._log_file

    def _print(self, console: str, file: str, is_error: bool = False):
        self._log_console += f"{console}\n"
        self._log_file += f"{file}\n"
        if self._output:
            print(console)
            # print(console, file=sys.stderr)
        if self._path_log:
            with open(self._path_log, "a") as f:
                f.write(f"{file}\n")
        return

    def _h(self, level: Literal[1, 2, 3, 4], title: str):
        spec = self._heading_spec[level]
        style = sgr.style(**spec["styles"])
        console = sgr.format(title.center(spec["line_length"]), style)
        file = f"{'#' * level} {title}\n"
        self._print(console, file)
        return

    def h1(self, title: str):
        return self._h(1, title)

    def h2(self, title: str):
        return self._h(2, title)

    def h3(self, title: str):
        return self._h(3, title)

    def h4(self, title: str):
        return self._h(4, title)

    def log(
        self,
        level: Literal["info", "debug", "success", "error", "warning", "attention", "skip", "input"],
        message: str,
        details: str | list | dict = None,
        is_error: bool = False,
        index_stack: int = 3,
    ):
        fully_qualified_name = self._get_fully_qualified_name_of_original_caller(index_stack)
        msg = sgr.format(message, sgr.style(text_color=self._color[level]))
        console = f"{self.emoji[level]} {msg}"
        details_ = f"- Caller: {fully_qualified_name}\n"
        if details:
            if isinstance(details, list):
                details = "\n".join(details)
            elif isinstance(details, dict):
                details = YAML(typ=["rt", "string"]).dumps(details)
            else:
                details = str(details)
            details_ += details
            if self._output == "github":
                console = f"::group::{console}\n{details_}\n::endgroup::"
            else:
                details_summary = details_ if len(details_) < 300 else f"{details_[:500]} ...[shortened]"
                console = f"{console}\n{details_summary}"
        file = html.li(html.details(md.code_block(details_), summary=message))
        self._print(console, str(file), is_error=is_error)
        return console

    def info(self, message: str, details: str | list = None):
        return self.log("info", message, details)

    def input(self, message: str, details: str | list = None):
        return self.log("input", message, details)

    def debug(self, message: str, details: str | list = None):
        return self.log("debug", message, details)

    def success(self, message: str, details: str | list = None):
        return self.log("success", message, details)

    def skip(self, message: str, details: str | list = None):
        return self.log("skip", message, details)

    def warning(self, message: str, details: str | list = None):
        return self.log("warning", message, details)

    def attention(self, message: str, details: str | list = None):
        return self.log("attention", message, details)

    def error(self, message: str, details: str | list = None, raise_error: bool = True, exit_code: int = 1):
        console_msg = self.log("error", message, details)
        if raise_error:
            sys.exit(exit_code)
        return console_msg

    @staticmethod
    def _get_fully_qualified_name_of_original_caller(self, stack_index: int = 3) -> str:
        stack = inspect.stack()
        # The caller is the second element in the stack list
        caller_frame = stack[stack_index]
        module = inspect.getmodule(caller_frame[0])
        module_name = module.__name__ if module else "<module>"
        # Get the function or method name
        func_name = caller_frame.function
        # Combine them to get a fully qualified name
        fully_qualified_name = f"{module_name}.{func_name}"
        return fully_qualified_name
