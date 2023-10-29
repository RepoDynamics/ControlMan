"""
Writer
"""

from typing import Literal
from pathlib import Path
import json
import difflib
import shutil

from markitup import html, md

from repodynamics.logger import Logger
from repodynamics import git
from repodynamics.datatype import DynamicFile, DynamicFileType, DynamicFileChangeType, Diff


class MetaWriter:
    def __init__(self, path_root: str | Path = ".", logger: Logger | None = None):
        self.path_root = Path(path_root).resolve()
        self._logger = logger or Logger()

        self._results: list[tuple[DynamicFile, Diff]] = []
        self._applied: bool = False
        self._commit_hash: str = ""
        return

    def write(
        self, updates: list[tuple[DynamicFile, str]], action: Literal["report", "apply", "amend", "commit"]
    ):
        if action not in ["report", "apply", "amend", "commit"]:
            self._logger.error(f"Action '{action}' not recognized.")
        self._results = {}
        self._applied = False
        self._commit_hash = ""
        self.compare(updates)
        changes = self._changes()
        if changes["any"]:
            if action != "report":
                self.apply()
                self._applied = True
            if action in ["amend", "commit"]:
                self._commit_hash = git.Git(path_repo=self.path_root).commit(
                    message="" if action == "amend" else "meta: sync dynamic files",
                    stage="all",
                    amend=action == "amend",
                )
        output = {
            "passed": not changes["any"],
            "modified": self._applied,
            "changes": changes,
            "summary": self._summary(changes),
            "commit_hash": self._commit_hash,
        }
        return output

    def compare(
        self,
        updates: list[tuple[DynamicFile, str]],
    ) -> tuple[list[tuple[DynamicFile, Diff]], dict[DynamicFileType, dict[str, bool]], str]:
        results = []
        file_updates = []
        for info, content in updates:
            if info.is_dir:
                result = self._compare_dir(
                    path_old=info.alt_paths[0] if info.alt_paths else None, path_new=info.path
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
    def apply(results: list[tuple[DynamicFile, Diff]]):
        for info, diff in results:
            if diff.status in [DynamicFileChangeType.DISABLED, DynamicFileChangeType.UNCHANGED]:
                continue
            if diff.status == DynamicFileChangeType.REMOVED:
                shutil.rmtree(info.path) if info.is_dir else info.path.unlink()
                continue
            if diff.status == DynamicFileChangeType.MOVED:
                diff.path_before.rename(info.path)
                continue
            if info.is_dir:
                info.path.mkdir(parents=True, exist_ok=True)
            else:
                info.path.parent.mkdir(parents=True, exist_ok=True)
                if diff.status == DynamicFileChangeType.MOVED_MODIFIED:
                    diff.path_before.unlink()
                with open(info.path, "w") as f:
                    f.write(f"{diff.after.strip()}\n")
        return

    def _compare_file(self, path: Path, content: str) -> Diff:
        content = content.strip()
        if not path.exists():
            before = ""
            status = DynamicFileChangeType.CREATED if content else DynamicFileChangeType.DISABLED
        elif not path.is_file():
            self._logger.error(f"Cannot write file to '{path}'; path exists as a directory.")
        else:
            with open(path) as f:
                before = f.read().strip()
            status = (
                DynamicFileChangeType.UNCHANGED
                if before == content
                else (DynamicFileChangeType.MODIFIED if content else DynamicFileChangeType.REMOVED)
            )
        return Diff(status=status, before=before, after=content)

    def _compare_file_multiloc(self, path: Path, alt_paths: list[Path], content: str) -> Diff:
        alts = self._remove_alts(alt_paths)
        main = self._compare_file(path, content)
        if not alts:
            return main
        if len(alts) > 1 or main.status not in [DynamicFileChangeType.CREATED, DynamicFileChangeType.DISABLED]:
            paths_str = "\n".join(
                [str(path.relative_to(self.path_root))]
                + [str(alt["path"].relative_to(self.path_root)) for alt in alts]
            )
            self._logger.error(f"File '{path.name}' found in multiple paths", paths_str)
        alt = alts[0]
        diff = Diff(
            status=DynamicFileChangeType.MOVED_REMOVED
            if main.status == DynamicFileChangeType.DISABLED
            else (
                DynamicFileChangeType.MOVED
                if content == alt["before"]
                else DynamicFileChangeType.MOVED_MODIFIED
            ),
            before=alt["before"],
            after=content,
            path_before=alt["path"],
        )
        return diff

    def _remove_alts(self, alt_paths: list[Path]):
        alts = []
        for alt_path in alt_paths:
            if alt_path.exists():
                if not alt_path.is_file():
                    self._logger.error(f"Alternate path '{alt_path}' is not a file.")
                with open(alt_path) as f:
                    alts.append({"path": alt_path, "before": f.read()})
        return alts

    @staticmethod
    def _compare_dir(path_old: Path | None, path_new: Path):
        if path_old == path_new:
            status = DynamicFileChangeType.UNCHANGED
        elif not path_old:
            status = DynamicFileChangeType.CREATED
        else:
            status = DynamicFileChangeType.MOVED
        return Diff(status=status, after="", path_before=path_old)

    def _summary(
        self, results: list[tuple[DynamicFile, Diff]]
    ) -> tuple[dict[DynamicFileType, dict[str, bool]], str]:
        details, changes = self._summary_section_details(results)
        summary = html.ElementCollection([html.h(3, "Meta")])
        any_changes = any(any(category.values()) for category in changes.values())
        if not any_changes:
            rest = [html.ul(["✅ All dynamic files were in sync with meta content."]), html.hr()]
        else:
            rest = [
                html.ul(["❌ Some dynamic files were out of sync with meta content:"]),
                details,
                html.hr(),
                self._color_legend(),
            ]
        rest.append(html.details(self._logger.file_log, "Log"))
        summary.extend(rest)
        return changes, str(summary)

    def _summary_section_details(
        self, results: list[tuple[DynamicFile, Diff]]
    ) -> tuple[html.ElementCollection, dict[DynamicFileType, dict[str, bool]]]:
        categories_sorted = [cat for cat in DynamicFileType]
        results = sorted(
            results, key=lambda elem: (categories_sorted.index(elem[0].category), elem[0].rel_path)
        )
        details = html.ElementCollection()
        changes = {}
        for info, diff in results:
            if info.category not in changes:
                changes[info.category] = {}
                details.append(html.h(4, info.category.value))
            changes[info.category][info.id] = diff.status not in [
                DynamicFileChangeType.UNCHANGED,
                DynamicFileChangeType.DISABLED,
            ]
            details.append(self._item_summary(info, diff))
        return details, changes

    @staticmethod
    def _color_legend():
        legend = [f"{status.value.emoji}  {status.value.title}" for status in DynamicFileChangeType]
        color_legend = html.details(content=html.ul(legend), summary="Color Legend")
        return color_legend

    @staticmethod
    def _item_summary(info: DynamicFile, diff: Diff) -> html.DETAILS:
        details = html.ElementCollection()
        output = html.details(content=details, summary=f"{diff.status.value.emoji}  {info.rel_path}")
        typ = "Directory" if info.is_dir else "File"
        status = (
            f"{typ} {diff.status.value.title}{':' if diff.status != DynamicFileChangeType.DISABLED else ''}"
        )
        details.append(status)
        if diff.status == DynamicFileChangeType.DISABLED:
            return output
        details_ = (
            [f"Old Path: <code>{diff.path_before}</code>", f"New Path: <code>{info.path}</code>"]
            if diff.status
            in [
                DynamicFileChangeType.MOVED,
                DynamicFileChangeType.MOVED_MODIFIED,
                DynamicFileChangeType.MOVED_REMOVED,
            ]
            else [f"Path: <code>{info.path}</code>"]
        )
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
