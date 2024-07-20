from loggerman import logger as _logger

from controlman.datatype import DynamicFile
from controlman import ControlCenterContentManager
from controlman._path_manager import PathManager
from controlman.file_gen.readme.main import ReadmeFileGenerator
from controlman.file_gen.readme.pypackit_default import PyPackITDefaultReadmeFileGenerator
from controlman.center_man.hook import HookManager as _ControlCenterCustomContentGenerator


_THEME_GENERATOR = {
    "pypackit-default": PyPackITDefaultReadmeFileGenerator,
}


def generate(
    content_manager: ControlCenterContentManager,
    path_manager: PathManager,
    custom_generator: _ControlCenterCustomContentGenerator
) -> list[tuple[DynamicFile, str]]:

    def gen_repo(name: str):
        if content_manager["readme"][name]:
            theme = content_manager["readme"][name]["type"]
            if theme == "manual":
                return [(path[name], content_manager["readme"][name]["config"])]
            if theme == "custom":
                file_content = custom_generator.generate(f"generate_{name}_readme", content_manager, path_manager)
                if file_content is None:
                    _logger.critical(f"Custom {name} README generator not found.")
                return [(path[name], file_content)]
            return _THEME_GENERATOR[theme](
                content_manager=content_manager, path_manager=path_manager, custom_generator=custom_generator, target=name
            ).generate()

    path = {
        "github": path_manager.readme_main,
        "pypi": path_manager.readme_pypi,
        "conda": path_manager.readme_conda,
    }
    out = ReadmeFileGenerator(
        content_manager=content_manager, path_manager=path_manager, custom_generator=custom_generator, target="github"
    ).generate()
    for repo_name in ["github", "pypi", "conda"]:
        out.extend(gen_repo(repo_name))
    return out
