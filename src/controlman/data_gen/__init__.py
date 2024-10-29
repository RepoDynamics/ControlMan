from gittidy import Git as _Git
from pylinks.api import GitHub as _GitHubAPI
from pyserials.nested_dict import NestedDict as _NestedDict

import controlman as _controlman
from controlman import const as _const
from controlman.cache_manager import CacheManager as _CacheManager
from controlman.data_gen.main import MainDataGenerator as _MainDataGenerator
from controlman.data_gen.python import PythonDataGenerator as _PythonDataGenerator
from controlman.data_gen.repo import RepoDataGenerator as _RepoDataGenerator


def generate(
    git_manager: _Git,
    cache_manager: _CacheManager,
    github_api: _GitHubAPI,
    data: _NestedDict,
    data_before: _NestedDict,
    data_main: _NestedDict,
    future_versions: dict[str, str],
) -> _NestedDict:
    _MainDataGenerator(
        data=data,
        cache_manager=cache_manager,
        git_manager=git_manager,
        github_api=github_api,
    ).generate()
    if not data_main:
        curr_branch, other_branches = git_manager.get_all_branch_names()
        main_branch = data["repo.default_branch"]
        if curr_branch == main_branch:
            data_main = data_before or data
        else:
            git_manager.fetch_remote_branches_by_name(main_branch)
            git_manager.stash()
            git_manager.checkout(main_branch)
            if (git_manager.repo_path / _const.FILEPATH_METADATA).is_file():
                data_main = _controlman.from_json_file(repo_path=git_manager.repo_path)
            else:
                data_main = data_before or data
            git_manager.checkout(curr_branch)
            git_manager.stash_pop()
    if data.get("pkg"):
        _PythonDataGenerator(
            data=data,
            git_manager=git_manager,
            cache=cache_manager,
            github_api=github_api,
        ).generate()
    _RepoDataGenerator(
        data=data,
        git_manager=git_manager,
        data_main=data_main,
        future_versions=future_versions,
    ).generate()
    return data
