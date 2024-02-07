from pathlib import Path as _Path

from loggerman import logger as _logger
import pyshellman as _pyshellman


def run(
    command: list[str],
    cwd: str | _Path | None = None,
    raise_execution: bool = True,
    raise_exit_code: bool = True,
    raise_stderr: bool = False,
    text_output: bool = True,
) -> _pyshellman.output.ShellOutput:
    result = _pyshellman.shell.run(
        command=command,
        cwd=cwd,
        raise_execution=raise_execution,
        raise_exit_code=raise_exit_code,
        raise_stderr=raise_stderr,
        text_output=text_output,
    )
    _logger.info("Execute shell command", msg=result.summary, code_title="Result", code=result)
    return result
