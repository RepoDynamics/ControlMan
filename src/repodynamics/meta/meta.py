from typing import Literal, Optional, Sequence, Callable
from pathlib import Path
import json

from ruamel.yaml import YAML

from repodynamics.logger import Logger
from repodynamics.meta.metadata import MetadataGenerator
from repodynamics.meta.reader import MetaReader
from repodynamics.meta.writer import MetaWriter, OutputPaths, OutputFile, FileCategory
from repodynamics import _util

from repodynamics.meta.files.config import ConfigFileGenerator
from repodynamics.meta.files.health import HealthFileGenerator
from repodynamics.meta.files.package import PackageFileGenerator
from repodynamics.meta.files.readme import ReadmeFileGenerator


class Meta:
    def __init__(
        self,
        path_root: str | Path = ".",
        github_token: Optional[str] = None,
        logger: Optional[Logger] = None,
    ):
        self._logger = logger or Logger()
        self._path_root = Path(path_root).resolve()
        self._github_token = github_token

        self._out_db: OutputPaths = OutputPaths(path_root=self._path_root, logger=self._logger)

        self._reader: MetaReader | None = None
        self._metadata_raw: dict = {}
        self._metadata: dict = {}
        self._generated_files: list[tuple[OutputFile, str]] = []
        self._writer: MetaWriter | None = None
        self._results: list[tuple[OutputFile, str]] = []
        self._changes: dict[FileCategory, dict[str, bool]] = {}
        self._summary: str = ""
        return

    def read_metadata_output(self):
        path_metadata = self._out_db.metadata.path
        metadata = _util.dict.read(path_metadata, logger=self._logger, raise_empty=False)
        if metadata:
            self._logger.success(
                f"Loaded metadata from {path_metadata}.",
                json.dumps(metadata, indent=3)
            )
        else:
            self._logger.attention(f"No metadata found in {path_metadata}.")
        return metadata

    def read_metadata_raw(self):
        if self._metadata_raw:
            return self._metadata_raw
        self._reader = MetaReader(
            path_root=self._path_root,
            github_token=self._github_token,
            logger=self._logger
        )
        self._metadata_raw = self._reader.metadata
        return self._metadata_raw

    def read_metadata_full(self):
        if self._metadata:
            return self._metadata
        self.read_metadata_raw()
        self._metadata = MetadataGenerator(reader=self._reader, logger=self._logger).generate()
        return self._metadata

    def generate_files(self) -> list[tuple[OutputFile, str]]:
        if self._generated_files:
            return self._generated_files
        metadata = self.read_metadata_full()
        self._logger.h2("Generate Files")

        generated_files = [
            (self._out_db.metadata, json.dumps(metadata)),
            (self._out_db.license, metadata["license"].get("text", "")),
        ]
        generated_files += ConfigFileGenerator(
            metadata=metadata, path_root=self._reader.path.root, logger=self._logger
        ).generate()
        generated_files += HealthFileGenerator(
            metadata=metadata, path_root=self._reader.path.root, logger=self._logger
        ).generate()
        if "package" in self._metadata:
            generated_files += PackageFileGenerator(
                metadata=metadata,
                package_config=self._reader.package_config,
                path_root=self._reader.path.root,
                logger=self._logger
            ).generate()
        generated_files += ReadmeFileGenerator(
            metadata=metadata, path_root=self._reader.path.root, logger=self._logger
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

