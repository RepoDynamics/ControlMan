from actionman.logger import Logger

from repodynamics.datatype import DynamicFile
from repodynamics.control.files.generator.package.python import PythonPackageFileGenerator
from repodynamics.control.content import ControlCenterContentManager
from repodynamics.path import PathManager


def generate(
    content_manager: ControlCenterContentManager,
    path_manager: PathManager,
    logger: Logger,
) -> list[tuple[DynamicFile, str]]:
    if content_manager["package"]["type"] == "python":
        return PythonPackageFileGenerator(
            content_manager=content_manager, path_manager=path_manager, logger=logger
        ).generate()
    else:
        return []
