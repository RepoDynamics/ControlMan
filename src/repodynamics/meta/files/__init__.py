import json

from repodynamics.logger import Logger
from repodynamics.meta.reader import MetaReader
from repodynamics.meta.files.config import ConfigFileGenerator
from repodynamics.meta.files.health import HealthFileGenerator
from repodynamics.meta.files.package import PackageFileGenerator
from repodynamics.meta.files.readme import ReadmeFileGenerator


def generate(metadata: dict, reader: MetaReader, logger: Logger = None) -> list[dict]:
    if not isinstance(reader, MetaReader):
        raise TypeError(f"reader must be of type MetaReader, not {type(reader)}")
    logger = logger or reader.logger
    logger.h2("Generate Files")
    updates = [
        dict(category="metadata", name="metadata", content=json.dumps(metadata)),
        dict(category="license", name="license", content=metadata["license"].get("fulltext", "")),
    ]
    updates += ReadmeFileGenerator(metadata=metadata, logger=logger, path_root=reader.path.root).generate()
    updates += ConfigFileGenerator(metadata=metadata, logger=logger).generate()
    updates += HealthFileGenerator(metadata=metadata, reader=reader, logger=logger).generate()
    updates += PackageFileGenerator(metadata=metadata, reader=reader, logger=logger).generate()
    return updates
