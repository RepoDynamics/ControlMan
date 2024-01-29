import json

from actionman.logger import Logger

from repodynamics.path import PathManager
from repodynamics.datatype import DynamicFile
from repodynamics.control.content import ControlCenterContentManager
from repodynamics.control.files.generator import package, readme
from repodynamics.control.files.generator.forms import FormGenerator
from repodynamics.control.files.generator.config import ConfigFileGenerator
from repodynamics.control.files.generator.health import HealthFileGenerator


def generate(
    content_manager: ControlCenterContentManager,
    path_manager: PathManager,
    logger: Logger,
) -> list[tuple[DynamicFile, str]]:
    generated_files = [
        (path_manager.metadata, json.dumps(content_manager.as_dict)),
        (path_manager.license, content_manager["license"].get("text", "")),
    ]

    generated_files += ConfigFileGenerator(
        metadata=content_manager, output_path=path_manager, logger=logger
    ).generate()

    generated_files += FormGenerator(
        metadata=content_manager, output_path=path_manager, logger=logger
    ).generate()

    generated_files += HealthFileGenerator(
        metadata=content_manager, output_path=path_manager, logger=logger
    ).generate()

    generated_files += package.generate(
        metadata=content_manager,
        paths=path_manager,
        logger=logger,
    )

    generated_files += readme.generate(ccm=content_manager, path=path_manager, logger=logger)
    return generated_files
