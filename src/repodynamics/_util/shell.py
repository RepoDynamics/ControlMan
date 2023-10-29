from typing import Optional
import subprocess
from pathlib import Path
from repodynamics.logger import Logger


_LOGGER = Logger("console")


def run_command(
    command: list[str],
    cwd: Optional[str | Path] = None,
    raise_command: bool = True,
    raise_returncode: bool = True,
    raise_stderr: bool = True,
    text_output: bool = True,
    logger: Logger = _LOGGER,
) -> Optional[tuple[str, str, int]]:
    cmd_str = " ".join(command)
    title = f"Run shell command '{cmd_str}'"
    try:
        process = subprocess.run(command, text=text_output, cwd=cwd, capture_output=True)
    except FileNotFoundError:
        logger.error(title, f"- Failed: Command '{command[0]}' not found.", raise_error=raise_command)
        return
    out = process.stdout.strip() if text_output else process.stdout
    err = process.stderr.strip() if text_output else process.stderr
    code = process.returncode
    if code == 0 and not err:
        logger.success(title, f"- Shell command executed successfully with following output:\n{out}")
    else:
        logger.error(
            title,
            f"Shell command failed with following outputs:\n"
            f"Return Code: {code}\n\nError Message: {err}\n\nOutput: {out}",
            raise_error=(code != 0 and raise_returncode) or (err and raise_stderr),
        )
    return out, err, code
