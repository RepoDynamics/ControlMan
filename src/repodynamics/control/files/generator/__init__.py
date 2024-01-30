import pyserials as _pyserials
from actionman.logger import Logger as _Logger

from repodynamics.path import PathManager as _PathManager
from repodynamics.datatype import DynamicFile as _DynamicFile
from repodynamics.control.content import ControlCenterContentManager as _ControlCenterContentManager
from repodynamics.control.files.generator import (
    config as _config,
    forms as _forms,
    health as _health,
    package as _package,
    readme as _readme,
)


def generate(
    content_manager: _ControlCenterContentManager,
    path_manager: _PathManager,
    logger: _Logger,
) -> list[tuple[_DynamicFile, str]]:
    logger.section("Generate Dynamic Repository Files", group=True)
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
        generated_files += generator(
            content_manager=content_manager,
            path_manager=path_manager,
            logger=logger,
        )
    logger.section_end()
    return generated_files


def _generate_metadata(
    content_manager: _ControlCenterContentManager,
    path_manager: _PathManager,
    logger: _Logger,
) -> list[tuple[_DynamicFile, str]]:
    logger.section("Metadata File", group=True)
    file_info = path_manager.metadata
    file_content = _pyserials.write.to_json_string(data=content_manager.as_dict, sort_keys=True, indent=None)
    logger.info(message="File info:", code=str(file_info))
    logger.debug(message="File content:", code=file_content)
    logger.section_end()
    return [(file_info, file_content)]


def _generate_license(
    content_manager: _ControlCenterContentManager,
    path_manager: _PathManager,
    logger: _Logger,
) -> list[tuple[_DynamicFile, str]]:
    logger.section("License File", group=True)
    file_info = path_manager.license
    file_content = content_manager["license"].get("text", "")
    logger.info(message="File info:", code=str(file_info))
    logger.debug(message="File content:", code=file_content)
    logger.section_end()
    return [(file_info, file_content)]
