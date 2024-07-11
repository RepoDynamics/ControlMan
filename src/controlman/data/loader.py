from pathlib import Path as _Path
import hashlib
import re

import pyserials as _pyserials
from loggerman import logger as _logger
import pylinks as _pylinks

from controlman._path_manager import PathManager as _PathManager
from controlman import _util


@_logger.sectioner("Load Control Center")
def load(path_manager: _PathManager, github_token: str | None = None) -> tuple[dict, dict]:
    data, local_config = _ControlCenterContentLoader(
        path_manager=path_manager, github_token=github_token,
    ).load()
    return data, local_config


class _ControlCenterContentLoader:
    def __init__(self, path_manager: _PathManager, github_token: str | None = None):
        self._github_token = github_token
        self._pathman = path_manager
        self._github_api = _pylinks.api.github(self._github_token)

        self._path_root = self._pathman.root
        self._path_cc = self._pathman.dir_meta
        return

    def load(self):
        full_data = {}
        for file in self._path_cc.glob('*'):
            if file.is_file() and file.suffix.lower() in ['.yaml', '.yml']:
                filename = file.relative_to(self._path_cc)
                _logger.section(f"Load Control Center File '{filename}'")
                parser = self.create_yaml_parser()
                with open(file, 'r') as f:
                    data = parser.load(f)
                duplicate_keys = set(data.keys()) & set(full_data.keys())
                if duplicate_keys:
                    raise RuntimeError(f"Duplicate keys '{', '.join(duplicate_keys)}' in project config")
                full_data.update(data)

        base_config = _util.file.read_datafile(
            path_repo=self._pathman.root,
            path_data=str((self._pathman.dir_meta / "config.yaml").relative_to(self._pathman.root)),
            schema="config",
            log_section_title=f"Read Config File",
        )
        metadata = {"config": base_config, "path": self._pathman.paths_dict}
        if self._pathman.file_local_config.is_file():
            base_config = _util.file.read_datafile(
                path_repo=self._pathman.root,
                path_data=str(self._pathman.file_local_config.relative_to(self._pathman.root)),
                schema="config",
                log_section_title="Read Local Config File",
            )
        extensions, path_extensions = self._load_extensions(config=base_config)
        for config_name, config_filepath in _CONFIG_FILEPATH.items():
            section = self._read_single_file(
                rel_path=config_filepath, extensions=extensions, path_extensions=path_extensions
            )
            if config_name != "project":
                if config_name in metadata:
                    raise RuntimeError(f"Duplicate config name '{config_name}'")
                metadata[config_name] = section
            else:
                for key in section:
                    if key in metadata:
                        raise RuntimeError(f"Duplicate key '{key}' in project config")
                    metadata[key] = section[key]
        return metadata, base_config

    def create_yaml_parser(self):

        def load_external_data(loader: SafeConstructor, node: ScalarNode):
            # Define the constructor for the !include tag
            tag_value = loader.construct_scalar(node)
            _logger.info("Load external data", code_title="Path", code=tag_value)
            if not tag_value:
                raise ValueError("The !ext tag requires a value")
            url, jsonpath_expr = tag_value.split(' ', 1)
            response = requests.get(url)
            response.raise_for_status()
            data_raw = response.text
            new_parser = self.create_yaml_parser()
            json_data = new_parser.load(data_raw)
            jsonpath_expr = jsonpath_ng.parse(jsonpath_expr)
            match = jsonpath_expr.find(json_data)
            if not match:
                raise ValueError(
                    f"No match found for JSONPath '{jsonpath_expr}' in the JSON data from '{url}'")
            value = match[0].value

            return new_parser.load(value)

        yaml = YAML(typ="safe")
        yaml.constructor.add_constructor(u'!ext', load_external_data)
        return yaml

    @_logger.sectioner("Load Control Center Extensions")
    def _load_extensions(self, config: dict) -> tuple[list[dict], _Path | None]:
        extensions: list[dict] = config.get("extensions", [])
        if not extensions:
            _logger.info("No extensions defined")
            return extensions, None
        local_path, exists = self._get_local_extensions(
            extensions, cache_retention_days=config["cache_retention_days"]["extensions"]
        )
        if not exists:
            self._download_extensions(extensions, download_path=local_path)
        return extensions, local_path

    @_logger.sectioner("Load Local Extensions")
    def _get_local_extensions(self, extensions: list[dict], cache_retention_days: float) -> tuple[_Path, bool]:
        file_hash = hashlib.md5(
            _pyserials.write.to_json_string(data=extensions, sort_keys=True, indent=None).encode("utf-8")
        ).hexdigest()
        new_path = self._pathman.dir_local_meta_extensions / f"{_util.time.now()}__{file_hash}"
        if not self._pathman.dir_local_meta_extensions.is_dir():
            _logger.info(
                f"Local extensions directory not found at '{self._pathman.dir_local_meta_extensions}'."
            )
            return new_path, False
        _logger.info(f"Looking for non-expired local extensions", code_title="Hash", code=file_hash)
        dir_pattern = re.compile(
            r"^(20\d{2}_(?:0[1-9]|1[0-2])_(?:0[1-9]|[12]\d|3[01])_(?:[01]\d|2[0-3])_[0-5]\d_[0-5]\d)__"
            r"([a-fA-F0-9]{32})$"
        )
        for path in self._pathman.dir_local_meta_extensions.iterdir():
            if path.is_dir():
                match = dir_pattern.match(path.name)
                if match and match.group(2) == file_hash and not _util.time.is_expired(
                    timestamp=match.group(1),
                    expiry_days=cache_retention_days
                ):
                    _logger.info(f"Found non-expired local extensions at '{path}'.")
                    return path, True
        _logger.info(f"No non-expired local extensions found.")
        return new_path, False

    @_logger.sectioner("Download Extensions")
    def _download_extensions(self, extensions: list[dict], download_path: _Path) -> None:
        self._pathman.dir_local_meta_extensions.mkdir(parents=True, exist_ok=True)
        _util.file.delete_dir_content(self._pathman.dir_local_meta_extensions, exclude=["README.md"])
        for idx, extension in enumerate(extensions):
            _logger.section(f"Download Extension {idx + 1}")
            _logger.debug(f"Extension data:", code=str(extension))
            repo_owner, repo_name = extension["repo"].split("/")
            dir_path = download_path / f"{idx + 1 :03}"
            full_dl_path = (dir_path / _CONFIG_FILEPATH[extension["type"]]).with_suffix(".yaml")
            try:
                extension_filepath = (
                    self._github_api.user(repo_owner)
                    .repo(repo_name)
                    .download_file(
                        path=extension["path"],
                        ref=extension.get("ref"),
                        download_path=full_dl_path.parent,
                        download_filename=full_dl_path.name,
                    )
                )
            except _pylinks.exceptions.WebAPIPersistentStatusCodeError as e:
                _logger.critical(title=f"Failed to download extension")
                raise e  # This will never be reached, but is required to satisfy the type checker and IDE.
            if not extension_filepath:
                _logger.critical(
                    title=f"Failed to download extension",
                    msg=f"No files found in extension:",
                    code=str(extension)
                )
            else:
                _logger.info(
                    f"Downloaded extension file '{extension_filepath}' from '{extension['repo']}'",
                )
            _logger.section_end()
        return

    def _read_single_file(self, rel_path: str, extensions: list[dict], path_extensions: _Path | None):


        section = _util.file.read_datafile(
            path_repo=self._pathman.root,
            path_data=str((self._pathman.dir_meta / filename).relative_to(self._pathman.root)),
            log_section_title="Read Main File"
        )
        has_extension = False
        for idx, extension in enumerate(extensions):
            if extension["type"] == rel_path.split("/")[-1]:
                has_extension = True
                _logger.section(f"Merge Extension {idx + 1}")
                extionsion_path = path_extensions / f"{idx + 1 :03}" / f"{rel_path}.yaml"
                section_extension = _util.file.read_datafile(
                    path_repo=self._pathman.root,
                    path_data=str(extionsion_path.relative_to(self._pathman.root)),
                    log_section_title="Read Extension File",
                )
                if not section_extension:
                    _logger.critical(
                        title=f"Failed to read extension file at {extionsion_path}",
                        msg=f"Extension file does not exist or is empty.",
                    )
                    # This will never be reached, but is required to satisfy the type checker and IDE.
                    raise Exception()
                try:
                    log = _pyserials.update.dict_from_addon(
                        data=section,
                        addon=section_extension,
                        append_list=extension["extend_arrays"],
                        append_dict=extension["extend_objects"],
                        raise_duplicates=extension["raise_duplicates"],
                    )
                except _pyserials.exception.DictUpdateError as e:
                    _logger.critical(
                        title=f"Failed to merge extension file at {extionsion_path} to '{filename}'",
                        msg=e.message,
                    )
                    raise e  # This will never be reached, but is required to satisfy the type checker and IDE.
                _logger.info(
                    title=f"Successfully merged extension file at '{extionsion_path}' to '{filename}'.",
                    msg=str(log),
                )
                _logger.section_end()
        # _util.file.validate_data(
        #     data=section, schema_relpath=rel_path, datafile_ext=ext, is_dir=False, has_extension=has_extension
        # )
        _logger.section_end()
        return section
