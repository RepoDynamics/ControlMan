from pathlib import Path as _Path

from loggerman import logger as _logger
import pyshellman
import pkgdata as _pkgdata
import mdit as _mdit

from controlman import const as _const, exception as _exception


class HookManager:

    def __init__(
        self,
        dir_path: _Path,
        module_name_staged: str = _const.FILENAME_CC_HOOK_STAGED,
        module_name_inline: str = _const.FILENAME_CC_HOOK_INLINE,
        filename_env: str = _const.FILENAME_CC_HOOK_REQUIREMENTS,
    ):

        def load_module(module_filename: str):
            module_filepath = dir_path / module_filename
            module_filepath_md = _mdit.element.code_span(str(module_filepath))
            module_name = module_filename.removesuffix(".py")
            if not module_filepath.is_file():
                _logger.notice(
                    log_title,
                    _mdit.inline_container(
                        f"No {module_name} hooks module found at",
                        module_filepath_md,
                        ".",
                    ),
                )
                return
            try:
                module = _pkgdata.import_module_from_path(path=module_filepath)
            except _pkgdata.exception.PkgDataModuleImportError as e:
                msg = _mdit.inline_container(
                    f"Failed to import the {module_name} hooks module at ",
                    module_filepath_md,
                    "."
                )
                error_traceback = _mdit.element.admonition(
                    title="Error Traceback",
                    body=_logger.traceback(),
                    opened=True,
                    type="error",
                )
                _logger.critical(
                    log_title,
                    msg,
                    error_traceback,
                    env_md,
                )
                raise _exception.data_gen.ControlManHookError(
                    problem=msg,
                    details=[error_traceback, env_md],
                ) from None
            _logger.success(
                log_title,
                _mdit.inline_container(
                    f"Successfully imported the {module_name} hooks module at ",
                    module_filepath_md,
                ),
                env_md,
            )
            return module

        self._generator = None
        self.inline_hooks = None
        log_title = "User Hook Initialization"
        dir_path_md = _mdit.element.code_span(str(dir_path))
        if not dir_path.is_dir():
            _logger.info(
                log_title,
                _mdit.inline_container("No hook directory found at ", dir_path_md),
            )
            return
        env_filepath = dir_path / filename_env
        env_filepath_md = _mdit.element.code_span(str(env_filepath))
        if not env_filepath.is_file():
            env_msg = _mdit.inline_container(
                "No user hook requirements file found at ",
                env_filepath_md,
            )
            env_log = [env_msg]
            env_log_type = "note"
        else:
            pip_output = pyshellman.pip.install_requirements(path=env_filepath)
            pip_output.title = "Pip Installation Results"
            execution_report_dropdown = pip_output.report()
            if not pip_output.succeeded:
                msg = _mdit.inline_container(
                    "Failed to install user hook requirements from ",
                    env_filepath_md,
                )
                _logger.critical(log_title, msg, execution_report_dropdown)
                raise _exception.data_gen.ControlManHookError(
                    problem=msg,
                    details=execution_report_dropdown,
                )
            env_msg = _mdit.inline_container(
                "Installed user hook requirements from ",
                env_filepath_md,
            )
            env_log = [env_msg, execution_report_dropdown]
            env_log_type = "tip"
        env_md = _mdit.element.admonition(
            title="Requirements Installation",
            body=env_log,
            opened=True,
            type=env_log_type,
        )
        self._generator = load_module(module_name_staged)
        self.inline_hooks = load_module(module_name_inline)
        return

    def generate(self, func_name: str, *args, **kwargs):
        log_title = "Hook Execution"
        if not self._generator:
            _logger.info(
                log_title,
                _mdit.inline_container(
                    "No user hook module found. Skipping hook ",
                    _mdit.element.code_span(func_name),
                    "."
                ),
            )
            return
        hook = getattr(self._generator, func_name, None)
        if not hook:
            _logger.info(
                log_title,
                _mdit.inline_container(
                    "No user hook function found. Skipping hook ",
                    _mdit.element.code_span(func_name),
                    "."
                ),
            )
            return
        try:
            hook(*args, **kwargs)
        except Exception:
            error_traceback = _mdit.element.admonition(
                title="Error Traceback",
                body=_logger.traceback(),
                opened=True,
                type="error",
            )
            _logger.critical(
                log_title,
                _mdit.inline_container(
                    "Failed to execute user hook ",
                    _mdit.element.code_span(func_name),
                    "."
                ),
                error_traceback,
            )
            raise _exception.data_gen.ControlManHookError(
                details=error_traceback,
                hook_name=func_name,
            ) from None
        _logger.success(
            log_title,
            _mdit.inline_container(
                "Successfully executed user hook ",
                _mdit.element.code_span(func_name),
                "."
            ),
        )
        return
