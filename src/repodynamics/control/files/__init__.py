import json
import shutil
from actionman.log import Logger

from repodynamics.datatype import DynamicFile, Diff, DynamicFileChangeType
from repodynamics.control.content import ControlCenterContentManager
from repodynamics.path import PathManager
from repodynamics.control.files import package
from repodynamics.control.files import readme
from repodynamics.control.files.forms import FormGenerator
from repodynamics.control.files.config import ConfigFileGenerator
from repodynamics.control.files.health import HealthFileGenerator


def generate(
    content_manager: ControlCenterContentManager,
    path_manager: PathManager,
    logger: Logger,
) -> list[tuple[DynamicFile, str]]:
    generated_files = [
        (path_manager.metadata, json.dumps(content_manager.as_dict)),
        (path_manager.license, content_manager["license"].get("text", "")),
    ]

    generated_files += ConfigFileGenerator(
        metadata=content_manager, output_path=path_manager, logger=logger
    ).generate()

    generated_files += FormGenerator(
        metadata=content_manager, output_path=path_manager, logger=logger
    ).generate()

    generated_files += HealthFileGenerator(
        metadata=content_manager, output_path=path_manager, logger=logger
    ).generate()

    generated_files += package.generate(
        metadata=content_manager,
        paths=path_manager,
        logger=logger,
    )

    generated_files += readme.generate(ccm=content_manager, path=path_manager, logger=logger)
    return generated_files


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
