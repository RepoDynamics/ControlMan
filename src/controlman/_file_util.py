from pathlib import Path
from typing import Literal

import pkgdata as _pkgdata
import pyserials

from controlman import exception as _exception


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
