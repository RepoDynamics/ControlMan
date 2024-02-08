from pathlib import Path as _Path
import shutil as _shutil
from actionman.logger import Logger as _Logger

from controlman.datatype import (
    Diff as _Diff,
    DynamicFile as _DynamicFile,
    DynamicFileType as _DynamicFileType,
    DynamicFileChangeType as _DynamicFileChangeType,
)
from controlman.control.content import ControlCenterContentManager as _ControlCenterContentManager
from controlman._path_manager import PathManager as _PathManager
from controlman.control.files import comparer as _comparer
from controlman.files import generator as _generator


def generate(
    content_manager: _ControlCenterContentManager,
    path_manager: _PathManager,
    logger: _Logger,
) -> list[tuple[_DynamicFile, str]]:
    return _generator.generate(
        content_manager=content_manager,
        path_manager=path_manager,
        logger=logger,
    )


def compare(
    generated_files: list[tuple[_DynamicFile, str]],
    path_repo: _Path,
    logger: _Logger,
) -> tuple[list[tuple[_DynamicFile, _Diff]], dict[_DynamicFileType, dict[str, bool]], str]:
    """Compare generated dynamic repository files to the current state of repository."""
    return _comparer.compare(generated_files=generated_files, path_root=path_repo, logger=logger)


def apply(results: list[tuple[_DynamicFile, _Diff]], logger: _Logger) -> None:
    """Apply changes to dynamic repository files."""
    def log():
        path_message = (
            f"{'from' if diff.status is _DynamicFileChangeType.REMOVED else 'at'} '{info.path}'"
            if not diff.path_before else f"from '{diff.path_before}' to '{info.path}'"
        )
        logger.info(
            title=f"{info.category.value}: {info.id}",
            message=f"{diff.status.value.emoji} {diff.status.value.title} {path_message}"
        )
        return

    logger.section("Apply Changes To Dynamic Repository File", group=True)
    for info, diff in results:
        if diff.status is _DynamicFileChangeType.REMOVED:
            _shutil.rmtree(info.path) if info.is_dir else info.path.unlink()
        elif diff.status is _DynamicFileChangeType.MOVED:
            diff.path_before.rename(info.path)
        elif info.is_dir:
            info.path.mkdir(parents=True, exist_ok=True)
        elif diff.status not in [_DynamicFileChangeType.DISABLED, _DynamicFileChangeType.UNCHANGED]:
            info.path.parent.mkdir(parents=True, exist_ok=True)
            if diff.status is _DynamicFileChangeType.MOVED_MODIFIED:
                diff.path_before.unlink()
            with open(info.path, "w") as f:
                f.write(f"{diff.after.strip()}\n")
        log()
    logger.section_end()
    return
