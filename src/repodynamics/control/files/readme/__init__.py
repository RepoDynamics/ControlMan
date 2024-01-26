from repodynamics.datatype import DynamicFile
from repodynamics.control.manager import MetaManager
from repodynamics.path import PathManager
from repodynamics.logger import Logger
from repodynamics.control.files.readme.main import ReadmeFileGenerator
from repodynamics.control.files.readme.pypackit_default import PypackitDefaultReadmeFileGenerator


_THEME_GENERATOR = {
    "pypackit-default": PypackitDefaultReadmeFileGenerator,
}


def generate(
    ccm: MetaManager,
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
