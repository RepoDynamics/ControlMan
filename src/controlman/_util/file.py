from pathlib import Path
from typing import Literal, Type
from types import ModuleType as _ModuleType

import jsonschema
import fileex as _fileex
import pkgdata as _pkgdata
import pyserials
from loggerman import logger as _logger

from controlman import exception as _exception


def read_datafile(
    path_repo: str | Path,
    path_data: str,
    relpath_schema: str = "",
    root_type: Type[dict | list] = dict,
    extension: Literal["json", "yaml", "toml"] | None = None,
    log_section_title: str = "Read Datafile",
) -> dict | list:
    _logger.section(log_section_title)
    fullpath_data = Path(path_repo).resolve() / path_data
    _logger.info("Path", fullpath_data)
    _logger.info("Root Type", root_type.__name__)
    file_exists = fullpath_data.is_file()
    _logger.info("File Exists", file_exists)
    if not file_exists:
        content = root_type()
    else:
        raw_content = fullpath_data.read_text().strip()
        if raw_content == "":
            content = root_type()
        else:
            extension = extension or fullpath_data.suffix.removeprefix(".")
            if extension == "yml":
                extension = "yaml"
            try:
                content = pyserials.read.from_string(
                    data=raw_content,
                    data_type=extension,
                    json_strict=True,
                    yaml_safe=True,
                    toml_as_dict=False,
                )
            except pyserials.exception.read.PySerialsReadFromStringException as e:
                raise _exception.content.ControlManFileReadError(
                    relpath_data=path_data, data=raw_content
                ) from e
            if content is None:
                _logger.info("File is empty.")
                content = root_type()
            if not isinstance(content, root_type):
                raise _exception.content.ControlManFileDataTypeError(
                    relpath_data=path_data, data=content, expected_type=root_type
                )
    if relpath_schema:
        validate_data(data=content, schema_relpath=relpath_schema)
    _logger.info(f"Successfully read data file at '{fullpath_data}'.")
    _logger.debug("Content:", code=str(content))
    _logger.section_end()
    return content


@_logger.sectioner("Validate Datafile Against Schema")
def validate_data(
    data: dict | list,
    schema_relpath: str,
    datafile_ext: str = "yaml",
    is_dir: bool = False,
    has_extension: bool = False,
) -> None:
    schema = get_package_datafile(f"schema/{schema_relpath}.yaml")
    try:
        pyserials.validate.jsonschema(
            data=data,
            schema=schema,
            validator=jsonschema.Draft202012Validator,
            fill_defaults=True,
            raise_invalid_data=True,
        )
    except pyserials.exception.validate.PySerialsSchemaValidationError as e:
        raise _exception.content.ControlManSchemaValidationError(
            rel_path=schema_relpath,
            file_ext=datafile_ext,
            is_dir=is_dir,
            has_extension=has_extension,
        ) from e
    _logger.info(f"Successfully validated data against schema '{schema_relpath}'.")
    return


def get_package_datafile(path: str) -> str | dict | list:
    """
    Get a data file in the package's '_data' directory.

    Parameters
    ----------
    path : str
        The path of the data file relative to the package's '_data' directory.
    """
    full_path = _pkgdata.get_package_path_from_caller(top_level=True) / "_data" / path
    data = full_path.read_text()
    if full_path.suffix == ".yaml":
        return pyserials.read.yaml_from_string(data=data, safe=True)
    return data


def delete_dir_content(path: str | Path, exclude: list[str] = None, raise_existence: bool = True):
    """
    Delete all files and directories within a given directory,
    excluding those specified by `exclude`.

    Parameters
    ----------
    path : str | pathlib.Path
        Path to the directory whose content should be deleted.
    exclude : list[str] | None, default: None
        List of file and directory names to exclude from deletion.
    raise_existence : bool, default: True
        Raise an error when the directory does not exist.
    """
    _fileex.directory.delete_contents(path=path, exclude=exclude, raise_existence=raise_existence)
    return


def import_module_from_path(path: str | Path) -> _ModuleType:
    """Import a Python module from a local path.

    Parameters
    ----------
    path : str | Path
        Local path to the module.
        If the path corresponds to a directory,
        the '__init__.py' file in the directory is imported.

    Returns
    -------
    module : types.ModuleType
        The imported module.
    """
    return _pkgdata.import_module_from_path(path=path)
