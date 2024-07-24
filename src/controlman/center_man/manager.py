import copy as _copy
from pathlib import Path as _Path
import shutil as _shutil

from versionman import PEP440SemVer as _PEP440SemVer
from loggerman import logger as _logger
import pylinks as _pylinks

from controlman.center_man.file_comparer import FileComparer as _FileComparer

from controlman.data_man.manager import DataManager as _DataManager
from controlman.data_man.validator import DataValidator as _DataValidator
from controlman import data_gen as _data_gen
from controlman.center_man.hook import HookManager as _HookManager
from controlman.datatype import (
    DynamicFile as _DynamicFile,
    Diff as _Diff,
    DynamicFileType as _DynamicFileType,
    DynamicFileChangeType as _DynamicFileChangeType,
)
from controlman.protocol import Git as _Git
import controlman
from controlman import const
from controlman import _util
from controlman import exception as _exception
from controlman.center_man.cache import CacheManager
from controlman.nested_dict import NestedDict as _NestedDict


class CenterManager:

    def __init__(
        self,
        git_manager: _Git,
        github_token: str | None = None,
        data_main: _DataManager | dict | None = None,
        future_versions: dict[str, str | _PEP440SemVer] | None = None,
        control_center_path: _Path | str | None = None,
    ):
        self._git = git_manager
        self._github_api = _pylinks.api.github(token=github_token)
        self._data_main = data_main
        self._future_vers = future_versions or {}
        self._path_cc = control_center_path
        self._path_root = self._git.repo_path

        self._data_before: _NestedDict | None = None
        self._hook_manager: _HookManager | None = None
        self._cache_manager: CacheManager | None = None
        self._contents_raw: _NestedDict | None = None
        self._local_config: dict = {}
        self._ccm: _DataManager | None = None
        self._generated_files: list[tuple[_DynamicFile, str]] = []
        self._results: list[tuple[_DynamicFile, _Diff]] = []
        self._changes: dict[_DynamicFileType, dict[str, bool]] = {}
        self._summary: str = ""
        return

    def load(self) -> _NestedDict:
        if self._contents_raw:
            return self._contents_raw
        if not self._path_cc:
            self._data_before = controlman.data_man.from_json_file(repo_path=self._path_root).ndict
            self._path_cc = self._path_root / self._data_before["dir.control"]
            cache_retention_hours = self._data_before["control.cache.retention_hours"]
        else:
            self._data_before = _NestedDict(data={})
            self._path_cc = self._path_root / self._path_cc
            cache_retention_hours = {k: 0 for k in ("extension", "repo", "user", "orcid", "doi", "python")}
        self._hook_manager = _HookManager(
            dir_path=self._path_root / self._path_cc / const.DIRNAME_CC_HOOK
        )
        self._cache_manager = CacheManager(
            path_repo=self._path_root,
            retention_hours=cache_retention_hours,
        )
        full_data = {}
        for filepath in self._path_cc.glob('*'):
            if filepath.is_file() and filepath.suffix.lower() in ['.yaml', '.yml']:
                filename = filepath.relative_to(self._path_cc)
                _logger.section(f"Load Control Center File '{filename}'")
                data = _util.file.read_control_center_file(
                    path=filepath,
                    cache_manager=self._cache_manager,
                    tag_name=const.CC_EXTENSION_TAG,
                )
                duplicate_keys = set(data.keys()) & set(full_data.keys())
                if duplicate_keys:
                    raise RuntimeError(f"Duplicate keys '{', '.join(duplicate_keys)}' in project config")
                full_data.update(data)
        if self._hook_manager.has_hook(const.FUNCNAME_CC_HOOK_POST_LOAD):
            full_data = self._hook_manager.generate(
                const.FUNCNAME_CC_HOOK_POST_LOAD,
                full_data,
            )
        # TODO: Run an initial validation here
        self._contents_raw = _NestedDict(full_data)
        return self._contents_raw

    def generate_data(self) -> _DataManager:
        if self._ccm:
            return self._ccm
        data = self.load()
        _data_gen.MainDataGenerator(
            data=data,
            cache_manager=self._cache_manager,
            git_manager=self._git,
            github_api=self._github_api,
        ).generate()
        if not self._data_main:
            curr_branch, other_branches = self._git.get_all_branch_names()
            main_branch = data["repo.default_branch"]
            if curr_branch == main_branch:
                self._data_main = self._data_before or data
            else:
                self._git.fetch_remote_branches_by_name(main_branch)
                self._git.stash()
                self._git.checkout(main_branch)
                if (self._git.repo_path / const.FILEPATH_METADATA).is_file():
                    self._data_main = controlman.data_man.from_json_file(repo_path=self._git.repo_path)
                else:
                    self._data_main = data
                self._git.checkout(curr_branch)
                self._git.stash_pop()
        if data.get("pkg"):
            _data_gen.PythonDataGenerator(
                data=data,
                git_manager=self._git,
                cache=self._cache_manager,
                github_api=self._github_api,
            ).generate()
        if data.get("web"):
            website_path = self._data_before["dir.web"] or data["dir.web"]
            _data_gen.WebDataGenerator(
                data=data,
                website_dir_path=self._path_root / website_path,
            ).generate()
        _data_gen.RepoDataGenerator(
            data=data,
            git_manager=self._git,
            data_main=self._data_main,
            future_versions=self._future_vers,
        ).generate()
        if self._hook_manager.has_hook(const.FUNCNAME_CC_HOOK_POST_DATA):
            self._hook_manager.generate(
                const.FUNCNAME_CC_HOOK_POST_DATA,
                data,
            )
        data.fill()
        self._cache_manager.save()
        _DataValidator(data=data).validate()
        self._ccm = _DataManager(data=data)
        return self._ccm

    def generate_files(self) -> list[tuple[_DynamicFile, str]]:
        if self._generated_files:
            return self._generated_files
        metadata = self.generate_data()
        self._generated_files = _generator.generate(
            content_manager=metadata,
            path_manager=self.path_manager,
            custom_generator=self._hook_manager,
        )
        return self._generated_files

    def generate(
        content_manager: _DataManager,
        custom_generator: _HookManager,
    ) -> list[tuple[_DynamicFile, str]]:
        return _generator.generate(content_manager=content_manager, path_manager=path_manager,
                                   custom_generator=custom_generator)

    def compare_files(
        self,
    ) -> tuple[list[tuple[_DynamicFile, _Diff]], dict[_DynamicFileType, dict[str, bool]], str]:
        """Compare generated dynamic repository files to the current state of repository."""
        if self._results:
            return self._results, self._changes, self._summary
        updates = self.generate_files()
        self._results, self._changes, self._summary = _FileComparer(
            path_root=self._path_root
        ).compare(generated_files=updates)
        return self._results, self._changes, self._summary

    @_logger.sectioner("Apply Changes To Dynamic Repository File")
    def apply_changes(self) -> None:
        """Apply changes to dynamic repository files."""

        def log():
            path_message = (
                f"{'from' if diff.status is _DynamicFileChangeType.REMOVED else 'at'} '{info.path}'"
                if not diff.path_before else f"from '{diff.path_before}' to '{info.path}'"
            )
            _logger.info(
                title=f"{info.category.value}: {info.id}",
                msg=f"{diff.status.value.emoji} {diff.status.value.title} {path_message}"
            )
            return

        if not self._results:
            self.compare_files()
        for info, diff in self._results:
            log()
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
        return
