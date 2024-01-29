from actionman.logger import Logger

from repodynamics.datatype import DynamicFile
from repodynamics.control.content import ControlCenterContentManager
from repodynamics.path import PathManager
from repodynamics.control.files.generator.readme.main import ReadmeFileGenerator
from repodynamics.control.files.generator.readme.pypackit_default import PypackitDefaultReadmeFileGenerator


_THEME_GENERATOR = {
    "pypackit-default": PypackitDefaultReadmeFileGenerator,
}


def generate(
    content_manager: ControlCenterContentManager,
    path_manager: PathManager,
    logger: Logger,
) -> list[tuple[DynamicFile, str]]:
    out = ReadmeFileGenerator(ccm=content_manager, path=path_manager, logger=logger).generate()
    if content_manager["readme"]["repo"]:
        theme = content_manager["readme"]["repo"]["theme"]
        out.extend(_THEME_GENERATOR[theme](ccm=content_manager, path=path_manager, target="repo", logger=logger).generate())
    if content_manager["readme"]["package"]:
        theme = content_manager["readme"]["package"]["theme"]
        out.extend(_THEME_GENERATOR[theme](ccm=content_manager, path=path_manager, target="package", logger=logger).generate())
    return out
