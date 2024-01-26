from typing import Literal, Optional
from pathlib import Path
import json
import hashlib
import re

import pyserials
from actionman.log import Logger
from pylinks import api
from pylinks.exceptions import WebAPIPersistentStatusCodeError

from repodynamics.path import PathFinder
from repodynamics import file_io
from repodynamics import time


class MetaReader:
    def __init__(self, paths: PathFinder, github_token: Optional[str] = None, logger: Logger = None):
        self.logger = logger or Logger()
        self.logger.section("Process Meta Source Files")
        self._github_token = github_token
        self._pathfinder = paths
        self._local_config = self._get_local_config()

        self._extensions, self._path_extensions = self._read_extensions()
        self._metadata: dict = self._read_raw_metadata()
        self._metadata["extensions"] = self._extensions
        self._metadata["path"] = self._pathfinder.paths_dict
        self._metadata["path"]["file"] = {
            "website_announcement": f"{self._metadata['path']['dir']['website']}/announcement.html",
            "readme_pypi": f"{self._metadata['path']['dir']['source']}/README_pypi.md",
        }
        self._db = file_io.read_datafile(
            path_data=file_io.get_package_datafile("db.yaml", return_content=False)
        )
        return

    @property
    def metadata(self) -> dict:
        return self._metadata

    @property
    def github(self):
        return api.github(self._github_token)

    @property
    def local_config(self) -> dict:
        return self._local_config

    @property
    def db(self) -> dict:
        return self._db

    def _read_extensions(self) -> tuple[dict, Path | None]:
        extensions = file_io.read_datafile(
            path_data=self._pathfinder.file_meta_core_extensions,
            relpath_schema="extensions",
            root_type=list,
        )  # TODO: add logging and error handling
        if not extensions:
            return extensions, None
        local_path, exists = self._get_local_extensions(extensions)
        if not exists:
            self._download_extensions(extensions, download_path=local_path)
        return extensions, local_path

    def _get_local_extensions(self, extensions: list[dict]) -> tuple[Path, bool]:
        self.logger.h3("Get Local Extensions")
        extention_defs = json.dumps(extensions).encode("utf-8")
        hash = hashlib.md5(extention_defs).hexdigest()
        self.logger.info(f"Looking for non-expired local extensions with hash '{hash}'.")
        dir_pattern = re.compile(
            r"^(20\d{2}_(?:0[1-9]|1[0-2])_(?:0[1-9]|[12]\d|3[01])_(?:[01]\d|2[0-3])_[0-5]\d_[0-5]\d)__"
            r"([a-fA-F0-9]{32})$"
        )
        new_path = self._pathfinder.dir_local_meta_extensions / f"{time.now()}__{hash}"
        if not self._pathfinder.dir_local_meta_extensions.is_dir():
            self.logger.info(
                f"Local extensions directory not found at '{self._pathfinder.dir_local_meta_extensions}'."
            )
            return new_path, False
        for path in self._pathfinder.dir_local_meta_extensions.iterdir():
            if path.is_dir():
                match = dir_pattern.match(path.name)
                if match and match.group(2) == hash and not time.is_expired(
                    timestamp=match.group(1),
                    expiry_days=self._local_config["cache_retention_days"]["extensions"]
                ):
                    self.logger.success(f"Found non-expired local extensions at '{path}'.")
                    return path, True
        self.logger.info(f"No non-expired local extensions found.")
        return new_path, False

    def _download_extensions(self, extensions: list[dict], download_path: Path) -> None:
        self.logger.h3("Download Meta Extensions")
        self._pathfinder.dir_local_meta_extensions.mkdir(parents=True, exist_ok=True)
        file_io.delete_dir_content(self._pathfinder.dir_local_meta_extensions, exclude=["README.md"])
        for idx, extension in enumerate(extensions):
            self.logger.h4(f"Download Extension {idx + 1}")
            self.logger.info(f"Input: {extension}")
            repo_owner, repo_name = extension["repo"].split("/")
            dir_path = download_path / f"{idx + 1 :03}"
            rel_dl_path = Path(extension["type"])
            if extension["type"] == "package/build":
                rel_dl_path = rel_dl_path.with_suffix(".toml")
            elif extension["type"] == "package/tools":
                filename = Path(extension["path"]).with_suffix(".toml").name
                rel_dl_path = rel_dl_path / filename
            else:
                rel_dl_path = rel_dl_path.with_suffix(".yaml")
            full_dl_path = dir_path / rel_dl_path
            try:
                extension_filepath = (
                    self.github.user(repo_owner)
                    .repo(repo_name)
                    .download_file(
                        path=extension["path"],
                        ref=extension.get("ref"),
                        download_path=full_dl_path.parent,
                        download_filename=full_dl_path.name,
                    )
                )
            except WebAPIPersistentStatusCodeError as e:
                self.logger.error(f"Error downloading extension data:", str(e))
            if not extension_filepath:
                self.logger.error(f"No files found in extension.")
            else:
                self.logger.success(
                    f"Downloaded extension file '{extension_filepath}' from '{extension['repo']}'",
                )
        return

    def _get_local_config(self):
        self.logger.h3("Read Local Config")
        source_path = (
            self._pathfinder.file_local_config
            if self._pathfinder.file_local_config.is_file()
            else self._pathfinder.dir_meta / "config.yaml"
        )
        local_config = file_io.read_datafile(
            path_data=source_path,
            relpath_schema="config",
        )
        self.logger.success("Local config set.", json.dumps(local_config, indent=3))
        return local_config

    def _read_raw_metadata(self):
        self.logger.h3("Read Raw Metadata")
        metadata = {}
        for entry in ("credits", "intro", "license"):
            section = self._read_single_file(rel_path=f"project/{entry}")
            try:
                log = pyserials.update.dict_from_addon(
                    data=metadata,
                    addon=section,
                    append_list=False,
                    append_dict=True,
                    raise_duplicates=True,
                )
            except pyserials.exception.DictUpdateError as e:
                # TODO
                pass
        for entry in (
            "custom/custom",
            "dev/branch",
            "dev/changelog",
            "dev/commit",
            "dev/discussion",
            "dev/issue",
            "dev/label",
            "dev/maintainer",
            "dev/pull",
            "dev/repo",
            "dev/tag",
            "dev/workflow",
            "ui/health_file",
            "ui/readme",
            "ui/theme",
            "ui/web",
        ):
            section = {entry.split("/")[1]: self._read_single_file(rel_path=entry)}
            try:
                log = pyserials.update.dict_from_addon(
                    data=metadata,
                    addon=section,
                    append_list=False,
                    append_dict=True,
                    raise_duplicates=True,
                )
            except pyserials.exception.DictUpdateError as e:
                # TODO
                pass
        package = {}
        if (self._pathfinder.dir_meta / "package_python").is_dir():
            package["type"] = "python"
            for entry in (
                "package_python/conda",
                "package_python/dev_config",
                "package_python/docs",
                "package_python/entry_points",
                "package_python/metadata",
                "package_python/requirements",
            ):
                section = self._read_single_file(rel_path=entry)
                try:
                    log = pyserials.update.dict_from_addon(
                        data=package,
                        addon=section,
                        append_list=False,
                        append_dict=True,
                        raise_duplicates=True,
                    )
                except pyserials.exception.DictUpdateError as e:
                    # TODO
                    pass
            package["pyproject"] = self._read_package_python_pyproject()
            package["pyproject_tests"] = self._read_single_file(rel_path="package_python/build_tests", ext="toml")
        else:
            package["type"] = None
        metadata["package"] = package
        self.logger.success("Full metadata file assembled.", json.dumps(metadata, indent=3))
        return metadata

    def _read_single_file(self, rel_path: str, ext: str = "yaml"):
        section = file_io.read_datafile(path_data=self._pathfinder.dir_meta / f"{rel_path}.{ext}")
        for idx, extension in enumerate(self._extensions):
            if extension["type"] == rel_path:
                self.logger.h4(f"Read Extension Metadata {idx + 1}")
                extionsion_path = self._path_extensions / f"{idx + 1 :03}" / f"{rel_path}.{ext}"
                section_extension = file_io.read_datafile(path_data=extionsion_path)
                if not section_extension:
                    raise  # TODO
                try:
                    log = pyserials.update.dict_from_addon(
                        data=section,
                        addon=section_extension,
                        append_list=extension["append_list"],
                        append_dict=extension["append_dict"],
                        raise_duplicates=extension["raise_duplicate"],
                    )
                except pyserials.exception.DictUpdateError as e:
                    # TODO
                    pass
        file_io.validate_data(data=section, schema_relpath=rel_path)
        return section

    def _read_package_python_pyproject(self):
        self.logger.h3("Read Package Config")

        def read_package_toml(path: Path):
            dirpath_config = Path(path) / "package_python" / "tools"
            paths_config_files = list(dirpath_config.glob("*.toml"))
            config = dict()
            for path_file in paths_config_files:
                config_section = file_io.read_datafile(path_data=path_file)
                try:
                    log = pyserials.update.dict_from_addon(
                        data=config,
                        addon=config_section,
                        append_list=True,
                        append_dict=True,
                        raise_duplicates=True,
                    )
                except pyserials.exception.DictUpdateError as e:
                    # TODO
                    pass
            return config

        build = self._read_single_file(rel_path="package_python/build", ext="toml")
        tools = read_package_toml(self._pathfinder.dir_meta)
        for idx, extension in enumerate(self._extensions):
            if extension["type"] == "package_python/tools":
                extension_config = read_package_toml(self._path_extensions / f"{idx + 1 :03}")
                try:
                    log = pyserials.update.dict_from_addon(
                        data=tools,
                        addon=extension_config,
                        append_list=extension["append_list"],
                        append_dict=extension["append_dict"],
                        raise_duplicates=extension["raise_duplicate"],
                    )
                except pyserials.exception.DictUpdateError as e:
                    # TODO
                    pass
        file_io.validate_data(data=tools, schema_relpath="package_python/tools")
        try:
            log = pyserials.update.dict_from_addon(
                data=build,
                addon=tools,
                append_list=True,
                append_dict=True,
                raise_duplicates=True,
            )
        except pyserials.exception.DictUpdateError as e:
            # TODO
            pass
        return build
