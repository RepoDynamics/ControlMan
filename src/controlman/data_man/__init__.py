from pathlib import Path as _Path

from controlman import const as _const
from controlman import protocol, _util
from controlman.nested_dict import NestedDict as _NestedDict
from controlman.data_man.manager import DataManager
from controlman.data_man.validator import DataValidator


def from_json_file(
    repo_path: str | _Path,
    filepath: str = _const.FILEPATH_METADATA,
    validate: bool = True,
) -> DataManager:
    """Load control center data from the full JSON file.

    Parameters
    ----------
    repo_path : str | _Path
        Path to the repository root.
    filepath : str, default: controlman.const.FILEPATH_METADATA
        Relative path to the JSON file in the repository.
    validate : bool, default: True
        Validate the data against the schema.

    Raises
    ------
    controlman.exception.ControlManFileReadError
        If the file cannot be read.
    """
    data_dict = _util.file.read_data_from_file(
        path=_Path(repo_path) / filepath,
        base_path=repo_path,
        extension="json",
        raise_errors=True,
    )
    data = _NestedDict(data_dict)
    if validate:
        DataValidator(data=data).validate()
    return DataManager(data=data)


def from_json_file_at_commit(
    git_manager: protocol.Git,
    commit_hash: str,
    filepath: str = _const.FILEPATH_METADATA,
    validate: bool = True,
) -> DataManager | None:
    data_str = git_manager.file_at_hash(
        commit_hash=commit_hash,
        path=filepath,
    )
    return from_json_string(data=data_str, validate=validate)


def from_json_string(
    data: str,
    validate: bool = True,
) -> DataManager:
    """Load control center data from the full JSON string.

    Parameters
    ----------
    data : str
        JSON data string.
    validate : bool, default: True
        Validate the data against the schema.

    Raises
    ------
    controlman.exception.ControlManFileReadError
        If the data cannot be read.
    """
    data_dict = _util.file.read_datafile_from_string(
        data=data,
        extension="json",
        raise_errors=True,
    )
    data = _NestedDict(data_dict)
    if validate:
        DataValidator(data=data).validate()
    return DataManager(data=data)
