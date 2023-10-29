from importlib.resources import files
from pathlib import Path
import inspect
import shutil


def datafile(filepath: str, dirname: str = "_data") -> Path:
    """
    Get the path to a data file included in the caller's package or any of its parent packages.

    Parameters
    ----------
    filepath : str
        The relative path of the data file (from `dirname`) to get the path to.
    dirname: str
        The name of the directory in the package containing the data file.
    """

    def recursive_search(path):
        full_filepath = path / dirname / filepath
        if full_filepath.exists():
            return full_filepath
        if path == path_root:
            raise FileNotFoundError(
                f"File '{filepath}' not found in '{caller_package_name}' or any of its parent packages."
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
    return recursive_search(files(caller_package_name))


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
