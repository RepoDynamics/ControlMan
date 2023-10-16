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
    action: Literal["report", "apply", "amend", "commit"] = "report",
    github_token: Optional[str] = None,
    logger: Logger = None
) -> dict:


    writer = MetaWriter(path_root=path_root, logger=logger)
    output = writer.write(generated_files, action=action)
    output['metadata'] = metadata
    return output
