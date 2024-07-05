from pathlib import Path as _Path

from loggerman import logger as _logger
import pyshellman

from controlman import _util


class ControlCenterCustomContentGenerator:

    def __init__(self, dir_path_custom: _Path):
        self._dir = dir_path_custom
        self._generator = None
        return

    def generate(self, func_name: str, *args):
        generator = self._get_generator()
        if not generator:
            return
        try:
            func = getattr(generator, func_name)
        except AttributeError:
            _logger.info(f"Custom generator does not have function '{func_name}'.")
            return
        return func(*args)

    def _get_generator(self):
        if self._generator:
            return self._generator
        if not self._dir.is_dir():
            _logger.info("No custom configuration directory found.")
            return
        self._install_requirements()
        filepath = self._dir / "generator.py"
        if not filepath.is_file():
            _logger.warning("No custom generator found.")
            return
        return _util.file.import_module_from_path(path=filepath)

    @_logger.sectioner("Install Requirements")
    def _install_requirements(self):
        filepath = self._dir / "requirements.txt"
        if not filepath.is_file():
            _logger.info("No requirements file found.")
            return
        result = pyshellman.pip.install_requirements(path=self._dir / "requirements.txt")
        for title, detail in result.details.items():
            _logger.info(code_title=title, code=detail)
        return
