from pathlib import Path
import copy

from actionman.logger import Logger

from repodynamics.control import files
from repodynamics.control.content import ControlCenterContentManager
from repodynamics.control.data import loader, generator, validator
from repodynamics.path import PathManager
from repodynamics.datatype import DynamicFile, Diff
from repodynamics.datatype import DynamicFileType
from repodynamics.version import PEP440SemVer
from repodynamics.control.data.cache import APICacheManager


class ControlCenterManager:
    def __init__(
        self,
        path_repo: str | Path,
        logger: Logger,
        github_token: str | None = None,
        ccm_before: ControlCenterContentManager | dict | None = None,
        future_versions: dict[str, str | PEP440SemVer] | None = None,
        log_section_title: str = "Initialize Control Center Manager"
    ):
        self._logger = logger
        self._logger.section(log_section_title, group=True)
        self._path_root = Path(path_repo).resolve()
        self._github_token = github_token
        self._ccm_before = ccm_before
        self._future_versions = future_versions or {}

        self._path_manager = PathManager(path_repo=self._path_root, logger=self._logger)

        self._cache_manager: APICacheManager | None = None
        self._metadata_raw: dict = {}
        self._local_config: dict = {}
        self._metadata: ControlCenterContentManager | None = None
        self._generated_files: list[tuple[DynamicFile, str]] = []
        self._results: list[tuple[DynamicFile, Diff]] = []
        self._changes: dict[DynamicFileType, dict[str, bool]] = {}
        self._summary: str = ""
        self._logger.section_end()
        return

    @property
    def path(self) -> PathManager:
        return self._path_manager

    def load(self) -> dict:
        if self._metadata_raw:
            return self._metadata_raw
        self._metadata_raw, self._local_config = loader.load(
            path_manager=self.path, github_token=self._github_token, logger=self._logger
        )
        self._cache_manager = APICacheManager(
            path_cachefile=self._path_manager.file_local_api_cache,
            retention_days=self._local_config["cache_retention_days"]["api"]
        )
        return self._metadata_raw

    def generate_data(self) -> ControlCenterContentManager:
        if self._metadata:
            return self._metadata
        self.load()
        metadata_dict = generator.generate(
            initial_data=copy.deepcopy(self._metadata_raw),
            output_path=self.path,
            api_cache_manager=self._cache_manager,
            github_token=self._github_token,
            ccm_before=self._ccm_before,
            future_versions=self._future_versions,
            logger=self._logger,
        )
        self._metadata = ControlCenterContentManager(data=metadata_dict)
        validator.validate(content_manager=self._metadata, logger=self._logger)
        return self._metadata

    def generate_files(self) -> list[tuple[DynamicFile, str]]:
        if self._generated_files:
            return self._generated_files
        metadata = self.generate_data()
        self._logger.h2("Generate Files")
        self._generated_files = files.generate(
            content_manager=metadata,
            path_manager=self.path,
            logger=self._logger,
        )
        return self._generated_files

    def compare_files(
        self,
    ) -> tuple[list[tuple[DynamicFile, Diff]], dict[DynamicFileType, dict[str, bool]], str]:
        if self._results:
            return self._results, self._changes, self._summary
        updates = self.generate_files()
        self._results, self._changes, self._summary = files.compare(
            generated_files=updates, path_root=self._path_root, logger=self._logger
        )
        return self._results, self._changes, self._summary

    def apply_changes(self) -> None:
        if not self._results:
            self.compare_files()
        files.apply(self._results)
        return
