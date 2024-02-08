import copy as _copy

from versionman import PEP440SemVer as _PEP440SemVer

from controlman import files as _files
from controlman.content_manager import ControlCenterContentManager as _ControlCenterContentManager
from controlman.data import loader as _loader, generator as _generator, validator as _validator
from controlman._path_manager import PathManager as _PathManager
from controlman.datatype import (
    DynamicFile as _DynamicFile,
    Diff as _Diff,
    DynamicFileType as _DynamicFileType,
)
from controlman.protocol import Git as _Git


class ControlCenterManager:

    def __init__(
        self,
        git_manager: _Git,
        github_token: str | None = None,
        content_manager: _ControlCenterContentManager | dict | None = None,
        future_versions: dict[str, str | _PEP440SemVer] | None = None,
    ):
        self._git = git_manager
        self._path_root = self._git.repo_path
        self._github_token = github_token
        self._ccm_before = content_manager
        self._future_versions = future_versions or {}
        self._path_manager = _PathManager(repo_path=self._path_root)
        self._contents_raw: dict = {}
        self._local_config: dict = {}
        self._ccm: _ControlCenterContentManager | None = None
        self._generated_files: list[tuple[_DynamicFile, str]] = []
        self._results: list[tuple[_DynamicFile, _Diff]] = []
        self._changes: dict[_DynamicFileType, dict[str, bool]] = {}
        self._summary: str = ""
        return

    @property
    def path_manager(self) -> _PathManager:
        return self._path_manager

    def load(self) -> dict:
        if self._contents_raw:
            return self._contents_raw
        self._contents_raw, self._local_config = _loader.load(
            path_manager=self.path_manager, github_token=self._github_token
        )
        return self._contents_raw

    def generate_data(self) -> _ControlCenterContentManager:
        if self._ccm:
            return self._ccm
        self.load()
        metadata_dict = _generator.generate(
            initial_data=_copy.deepcopy(self._contents_raw),
            path_manager=self.path_manager,
            api_cache_retention_days=self._local_config["cache_retention_days"]["api"],
            git_manager=self._git,
            github_token=self._github_token,
            ccm_before=self._ccm_before,
            future_versions=self._future_versions,
        )
        self._ccm = _ControlCenterContentManager(data=metadata_dict)
        _validator.validate(content_manager=self._ccm)
        return self._ccm

    def generate_files(self) -> list[tuple[_DynamicFile, str]]:
        if self._generated_files:
            return self._generated_files
        metadata = self.generate_data()
        self._generated_files = _files.generate(
            content_manager=metadata,
            path_manager=self.path_manager,
        )
        return self._generated_files

    def compare_files(
        self,
    ) -> tuple[list[tuple[_DynamicFile, _Diff]], dict[_DynamicFileType, dict[str, bool]], str]:
        if self._results:
            return self._results, self._changes, self._summary
        updates = self.generate_files()
        self._results, self._changes, self._summary = _files.compare(
            generated_files=updates, path_repo=self._path_root
        )
        return self._results, self._changes, self._summary

    def apply_changes(self) -> None:
        if not self._results:
            self.compare_files()
        _files.apply(results=self._results)
        return
