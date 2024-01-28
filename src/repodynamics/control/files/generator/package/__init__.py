from actionman.log import Logger

from repodynamics.datatype import DynamicFile
from repodynamics.control.files.generator.package.python import PythonPackageFileGenerator
from repodynamics.control.content import ControlCenterContentManager
from repodynamics.path import PathManager


def generate(
    metadata: ControlCenterContentManager,
    paths: PathManager,
    logger: Logger = None,
) -> list[tuple[DynamicFile, str]]:
    if metadata["package"]["type"] == "python":
        return PythonPackageFileGenerator(metadata=metadata, paths=paths, logger=logger).generate()
    else:
        return []
