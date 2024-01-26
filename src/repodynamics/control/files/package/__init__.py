from repodynamics.datatype import DynamicFile
from repodynamics.control.files.package.python import PythonPackageFileGenerator
from repodynamics.control.manager import MetaManager
from repodynamics.path import PathManager
from repodynamics.logger import Logger


def generate(
    metadata: MetaManager,
    paths: PathManager,
    logger: Logger = None,
) -> list[tuple[DynamicFile, str]]:
    if metadata["package"]["type"] == "python":
        return PythonPackageFileGenerator(metadata=metadata, paths=paths, logger=logger).generate()
    else:
        return []
