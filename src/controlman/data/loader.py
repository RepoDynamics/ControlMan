from pathlib import Path as _Path
import hashlib
import re

import pyserials as _pyserials
from loggerman import logger as _logger
import pylinks as _pylinks

from controlman._path_manager import PathManager as _PathManager
from controlman import _util


@_logger.sectioner("Load Control Center Contents")
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
        self._extensions: list[dict] | None = None
        self._path_extensions: _Path | None = None
        return

    def load(self):
        local_config = self._load_config()
        self._extensions, self._path_extensions = self._load_extensions(
            cache_retention_days=local_config["cache_retention_days"]["extensions"]
        )
        data: dict = self._load_data()
        data["extensions"] = self._extensions
        data["path"] = self._pathman.paths_dict
        data["path"]["file"] = {
            "website_announcement": f"{data['path']['dir']['website']}/announcement.html",
            "readme_pypi": f"{data['path']['dir']['source']}/README_pypi.md",
        }
        return data, local_config

    @_logger.sectioner("Load Control Center Configurations")
    def _load_config(self):
        if self._pathman.file_local_config.is_file():
            source_path = self._pathman.file_local_config
            source = "Local"
        else:
            source_path = self._pathman.dir_meta / "config.yaml"
            source = "Main"
        local_config = _util.file.read_datafile(
            path_repo=self._pathman.root,
            path_data=str(source_path.relative_to(self._pathman.root)),
            relpath_schema="config",
            log_section_title=f"Read {source} Config File",
        )
        return local_config

    @_logger.sectioner("Load Control Center Extensions")
    def _load_extensions(self, cache_retention_days: float) -> tuple[list[dict], _Path | None]:
        extensions: list[dict] = _util.file.read_datafile(
            path_repo=self._pathman.root,
            path_data=str(self._pathman.file_meta_core_extensions.relative_to(self._pathman.root)),
            relpath_schema="extensions",
            root_type=list,
            log_section_title="Read Extensions Declaration File",
        )
        if not extensions:
            _logger.info("No extensions defined")
            return extensions, None
        local_path, exists = self._get_local_extensions(extensions, cache_retention_days=cache_retention_days)
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
            rel_dl_path = _Path(extension["type"])
            if extension["type"] == "package/build":
                rel_dl_path = rel_dl_path.with_suffix(".toml")
            elif extension["type"] == "package/tools":
                filename = _Path(extension["path"]).with_suffix(".toml").name
                rel_dl_path = rel_dl_path / filename
            else:
                rel_dl_path = rel_dl_path.with_suffix(".yaml")
            full_dl_path = dir_path / rel_dl_path
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

    @_logger.sectioner("Load Control Center Data")
    def _load_data(self):
        metadata = {}
        for entry in ("credits", "intro", "license"):
            section = self._read_single_file(rel_path=f"project/{entry}")
            try:
                log = _pyserials.update.dict_from_addon(
                    data=metadata,
                    addon=section,
                    append_list=False,
                    append_dict=True,
                    raise_duplicates=True,
                )
            except _pyserials.exception.DictUpdateError as e:
                _logger.critical(
                    title=f"Failed to merge data file '{entry}' into control center data",
                    msg=e.message,
                )
                raise e  # This will never be reached, but is required to satisfy the type checker and IDE.
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
                log = _pyserials.update.dict_from_addon(
                    data=metadata,
                    addon=section,
                    append_list=False,
                    append_dict=True,
                    raise_duplicates=True,
                )
            except _pyserials.exception.DictUpdateError as e:
                _logger.critical(
                    title=f"Failed to merge data file '{entry}' into control center data",
                    msg=e.message,
                )
                raise e  # This will never be reached, but is required to satisfy the type checker and IDE.
        package = {}
        if (self._pathman.dir_meta / "package_python").is_dir():
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
                    log = _pyserials.update.dict_from_addon(
                        data=package,
                        addon=section,
                        append_list=False,
                        append_dict=True,
                        raise_duplicates=True,
                    )
                except _pyserials.exception.DictUpdateError as e:
                    _logger.critical(
                        title=f"Failed to merge data file '{entry}' into control center data",
                        msg=e.message,
                    )
                    raise e  # This will never be reached, but is required to satisfy the type checker and IDE.
            package["pyproject_tests"] = self._read_single_file(
                rel_path="package_python/build_tests", ext="toml"
            )
            package["pyproject"] = self._read_package_python_pyproject()
        else:
            package["type"] = None
        metadata["package"] = package
        return metadata

    def _read_single_file(self, rel_path: str, ext: str = "yaml"):
        filename = f"{rel_path}.{ext}"
        _logger.section(f"Load Control Center File '{filename}'")
        section = _util.file.read_datafile(
            path_repo=self._pathman.root,
            path_data=str((self._pathman.dir_meta / filename).relative_to(self._pathman.root)),
            log_section_title="Read Main File"
        )
        has_extension = False
        for idx, extension in enumerate(self._extensions):
            if extension["type"] == rel_path:
                has_extension = True
                _logger.section(f"Merge Extension {idx + 1}")
                extionsion_path = self._path_extensions / f"{idx + 1 :03}" / f"{rel_path}.{ext}"
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
                        append_list=extension["append_list"],
                        append_dict=extension["append_dict"],
                        raise_duplicates=extension["raise_duplicate"],
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
        _util.file.validate_data(
            data=section, schema_relpath=rel_path, datafile_ext=ext, is_dir=False, has_extension=has_extension
        )
        _logger.section_end()
        return section

    @_logger.sectioner("Load Package Pyproject")
    def _read_package_python_pyproject(self):

        def read_package_tools_config(path: _Path):
            dirpath_config = _Path(path) / "package_python" / "tools"
            paths_config_files = list(dirpath_config.glob("*.toml"))
            config = dict()
            for path_file in paths_config_files:
                config_section = _util.file.read_datafile(
                    path_repo=self._pathman.root, path_data=str(path_file.relative_to(self._pathman.root))
                )
                try:
                    log = _pyserials.update.dict_from_addon(
                        data=config,
                        addon=config_section,
                        append_list=True,
                        append_dict=True,
                        raise_duplicates=True,
                    )
                except _pyserials.exception.DictUpdateError as e:
                    # TODO
                    pass
            return config

        build = self._read_single_file(rel_path="package_python/build", ext="toml")
        _logger.section("Load Package Tools Configurations")
        _logger.section("Read Main Configurations")
        tools = read_package_tools_config(self._pathman.dir_meta)
        _logger.section_end()
        has_extension = False
        for idx, extension in enumerate(self._extensions):
            if extension["type"] == "package_python/tools":
                has_extension = True
                _logger.section(f"Merge Extension {idx + 1}")
                extension_config = read_package_tools_config(self._path_extensions / f"{idx + 1 :03}")
                try:
                    log = _pyserials.update.dict_from_addon(
                        data=tools,
                        addon=extension_config,
                        append_list=extension["append_list"],
                        append_dict=extension["append_dict"],
                        raise_duplicates=extension["raise_duplicate"],
                    )
                except _pyserials.exception.DictUpdateError as e:
                    _logger.critical(
                        title=f"Failed to merge extension",
                        message=e.message,
                    )
                    raise e  # This will never be reached, but is required to satisfy the type checker and IDE.
                _logger.section_end()
        _logger.section_end()
        _util.file.validate_data(
            data=tools, schema_relpath="package_python/tools", is_dir=True, has_extension=has_extension,
        )
        try:
            log = _pyserials.update.dict_from_addon(
                data=build,
                addon=tools,
                append_list=True,
                append_dict=True,
                raise_duplicates=True,
            )
        except _pyserials.exception.DictUpdateError as e:
            _logger.critical(
                title=f"Failed to merge tools configurations to package pyproject",
                message=e.message,
            )
            raise e  # This will never be reached, but is required to satisfy the type checker and IDE.
        return build
