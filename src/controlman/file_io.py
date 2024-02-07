from pathlib import Path
from typing import Literal, Type
from types import ModuleType as _ModuleType
from importlib.resources import files
import inspect
import shutil
import importlib.util as _importlib_util
import sys as _sys

import jsonschema
import pyserials
from loggerman import logger as _logger


def read_datafile(
    path_data: str | Path,
    relpath_schema: str = "",
    root_type: Type[dict | list] = dict,
    extension: Literal["json", "yaml", "toml"] | None = None,
    log_section_title: str = "Read Datafile",
) -> dict | list:
    _logger.section(log_section_title)
    path_data = Path(path_data).resolve()
    _logger.info("Path", path_data)
    _logger.info("Root Type", root_type.__name__)
    file_exists = path_data.is_file()
    _logger.info("File Exists", file_exists)
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
                _logger.info("File is empty.")
                content = root_type()
            if not isinstance(content, root_type):
                _logger.critical(
                    f"Invalid datafile at {path_data}",
                    f"Expected a {root_type.__name__}, but got {type(content).__name__}.",
                    code_title="Content",
                    code=content,
                )
                # This will never be reached, but is required to satisfy the type checker and IDE.
                raise TypeError()
    if relpath_schema:
        validate_data(data=content, schema_relpath=relpath_schema)
    _logger.info(f"Successfully read data file at '{path_data}'.")
    _logger.debug("Content:", code=str(content))
    _logger.section_end()
    return content


@_logger.sectioner("Validate Datafile Against Schema")
def validate_data(data: dict | list, schema_relpath: str) -> None:
    pyserials.validate.jsonschema(
        data=data,
        schema=_get_schema(rel_path=schema_relpath),
        validator=jsonschema.Draft202012Validator,
        fill_defaults=True,
    )
    _logger.info(f"Successfully validated data against schema at '{schema_relpath}'.")
    return


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


def import_module(name: str, path: str | Path) -> _ModuleType:
    """Import a Python source file directly from a path.

    Parameters
    ----------
    name : str
        Name of the module to import.
    path : str | Path
        Path to the Python source file.

    References
    ----------
    - [Python Documentation](https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly)
    """
    spec = _importlib_util.spec_from_file_location(name=name, location=path)
    module = _importlib_util.module_from_spec(spec)
    _sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _get_schema(rel_path: str) -> dict:
    schema_raw = get_package_datafile(f"schema/{rel_path}.yaml")
    schema = pyserials.read.yaml_from_string(data=schema_raw, safe=True)
    return schema

