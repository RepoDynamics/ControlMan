from repodynamics.datatype import DynamicFile
from repodynamics.meta.manager import MetaManager
from repodynamics.path import PathFinder
from repodynamics.logger import Logger
from repodynamics.meta.files.readme.main import ReadmeFileGenerator
from repodynamics.meta.files.readme.pypackit_default import PypackitDefaultReadmeFileGenerator


_THEME_GENERATOR = {
    "pypackit-default": PypackitDefaultReadmeFileGenerator,
}


def generate(
    ccm: MetaManager,
    path: PathFinder,
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
