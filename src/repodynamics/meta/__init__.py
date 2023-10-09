from typing import Literal, Optional, Sequence, Callable
from pathlib import Path
import json

from ruamel.yaml import YAML

from repodynamics.logger import Logger
from repodynamics.meta.metadata import MetadataGenerator
from repodynamics.meta.reader import MetaReader
from repodynamics.meta import files
from repodynamics.meta.writer import MetaWriter
from repodynamics import _util


def update(
    path_root: str | Path = ".",
    path_meta: str = ".meta",
    action: Literal["report", "apply", "amend", "commit"] = "report",
    github_token: Optional[str] = None,
    logger: Logger = None
) -> dict:
    logger = logger or Logger()
    reader = MetaReader(
        path_root=path_root,
        path_meta=path_meta,
        github_token=github_token,
        logger=logger
    )
    metadata_gen = MetadataGenerator(
        reader=reader,
    )
    metadata = metadata_gen.generate()
    generated_files = files.generate(metadata=metadata, reader=reader, logger=logger)
    writer = MetaWriter(path_root=path_root, logger=logger)
    output = writer.write(generated_files, action=action)
    output['metadata'] = metadata
    return output


def load(
    path_root: str | Path = ".",
    path_metadata: str = ".meta/.metadata.json",
    logger: Logger = None
) -> dict:
    logger = logger or Logger()
    path_metadata = Path(path_root) / path_metadata
    metadata = _util.dict.read(path_metadata, logger=logger) or {}
    if metadata:
        logger.success(
            f"Loaded metadata from {path_metadata}.",
            json.dumps(metadata, indent=3)
        )
    else:
        logger.attention(f"No metadata found in {path_metadata}.")
    defaults = _util.dict.read(_util.file.datafile("default_metadata.yaml"))
    _util.dict.update_recursive(source=metadata, add=defaults, append_list=False, logger=logger)
    logger.success("Full metadata file assembled.", json.dumps(metadata, indent=3))
    return metadata
