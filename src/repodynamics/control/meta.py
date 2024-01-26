from typing import Optional
from pathlib import Path
import json


from repodynamics.logger import Logger
from repodynamics.control.generator import MetadataGenerator
from repodynamics.control.reader import MetaReader
from repodynamics.control.writer import MetaWriter
from repodynamics.control.manager import MetaManager
from repodynamics.control.validator import MetaValidator
from repodynamics.path import PathFinder
from repodynamics.datatype import DynamicFile, Diff
from repodynamics.datatype import DynamicFileType
from repodynamics.version import PEP440SemVer
from repodynamics.control.files.config import ConfigFileGenerator
from repodynamics.control.files.health import HealthFileGenerator
from repodynamics.control.files import package
from repodynamics.control.files import readme
from repodynamics.control.files.forms import FormGenerator
from repodynamics.control.cache import APICacheManager


class ControlCenter:
    def __init__(
        self,
        path_root: str | Path = ".",
        github_token: Optional[str] = None,
        ccm_before: MetaManager | dict | None = None,
        future_versions: dict[str, str | PEP440SemVer] | None = None,
        logger: Optional[Logger] = None,
    ):
        self._logger = logger or Logger()
        self._logger.h2("Initialize Meta Manager")
        self._path_root = Path(path_root).resolve()
        self._github_token = github_token
        self._ccm_before = ccm_before
        self._future_versions = future_versions or {}

        self._pathfinder = PathFinder(path_root=self._path_root, logger=self._logger)

        self._reader: MetaReader | None = None
        self._cache_manager: APICacheManager | None = None
        self._metadata_raw: dict = {}
        self._metadata: MetaManager | None = None
        self._generated_files: list[tuple[DynamicFile, str]] = []
        self._writer: MetaWriter | None = None
        self._results: list[tuple[DynamicFile, Diff]] = []
        self._changes: dict[DynamicFileType, dict[str, bool]] = {}
        self._summary: str = ""
        return

    @property
    def paths(self) -> PathFinder:
        return self._pathfinder

    def read_metadata_raw(self) -> dict:
        if self._metadata_raw:
            return self._metadata_raw
        self._reader = MetaReader(paths=self.paths, github_token=self._github_token, logger=self._logger)
        self._cache_manager = APICacheManager(
            path_cachefile=self._pathfinder.file_local_api_cache,
            retention_days=self._reader.local_config["cache_retention_days"]["api"]
        )
        self._metadata_raw = self._reader.metadata
        return self._metadata_raw

    def read_metadata_full(self) -> MetaManager:
        if self._metadata:
            return self._metadata
        self.read_metadata_raw()
        metadata_dict = MetadataGenerator(
            reader=self._reader,
            output_path=self.paths,
            api_cache_manager=self._cache_manager,
            ccm_before=self._ccm_before,
            future_versions=self._future_versions,
            logger=self._logger,
        ).generate()
        self._metadata = MetaManager(options=metadata_dict)
        MetaValidator(metadata=self._metadata, logger=self._logger).validate()
        return self._metadata

    def generate_files(self) -> list[tuple[DynamicFile, str]]:
        if self._generated_files:
            return self._generated_files
        metadata = self.read_metadata_full()
        self._logger.h2("Generate Files")

        generated_files = [
            (self.paths.metadata, json.dumps(metadata.as_dict)),
            (self.paths.license, metadata["license"].get("text", "")),
        ]

        generated_files += ConfigFileGenerator(
            metadata=metadata, output_path=self.paths, logger=self._logger
        ).generate()

        generated_files += FormGenerator(
            metadata=metadata, output_path=self.paths, logger=self._logger
        ).generate()

        generated_files += HealthFileGenerator(
            metadata=metadata, output_path=self.paths, logger=self._logger
        ).generate()

        generated_files += package.generate(
            metadata=metadata,
            paths=self.paths,
            logger=self._logger,
        )

        generated_files += readme.generate(ccm=metadata, path=self.paths, logger=self._logger)

        self._generated_files = generated_files
        return self._generated_files

    def compare_files(
        self,
    ) -> tuple[list[tuple[DynamicFile, Diff]], dict[DynamicFileType, dict[str, bool]], str]:
        if self._results:
            return self._results, self._changes, self._summary
        updates = self.generate_files()
        self._writer = MetaWriter(path_root=self._path_root, logger=self._logger)
        self._results, self._changes, self._summary = self._writer.compare(updates)
        return self._results, self._changes, self._summary

    def apply_changes(self) -> None:
        if not self._results:
            self.compare_files()
        self._writer.apply(self._results)
        return
