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
import tomlkit


class MetaReader:
    def __init__(
        self,
        path_root: str | Path = ".",
        path_meta: str | Path = "meta",
        github_token: Optional[str] = None,
        logger: Logger = None
    ):
        self.logger = logger or Logger()
        self.logger.h2("Process Meta Source Files")
        self._path_root = Path(path_root).resolve()
        self._github_token = github_token
        self._path_meta = self._path_root / path_meta
        self._path_local = self._path_root / ".local"
        self._path_meta_local = self._path_local / "meta"
        self._path_api_cache = self._path_meta_local / "api_cache.yaml"
        self._path_extensions_dir = self._path_meta_local / "extensions"
        if not self._path_meta.is_dir():
            self.logger.error(f"Input meta directory '{self._path_meta}' not found.")
        if not self._path_extensions_dir.is_dir():
            self.logger.error(
                f"Could not find Local meta extensions directory at: '{self._path_extensions_dir}'."
            )
        self._metadata: dict = self._read_core_metadata()
        self._extensions: list[dict] = self._metadata.get("extensions", [])
        self._local_config = self._get_local_config()
        if self._extensions:
            self._path_extensions, exists = self._get_local_extensions()
            if not exists:
                self._download_extensions(self._extensions, self._path_extensions)
            self._update_metadata_from_extensions()
        self._add_metadata_default_values()
        self._validate_metadata()
        if self._metadata.get("package"):
            self._package_config = self._read_package_config()
        else:
            self._package_config = None
        self._cache: dict = self._initialize_api_cache()
        self._db = self._read_yaml(_util.file.datafile("db.yaml"))
        return

    def template(
            self,
            category: Literal["health_file", "license", "issue", "discussion", "pull", "config"],
            name: str
    ):
        ext = {
            'health_file': '.md',
            'license': '.txt',
            'issue': '.yaml',
            'discussion': '.yaml',
            'pull': '.md',
            'config': '.toml'
        }

        def read_path(path: Path, extension_nr: int = 0):
            path = (path / "template" / category / name).with_suffix(ext[category])
            if not path.is_file():
                return
            self.logger.success(
                "Found template in "
                f"{f'extension repository {extension_nr}' if extension_nr else 'main repository'}."
            )
            if category in ["issue", "discussion"]:
                return self._read_yaml(path)
            with open(path) as f:
                content = f.read()
            self.logger.success("File successfully loaded.", str(content))
            return content
        self.logger.h4(f"Read Template '{category}/{Path(name).with_suffix(ext[category])}'")
        if category not in ["health_file", "license", "issue", "discussion", "pull"]:
            self.logger.error(f"Category '{category}' not recognized.")
        content = read_path(self._path_meta)
        if content:
            return content
        if not self._extensions:
            self.logger.error(f"Template '{name}' not found in any of template sources.")
            return
        for idx, extension in enumerate(self._extensions):
            if extension["type"] not in [
                "meta", "template", "health_file", "license", "issue", "discussion", "pull"
            ]:
                continue
            content = read_path(self._path_extensions / f"{idx + 1 :03}", extension_nr=idx + 1)
            if content:
                return content
        self.logger.error(f"Template '{name}' not found in any of template sources.")
        return

    @property
    def metadata(self) -> dict:
        return self._metadata

    @property
    def package_config(self) -> dict:
        return self._package_config

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
            self.logger.skip(
                log_title, f"Item found with expired timestamp '{timestamp}:\n{item['data']}."
            )
            return None
        self.logger.success(
            log_title, f"Item found with valid timestamp '{timestamp}':\n{item['data']}."
        )
        return item["data"]

    def cache_set(self, key, value):
        self._cache[key] = {
            "timestamp": self._now,
            "data": value,
        }
        self.logger.success(f"Set cache for '{key}'", json.dumps(self._cache[key], indent=3))
        return

    def cache_save(self):
        with open(self._path_api_cache, "w") as f:
            YAML(typ="safe").dump(self._cache, f)
        self.logger.success(f"Cache file saved at {self._path_api_cache}.")
        return

    @property
    def path_root(self) -> Path:
        return self._path_root

    @property
    def path_meta(self) -> Path:
        return self._path_meta

    @property
    def path_meta_local(self) -> Path:
        return self._path_meta_local

    def _get_local_extensions(self) -> tuple[Path, bool]:
        self.logger.h3("Get Local Extensions")
        extention_defs = json.dumps(self._metadata["extensions"]).encode('utf-8')
        hash = hashlib.md5(extention_defs).hexdigest()
        self.logger.info(f"Looking for non-expired local extensions with hash '{hash}'.")
        dir_pattern = re.compile(
            r"^(20\d{2}_(?:0[1-9]|1[0-2])_(?:0[1-9]|[12]\d|3[01])_(?:[01]\d|2[0-3])_[0-5]\d_[0-5]\d)__"
            r"([a-fA-F0-9]{32})$"
        )
        for path in self._path_extensions_dir.iterdir():
            if path.is_dir():
                match = dir_pattern.match(path.name)
                if match and match.group(2) == hash and not self._is_expired(match.group(1), typ="extensions"):
                    self.logger.success(f"Found non-expired local extensions at '{path}'.")
                    return path, True
        self.logger.info(f"No non-expired local extensions found.")
        new_path = self._path_extensions_dir / f"{self._now}__{hash}"
        return new_path, False

    def _initialize_api_cache(self):
        self.logger.h3("Initialize Cache")
        if not self._path_api_cache.is_file():
            self.logger.info(f"API cache file not found at '{self._path_api_cache}'.")
            cache = {}
            return cache
        cache = self._read_yaml(self._path_api_cache)
        self.logger.success(f"API cache loaded from '{self._path_api_cache}'", json.dumps(cache, indent=3))
        return cache

    def _get_local_config(self):
        local_config = {
            "meta_cache_retention_days": {
                "api": 1,
                "extensions": 1
            }
        }
        self.logger.h3("Read Local Config")
        path_local_config = self._path_local / "config.yaml"
        if not path_local_config.is_file():
            self.logger.attention(
                f"Local config file '{path_local_config}' not found; setting default values.",
                json.dumps(local_config, indent=3)
            )
            return local_config
        local_config = local_config | self._read_yaml(
            path_local_config,
            schema=_util.file.datafile("schema_local_config.yaml")
        )
        self.logger.success("Local config set.", json.dumps(local_config, indent=3))
        return local_config

    def _read_core_metadata(self) -> dict:
        self.logger.h3("Read Core Metadata")
        data_path = self._path_meta / "data"
        if not data_path.is_dir():
            self.logger.error(
                f"Meta directory '{self._path_meta}' does not contain a 'data' directory"
            )
        metadata = self._read_data(self._path_meta)
        if not metadata:
            self.logger.error(f"No '.yaml' file found at {data_path}.")
        return metadata

    def _update_metadata_from_extensions(self) -> None:
        self.logger.h3("Read Extended Metadata")
        for idx, extension in enumerate(self._extensions):
            if extension["type"] in ["meta", "data"]:
                self.logger.h4(f"Read Extension Metadata {idx + 1}")
                extension_metadata = self._read_data(self._path_extensions / f"{idx + 1 :03}")
                if not extension_metadata:
                    if extension["type"] == "data":
                        self.logger.error(
                            f"Extension '{extension}' has type 'data' but no metadata were found."
                        )
                    else:
                        self.logger.skip(
                            f"Extension '{extension}' with type 'meta' has no metadata."
                        )
                    continue
                self._recursive_update(
                    self._metadata,
                    extension_metadata,
                    append_list=extension.get('append_list', True),
                    append_dict=extension.get('append_dict', True),
                    raise_on_duplicated=extension.get('raise_duplicate', False),
                )
        return

    def _add_metadata_default_values(self):
        self.logger.h3("Set Metadata Missing Values")
        defaults = self._read_yaml(_util.file.datafile("default_metadata.yaml"))
        for key, value in defaults.items():
            if key not in self._metadata:
                self._metadata[key] = value
                self.logger.success(f"Set default value for '{key}'", str(value))
            else:
                self.logger.skip(f"'{key}' already set", str(value))
        self.logger.success("Full metadata file assembled.", json.dumps(self._metadata, indent=3))
        return

    def _validate_metadata(self):
        self.logger.h3("Validate Metadata")
        with open(_util.file.datafile("schema_metadata.json")) as f:
            schema = json.load(f)
        try:
            jsonschema.validate(instance=self._metadata, schema=schema)
        except jsonschema.exceptions.ValidationError as e:
            self.logger.error(f"Invalid metadata schema: {e.message}.", traceback.format_exc())
        self.logger.success("Metadata schema validated")
        return

    def _read_data(self, dirpath_meta: Path) -> dict:
        """
        Read metadata from a single 'meta' directory.

        Parameters
        ----------
        dirpath_meta : Path
            Path to the 'meta' directory containing the 'data' subdirectory with metadata files.
        """
        dirpath_data = Path(dirpath_meta) / "data"
        metadata_files = list(dirpath_data.glob("*.yaml"))
        metadata = dict()
        for path_file in metadata_files:
            section = self._read_yaml(path_file)
            if not isinstance(section, dict):
                self.logger.error(
                    f"Invalid metadata file",
                    f"Expected a dict, but '{path_file}' had:\n{json.dumps(section, indent=3)}"
                )
            for new_key in section:
                if new_key in metadata:
                    self.logger.error(
                        f"Found a duplicate of metadata key '{new_key}' in '{path_file.name}'."
                    )
            metadata |= section
        return metadata

    def _read_package_config(self):
        self.logger.h3("Read Package Config")

        def read_path(path: Path, extension_nr: int = 0):
            dirpath_config = Path(path) / "config"
            paths_config_files = list(dirpath_config.glob("*.toml"))
            config = dict()
            for path_file in paths_config_files:
                with open(path_file) as f:
                    config_section: tomlkit.TOMLDocument = tomlkit.load(f)
                self._recursive_update(
                    config,
                    config_section,
                    append_list=True,
                    append_dict=True,
                    raise_on_duplicated=True
                )
            return config
        final_config = read_path(self._path_meta)
        if not self._extensions:
            return final_config
        for idx, extension in enumerate(self._extensions):
            if extension["type"] not in ["meta", "config"]:
                continue
            extension_config = read_path(self._path_extensions / f"{idx + 1 :03}", extension_nr=idx + 1)
            self._recursive_update(
                final_config,
                extension_config,
                append_list=extension.get('append_list', True),
                append_dict=extension.get('append_dict', True),
                raise_on_duplicated=extension.get('raise_duplicate', False),
            )
        return final_config


        return package_config

    def _download_extensions(self, extensions: list[dict], download_path: Path) -> None:
        dest_path = {
            "meta": ".",
            "config": "config",
            "data": "data",
            "template": "template",
            "health_file": "template/health_file",
            "license": "template/license",
            "issue": "template/issue",
            "discussion": "template/discussion",
            "pull": "template/pull",
            "media": "media",
            "logo": "media/logo",
        }
        self.logger.h3("Download Meta Extensions")
        _util.file.delete_dir_content(self._path_extensions_dir, exclude=["README.md"])
        for idx, extension in enumerate(extensions):
            self.logger.h4(f"Download Extension {idx + 1}")
            self.logger.info(f"Input: {extension}")
            repo_owner, repo_name = extension['repo'].split("/")
            dir_path = download_path / f"{idx + 1 :03}"
            try:
                extension_filepaths = self.github.user(repo_owner).repo(repo_name).download_content(
                    path=extension.get('path', ''),
                    ref=extension.get('ref'),
                    download_path=dir_path / dest_path[extension['type']],
                    recursive=True,
                    keep_full_path=False,
                )
            except WebAPIPersistentStatusCodeError as e:
                self.logger.error(f"Error downloading extension data:", str(e))
            if not extension_filepaths:
                self.logger.error(f"No files found in extension.")
            else:
                self.logger.success(
                    f"Downloaded extension files",
                    "\n".join([str(path.relative_to(dir_path)) for path in extension_filepaths])
                )
        return

    def _read_yaml(self, source: Path, schema: Path = None):
        self.logger.info(f"Read YAML from '{source}'.")
        try:
            content = YAML(typ="safe").load(source)
        except YAMLError as e:
            self.logger.error(f"Invalid YAML at '{source}': {e}.", traceback.format_exc())
        self.logger.success(
            f"YAML file successfully read from '{source}'", json.dumps(content, indent=3)
        )
        if not schema:
            return content
        schema = self._read_yaml(source=schema)
        try:
            jsonschema.validate(instance=content, schema=schema)
        except jsonschema.exceptions.ValidationError as e:
            self.logger.error(
                f"Schema validation failed for YAML file '{source}': {e.message}.", traceback.format_exc()
            )
        self.logger.success(f"Schema validation successful.")
        return content

    def _is_expired(self, timestamp: str, typ: Literal['api', 'extensions'] = 'api') -> bool:
        exp_date = datetime.datetime.strptime(timestamp, "%Y_%m_%d_%H_%M_%S") + datetime.timedelta(
            days=self._local_config["meta_cache_retention_days"][typ]
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
        def recursive(source, add, path=".", result=None, logger=None):
            for key, value in add.items():
                fullpath = f"{path}{key}"
                if key not in source:
                    result.append(f"{logger.emoji['success']} Added new key '{fullpath}'")
                    source[key] = value
                    continue
                if type(source[key]) != type(value):
                    result.append(
                        f"{logger.emoji['error']} Type mismatch: "
                        f"Key '{fullpath}' has type '{type(source[key])}' in 'source' "
                        f"but '{type(value)}' in 'add'."
                    )
                    logger.error(log_title, result)
                if not isinstance(value, (list, dict)):
                    if raise_on_duplicated:
                        result.append(
                            f"{logger.emoji['error']} Duplicated: "
                            f"Key '{fullpath}' with type '{type(value)}' already exists in 'source'."
                        )
                        logger.error(log_title, result)
                    result.append(f"{logger.emoji['skip']} Ignored key '{key}' with type '{type(value)}'")
                elif isinstance(value, list):
                    if append_list:
                        for elem in value:
                            if elem not in source[key]:
                                source[key].append(elem)
                                result.append(f"{logger.emoji['success']} Appended to list '{fullpath}'")
                            else:
                                result.append(f"{logger.emoji['skip']} Ignored duplicate in list '{fullpath}'")
                    elif raise_on_duplicated:
                        result.append(
                            f"{logger.emoji['error']} Duplicated: "
                            f"Key '{fullpath}' with type 'list' already exists in 'source'."
                        )
                        logger.error(log_title, result)
                    else:
                        result.append(f"{logger.emoji['skip']} Ignored key '{fullpath}' with type 'list'")
                else:
                    if append_dict:
                        recursive(source[key], value, f"{fullpath}.", result=result, logger=logger)
                    elif raise_on_duplicated:
                        result.append(
                            f"{logger.emoji['error']} Duplicated: "
                            f"Key '{fullpath}' with type 'dict' already exists in 'source'."
                        )
                        logger.error(log_title, result)
                    else:
                        result.append(f"{logger.emoji['skip']} Ignored key '{fullpath}' with type 'dict'")
            return result
        log_title = "Update dictionary recursively"
        result = recursive(source, add, result=[], logger=self.logger)
        self.logger.success(log_title, result)
        return
