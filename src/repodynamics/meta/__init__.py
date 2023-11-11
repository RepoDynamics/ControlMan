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
from repodynamics.git import Git


def read_from_json_file(
    path_root: str | Path = ".", commit_hash: str = "", git: Git | None = None, logger: Logger | None = None
) -> MetaManager | None:
    logger = logger or Logger()
    path_root = Path(path_root).resolve()
    if commit_hash:
        git = git or Git(path_repo=path_root)
        content = git.file_at_hash(
            commit_hash=commit_hash,
            path=RelativePath.file_metadata,
            raise_missing=False,
        )
        return read_from_json_string(content=content, logger=logger) if content else None
    path_json = path_root / RelativePath.file_metadata
    metadata = _util.dict.read(path_json, logger=logger, raise_empty=False)
    if not metadata:
        return None
    MetaValidator(metadata=metadata, logger=logger).validate()
    return MetaManager(metadata=metadata)


def read_from_json_string(content: str, logger: Logger | None = None) -> MetaManager:
    logger = logger or Logger()
    metadata = json.loads(content)
    MetaValidator(metadata=metadata, logger=logger).validate()
    return MetaManager(metadata=metadata)
