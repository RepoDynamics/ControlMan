import re
import json
from pathlib import Path
from typing import Optional, Literal
import traceback

import tomlkit
from ruamel.yaml import YAML, YAMLError
import jsonschema

from repodynamics.logger import Logger


def read(
    path: str | Path,
    schema: Optional[str | Path | dict] = None,
    raise_missing: bool = False,
    raise_empty: bool = False,
    root_type: Literal["dict", "list"] = "dict",
    extension: Optional[Literal["json", "yaml", "toml"]] = None,
    logger: Optional[Logger] = None,
) -> dict | list:
    logger = logger or Logger()
    path = Path(path).resolve()
    logger.info(f"Read data file from '{path}'")
    if not path.is_file():
        if raise_missing:
            logger.error(f"No file exists at '{path}'.")
        content = {} if root_type == "dict" else []
    elif path.read_text().strip() == "":
        if raise_empty:
            logger.error(f"File at '{path}' is empty.")
        content = {} if root_type == "dict" else []
    else:
        extension = extension or path.suffix.removeprefix(".")
        match extension:
            case "json":
                content = _read_json(path=path, logger=logger)
            case "yaml" | "yml":
                content = _read_yaml(path=path, logger=logger)
            case "toml":
                content = _read_toml(path=path, logger=logger)
            case _:
                logger.error(f"Unsupported file extension '{extension}'.")
        if content is None:
            content = {} if root_type == "dict" else []
        if not isinstance(content, (dict, list)):
            logger.error(
                f"Invalid datafile.", f"Expected a dict, but '{path}' had:\n{json.dumps(content, indent=3)}"
            )
    if schema:
        validate_schema(source=content, schema=schema, logger=logger)
    logger.success(f"Data file successfully read from '{path}'", json.dumps(content, indent=3))
    return content


def _read_yaml(path: str | Path, logger: Optional[Logger] = None):
    try:
        content = YAML(typ="safe").load(Path(path))
    except YAMLError as e:
        logger.error(f"Invalid YAML at '{path}': {e}.", traceback.format_exc())
    return content


def _read_json(path: str | Path, logger: Optional[Logger] = None):
    try:
        content = json.loads(Path(path).read_text())
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON at '{path}': {e}.", traceback.format_exc())
    return content


def _read_toml(path: str | Path, logger: Optional[Logger] = None):
    try:
        content = tomlkit.loads(Path(path).read_text())
    except tomlkit.exceptions.TOMLKitError as e:
        logger.error(f"Invalid TOML at '{path}': {e}.", traceback.format_exc())
    return content
