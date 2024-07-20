from pathlib import Path
from typing import Literal, Type
from types import ModuleType as _ModuleType

import fileex as _fileex
import pkgdata as _pkgdata
import pyserials
from loggerman import logger as _logger

from controlman import exception as _exception
from controlman.data_man.manager import DataManager
from controlman import const
from controlman.nested_dict import NestedDict as _NestedDict
from controlman.center_man.cache import CacheManager as _CacheManager
from controlman import _util as _util


_data_dir_path = _pkgdata.get_package_path_from_caller(top_level=True) / "_data"


def read_data_from_file(
    path: Path | str,
    base_path: Path | str | None = None,
    extension: Literal["json", "yaml", "toml"] | None = None,
    raise_errors: bool = True,
) -> dict | None:
    try:
        data = pyserials.read.from_file(
            path=path,
            data_type=extension,
            json_strict=True,
            yaml_safe=True,
            toml_as_dict=False,
        )
    except pyserials.exception.read.PySerialsReadException as e:
        if raise_errors:
            raise _exception.ControlManFileReadError(
                path=Path(path).relative_to(base_path) if base_path else path,
                data=getattr(e, "data", None),
            ) from e
        return
    if not isinstance(data, dict):
        if raise_errors:
            raise _exception.ControlManFileDataTypeError(
                expected_type=dict,
                path=Path(path).relative_to(base_path) if base_path else path,
                data=data,
            )
        return
    return data


def read_datafile_from_string(
    data: str,
    extension: Literal["json", "yaml", "toml"],
    raise_errors: bool = True,
) -> dict | None:
    try:
        data = pyserials.read.from_string(
            data=data,
            data_type=extension,
            json_strict=True,
            yaml_safe=True,
            toml_as_dict=False,
        )
    except pyserials.exception.read.PySerialsReadException as e:
        if raise_errors:
            raise _exception.ControlManFileReadError(data=data) from e
        return
    if not isinstance(data, dict):
        if raise_errors:
            raise _exception.ControlManFileDataTypeError(
                expected_type=dict,
                data=data,
            )
        return
    return data


def read_control_center_file(
    path: Path | str,
    cache_manager: _CacheManager,
    tag_name: str = u"!ext",
):
    return pyserials.read.yaml_from_file(
        path=path,
        safe=True,
        constructors={
            tag_name: _util.yaml.create_external_tag_constructor(
                tag_name=tag_name,
                cache_manager=cache_manager
            )
        },
    )

def get_package_datafile(path: str) -> str | dict | list:
    """
    Get a data file in the package's '_data' directory.

    Parameters
    ----------
    path : str
        The path of the data file relative to the package's '_data' directory.
    """
    full_path = _data_dir_path / path
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






