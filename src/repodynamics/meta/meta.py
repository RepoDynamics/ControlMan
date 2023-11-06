from typing import Literal, Optional, Sequence, Callable
from pathlib import Path
import json

from ruamel.yaml import YAML

from repodynamics.logger import Logger
from repodynamics.meta.metadata import MetadataGenerator
from repodynamics.meta.reader import MetaReader
from repodynamics.meta.writer import MetaWriter
from repodynamics.meta.manager import MetaManager
from repodynamics.meta.validator import MetaValidator
from repodynamics.path import InputPath, OutputPath
from repodynamics.datatype import DynamicFile, Diff
from repodynamics import _util
from repodynamics.datatype import DynamicFileType

from repodynamics.meta.files.config import ConfigFileGenerator
from repodynamics.meta.files.health import HealthFileGenerator
from repodynamics.meta.files.package import PackageFileGenerator
from repodynamics.meta.files.readme import ReadmeFileGenerator
from repodynamics.meta.files.forms import FormGenerator


class Meta:
    def __init__(
        self,
        path_root: str | Path = ".",
        github_token: Optional[str] = None,
        hash_before: str = "",
        logger: Optional[Logger] = None,
    ):
        self._logger = logger or Logger()
        self._logger.h2("Initialize Meta Manager")
        self._path_root = Path(path_root).resolve()
        self._github_token = github_token
        self._hash_before = hash_before

        pathfile = self._path_root / ".github" / ".repodynamics_meta_path.txt"
        rel_path_meta = pathfile.read_text().strip() if pathfile.is_file() else ".meta"
        paths = _util.dict.read(
            path=self._path_root / rel_path_meta / "paths.yaml",
            schema=_util.file.datafile("schema/paths.yaml"),
            logger=self._logger,
        )
        paths["dir"]["meta"] = rel_path_meta
        self._input_path = InputPath(super_paths=paths, path_root=self._path_root, logger=self._logger)
        self._output_path = OutputPath(super_paths=paths, path_root=self._path_root, logger=self._logger)

        self._reader: MetaReader | None = None
        self._manager: MetaManager | None = None
        self._metadata_raw: dict = {}
        self._metadata: dict = {}
        self._generated_files: list[tuple[DynamicFile, str]] = []
        self._writer: MetaWriter | None = None
        self._results: list[tuple[DynamicFile, Diff]] = []
        self._changes: dict[DynamicFileType, dict[str, bool]] = {}
        self._summary: str = ""
        return

    @property
    def input_path(self) -> InputPath:
        return self._input_path

    @property
    def output_path(self) -> OutputPath:
        return self._output_path

    @property
    def manager(self) -> MetaManager:
        if self._manager:
            return self._manager
        metadata_full, _ = self.read_metadata_full()
        self._manager = MetaManager(metadata=metadata_full)
        return self._manager

    def read_metadata_raw(self):
        if self._metadata_raw:
            return self._metadata_raw
        self._reader = MetaReader(
            input_path=self._input_path, github_token=self._github_token, logger=self._logger
        )
        self._metadata_raw = self._reader.metadata
        return self._metadata_raw

    def read_metadata_full(self):
        if self._metadata:
            return self._metadata
        self.read_metadata_raw()
        self._metadata = MetadataGenerator(
            reader=self._reader,
            output_path=self.output_path,
            hash_before=self._hash_before,
            logger=self._logger,
        ).generate()
        MetaValidator(metadata=self._metadata, logger=self._logger).validate()
        return self._metadata

    def generate_files(self) -> list[tuple[DynamicFile, str]]:
        if self._generated_files:
            return self._generated_files
        metadata = self.read_metadata_full()
        self._logger.h2("Generate Files")

        generated_files = [
            (self.output_path.metadata, json.dumps(metadata)),
            (self.output_path.license, metadata["license"].get("text", "")),
        ]

        generated_files += ConfigFileGenerator(
            metadata=metadata, output_path=self.output_path, logger=self._logger
        ).generate()

        generated_files += FormGenerator(
            metadata=metadata, output_path=self.output_path, logger=self._logger
        ).generate()

        generated_files += HealthFileGenerator(
            metadata=metadata, output_path=self.output_path, logger=self._logger
        ).generate()

        if "package" in self._metadata:
            generated_files += PackageFileGenerator(
                metadata=metadata,
                package_config=self._reader.package_config,
                test_package_config=self._reader.test_package_config,
                output_path=self.output_path,
                logger=self._logger,
            ).generate()

        generated_files += ReadmeFileGenerator(
            metadata=metadata, input_path=self._input_path, output_path=self.output_path, logger=self._logger
        ).generate()

        self._generated_files = generated_files
        return self._generated_files

    def compare_files(self):
        if self._results:
            return self._results, self._changes, self._summary
        updates = self.generate_files()
        self._writer = MetaWriter(path_root=self._path_root, logger=self._logger)
        self._results, self._changes, self._summary = self._writer.compare(updates)
        return self._results, self._changes, self._summary

    def apply_changes(self):
        if not self._results:
            self.compare_files()
        self._writer.apply(self._results)
        return
