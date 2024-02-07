from actionman.logger import Logger

from controlman.datatype import DynamicFile
from controlman.control.content import ControlCenterContentManager
from controlman.path import PathManager
from controlman.control.files.generator.readme.main import ReadmeFileGenerator
from controlman.control.files.generator.readme.pypackit_default import PyPackITDefaultReadmeFileGenerator


_THEME_GENERATOR = {
    "pypackit-default": PyPackITDefaultReadmeFileGenerator,
}


def generate(
    content_manager: ControlCenterContentManager,
    path_manager: PathManager,
    logger: Logger,
) -> list[tuple[DynamicFile, str]]:
    out = ReadmeFileGenerator(
        content_manager=content_manager, path_manager=path_manager, target="repo", logger=logger
    ).generate()
    if content_manager["readme"]["repo"]:
        theme = content_manager["readme"]["repo"]["theme"]
        out.extend(_THEME_GENERATOR[theme](
            content_manager=content_manager, path_manager=path_manager, target="repo", logger=logger
        ).generate())
    if content_manager["readme"]["package"]:
        theme = content_manager["readme"]["package"]["theme"]
        out.extend(_THEME_GENERATOR[theme](
            content_manager=content_manager, path_manager=path_manager, target="package", logger=logger
        ).generate())
    return out
