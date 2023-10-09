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
        github_token: Optional[str] = None,
        logger: Logger = None
    ):
        self.logger = logger or Logger()
        self.logger.h2("Process Meta Source Files")
        self._github_token = github_token
        self._path = PathReader(path_root=path_root, logger=self.logger)
        self._local_config = self._get_local_config()

        self._extensions, self._path_extensions = self._read_extensions()
        self._metadata: dict = self._read_raw_metadata()

        if self._metadata.get("package"):
            self._package_config = self._read_package_config()
        else:
            self._package_config = None

        self._cache: dict = self._initialize_api_cache()
        self._db = self._read_datafile(_util.file.datafile("db.yaml"))
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
                return self._read_datafile(path)
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
        with open(self.path.local_api_cache, "w") as f:
            YAML(typ="safe").dump(self._cache, f)
        self.logger.success(f"Cache file saved at {self.path.local_api_cache}.")
        return

    @property
    def path(self):
        return self._path

    def _read_extensions(self) -> tuple[dict, Path | None]:
        extensions = _util.dict.read(
            path=self.path.meta_core_extensions,
            schema=self._get_schema("core/extensions"),
            logger=self.logger
        )
        if not extensions["extensions"]:
            return extensions, None
        local_path, exists = self._get_local_extensions(extensions["extensions"])
        if not exists:
            self._download_extensions(extensions["extensions"], download_path=local_path)
        return extensions, local_path

    def _get_local_extensions(self, extensions: list[dict]) -> tuple[Path, bool]:
        self.logger.h3("Get Local Extensions")
        extention_defs = json.dumps(extensions).encode('utf-8')
        hash = hashlib.md5(extention_defs).hexdigest()
        self.logger.info(f"Looking for non-expired local extensions with hash '{hash}'.")
        dir_pattern = re.compile(
            r"^(20\d{2}_(?:0[1-9]|1[0-2])_(?:0[1-9]|[12]\d|3[01])_(?:[01]\d|2[0-3])_[0-5]\d_[0-5]\d)__"
            r"([a-fA-F0-9]{32})$"
        )
        for path in self.path.dir_local_meta_extensions.iterdir():
            if path.is_dir():
                match = dir_pattern.match(path.name)
                if match and match.group(2) == hash and not self._is_expired(match.group(1), typ="extensions"):
                    self.logger.success(f"Found non-expired local extensions at '{path}'.")
                    return path, True
        self.logger.info(f"No non-expired local extensions found.")
        new_path = self.path.dir_local_meta_extensions / f"{self._now}__{hash}"
        return new_path, False

    def _download_extensions(self, extensions: list[dict], download_path: Path) -> None:
        dest_path = {
            "meta": ".",
            "config": "config",
            "pyproject": "config/pyproject",
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
        _util.file.delete_dir_content(self.path.dir_local_meta_extensions, exclude=["README.md"])
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

    def _initialize_api_cache(self):
        self.logger.h3("Initialize Cache")
        if not self.path.local_api_cache.is_file():
            self.logger.info(f"API cache file not found at '{self.path.local_api_cache}'.")
            cache = {}
            return cache
        cache = self._read_datafile(self.path.local_api_cache)
        self.logger.success(f"API cache loaded from '{self.path.local_api_cache}'", json.dumps(cache, indent=3))
        return cache

    def _get_local_config(self):
        self.logger.h3("Read Local Config")
        local_config = self._read_datafile(
            source=self.path.local_config,
            schema=self._get_schema("local_config"),
        )
        self.logger.success("Local config set.", json.dumps(local_config, indent=3))
        return local_config

    def _read_raw_metadata(self):
        self.logger.h3("Read Raw Metadata")
        data = [
            "core/credits",
            "core/intro",
            "core/license",
            "dev/branches",
            "dev/changelogs",
            "dev/commits",
            "dev/issues",
            "dev/labels",
            "dev/maintainers",
            "dev/repo",
            "dev/tags",
            "dev/workflows",
            "package/metadata",
            "ui/health_files",
            "ui/readme",
            "ui/theme",
            "ui/web",
        ]
        metadata = {}
        for entry in data:
            section = self._read_datafile(self.path.dir_meta / f"{entry}.yaml")
            for idx, extension in enumerate(self._extensions["extensions"]):
                if extension["type"] == entry:
                    self.logger.h4(f"Read Extension Metadata {idx + 1}")
                    extionsion_path = self._path_extensions / f"{idx + 1 :03}" / f"{entry}.yaml"
                    section_extension = self._read_datafile(extionsion_path, raise_missing=True)
                    self._recursive_update(
                        source=section,
                        add=section_extension,
                        append_list=extension['append_list'],
                        append_dict=extension['append_dict'],
                        raise_on_duplicated=extension['raise_duplicate']
                    )
            self._validate_datafile(source=section, schema=entry)
            shared_keys = set(metadata.keys()) & set(section.keys())
            if shared_keys:
                self.logger.error(
                    f"Found duplicate metadata key(s) '{shared_keys}' in {entry}.yaml."
                )
            metadata |= section
        self.logger.success("Full metadata file assembled.", json.dumps(metadata, indent=3))
        return metadata

    def _read_package_config(self):
        self.logger.h3("Read Package Config")

        def read_path(path: Path):
            dirpath_config = Path(path) / "config" / "pyproject"
            paths_config_files = list(dirpath_config.glob("*.toml"))
            config = dict()
            for path_file in paths_config_files:
                config_section: tomlkit.TOMLDocument = _util.dict.read(path=path_file)
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
            extension_config = read_path(self._path_extensions / f"{idx + 1 :03}")
            self._recursive_update(
                final_config,
                extension_config,
                append_list=extension.get('append_list', True),
                append_dict=extension.get('append_dict', True),
                raise_on_duplicated=extension.get('raise_duplicate', False),
            )
        return final_config

    def _read_datafile(self, source: Path, schema: Path = None, **kwargs):
        return _util.dict.read(path=source, schema=schema, logger=self.logger, **kwargs)

    def _validate_datafile(self, source: dict, schema: str):
        return _util.dict.validate_schema(source=source, schema=self._get_schema(schema), logger=self.logger)

    @staticmethod
    def _get_schema(schema: str):
        return _util.file.datafile(f"schema/{schema}.yaml")

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
        _util.dict.update_recursive(
            source=source,
            add=add,
            append_list=append_list,
            append_dict=append_dict,
            raise_on_duplicated=raise_on_duplicated,
            logger=self.logger
        )
        return


class PathReader:
    def __init__(self, path_root: str | Path, logger: Logger | None = None):
        self._logger = logger or Logger()
        self._path_root = Path(path_root).resolve()
        self._paths = _util.dict.read(
            path=self._path_root / ".path.json",
            schema=_util.file.datafile("schema/path.yaml"),
            logger=self._logger
        )

        if not self.dir_meta.is_dir():
            self._logger.error(f"Input meta directory '{self.dir_meta}' not found.")

        if not self.dir_local_meta_extensions.is_dir():
            self._logger.error(
                f"Could not find Local meta extensions directory at: '{self.dir_local_meta_extensions}'."
            )
        return

    @property
    def paths(self) -> dict:
        return self._paths

    @property
    def root(self):
        return self._path_root

    @property
    def dir_source(self):
        return self._path_root / self._paths["dir"]["source"]

    @property
    def dir_meta(self):
        return self._path_root / self._paths["dir"]["meta"]

    @property
    def dir_local(self):
        return self._path_root / self._paths["dir"]["local"]

    @property
    def dir_local_meta(self):
        return self.dir_local / "meta"

    @property
    def dir_local_meta_extensions(self):
        return self.dir_local_meta / "extensions"

    @property
    def dir_meta_package_config_build(self):
        return self.dir_meta / "package" / "config_build"

    @property
    def dir_meta_package_config_tools(self):
        return self.dir_meta / "package" / "config_tools"

    @property
    def local_config(self) -> Path:
        return self._path_root / self._paths["file"]["meta"]["config_local"]

    @property
    def local_api_cache(self):
        return self.dir_local_meta / "api_cache.yaml"

    @property
    def meta_core_extensions(self):
        return self.dir_meta / "core" / "extensions.yaml"



