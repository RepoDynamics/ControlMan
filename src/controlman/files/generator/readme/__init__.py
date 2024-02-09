from controlman.datatype import DynamicFile
from controlman import ControlCenterContentManager
from controlman._path_manager import PathManager
from controlman.files.generator.readme.main import ReadmeFileGenerator
from controlman.files.generator.readme.pypackit_default import PyPackITDefaultReadmeFileGenerator


_THEME_GENERATOR = {
    "pypackit-default": PyPackITDefaultReadmeFileGenerator,
}


def generate(
    content_manager: ControlCenterContentManager,
    path_manager: PathManager,
) -> list[tuple[DynamicFile, str]]:
    out = ReadmeFileGenerator(
        content_manager=content_manager, path_manager=path_manager, target="repo"
    ).generate()
    if content_manager["readme"]["repo"]:
        theme = content_manager["readme"]["repo"]["theme"]
        out.extend(_THEME_GENERATOR[theme](
            content_manager=content_manager, path_manager=path_manager, target="repo"
        ).generate())
    if content_manager["readme"]["package"]:
        theme = content_manager["readme"]["package"]["theme"]
        out.extend(_THEME_GENERATOR[theme](
            content_manager=content_manager, path_manager=path_manager, target="package"
        ).generate())
    return out
