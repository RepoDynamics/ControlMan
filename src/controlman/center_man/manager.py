import copy as _copy
from pathlib import Path as _Path
import shutil as _shutil

from versionman import PEP440SemVer as _PEP440SemVer
from loggerman import logger as _logger
import pylinks as _pylinks
import markitup as _miu

from controlman.data_man.manager import DataManager as _DataManager
from controlman.data_man.validator import DataValidator as _DataValidator
from controlman import data_gen as _data_gen
from controlman.center_man.hook import HookManager as _HookManager
from controlman.datatype import (
    DynamicFileType as _DynamicFileType,
    DynamicFileChangeType,
    GeneratedFile as _GeneratedFile,
)
from controlman.protocol import Git as _Git
import controlman
from controlman import const
from controlman import _util
from controlman import exception as _exception
from controlman.center_man.cache import CacheManager
from controlman.nested_dict import NestedDict as _NestedDict
from controlman import file_gen as _file_gen


class CenterManager:

    def __init__(
        self,
        git_manager: _Git,
        github_token: str | None = None,
        data_main: _DataManager | dict | None = None,
        future_versions: dict[str, str | _PEP440SemVer] | None = None,
        control_center_path: _Path | str | None = None,
    ):
        self._git = git_manager
        self._github_api = _pylinks.api.github(token=github_token)
        self._data_main = data_main
        self._future_vers = future_versions or {}
        self._path_cc = control_center_path
        self._path_root = self._git.repo_path

        self._data_before: _NestedDict | None = None
        self._hook_manager: _HookManager | None = None
        self._cache_manager: CacheManager | None = None
        self._contents_raw: _NestedDict | None = None
        self._local_config: dict = {}
        self._data: _NestedDict | None = None
        self._generated_files: list[tuple[_GeneratedFile, DynamicFileChangeType]] = []
        self._compared_dirs: list = []
        self._dirs_to_apply: list[tuple[str, str, DynamicFileChangeType]] = []
        self._dirs_to_apply_sub: list[tuple[str, str, DynamicFileChangeType]] = []
        self._changes: dict[_DynamicFileType, dict[str, bool]] = {}
        self._summary: str = ""
        return

    def load(self) -> _NestedDict:
        if self._contents_raw:
            return self._contents_raw
        if not self._path_cc:
            self._data_before = controlman.data_man.from_json_file(repo_path=self._path_root).ndict
            self._path_cc = self._path_root / self._data_before["control.path"]
            cache_retention_hours = self._data_before["control.cache.retention_hours"]
        else:
            self._data_before = _NestedDict(data={})
            self._path_cc = self._path_root / self._path_cc
            cache_retention_hours = {k: 0 for k in ("extension", "repo", "user", "orcid", "doi", "python")}
        self._hook_manager = _HookManager(
            dir_path=self._path_root / self._path_cc / const.DIRNAME_CC_HOOK
        )
        self._cache_manager = CacheManager(
            path_repo=self._path_root,
            retention_hours=cache_retention_hours,
        )
        full_data = {}
        for filepath in self._path_cc.glob('*'):
            if filepath.is_file() and filepath.suffix.lower() in ['.yaml', '.yml']:
                filename = filepath.relative_to(self._path_cc)
                _logger.section(f"Load Control Center File '{filename}'")
                data = _util.file.read_control_center_file(
                    path=filepath,
                    cache_manager=self._cache_manager,
                    tag_name=const.CC_EXTENSION_TAG,
                )
                duplicate_keys = set(data.keys()) & set(full_data.keys())
                if duplicate_keys:
                    raise RuntimeError(f"Duplicate keys '{", ".join(duplicate_keys)}' in project config")
                full_data.update(data)
        if self._hook_manager.has_hook(const.FUNCNAME_CC_HOOK_POST_LOAD):
            full_data = self._hook_manager.generate(
                const.FUNCNAME_CC_HOOK_POST_LOAD,
                full_data,
            )
        _util.jsonschema.validate_data(
            data=full_data,
            schema="full",
            before_substitution=True,
        )
        self._contents_raw = _NestedDict(full_data)
        return self._contents_raw

    def generate_data(self) -> _DataManager:
        if self._data:
            return _DataManager(self._data)
        data = self.load()
        _data_gen.MainDataGenerator(
            data=data,
            cache_manager=self._cache_manager,
            git_manager=self._git,
            github_api=self._github_api,
        ).generate()
        if not self._data_main:
            curr_branch, other_branches = self._git.get_all_branch_names()
            main_branch = data["repo.default_branch"]
            if curr_branch == main_branch:
                self._data_main = self._data_before or data
            else:
                self._git.fetch_remote_branches_by_name(main_branch)
                self._git.stash()
                self._git.checkout(main_branch)
                if (self._git.repo_path / const.FILEPATH_METADATA).is_file():
                    self._data_main = controlman.data_man.from_json_file(repo_path=self._git.repo_path)
                else:
                    self._data_main = data
                self._git.checkout(curr_branch)
                self._git.stash_pop()
        if data.get("pkg"):
            _data_gen.PythonDataGenerator(
                data=data,
                git_manager=self._git,
                cache=self._cache_manager,
                github_api=self._github_api,
            ).generate()
        if data.get("web"):
            web_data_source = self._data_before if self._data_before["web.path.source"] else data
            _data_gen.WebDataGenerator(
                data=data,
                source_path=self._path_root / web_data_source["web.path.root"] / web_data_source["web.path.source"],
            ).generate()
        _data_gen.RepoDataGenerator(
            data=data,
            git_manager=self._git,
            data_main=self._data_main,
            future_versions=self._future_vers,
        ).generate()
        if self._hook_manager.has_hook(const.FUNCNAME_CC_HOOK_POST_DATA):
            self._hook_manager.generate(
                const.FUNCNAME_CC_HOOK_POST_DATA,
                data,
            )
        self._cache_manager.save()
        data.fill()
        _DataValidator(data=data).validate()
        self._data = data
        return _DataManager(data)

    def generate_files(self) -> list[tuple[_GeneratedFile, DynamicFileChangeType]]:
        if self._generated_files:
            return self._generated_files
        self.generate_data()
        generated_files = []
        form_files = _file_gen.FormGenerator(
            data=self._data,
            repo_path=self._path_root,
        ).generate()
        generated_files.extend(form_files)
        config_files, pyproject_pkg, pyproject_test = _file_gen.ConfigFileGenerator(
            data=self._data,
            data_before=self._data_before,
            repo_path=self._path_root,
        ).generate()
        generated_files.extend(config_files)
        if self._data["pkg"]:
            package_files = _file_gen.PythonPackageFileGenerator(
                data=self._data,
                data_before=self._data_before,
                repo_path=self._path_root,
            ).generate(typ="pkg", pyproject_tool_config=pyproject_pkg)
            generated_files.extend(package_files)
        if self._data["test"]:
            test_files = _file_gen.PythonPackageFileGenerator(
                data=self._data,
                data_before=self._data_before,
                repo_path=self._path_root,
            ).generate(typ="test", pyproject_tool_config=pyproject_test)
            generated_files.extend(test_files)
        readme_files = _file_gen.readme.generate(
            data=self._data,
            data_before=self._data_before,
            root_path=self._path_root,
        )
        generated_files.extend(readme_files)
        self._generated_files = [
            (generated_file, self._compare_file(generated_file)) for generated_file in generated_files
        ]
        return self._generated_files

    def compare_dirs(self):
        if self._compared_dirs:
            return self._compared_dirs
        compared_dirs = []
        for_apply = []
        for path_key in ("theme.path", "control.path", "local.path"):
            path, path_before, status = self._compare_dir(path_key)
            for_apply.append((path, path_before, status))
        for path_key in ("web.path", "pkg.path", "test.path"):
            root_path, root_path_before, root_status = self._compare_dir(f"{path_key}.root")
            for_apply.append((root_path, root_path_before, root_status))
            source_name, source_name_before, source_status = self._compare_dir(f"{path_key}.source")
            source_path = f"{root_path}/{source_name}" if root_path else None
            source_path_before = f"{root_path}/{source_name_before}" if root_path else None
            for_apply.append((source_path, source_path_before, source_status))
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
                filepath_before_abs.unlink()
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
                    filepath_before_abs.unlink()
        return

    def _compare_file(self, file: _GeneratedFile) -> DynamicFileChangeType:
        if not file.content:
            if not file.path_before:
                return DynamicFileChangeType.DISABLED
            filepath_before = self._path_root/file.path_before
            if filepath_before.is_file():
                return DynamicFileChangeType.REMOVED
            return DynamicFileChangeType.DISABLED
        if not file.path:
            return DynamicFileChangeType.DISABLED
        if not file.path_before:
            return DynamicFileChangeType.CREATED
        fullpath_before = self._path_root/file.path_before
        if not fullpath_before.is_file():
            return DynamicFileChangeType.CREATED
        with open(self._path_root/file.path_before) as f:
            content_before = f.read()
        contents_identical = file.content.strip() == content_before.strip()
        paths_identical = file.path == file.path_before
        change_type = {
            (True, True): DynamicFileChangeType.UNCHANGED,
            (True, False): DynamicFileChangeType.MOVED,
            (False, True): DynamicFileChangeType.MODIFIED,
            (False, False): DynamicFileChangeType.MOVED_MODIFIED,
        }
        return change_type[(contents_identical, paths_identical)]

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


