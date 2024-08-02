from pathlib import Path as _Path
import shutil as _shutil

from versionman import PEP440SemVer as _PEP440SemVer
from loggerman import logger as _logger
import pylinks as _pylinks
import pyserials as _ps
from gittidy import Git as _Git

from controlman.data_validator import DataValidator as _DataValidator
from controlman import data_gen as _data_gen
from controlman.hook_manager import HookManager as _HookManager
from controlman.datatype import (
    DynamicFileType as _DynamicFileType,
    DynamicFileChangeType,
    GeneratedFile as _GeneratedFile,
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
        self._files: list[tuple[_GeneratedFile, DynamicFileChangeType]] = []
        self._compared_dirs: list = []
        self._dirs_to_apply: list[tuple[str, str, DynamicFileChangeType]] = []
        self._dirs_to_apply_sub: list[tuple[str, str, DynamicFileChangeType]] = []
        self._changes: dict[_DynamicFileType, dict[str, bool]] = {}
        self._summary: str = ""
        return

    def load(self) -> dict:
        if self._data_raw:
            return self._data_raw()
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
        return full_data

    def generate_data(self) -> dict:
        if self._data:
            return self._data()
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
        return data()

    def generate_files(self) -> list[tuple[_GeneratedFile, DynamicFileChangeType]]:
        if self._files:
            return self._files
        self.generate_data()
        self._files = _file_gen.generate(
            data=self._data,
            data_before=self._data_before,
            repo_path=self._path_root,
        )
        return self._files

    def compare_dirs(self):

        def compare_source(main_key: str, root_path: str):
            source_name, source_name_before, source_status = self._compare_dir(f"{main_key}.path.source")
            source_path = f"{root_path}/{source_name}" if root_path else None
            source_path_before = f"{root_path}/{source_name_before}" if root_path else None
            return source_path, source_path_before, source_status

        def compare_import(main_key: str, source_path: str):
            import_name, import_name_before, import_status = self._compare_dir(f"{main_key}.import_name")
            import_path = f"{source_path}/{import_name}" if source_path else None
            import_path_before = f"{source_path}/{import_name_before}" if root_path else None
            return import_path, import_path_before, import_status


        if self._compared_dirs:
            return self._compared_dirs
        compared_dirs = []
        for_apply = []
        for path_key in ("theme", "control", "local"):
            path, path_before, status = self._compare_dir(f"{path_key}.path")
            for_apply.append((path, path_before, status))
        for path_key in ("web", "pkg", "test"):
            root_path, root_path_before, root_status = self._compare_dir(f"{path_key}.path.root")
            for_apply.append((root_path, root_path_before, root_status))
            source_data = compare_source(main_key=path_key, root_path=root_path)
            for_apply.append(source_data)
            if path_key == "web":
                continue
            import_data = compare_import(main_key=path_key, source_path=source_data[0])
            for_apply.append(import_data)
        self._dirs_to_apply = for_apply
        self._compared_dirs = compared_dirs
        return self._compared_dirs

    # def _summary(
    #     self, results: list[tuple[DynamicFile, Diff]]
    # ) -> tuple[dict[DynamicFileType, dict[str, bool]], str]:
    #     details, changes = self._summary_section_details(results)
    #     summary = html.ElementCollection([html.h(3, "Meta")])
    #     any_changes = any(any(category.values()) for category in changes.values())
    #     if not any_changes:
    #         rest = [html.ul(["✅ All dynamic files were in sync with meta content."]), html.hr()]
    #     else:
    #         rest = [
    #             html.ul(["❌ Some dynamic files were out of sync with meta content:"]),
    #             details,
    #             html.hr(),
    #             self._color_legend(),
    #         ]
    #     summary.extend(rest)
    #     return changes, str(summary)

    @_logger.sectioner("Apply Changes To Dynamic Repository File")
    def apply_changes(self) -> None:
        """Apply changes to dynamic repository files."""

        generated_files = self.generate_files()
        self.compare_dirs()
        for dir_path, dir_path_before, status in self._dirs_to_apply:
            dir_path_abs = self._path_root / dir_path if dir_path else None
            dir_path_before_abs = self._path_root / dir_path_before if dir_path_before else None
            if status is DynamicFileChangeType.REMOVED:
                _shutil.rmtree(dir_path_before_abs)
            elif status is DynamicFileChangeType.MOVED:
                _shutil.move(dir_path_before_abs, dir_path_abs)
            elif status is DynamicFileChangeType.CREATED:
                dir_path_abs.mkdir(parents=True, exist_ok=True)
        for generated_file, status in generated_files:
            filepath_abs = self._path_root / generated_file.path if generated_file.path else None
            filepath_before_abs = self._path_root / generated_file.path_before if generated_file.path_before else None
            if status is DynamicFileChangeType.REMOVED:
                filepath_before_abs.unlink(missing_ok=True)
            elif status in (
                DynamicFileChangeType.CREATED,
                DynamicFileChangeType.MODIFIED,
                DynamicFileChangeType.MOVED_MODIFIED,
                DynamicFileChangeType.MOVED,
            ):
                filepath_abs.parent.mkdir(parents=True, exist_ok=True)
                with open(filepath_abs, "w") as f:
                    f.write(f"{generated_file.content.strip()}\n")
                if status in (DynamicFileChangeType.MOVED, DynamicFileChangeType.MOVED_MODIFIED):
                    filepath_before_abs.unlink(missing_ok=True)
        return

    def _compare_dir(self, path_key: str) -> tuple[str, str, DynamicFileChangeType]:
        path = self._data[path_key]
        path_before = self._data_before[path_key]
        if not path and not path_before:
            status = DynamicFileChangeType.DISABLED
        elif not path_before:
            status = DynamicFileChangeType.CREATED
        elif not path:
            status = DynamicFileChangeType.REMOVED
        elif path == path_before:
            status = DynamicFileChangeType.UNCHANGED
        else:
            status = DynamicFileChangeType.MOVED
        return path, path_before, status

    # def _summary_section_details(
    #     self, results: list[tuple[DynamicFile, Diff]]
    # ) -> tuple[html.ElementCollection, dict[DynamicFileType, dict[str, bool]]]:
    #     categories_sorted = [cat for cat in DynamicFileType]
    #     results = sorted(
    #         results, key=lambda elem: (categories_sorted.index(elem[0].category), elem[0].rel_path)
    #     )
    #     details = html.ElementCollection()
    #     changes = {}
    #     for info, diff in results:
    #         if info.category not in changes:
    #             changes[info.category] = {}
    #             details.append(html.h(4, info.category.value))
    #         changes[info.category][info.id] = diff.status not in [
    #             DynamicFileChangeType.UNCHANGED,
    #             DynamicFileChangeType.DISABLED,
    #         ]
    #         details.append(self._item_summary(info, diff))
    #     return details, changes
    #
    # @staticmethod
    # def _color_legend():
    #     legend = [f"{status.value.emoji}  {status.value.title}" for status in DynamicFileChangeType]
    #     color_legend = html.details(content=html.ul(legend), summary="Color Legend")
    #     return color_legend
    #
    # @staticmethod
    # def _item_summary(info: DynamicFile, diff: Diff) -> html.DETAILS:
    #     details = html.ElementCollection()
    #     output = html.details(content=details, summary=f"{diff.status.value.emoji}  {info.rel_path}")
    #     typ = "Directory" if info.is_dir else "File"
    #     status = (
    #         f"{typ} {diff.status.value.title}{':' if diff.status != DynamicFileChangeType.DISABLED else ''}"
    #     )
    #     details.append(status)
    #     if diff.status == DynamicFileChangeType.DISABLED:
    #         return output
    #     details_ = (
    #         [f"Old Path: <code>{diff.path_before}</code>", f"New Path: <code>{info.path}</code>"]
    #         if diff.status
    #         in [
    #             DynamicFileChangeType.MOVED,
    #             DynamicFileChangeType.MOVED_MODIFIED,
    #             DynamicFileChangeType.MOVED_REMOVED,
    #         ]
    #         else [f"Path: <code>{info.path}</code>"]
    #     )
    #     if not info.is_dir:
    #         if info.id == "metadata":
    #             before, after = [
    #                 json.dumps(json.loads(state), indent=3) if state else ""
    #                 for state in (diff.before, diff.after)
    #             ]
    #         else:
    #             before, after = diff.before, diff.after
    #         diff_lines = list(difflib.ndiff(before.splitlines(), after.splitlines()))
    #         diff = "\n".join([line for line in diff_lines if line[:2] != "? "])
    #         details_.append(html.details(content=md.code_block(diff, "diff"), summary="Content"))
    #     details.append(html.ul(details_))
    #     return output


