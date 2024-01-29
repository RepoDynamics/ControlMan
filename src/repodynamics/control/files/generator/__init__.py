import json

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
    logger.section("Generate Metadata")

        # (path_manager.metadata, json.dumps(content_manager.as_dict)),
        # (path_manager.license, content_manager["license"].get("text", "")),

    for generator in (_config, _forms, _health, _package, _readme):
        generated_files += generator.generate(
            content_manager=content_manager,
            path_manager=path_manager,
            logger=logger,
        )
    logger.section_end()
    return generated_files
