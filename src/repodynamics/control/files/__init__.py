from pathlib import Path
import shutil
from actionman.logger import Logger

from repodynamics.datatype import DynamicFile, Diff, DynamicFileChangeType, DynamicFileType
from repodynamics.control.content import ControlCenterContentManager
from repodynamics.path import PathManager
from repodynamics.control.files import generator
from repodynamics.control.files.comparer import FileComparer


def generate(
    content_manager: ControlCenterContentManager,
    path_manager: PathManager,
    logger: Logger,
) -> list[tuple[DynamicFile, str]]:
    return generator.generate(
        content_manager=content_manager,
        path_manager=path_manager,
        logger=logger,
    )


def compare(
    generated_files: list[tuple[DynamicFile, str]],
    path_root: Path,
    logger: Logger,
) -> tuple[list[tuple[DynamicFile, Diff]], dict[DynamicFileType, dict[str, bool]], str]:
    return FileComparer(path_root=path_root, logger=logger).compare(updates=generated_files)


def apply(results: list[tuple[DynamicFile, Diff]]):
    for info, diff in results:
        if diff.status in [DynamicFileChangeType.DISABLED, DynamicFileChangeType.UNCHANGED]:
            continue
        if diff.status == DynamicFileChangeType.REMOVED:
            shutil.rmtree(info.path) if info.is_dir else info.path.unlink()
            continue
        if diff.status == DynamicFileChangeType.MOVED:
            diff.path_before.rename(info.path)
            continue
        if info.is_dir:
            info.path.mkdir(parents=True, exist_ok=True)
        else:
            info.path.parent.mkdir(parents=True, exist_ok=True)
            if diff.status == DynamicFileChangeType.MOVED_MODIFIED:
                diff.path_before.unlink()
            with open(info.path, "w") as f:
                f.write(f"{diff.after.strip()}\n")
    return
