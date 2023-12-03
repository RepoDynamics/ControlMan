import re
from pathlib import Path
import datetime

from typing import Literal, Optional
import jsonschema
from ruamel.yaml import YAML, YAMLError
import json
import hashlib
import traceback
from pylinks import api
from pylinks.http import WebAPIPersistentStatusCodeError
from repodynamics import _util
from repodynamics.logger import Logger
from repodynamics.path import PathFinder
import tomlkit


class MetaReader:
    def __init__(self, paths: PathFinder, github_token: Optional[str] = None, logger: Logger = None):
        self.logger = logger or Logger()
        self.logger.h2("Process Meta Source Files")
        self._github_token = github_token
        self._pathfinder = paths
        self._local_config = self._get_local_config()

        self._extensions, self._path_extensions = self._read_extensions()
        self._metadata: dict = self._read_raw_metadata()
        self._metadata["extensions"] = self._extensions
        self._metadata["path"] = self._pathfinder.paths_dict
        self._metadata["path"]["file"] = {
            "website_announcement": f"{self._metadata['path']['dir']['website']}/announcement.html",
        }
        self._cache: dict = self._initialize_api_cache()
        self._db = self._read_datafile(_util.file.datafile("db.yaml"))
        return

    @property
    def metadata(self) -> dict:
        return self._metadata

    @property
    def github(self):
        return api.github(self._github_token)

    @property
    def db(self) -> dict:
        return self._db

    def cache_get(self, item):
        log_title = f"Retrieve '{item}' from cache"
        item = self._cache.get(item)
        if not item:
            self.logger.skip(log_title, "Item not found")
            return None
        timestamp = item.get("timestamp")
        if timestamp and self._is_expired(timestamp):
            self.logger.skip(log_title, f"Item found with expired timestamp '{timestamp}:\n{item['data']}.")
            return None
        self.logger.success(log_title, f"Item found with valid timestamp '{timestamp}':\n{item['data']}.")
        return item["data"]

    def cache_set(self, key, value):
        self._cache[key] = {
            "timestamp": self._now,
            "data": value,
        }
        self.logger.success(f"Set cache for '{key}'", json.dumps(self._cache[key], indent=3))
        return

    def cache_save(self):
        path = self._pathfinder.file_local_api_cache
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            YAML(typ="safe").dump(self._cache, f)
        self.logger.success(f"Cache file saved at {self._pathfinder.file_local_api_cache}.")
        return

    def _read_extensions(self) -> tuple[dict, Path | None]:
        extensions = _util.dict.read(
            path=self._pathfinder.file_meta_core_extensions,
            schema=self._get_schema("extensions"),
            root_type="list",
            logger=self.logger,
        )
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
        new_path = self._pathfinder.dir_local_meta_extensions / f"{self._now}__{hash}"
        if not self._pathfinder.dir_local_meta_extensions.is_dir():
            self.logger.info(
                f"Local extensions directory not found at '{self._pathfinder.dir_local_meta_extensions}'."
            )
            return new_path, False
        for path in self._pathfinder.dir_local_meta_extensions.iterdir():
            if path.is_dir():
                match = dir_pattern.match(path.name)
                if match and match.group(2) == hash and not self._is_expired(match.group(1), typ="extensions"):
                    self.logger.success(f"Found non-expired local extensions at '{path}'.")
                    return path, True
        self.logger.info(f"No non-expired local extensions found.")
        return new_path, False

    def _download_extensions(self, extensions: list[dict], download_path: Path) -> None:
        self.logger.h3("Download Meta Extensions")
        self._pathfinder.dir_local_meta_extensions.mkdir(parents=True, exist_ok=True)
        _util.file.delete_dir_content(self._pathfinder.dir_local_meta_extensions, exclude=["README.md"])
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

    def _initialize_api_cache(self):
        self.logger.h3("Initialize Cache")
        if not self._pathfinder.file_local_api_cache.is_file():
            self.logger.info(f"API cache file not found at '{self._pathfinder.file_local_api_cache}'.")
            cache = {}
            return cache
        cache = self._read_datafile(self._pathfinder.file_local_api_cache)
        self.logger.success(
            f"API cache loaded from '{self._pathfinder.file_local_api_cache}'", json.dumps(cache, indent=3)
        )
        return cache

    def _get_local_config(self):
        self.logger.h3("Read Local Config")
        source_path = (
            self._pathfinder.file_local_config
            if self._pathfinder.file_local_config.is_file()
            else self._pathfinder.dir_meta / "config.yaml"
        )
        local_config = self._read_datafile(
            source=source_path,
            schema=self._get_schema("config"),
        )
        self.logger.success("Local config set.", json.dumps(local_config, indent=3))
        return local_config

    def _read_raw_metadata(self):
        self.logger.h3("Read Raw Metadata")
        metadata = {}
        for entry in ("credits", "intro", "license"):
            section = self._read_single_file(rel_path=f"project/{entry}")
            self._recursive_update(
                source=metadata, add=section, append_list=False, append_dict=True, raise_on_duplicated=True
            )
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
            self._recursive_update(
                source=metadata, add=section, append_list=False, append_dict=True, raise_on_duplicated=True
            )
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
                self._recursive_update(
                    source=package, add=section, append_list=False, append_dict=True, raise_on_duplicated=True
                )
            package["pyproject"] = self._read_package_python_pyproject()
            package["pyproject_tests"] = self._read_single_file(rel_path="package_python/build_tests", ext="toml")
        else:
            package["type"] = None
        metadata["package"] = package
        self.logger.success("Full metadata file assembled.", json.dumps(metadata, indent=3))
        return metadata

    def _read_single_file(self, rel_path: str, ext: str = "yaml"):
        section = self._read_datafile(self._pathfinder.dir_meta / f"{rel_path}.{ext}")
        for idx, extension in enumerate(self._extensions):
            if extension["type"] == rel_path:
                self.logger.h4(f"Read Extension Metadata {idx + 1}")
                extionsion_path = self._path_extensions / f"{idx + 1 :03}" / f"{rel_path}.{ext}"
                section_extension = self._read_datafile(extionsion_path, raise_missing=True)
                self._recursive_update(
                    source=section,
                    add=section_extension,
                    append_list=extension["append_list"],
                    append_dict=extension["append_dict"],
                    raise_on_duplicated=extension["raise_duplicate"],
                )
        self._validate_datafile(source=section, schema=rel_path)
        return section

    def _read_package_python_pyproject(self):
        self.logger.h3("Read Package Config")

        def read_package_toml(path: Path):
            dirpath_config = Path(path) / "package_python" / "tools"
            paths_config_files = list(dirpath_config.glob("*.toml"))
            config = dict()
            for path_file in paths_config_files:
                config_section = self._read_datafile(path_file)
                self._recursive_update(
                    config, config_section, append_list=True, append_dict=True, raise_on_duplicated=True
                )
            return config

        build = self._read_single_file(rel_path="package_python/build", ext="toml")
        tools = read_package_toml(self._pathfinder.dir_meta)
        for idx, extension in enumerate(self._extensions):
            if extension["type"] == "package_python/tools":
                extension_config = read_package_toml(self._path_extensions / f"{idx + 1 :03}")
                self._recursive_update(
                    tools,
                    extension_config,
                    append_list=extension["append_list"],
                    append_dict=extension["append_dict"],
                    raise_on_duplicated=extension["raise_duplicate"],
                )
        self._validate_datafile(source=tools, schema="package_python/tools")
        self._recursive_update(build, tools, raise_on_duplicated=True)
        return build

    def _read_datafile(self, source: Path, schema: Path = None, **kwargs):
        return _util.dict.read(path=source, schema=schema, raise_empty=False, logger=self.logger, **kwargs)

    def _validate_datafile(self, source: dict, schema: str):
        return _util.dict.validate_schema(source=source, schema=self._get_schema(schema), logger=self.logger)

    @staticmethod
    def _get_schema(schema: str):
        return _util.file.datafile(f"schema/{schema}.yaml")

    def _is_expired(self, timestamp: str, typ: Literal["api", "extensions"] = "api") -> bool:
        exp_date = datetime.datetime.strptime(timestamp, "%Y_%m_%d_%H_%M_%S") + datetime.timedelta(
            days=self._local_config["cache_retention_days"][typ]
        )
        if exp_date <= datetime.datetime.now():
            return True
        return False

    @property
    def _now(self) -> str:
        return datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y_%m_%d_%H_%M_%S")

    def _recursive_update(
        self,
        source: dict,
        add: dict,
        append_list: bool = True,
        append_dict: bool = True,
        raise_on_duplicated: bool = False,
    ):
        _util.dict.update_recursive(
            source=source,
            add=add,
            append_list=append_list,
            append_dict=append_dict,
            raise_on_duplicated=raise_on_duplicated,
            logger=self.logger,
        )
        return
