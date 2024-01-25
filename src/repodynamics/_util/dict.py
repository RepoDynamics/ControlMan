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


def validate_schema(source: dict | list, schema: str | Path | dict, logger: Optional[Logger] = None):
    logger = logger or Logger()
    if not isinstance(schema, dict):
        path_schema = Path(schema).resolve()
        logger.info(f"Read schema from '{path_schema}'")
        schema = read(path=path_schema, logger=logger)

    try:
        _JSONSCHEMA_VALIDATOR(schema).validate(source)
    except jsonschema.exceptions.ValidationError as e:
        logger.error(f"Schema validation failed: {e.message}.", traceback.format_exc())
    logger.success(f"Schema validation successful.")
    return


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


def extend_with_default(validator_class):
    # https://python-jsonschema.readthedocs.io/en/stable/faq/#why-doesn-t-my-schema-s-default-property-set-the-default-on-my-instance

    validate_properties = validator_class.VALIDATORS["properties"]

    def set_defaults(validator, properties, instance, schema):
        for property, subschema in properties.items():
            if "default" in subschema:
                instance.setdefault(property, subschema["default"])

        for error in validate_properties(
            validator,
            properties,
            instance,
            schema,
        ):
            yield error

    return jsonschema.validators.extend(
        validator_class,
        {"properties": set_defaults},
    )


_JSONSCHEMA_VALIDATOR = extend_with_default(jsonschema.Draft202012Validator)
