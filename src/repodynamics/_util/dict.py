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


def update_recursive(
    source: dict,
    add: dict,
    append_list: bool = True,
    append_dict: bool = True,
    raise_on_duplicated: bool = False,
    logger: Logger = None,
):
    def recursive(source, add, path=".", result=None, logger=None):
        for key, value in add.items():
            fullpath = f"{path}{key}"
            if key not in source:
                result.append(f"{logger.emoji['success']} Added new key '{fullpath}'")
                source[key] = value
                continue
            if type(source[key]) != type(value):
                result.append(
                    f"{logger.emoji['error']} Type mismatch: "
                    f"Key '{fullpath}' has type '{type(source[key])}' in 'source' "
                    f"but '{type(value)}' in 'add'."
                )
                logger.error(log_title, result)
            if not isinstance(value, (list, dict)):
                if raise_on_duplicated:
                    result.append(
                        f"{logger.emoji['error']} Duplicated: "
                        f"Key '{fullpath}' with type '{type(value)}' already exists in 'source'."
                    )
                    logger.error(log_title, result)
                result.append(f"{logger.emoji['skip']} Ignored key '{key}' with type '{type(value)}'")
            elif isinstance(value, list):
                if append_list:
                    for elem in value:
                        if elem not in source[key]:
                            source[key].append(elem)
                            result.append(f"{logger.emoji['success']} Appended to list '{fullpath}'")
                        else:
                            result.append(f"{logger.emoji['skip']} Ignored duplicate in list '{fullpath}'")
                elif raise_on_duplicated:
                    result.append(
                        f"{logger.emoji['error']} Duplicated: "
                        f"Key '{fullpath}' with type 'list' already exists in 'source'."
                    )
                    logger.error(log_title, result)
                else:
                    result.append(f"{logger.emoji['skip']} Ignored key '{fullpath}' with type 'list'")
            else:
                if append_dict:
                    recursive(source[key], value, f"{fullpath}.", result=result, logger=logger)
                elif raise_on_duplicated:
                    result.append(
                        f"{logger.emoji['error']} Duplicated: "
                        f"Key '{fullpath}' with type 'dict' already exists in 'source'."
                    )
                    logger.error(log_title, result)
                else:
                    result.append(f"{logger.emoji['skip']} Ignored key '{fullpath}' with type 'dict'")
        return result

    logger = logger or Logger()
    log_title = "Update dictionary recursively"
    result = recursive(source, add, result=[], logger=logger)
    logger.success(log_title, result)
    return result


def fill_template(templated_data: dict | list | str | bool | int | float, metadata: dict):
    return _DictFiller(templated_data=templated_data, metadata=metadata).fill()


class _DictFiller:
    def __init__(self, templated_data: dict | list | str | bool | int | float, metadata: dict):
        self._data = templated_data
        self._meta = metadata
        return

    def fill(self):
        return self._recursive_subst(self._data)

    def _recursive_subst(self, value):
        if isinstance(value, str):
            match_whole_str = re.match(r"^\${{([\w\.\:\-\[\] ]+)}}$", value)
            if match_whole_str:
                return self._substitute_val(match_whole_str.group(1))
            return re.sub(r"\${{([\w\.\:\-\[\] ]+?)}}", lambda x: str(self._substitute_val(x.group(1))), value)
        if isinstance(value, list):
            return [self._recursive_subst(elem) for elem in value]
        elif isinstance(value, dict):
            new_dict = {}
            for key, val in value.items():
                key_filled = self._recursive_subst(key)
                new_dict[key_filled] = self._recursive_subst(val)
            return new_dict
        return value

    def _substitute_val(self, match):
        def recursive_retrieve(obj, address):
            if len(address) == 0:
                return self._recursive_subst(obj)
            curr_add = address.pop(0)
            try:
                next_layer = obj[curr_add]
            except (TypeError, KeyError, IndexError) as e:
                try:
                    next_layer = self._recursive_subst(obj)[curr_add]
                except (TypeError, KeyError, IndexError) as e2:
                    raise KeyError(f"Object '{obj}' has no element '{curr_add}'") from e
            return recursive_retrieve(next_layer, address)

        parsed_address = []
        for add in match.strip().split("."):
            name = re.match(r"^([^[]+)", add).group()
            indices = re.findall(r"\[([^]]+)]", add)
            parsed_address.append(name)
            parsed_ind = []
            for idx in indices:
                if ":" not in idx:
                    parsed_ind.append(int(idx))
                else:
                    slice_ = [int(i) if i else None for i in idx.split(":")]
                    parsed_ind.append(slice(*slice_))
            parsed_address.extend(parsed_ind)
        return recursive_retrieve(self._meta, address=parsed_address)


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
