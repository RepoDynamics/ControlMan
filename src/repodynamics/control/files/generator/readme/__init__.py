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
    ccm: ControlCenterContentManager,
    path: PathManager,
    logger: Logger = None,
) -> list[tuple[DynamicFile, str]]:
    out = ReadmeFileGenerator(ccm=ccm, path=path, logger=logger).generate()
    if ccm["readme"]["repo"]:
        theme = ccm["readme"]["repo"]["theme"]
        out.extend(_THEME_GENERATOR[theme](ccm=ccm, path=path, target="repo", logger=logger).generate())
    if ccm["readme"]["package"]:
        theme = ccm["readme"]["package"]["theme"]
        out.extend(_THEME_GENERATOR[theme](ccm=ccm, path=path, target="package", logger=logger).generate())
    return out
