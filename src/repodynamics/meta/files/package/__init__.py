from repodynamics.meta.files.package.python import PythonPackageFileGenerator
from repodynamics.meta.manager import MetaManager
from repodynamics.path import PathFinder
from repodynamics.logger import Logger


def generate(
    metadata: MetaManager,
    paths: PathFinder,
    logger: Logger = None,
):
    if metadata["package"]["type"] == "python":
        return PythonPackageFileGenerator(metadata=metadata, paths=paths, logger=logger).generate()
    else:
        return []
