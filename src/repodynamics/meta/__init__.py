from typing import Literal, Optional, Sequence, Callable
from pathlib import Path
import json

from repodynamics.logger import Logger
from repodynamics.meta.metadata import MetadataGenerator
from repodynamics.meta.manager import MetaManager
from repodynamics.meta.reader import MetaReader
from repodynamics.meta.validator import MetaValidator
from repodynamics.meta import files
from repodynamics.path import RelativePath
from repodynamics.meta.writer import MetaWriter
from repodynamics import _util


def read_from_json_file(path_root: str | Path = ".", logger: Logger | None = None) -> MetaManager:
    logger = logger or Logger()
    path_root = Path(path_root).resolve()
    path_json = path_root / RelativePath.file_metadata
    metadata = _util.dict.read(path_json, logger=logger, raise_empty=True)
    MetaValidator(metadata=metadata, logger=logger).validate()
    return MetaManager(metadata=metadata)


def read_from_json_string(content: str, logger: Logger | None = None) -> MetaManager:
    logger = logger or Logger()
    metadata = json.loads(content)
    MetaValidator(metadata=metadata, logger=logger).validate()
    return MetaManager(metadata=metadata)
