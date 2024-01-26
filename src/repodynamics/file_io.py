from pathlib import Path
from typing import Literal, Type
from importlib.resources import files
import inspect
import shutil

import jsonschema
import pyserials


def read_datafile(
    path_data: str | Path,
    relpath_schema: str = "",
    root_type: Type[dict | list] = dict,
    extension: Literal["json", "yaml", "toml"] | None = None,
) -> dict | list:
    log = []
    path_data = Path(path_data).resolve()
    log.append(f"Path: {path_data}")
    file_exists = path_data.is_file()
    log.append(f"File Exists: {file_exists}")
    if not file_exists:
        content = root_type()
    else:
        raw_content = path_data.read_text().strip()
        if raw_content == "":
            content = root_type()
        else:
            extension = extension or path_data.suffix.removeprefix(".")
            if extension == "yml":
                extension = "yaml"
            content = pyserials.read.from_string(
                data=raw_content,
                data_type=extension,
                json_strict=True,
                yaml_safe=True,
                toml_as_dict=False,
            )
            if content is None:
                content = root_type()
            if not isinstance(content, root_type):
                logger.error(
                    f"Invalid datafile.", f"Expected a dict, but '{path_data}' had:\n{json.dumps(content, indent=3)}"
                )
    if relpath_schema:
        validate_data(data=content, schema_relpath=relpath_schema)
    logger.success(f"Data file successfully read from '{path_data}'", json.dumps(content, indent=3))
    return content


def validate_data(data: dict | list, schema_relpath: str) -> None:
    pyserials.validate.jsonschema(
        data=data,
        schema=get_schema(rel_path=schema_relpath),
        validator=jsonschema.Draft202012Validator,
        fill_defaults=True,
    )
    return


def get_schema(rel_path: str) -> dict:
    schema_raw = get_package_datafile(f"schema/{rel_path}.yaml")
    schema = pyserials.read.yaml_from_string(data=schema_raw, safe=True)
    return schema


def get_package_datafile(
    relative_filepath: str, dirname: str = "_data", return_content: bool = True
) -> str | Path:
    """
    Get the path to a data file included in the caller's package or any of its parent packages.

    Parameters
    ----------
    relative_filepath : str
        The relative path of the data file (from `dirname`) to get the path to.
    dirname: str
        The name of the directory in the package containing the data file.
    """

    def recursive_search(path):
        full_filepath = path / dirname / relative_filepath
        if full_filepath.exists():
            return full_filepath
        if path == path_root:
            raise FileNotFoundError(
                f"File '{relative_filepath}' not found in '{caller_package_name}' or any of its parent packages."
            )
        return recursive_search(path.parent)

    # Get the caller's frame
    caller_frame = inspect.stack()[1]
    # Get the caller's package name from the frame
    if caller_frame.frame.f_globals["__package__"] is None:
        raise ValueError(
            f"Cannot determine the package name of the caller '{caller_frame.frame.f_globals['__name__']}'."
        )
    caller_package_name = caller_frame.frame.f_globals["__package__"]
    main_package_name = caller_package_name.split(".")[0]
    path_root = files(main_package_name)
    path_datafile = recursive_search(files(caller_package_name)).resolve()
    return path_datafile.read_text() if return_content else path_datafile


def delete_dir_content(path: str | Path, exclude: list[str] = None, missing_ok: bool = False):
    """
    Delete all files and directories in a directory, excluding those specified by `exclude`.

    Parameters
    ----------
    path : Path
        Path to the directory whose content should be deleted.
    exclude : list[str], default: None
        List of file and directory names to exclude from deletion.
    missing_ok : bool, default: False
        If True, do not raise an error when the directory does not exist,
        otherwise raise a `NotADirectoryError`.
    """
    path = Path(path)
    if not path.is_dir():
        if missing_ok:
            return
        raise NotADirectoryError(f"Path '{path}' is not a directory.")
    for item in path.iterdir():
        if item.name in exclude:
            continue
        if item.is_file():
            item.unlink()
        elif item.is_dir():
            shutil.rmtree(item)
    return
