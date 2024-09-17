from pathlib import Path as _Path

from loggerman import logger as _logger
import pyshellman
import pkgdata as _pkgdata

from controlman import const as _const


class HookManager:

    def __init__(
        self,
        dir_path: _Path,
        module_name: str = _const.FILENAME_CC_HOOK_MODULE,
        filename_env: str = _const.FILENAME_CC_HOOK_REQUIREMENTS,
    ):
        self._path = dir_path
        self._module_name = module_name
        self._env_filename = filename_env
        self._generator = None
        return

    def has_hook(self, name: str) -> bool:
        generator = self._get_generator()
        if not generator:
            return False
        return hasattr(generator, name)

    def generate(self, func_name: str, *args, **kwargs):
        if not self.has_hook(func_name):
            return
        return getattr(self._generator, func_name)(*args, **kwargs)

    def _get_generator(self):
        if self._generator:
            return self._generator
        if not self._path.is_dir():
            _logger.info("No hooks directory found.")
            return
        self._install_requirements()
        module_path = self._path / self._module_name
        if not module_path.is_file():
            _logger.warning(f"No custom generator found at {module_path}.")
            return
        return _pkgdata.import_module_from_path(path=module_path)

    @_logger.sectioner("Install Requirements")
    def _install_requirements(self):
        filepath = self._path / self._env_filename
        if not filepath.is_file():
            _logger.info(f"No requirements file found at {filepath}.")
            return
        result = pyshellman.pip.install_requirements(path=filepath)
        for title, detail in result.details.items():
            _logger.info(title, detail)
        return
