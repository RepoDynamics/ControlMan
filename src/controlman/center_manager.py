from pathlib import Path as _Path
import shutil as _shutil

from versionman import PEP440SemVer as _PEP440SemVer
from loggerman import logger as _logger
import pylinks as _pylinks
import pyserials as _ps
from gittidy import Git as _Git
from markitup.html import elem as _html

from controlman import data_gen as _data_gen
from controlman.hook_manager import HookManager as _HookManager
from controlman.datatype import (
    DynamicFileChangeType,
    DynamicDirType,
    DynamicFile as _GeneratedFile,
    DynamicDir as _DynamicDir,
)
from controlman import const
from controlman.cache_manager import CacheManager
from controlman import file_gen as _file_gen
from controlman import data_loader as _data_loader
from controlman import data_validator as _data_validator


class CenterManager:

    def __init__(
        self,
        git_manager: _Git,
        cc_path: _Path,
        data_before: _ps.NestedDict,
        data_main: _ps.NestedDict,
        github_token: str | None = None,
        future_versions: dict[str, str | _PEP440SemVer] | None = None,
    ):
        self._git: _Git = git_manager
        self._path_cc = cc_path
        self._data_before: _ps.NestedDict = data_before
        self._data_main: _ps.NestedDict = data_main
        self._github_api = _pylinks.api.github(token=github_token)
        self._future_vers = future_versions or {}

        self._path_root = self._git.repo_path
        self._hook_manager = _HookManager(dir_path=self._path_cc / const.DIRNAME_CC_HOOK)
        self._cache_manager: CacheManager = CacheManager(
            path_repo=self._path_root,
            retention_hours=self._data_before.get("control.cache.retention_hours", {}),
        )

        self._data_raw: _ps.NestedDict | None = None
        self._data: _ps.NestedDict | None = None
        self._files: list[_GeneratedFile] = []
        self._dirs: list[_DynamicDir] = []
        self._dirs_to_apply: list[tuple[str, str, DynamicFileChangeType]] = []
        self._changes: list[tuple[str, DynamicFileChangeType]] = []
        return

    def load(self) -> _ps.NestedDict:
        if self._data_raw:
            return self._data_raw
        full_data = _data_loader.load(
            control_center_path=self._path_cc,
            cache_manager=self._cache_manager,
        )
        if self._hook_manager.has_hook(const.FUNCNAME_CC_HOOK_POST_LOAD):
            full_data = self._hook_manager.generate(
                const.FUNCNAME_CC_HOOK_POST_LOAD,
                full_data,
            )
        _data_validator.validate(data=full_data, before_substitution=True)
        self._data_raw = _ps.NestedDict(full_data)
        return self._data_raw

    def generate_data(self) -> _ps.NestedDict:
        if self._data:
            return self._data
        self.load()
        data = _data_gen.generate(
            git_manager=self._git,
            cache_manager=self._cache_manager,
            github_api=self._github_api,
            data=self._data_raw,
            data_before=self._data_before,
            data_main=self._data_main,
            future_versions=self._future_vers,
        )
        if self._hook_manager.has_hook(const.FUNCNAME_CC_HOOK_POST_DATA):
            self._hook_manager.generate(
                const.FUNCNAME_CC_HOOK_POST_DATA,
                data,
            )
        self._cache_manager.save()
        data.fill()
        _data_validator.validate(data=data())
        self._data = data
        return self._data

    def generate_files(self) -> list[_GeneratedFile]:
        if self._files:
            return self._files
        self.generate_data()
        self._files = _file_gen.generate(
            data=self._data,
            data_before=self._data_before,
            repo_path=self._path_root,
        )
        return self._files

    def compare(self):
        if self._changes and self._files and self._dirs:
            return self._changes, self._files, self._dirs
        files = self.generate_files()
        metadata_changes = _ps.compare.items(source=self._data(), target=self._data_before(), path="")
        all_paths = []
        for change_type in ("removed", "added", "modified"):
            for changed_key in metadata_changes[change_type]:
                all_paths.append((changed_key.removeprefix("$."), DynamicFileChangeType[change_type.upper()]))
        self._changes = all_paths
        dirs = self._compare_dirs()
        return self._changes, files, dirs

    def report(self) -> tuple[bool, _html.Figure, _html.Figure, _html.Figure, _html.Figure]:
        self.compare()
        table_data = self._report_metadata()
        table_files = self._report_files()
        table_dirs = self._report_dirs()
        rows = []
        sections = []
        has_changes = False
        for table, name in ((table_data, "Metadata"), (table_files, "Files"), (table_dirs, "Directories")):
            change_title = "Sync" if table else "No Changes"
            change_emoji = "🔄" if table else "✅"
            rows.append([name, (change_emoji, {"title": change_title})])
            if table:
                sections.append(_html.details([_html.summary(name), _html.br(), table]))
                has_changes = True
        summary_figure = _html.table_from_rows(
            body_rows=rows,
            head_rows=["Type", "Status"],
            as_figure=True,
            caption=f"Changes in the project's metadata and dynamic content.",
        )

        report = [_miu.html.h(1, "Control Center Report"), summary_table] + sections
        return has_changes, summary_table, table_data, table_files, table_dirs, _miu.html.ElementCollection(report)

    @_logger.sectioner("Apply Changes To Dynamic Repository File")
    def apply_changes(self) -> None:
        """Apply changes to dynamic repository files."""

        generated_files = self.generate_files()
        self._compare_dirs()
        for dir_path, dir_path_before, status in self._dirs_to_apply:
            dir_path_abs = self._path_root / dir_path if dir_path else None
            dir_path_before_abs = self._path_root / dir_path_before if dir_path_before else None
            if status is DynamicFileChangeType.REMOVED:
                _shutil.rmtree(dir_path_before_abs)
            elif status is DynamicFileChangeType.MOVED:
                _shutil.move(dir_path_before_abs, dir_path_abs)
            elif status is DynamicFileChangeType.ADDED:
                dir_path_abs.mkdir(parents=True, exist_ok=True)
        for generated_file in generated_files:
            filepath_abs = self._path_root / generated_file.path if generated_file.path else None
            filepath_before_abs = self._path_root / generated_file.path_before if generated_file.path_before else None
            if generated_file.change is DynamicFileChangeType.REMOVED:
                filepath_before_abs.unlink(missing_ok=True)
            elif generated_file.change in (
                DynamicFileChangeType.ADDED,
                DynamicFileChangeType.MODIFIED,
                DynamicFileChangeType.MOVED_MODIFIED,
                DynamicFileChangeType.MOVED,
            ):
                filepath_abs.parent.mkdir(parents=True, exist_ok=True)
                with open(filepath_abs, "w") as f:
                    f.write(f"{generated_file.content.strip()}\n")
                if generated_file.change in (DynamicFileChangeType.MOVED, DynamicFileChangeType.MOVED_MODIFIED):
                    filepath_before_abs.unlink(missing_ok=True)
        return

    def _compare_dirs(self):

        def compare_source(main_key: str, root_path: str, root_path_before: str):
            source_name, source_name_before = self._get_dirpath(f"{main_key}.path.source")
            source_path = f"{root_path}/{source_name}" if root_path else None
            source_path_before_real = f"{root_path_before}/{source_name_before}" if root_path_before and source_name_before else None
            change = self._compare_dir_paths(source_path, source_path_before_real)
            source_path_before = f"{root_path}/{source_name_before}" if root_path and source_name_before else None
            return source_path, source_path_before, source_path_before_real, change

        def compare_import(main_key: str, source_path: str, source_path_before: str, source_path_before_real: str):
            import_name, import_name_before = self._get_dirpath(f"{main_key}.import_name")
            import_path = f"{source_path}/{import_name}" if source_path and import_name else None
            import_path_before_real = f"{source_path_before_real}/{import_name_before}" if source_path_before_real and import_name_before else None
            change = self._compare_dir_paths(import_path, import_path_before_real)
            import_path_before = f"{source_path}/{import_name_before}" if source_path and import_name_before else None
            return import_path, import_path_before, import_path_before_real, change

        if self._dirs:
            return self._dirs
        dirs = []
        to_apply = []
        for path_key in ("theme", "control", "local"):
            path, path_before, status = self._compare_dir(f"{path_key}.path")
            dirs.append(
                _DynamicDir(
                    type=DynamicDirType[path_key.upper()],
                    path=path,
                    path_before=path_before,
                    change=status
                )
            )
            to_apply.append((path, path_before, status))
        for path_key in ("web", "pkg", "test"):
            root_path, root_path_before, root_status = self._compare_dir(f"{path_key}.path.root")
            dirs.append(
                _DynamicDir(
                    type=DynamicDirType[f"{path_key.upper()}_ROOT"],
                    path=root_path,
                    path_before=root_path_before,
                    change=root_status
                )
            )
            to_apply.append((root_path, root_path_before, root_status))
            source_path, source_path_before, source_path_before_real, source_change = compare_source(
                main_key=path_key, root_path=root_path, root_path_before=root_path_before
            )
            dirs.append(
                _DynamicDir(
                    type=DynamicDirType[f"{path_key.upper()}_SRC"],
                    path=source_path,
                    path_before=source_path_before_real,
                    change=source_change
                )
            )
            to_apply.append((source_path, source_path_before, source_change))
            if path_key == "web":
                continue
            import_path, import_path_before, import_path_before_real, import_change = compare_import(
                main_key=path_key, source_path=source_path, source_path_before=source_path_before, source_path_before_real=source_path_before_real
            )
            dirs.append(
                _DynamicDir(
                    type=DynamicDirType[f"{path_key.upper()}_IMPORT"],
                    path=import_path,
                    path_before=import_path_before_real,
                    change=import_change
                )
            )
            to_apply.append((import_path, import_path_before, import_change))
        self._dirs = dirs
        self._dirs_to_apply = to_apply
        return self._dirs

    def _compare_dir(self, path_key: str) -> tuple[str, str, DynamicFileChangeType]:
        path, path_before = self._get_dirpath(path_key)
        return path, path_before, self._compare_dir_paths(path, path_before)

    def _get_dirpath(self, path_key: str) -> tuple[str, str]:
        path = self._data[path_key]
        path_before = self._data_before[path_key]
        return path, path_before

    def _compare_dir_paths(self, path, path_before) -> DynamicFileChangeType:
        path_before_exists = (self._path_root / path_before).is_dir() if path_before else False
        if path and path_before_exists:
            status = DynamicFileChangeType.UNCHANGED if path == path_before else DynamicFileChangeType.MOVED
        elif not path and not path_before_exists:
            status = DynamicFileChangeType.DISABLED
        elif path_before_exists:
            status = DynamicFileChangeType.REMOVED
        else:
            path_exists = (self._path_root / path).is_dir()
            status = DynamicFileChangeType.UNCHANGED if path_exists else DynamicFileChangeType.ADDED
        return status

    def _report_metadata(self):
        if not self._changes:
            return
        rows = []
        for changed_key, change_type in sorted(self._changes, key=lambda elem: elem[0]):
            change = change_type.value
            rows.append([_html.code(changed_key), (change.emoji, {"title": change.title})])
        figure = _html.table_from_rows(
            body_rows=rows,
            head_rows=["Path", "Change"],
            as_figure=True,
            caption=f"Changes in the project's metadata.",
        )
        return figure

    def _report_files(self):
        rows = []
        for file in sorted(
            self.generate_files(),
            key=lambda elem: (elem.type.value[1], elem.subtype[1]),
        ):
            if file.change in (DynamicFileChangeType.DISABLED, DynamicFileChangeType.UNCHANGED):
                continue
            change = file.change.value
            rows.append(
                [
                    file.type.value[1],
                    file.subtype[1],
                    (change.emoji, {"title": change.title}),
                    _html.code(file.path),
                    _html.code(file.path_before) if file.path_before else "—"
                ]
            )
        if not rows:
            return
        figure = _html.table_from_rows(
            body_rows=rows,
            head_rows=["Type", "Subtype", "Change", "Path", "Old Path"],
            as_figure=True,
            caption=f"Changes in the project's dynamic files.",
        )
        return figure

    def _report_dirs(self):
        rows = []
        for dir_ in sorted(self._dirs, key=lambda elem: elem.type.value):
            if dir_.change in (DynamicFileChangeType.DISABLED, DynamicFileChangeType.UNCHANGED):
                continue
            change = dir_.change.value
            rows.append(
                [
                    dir_.type.value,
                    (change.emoji, {"title": change.title}),
                    _html.code(dir_.path),
                    _html.code(dir_.path_before or "—"),
                ]
            )
        if not rows:
            return
        figure = _html.table_from_rows(
            body_rows=rows,
            head_rows=["Type", "Change", "Path", "Old Path"],
            as_figure=True,
            caption=f"Changes in the project's dynamic directories.",
        )
        return figure
