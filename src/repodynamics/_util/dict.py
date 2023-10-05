import re
import json
from pathlib import Path
from typing import Optional

from ruamel.yaml import YAML, YAMLError

from repodynamics.logger import Logger


def read(
    path: str | Path,
    schema: Optional[str | Path | dict] = None,
    raise_missing: bool = False,
    raise_empty: bool = False,
    logger: Optional[Logger] = None
) -> dict | list | None:
    logger = logger or Logger()
    path = Path(path).resolve()
    logger.info(f"Read data file from '{path}'")
    if not path.is_file():
        if raise_missing:
            logger.error(f"No file exists at '{path}'.")
        return
    if path.read_text().strip() == "":
        if raise_empty:
            logger.error(f"File at '{path}' is empty.")
        return
    extension = path.suffix.removeprefix(".")
    match extension:
        case "json":
            content = _read_json(path=path, logger=logger)
        case "yaml", "yml":
            content = _read_yaml(path=path, logger=logger)
        case "toml":
            content = read_toml(path=path, logger=logger)
        case _:
            logger.error(f"Unsupported file extension '{extension}'.")
    logger.success(
        f"Data file successfully read from '{path}'", json.dumps(content, indent=3)
    )
    if not schema:
        return content
    if not isinstance(schema, dict):
        logger.info(f"Read schema from '{schema}'")
        schema = read(path=schema, logger=logger)
    try:
        jsonschema.validate(instance=content, schema=schema)
    except jsonschema.exceptions.ValidationError as e:
        self.logger.error(
            f"Schema validation failed for YAML file '{path}': {e.message}.", traceback.format_exc()
        )
    self.logger.success(f"Schema validation successful.")
    return content


def _read_yaml(path: str | Path, logger: Optional[Logger] = None):
    try:
        content = YAML(typ="safe").load(Path(path))
    except YAMLError as e:
        logger.error(f"Invalid YAML at '{path}': {e}.", traceback.format_exc())
    return content


def _read_json(path: str | Path, logger: Optional[Logger] = None):
    try:
        content = json.load(Path(path))
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
    logger: Logger = None
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
            match_whole_str = re.match(r"^\${{([^{}]+)}}$", value)
            if match_whole_str:
                return self._substitute_val(match_whole_str.group(1))
            return re.sub(r"{{{(.*?)}}}", lambda x: str(self._substitute_val(x.group(1))), value)
        if isinstance(value, list):
            for idx, elem in enumerate(value):
                value[idx] = self._recursive_subst(elem)
        elif isinstance(value, dict):
            for key, val in value.items():
                key_filled = self._recursive_subst(key)
                if key_filled == key:
                    value[key] = self._recursive_subst(val)
                else:
                    value[key_filled] = self._recursive_subst(value.pop(key))
        return value

    def _substitute_val(self, match):

        def recursive_retrieve(obj, address):
            if len(address) == 0:
                return obj
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
        return recursive_retrieve(self._data, address=parsed_address)