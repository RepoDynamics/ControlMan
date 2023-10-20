"""
Writer
"""

from typing import Literal, Optional, Sequence, Callable, NamedTuple
from pathlib import Path
import json
import difflib
import shutil
from enum import Enum

from markitup import html, md

from repodynamics.logger import Logger
from repodynamics import git
from repodynamics import _util


class FileCategory(Enum):
    METADATA = "Metadata Files"
    LICENSE = "License Files"
    PACKAGE = "Package Files"
    CONFIG = "Configuration Files"
    README = "ReadMe Files"
    HEALTH = "Health Files"
    FORM = "Forms"


class OutputFile(NamedTuple):
    id: str
    category: FileCategory
    filename: str
    rel_path: str
    path: Path
    alt_paths: list[Path] | None = None
    is_dir: bool = False


class OutputPaths:

    def __init__(self, path_root: str | Path, logger: Logger | None = None):
        self._path_root = Path(path_root).resolve()
        self._logger = logger or Logger()
        self._paths = _util.dict.read(
            path=self._path_root / ".path.json",
            schema=_util.file.datafile("schema/path.yaml"),
            logger=self._logger
        )
        return

    @property
    def input_paths(self):
        return self._paths

    @property
    def all_files(self):
        files = [
            self.metadata.path,
            self.metadata_ci.path,
            self.license.path,
            self.readme_main.path,
            self.readme_pypi.path,
            self.funding.path,
            self.pre_commit_config.path,
            self.read_the_docs_config.path,
            self.issue_template_chooser_config.path,
            self.package_pyproject.path,
            self.test_package_pyproject,
            self.package_requirements.path,
            self.package_manifest.path,
            self.codecov_config.path,
            self.gitignore.path,
            self.gitattributes.path,
            self.pull_request_template("default").path,
        ]
        files.extend(list((self._path_root / ".github/workflow_requirements").glob("*.txt")))
        for health_file_name in ['code_of_conduct', 'codeowners', 'contributing', 'governance', 'security', 'support']:
            for target_path in ['.', 'docs', '.github']:
                files.append(self.health_file(health_file_name, target_path).path)
        files.extend(list((self._path_root / ".github/ISSUE_TEMPLATE").glob("*.yaml")))
        files.extend(list((self._path_root / ".github/PULL_REQUEST_TEMPLATE").glob("*.md")))
        files.remove(self._path_root / ".github/PULL_REQUEST_TEMPLATE/README.md")
        files.extend(list((self._path_root / ".github/DISCUSSION_TEMPLATE").glob("*.yaml")))
        return files

    @property
    def metadata(self) -> OutputFile:
        filename = ".metadata.json"
        rel_path = f".github/{filename}"
        path = self._path_root / rel_path
        return OutputFile("metadata", FileCategory.METADATA, filename, rel_path, path)

    @property
    def metadata_ci(self) -> OutputFile:
        filename = ".metadata_ci.json"
        rel_path = f".github/{filename}"
        path = self._path_root / rel_path
        return OutputFile("metadata-ci", FileCategory.METADATA, filename, rel_path, path)

    @property
    def license(self) -> OutputFile:
        filename = "LICENSE"
        rel_path = filename
        path = self._path_root / rel_path
        return OutputFile("license", FileCategory.LICENSE, filename, rel_path, path)

    @property
    def readme_main(self) -> OutputFile:
        filename = "README.md"
        rel_path = filename
        path = self._path_root / rel_path
        return OutputFile("readme-main", FileCategory.README, filename, rel_path, path)

    @property
    def readme_pypi(self) -> OutputFile:
        filename = "readme_pypi.md"
        rel_path = f'{self._paths["dir"]["source"]}/{filename}'
        path = self._path_root / rel_path
        return OutputFile("readme-pypi", FileCategory.README, filename, rel_path, path)

    @property
    def funding(self) -> OutputFile:
        filename = "FUNDING.yml"
        rel_path = f'.github/{filename}'
        path = self._path_root / rel_path
        return OutputFile("funding", FileCategory.CONFIG, filename, rel_path, path)

    @property
    def pre_commit_config(self) -> OutputFile:
        filename = ".pre-commit-config.yaml"
        rel_path = f'.github/{filename}'
        path = self._path_root / rel_path
        return OutputFile("pre-commit-config", FileCategory.CONFIG, filename, rel_path, path)

    @property
    def read_the_docs_config(self) -> OutputFile:
        filename = ".readthedocs.yaml"
        rel_path = f'.github/{filename}'
        path = self._path_root / rel_path
        return OutputFile("read-the-docs-config", FileCategory.CONFIG, filename, rel_path, path)

    @property
    def issue_template_chooser_config(self) -> OutputFile:
        filename = "config.yml"
        rel_path = f'.github/ISSUE_TEMPLATE/{filename}'
        path = self._path_root / rel_path
        return OutputFile("issue-template-chooser-config", FileCategory.CONFIG, filename, rel_path, path)

    @property
    def package_pyproject(self) -> OutputFile:
        filename = "pyproject.toml"
        rel_path = filename
        path = self._path_root / rel_path
        return OutputFile("package-pyproject", FileCategory.PACKAGE, filename, rel_path, path)

    @property
    def test_package_pyproject(self) -> OutputFile:
        filename = "pyproject.toml"
        rel_path = f'{self._paths["dir"]["tests"]}/{filename}'
        path = self._path_root / rel_path
        return OutputFile("test-package-pyproject", FileCategory.PACKAGE, filename, rel_path, path)

    @property
    def package_requirements(self) -> OutputFile:
        filename = "requirements.txt"
        rel_path = filename
        path = self._path_root / rel_path
        return OutputFile("package-requirements", FileCategory.PACKAGE, filename, rel_path, path)

    @property
    def package_manifest(self) -> OutputFile:
        filename = "MANIFEST.in"
        rel_path = filename
        path = self._path_root / rel_path
        return OutputFile("package-manifest", FileCategory.PACKAGE, filename, rel_path, path)

    @property
    def codecov_config(self) -> OutputFile:
        filename = ".codecov.yml"
        rel_path = f'.github/{filename}'
        path = self._path_root / rel_path
        return OutputFile("codecov-config", FileCategory.CONFIG, filename, rel_path, path)

    @property
    def gitignore(self) -> OutputFile:
        filename = ".gitignore"
        rel_path = filename
        path = self._path_root / rel_path
        return OutputFile("gitignore", FileCategory.CONFIG, filename, rel_path, path)

    @property
    def gitattributes(self) -> OutputFile:
        filename = ".gitattributes"
        rel_path = filename
        path = self._path_root / rel_path
        return OutputFile("gitattributes", FileCategory.CONFIG, filename, rel_path, path)

    def workflow_requirements(self, name: str) -> OutputFile:
        filename = f"{name}.txt"
        rel_path = f'.github/workflow_requirements/{filename}'
        path = self._path_root / rel_path
        return OutputFile(f"workflow-requirement-{name}", FileCategory.CONFIG, filename, rel_path, path)

    def health_file(
        self,
        name: Literal['code_of_conduct', 'codeowners', 'contributing', 'governance', 'security', 'support'],
        target_path: Literal['.', 'docs', '.github'] = "."
    ) -> OutputFile:
        # Health files are only allowed in the root, docs, and .github directories
        allowed_paths = [".", "docs", ".github"]
        if target_path not in allowed_paths:
            self._logger.error(f"Path '{target_path}' not allowed for health files.")
        if name not in ['code_of_conduct', 'codeowners', 'contributing', 'governance', 'security', 'support']:
            self._logger.error(f"Health file '{name}' not recognized.")
        filename = name.upper() + (".md" if name != "codeowners" else "")
        rel_path = ("" if target_path == "." else f"{target_path}/") + filename
        path = self._path_root / rel_path
        allowed_paths.remove(target_path)
        alt_paths = [self._path_root / dir_ / filename for dir_ in allowed_paths]
        return OutputFile(f"health-file-{name}", FileCategory.HEALTH, filename, rel_path, path, alt_paths)

    def issue_form(self, name: str, priority: int) -> OutputFile:
        filename = f"{priority:02}_{name}.yaml"
        rel_path = f'.github/ISSUE_TEMPLATE/{filename}'
        path = self._path_root / rel_path
        return OutputFile(f"issue-form-{name}", FileCategory.FORM, filename, rel_path, path)

    def pull_request_template(self, name: str | Literal['default']) -> OutputFile:
        filename = "PULL_REQUEST_TEMPLATE.md" if name == "default" else f"{name}.md"
        rel_path = f'.github/{filename}' if name == "default" else f'.github/PULL_REQUEST_TEMPLATE/{filename}'
        path = self._path_root / rel_path
        return OutputFile(f"pull-request-template-{name}", FileCategory.CONFIG, filename, rel_path, path)

    def discussion_form(self, name: str) -> OutputFile:
        filename = f"{name}.yaml"
        rel_path = f'.github/DISCUSSION_TEMPLATE/{filename}'
        path = self._path_root / rel_path
        return OutputFile(f"discussion-form-{name}", FileCategory.FORM, filename, rel_path, path)

    def package_dir(self, package_name: str, old_path: Path | None, new_path: Path) -> OutputFile:
        filename = package_name
        rel_path = str(new_path.relative_to(self._path_root))
        alt_paths = [old_path] if old_path else None
        return OutputFile(
            "package-dir", FileCategory.PACKAGE, filename, rel_path, new_path, alt_paths=alt_paths, is_dir=True
        )

    def python_file(self, path: Path):
        filename = path.name
        rel_path = str(path.relative_to(self._path_root))
        return OutputFile(rel_path, FileCategory.PACKAGE, filename, rel_path, path)

    def package_tests_dir(self, package_name: str, old_path: Path | None, new_path: Path) -> OutputFile:
        filename = f"{package_name}_tests"
        rel_path = str(new_path.relative_to(self._path_root))
        alt_paths = [old_path] if old_path else None
        return OutputFile(
            "test-package-dir", FileCategory.PACKAGE, filename, rel_path, new_path, alt_paths=alt_paths, is_dir=True
        )

    def package_init(self, package_name: str) -> OutputFile:
        filename = "__init__.py"
        rel_path = f'{self._paths["dir"]["source"]}/{package_name}/{filename}'
        path = self._path_root / rel_path
        return OutputFile("package-init", FileCategory.PACKAGE, filename, rel_path, path)

    def package_typing_marker(self, package_name: str) -> OutputFile:
        filename = "py.typed"
        rel_path = f'{self._paths["dir"]["source"]}/{package_name}/{filename}'
        path = self._path_root / rel_path
        return OutputFile("package-typing-marker", FileCategory.PACKAGE, filename, rel_path, path)


class _FileStatus(NamedTuple):
    title: str
    emoji: str


class FileStatus(Enum):
    REMOVED = _FileStatus("Removed", "🔴")
    MODIFIED = _FileStatus("Modified", "🟣")
    MOVED_MODIFIED = _FileStatus("Moved & Modified", "🟠")
    MOVED_REMOVED = _FileStatus("Moved & Removed", "🟠")
    MOVED = _FileStatus("Moved", "🟡")
    CREATED = _FileStatus("Created", "🟢")
    UNCHANGED = _FileStatus("Unchanged", "⚪️")
    DISABLED = _FileStatus("Disabled", "⚫")


class Diff(NamedTuple):
    status: FileStatus
    after: str
    before: str = ""
    path_before: Path | None = None


class MetaWriter:

    def __init__(
        self,
        path_root: str | Path = ".",
        logger: Logger | None = None
    ):
        self.path_root = Path(path_root).resolve()
        self._logger = logger or Logger()

        self._results: list[tuple[OutputFile, Diff]] = []
        self._applied: bool = False
        self._commit_hash: str = ""
        return

    def write(
        self,
        updates: list[tuple[OutputFile, str]],
        action: Literal['report', 'apply', 'amend', 'commit']
    ):
        if action not in ['report', 'apply', 'amend', 'commit']:
            self._logger.error(f"Action '{action}' not recognized.")
        self._results = {}
        self._applied = False
        self._commit_hash = ""
        self.compare(updates)
        changes = self._changes()
        if changes['any']:
            if action != 'report':
                self.apply()
                self._applied = True
            if action in ['amend', 'commit']:
                self._commit_hash = git.Git(path_repo=self.path_root).commit(
                    message="" if action == "amend" else "meta: sync dynamic files",
                    stage="all",
                    amend=action == "amend"
                )
        output = {
            "passed": not changes["any"],
            "modified": self._applied,
            "changes": changes,
            "summary": self._summary(changes),
            "commit_hash": self._commit_hash
        }
        return output

    def compare(
        self,
        updates: list[tuple[OutputFile, str]],
    ) -> tuple[list[tuple[OutputFile, Diff]], dict[FileCategory, dict[str, bool]], str]:
        results = []
        file_updates = []
        for info, content in updates:
            if info.is_dir:
                result = self._compare_dir(
                    path_old=info.alt_paths[0] if info.alt_paths else None,
                    path_new=info.path
                )
                results.append((info, result))
            else:
                file_updates.append((info, content))
        for info, content in file_updates:
            if info.alt_paths:
                result = self._compare_file_multiloc(
                    path=info.path,
                    content=content,
                    alt_paths=info.alt_paths,
                )
            else:
                result = self._compare_file(path=info.path, content=content)
            results.append((info, result))
        changes, summary = self._summary(results)
        return results, changes, summary

    @staticmethod
    def apply(results: list[tuple[OutputFile, Diff]]):
        for info, diff in results:
            if diff.status in [FileStatus.DISABLED, FileStatus.UNCHANGED]:
                continue
            if diff.status == FileStatus.REMOVED:
                shutil.rmtree(info.path) if info.is_dir else info.path.unlink()
                continue
            if diff.status == FileStatus.MOVED:
                diff.path_before.rename(info.path)
                continue
            if info.is_dir:
                info.path.mkdir(parents=True, exist_ok=True)
            else:
                info.path.parent.mkdir(parents=True, exist_ok=True)
                if diff.status == FileStatus.MOVED_MODIFIED:
                    diff.path_before.unlink()
                with open(info.path, "w") as f:
                    f.write(f"{diff.after.strip()}\n")
        return

    def _compare_file(self, path: Path, content: str) -> Diff:
        content = content.strip()
        if not path.exists():
            before = ""
            status = FileStatus.CREATED if content else FileStatus.DISABLED
        elif not path.is_file():
            self._logger.error(f"Cannot write file to '{path}'; path exists as a directory.")
        else:
            with open(path) as f:
                before = f.read().strip()
            status = FileStatus.UNCHANGED if before == content else (
                FileStatus.MODIFIED if content else FileStatus.REMOVED
            )
        return Diff(status=status, before=before, after=content)

    def _compare_file_multiloc(self, path: Path, alt_paths: list[Path], content: str) -> Diff:
        alts = self._remove_alts(alt_paths)
        main = self._compare_file(path, content)
        if not alts:
            return main
        if len(alts) > 1 or main.status not in [FileStatus.CREATED, FileStatus.DISABLED]:
            paths_str = '\n'.join(
                [str(path.relative_to(self.path_root))]
                + [str(alt['path'].relative_to(self.path_root)) for alt in alts]
            )
            self._logger.error(f"File '{path.name}' found in multiple paths", paths_str)
        alt = alts[0]
        diff = Diff(
            status=FileStatus.MOVED_REMOVED if main.status == FileStatus.DISABLED else (
                FileStatus.MOVED if content == alt['before'] else FileStatus.MOVED_MODIFIED
            ),
            before=alt['before'],
            after=content,
            path_before=alt['path']
        )
        return diff

    def _remove_alts(self, alt_paths: list[Path]):
        alts = []
        for alt_path in alt_paths:
            if alt_path.exists():
                if not alt_path.is_file():
                    self._logger.error(f"Alternate path '{alt_path}' is not a file.")
                with open(alt_path) as f:
                    alts.append(
                        {"path": alt_path, "before": f.read()}
                    )
        return alts

    @staticmethod
    def _compare_dir(path_old: Path | None, path_new: Path):
        if path_old == path_new:
            status = FileStatus.UNCHANGED
        elif not path_old:
            status = FileStatus.CREATED
        else:
            status = FileStatus.MOVED
        return Diff(status=status, after="", path_before=path_old)

    def _summary(
        self, results: list[tuple[OutputFile, Diff]]
    ) -> tuple[dict[FileCategory, dict[str, bool]], str]:
        details, changes = self._summary_section_details(results)
        summary = html.ElementCollection([html.h(3, "Meta")])
        any_changes = any(any(category.values()) for category in changes.values())
        if not any_changes:
            rest = [
                html.ul(["✅ All dynamic files were in sync with meta content."]),
                html.hr()
            ]
        else:
            rest = [
                html.ul(["❌ Some dynamic files were out of sync with meta content:"]),
                details,
                html.hr(),
                self._color_legend()
            ]
        rest.append(html.details(self._logger.file_log, "Log"))
        summary.extend(rest)
        return changes, str(summary)

    def _summary_section_details(
        self, results: list[tuple[OutputFile, Diff]]
    ) -> tuple[html.ElementCollection, dict[FileCategory, dict[str, bool]]]:
        categories_sorted = [cat for cat in FileCategory]
        results = sorted(
            results,
            key=lambda elem: (categories_sorted.index(elem[0].category), elem[0].rel_path)
        )
        details = html.ElementCollection()
        changes = {}
        for info, diff in results:
            if info.category not in changes:
                changes[info.category] = {}
                details.append(html.h(4, info.category.value))
            changes[info.category][info.id] = diff.status not in [FileStatus.UNCHANGED, FileStatus.DISABLED]
            details.append(self._item_summary(info, diff))
        return details, changes

    @staticmethod
    def _color_legend():
        legend = [f"{status.value.emoji}  {status.value.title}" for status in FileStatus]
        color_legend = html.details(content=html.ul(legend), summary="Color Legend")
        return color_legend

    @staticmethod
    def _item_summary(info: OutputFile, diff: Diff) -> html.DETAILS:
        details = html.ElementCollection()
        output = html.details(
            content=details,
            summary=f"{diff.status.value.emoji}  {info.rel_path}"
        )
        typ = "Directory" if info.is_dir else "File"
        status = f"{typ} {diff.status.value.title}{':' if diff.status != FileStatus.DISABLED else ''}"
        details.append(status)
        if diff.status == FileStatus.DISABLED:
            return output
        details_ = [
            f"Old Path: <code>{diff.path_before}</code>", f"New Path: <code>{info.path}</code>"
        ] if diff.status in [FileStatus.MOVED, FileStatus.MOVED_MODIFIED, FileStatus.MOVED_REMOVED] else [
            f"Path: <code>{info.path}</code>"
        ]
        if not info.is_dir:
            if info.id == "metadata":
                before, after = [
                    json.dumps(json.loads(state), indent=3) if state else ""
                    for state in (diff.before, diff.after)
                ]
            else:
                before, after = diff.before, diff.after
            diff_lines = list(difflib.ndiff(before.splitlines(), after.splitlines()))
            diff = "\n".join([line for line in diff_lines if line[:2] != "? "])
            details_.append(html.details(content=md.code_block(diff, "diff"), summary="Content"))
        details.append(html.ul(details_))
        return output
