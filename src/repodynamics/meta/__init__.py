from typing import Literal, Optional, Sequence, Callable
from pathlib import Path
import json

from ruamel.yaml import YAML

from repodynamics.logger import Logger
from repodynamics.meta.metadata import MetadataGenerator
from repodynamics.meta.reader import MetaReader
from repodynamics.meta import files
from repodynamics.meta.writer import MetaWriter


def update(
    path_root: str | Path = ".",
    path_meta: str = "meta",
    action: Literal["report", "apply", "commit"] = "report",
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
