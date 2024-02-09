import pyserials as _pyserials
from loggerman import logger as _logger

from controlman._path_manager import PathManager as _PathManager
from controlman.datatype import DynamicFile as _DynamicFile
from controlman import ControlCenterContentManager as _ControlCenterContentManager
from controlman.files.generator import (
    config as _config,
    forms as _forms,
    package as _package,
    readme as _readme,
)
from controlman.files.generator import health as _health


@_logger.sectioner("Generate Dynamic Repository Files")
def generate(
    content_manager: _ControlCenterContentManager, path_manager: _PathManager,
) -> list[tuple[_DynamicFile, str]]:
    generated_files = []
    for generator in (
        _generate_metadata,
        _generate_license,
        _config.generate,
        _forms.generate,
        _health.generate,
        _package.generate,
        _readme.generate,
    ):
        generated_files += generator(content_manager=content_manager, path_manager=path_manager)
    return generated_files


@_logger.sectioner("Generate Metadata File")
def _generate_metadata(
    content_manager: _ControlCenterContentManager,
    path_manager: _PathManager,
) -> list[tuple[_DynamicFile, str]]:
    file_info = path_manager.metadata
    file_content = _pyserials.write.to_json_string(
        data=content_manager.content.as_dict, sort_keys=True, indent=None
    )
    _logger.info(code_title="File info", code=str(file_info))
    _logger.debug(code_title="File content", code=file_content)
    return [(file_info, file_content)]


@_logger.sectioner("Generate License File")
def _generate_license(
    content_manager: _ControlCenterContentManager,
    path_manager: _PathManager,
) -> list[tuple[_DynamicFile, str]]:
    file_info = path_manager.license
    file_content = content_manager["license"].get("text", "")
    _logger.info(code_title="File info", code=str(file_info))
    _logger.debug(code_title="File content", code=file_content)
    return [(file_info, file_content)]
