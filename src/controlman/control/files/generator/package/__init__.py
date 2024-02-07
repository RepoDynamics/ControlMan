from actionman.logger import Logger

from controlman.datatype import DynamicFile
from controlman.control.files.generator.package.python import PythonPackageFileGenerator
from controlman.control.content import ControlCenterContentManager
from controlman.path import PathManager


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
