from pathlib import Path as _Path
import copy as _copy

from actionman.logger import Logger as _Logger

from repodynamics.control import files as _files
from repodynamics.control.content import ControlCenterContentManager
from repodynamics.control.data import loader as _loader, generator as _generator, validator as _validator
from repodynamics.path import PathManager as _PathManager
from repodynamics.datatype import (
    DynamicFile as _DynamicFile,
    Diff as _Diff,
    DynamicFileType as _DynamicFileType,
)
from repodynamics.version import PEP440SemVer as _PEP440SemVer


class ControlCenterManager:
    def __init__(
        self,
        path_repo: str | _Path,
        logger: _Logger,
        github_token: str | None = None,
        ccm_before: ControlCenterContentManager | dict | None = None,
        future_versions: dict[str, str | _PEP440SemVer] | None = None,
        log_section_title: str = "Initialize Control Center Manager"
    ):
        self._logger = logger
        self._logger.section(log_section_title, group=True)
        self._path_root = _Path(path_repo).resolve()
        self._github_token = github_token
        self._ccm_before = ccm_before
        self._future_versions = future_versions or {}

        self._path_manager = _PathManager(path_repo=self._path_root, logger=self._logger)

        self._metadata_raw: dict = {}
        self._local_config: dict = {}
        self._metadata: ControlCenterContentManager | None = None
        self._generated_files: list[tuple[_DynamicFile, str]] = []
        self._results: list[tuple[_DynamicFile, _Diff]] = []
        self._changes: dict[_DynamicFileType, dict[str, bool]] = {}
        self._summary: str = ""
        self._logger.section_end()
        return

    @property
    def path_manager(self) -> _PathManager:
        return self._path_manager

    def load(self) -> dict:
        if self._metadata_raw:
            return self._metadata_raw
        self._metadata_raw, self._local_config = _loader.load(
            path_manager=self.path_manager, github_token=self._github_token, logger=self._logger
        )
        return self._metadata_raw

    def generate_data(self) -> ControlCenterContentManager:
        if self._metadata:
            return self._metadata
        self.load()
        metadata_dict = _generator.generate(
            initial_data=_copy.deepcopy(self._metadata_raw),
            output_path=self.path_manager,
            api_cache_manager=self._local_config["cache_retention_days"]["api"],
            github_token=self._github_token,
            ccm_before=self._ccm_before,
            future_versions=self._future_versions,
            logger=self._logger,
        )
        self._metadata = ControlCenterContentManager(data=metadata_dict)
        _validator.validate(content_manager=self._metadata, logger=self._logger)
        return self._metadata

    def generate_files(self) -> list[tuple[_DynamicFile, str]]:
        if self._generated_files:
            return self._generated_files
        metadata = self.generate_data()
        self._generated_files = _files.generate(
            content_manager=metadata,
            path_manager=self.path_manager,
            logger=self._logger,
        )
        return self._generated_files

    def compare_files(
        self,
    ) -> tuple[list[tuple[_DynamicFile, _Diff]], dict[_DynamicFileType, dict[str, bool]], str]:
        if self._results:
            return self._results, self._changes, self._summary
        updates = self.generate_files()
        self._results, self._changes, self._summary = _files.compare(
            generated_files=updates, path_repo=self._path_root, logger=self._logger
        )
        return self._results, self._changes, self._summary

    def apply_changes(self) -> None:
        if not self._results:
            self.compare_files()
        _files.apply(results=self._results, logger=self._logger)
        return
