from typing import Literal, Optional, Sequence, Callable
from pathlib import Path
import json
import difflib
import re
import shutil

from markitup import html, md
import tomlkit

from repodynamics.logger import Logger
from repodynamics import git


class MetaWriter:

    def __init__(
        self,
        path_root: str | Path = ".",
        logger: Logger = None
    ):
        self.path_root = Path(path_root).resolve()
        self.path_meta = self.path_root / "meta"
        self._logger = logger or Logger()
        self._categories = {
            'metadata': "Metadata Files",
            'license': "License Files",
            'config': "Configuration Files",
            'health_file': "Health Files",
            'package': "Package Files"
        }
        self._path = {
            ('metadata', 'metadata'): self.path_meta / ".out" / "metadata.json",
            ('license', 'license'): self.path_root / "LICENSE",
            ('config', 'funding'): self.path_root / ".github" / "FUNDING.yml",
            ('config', 'labels'): self.path_root / ".github" / "workflows" / "config" / "labels.yaml",
            ('config', 'labels_pr'): self.path_root / ".github" / "workflows" / "config" / "labels_pr.yaml",
            ('package', 'pyproject'): self.path_root / "pyproject.toml",
        }
        self._filename = {
            'metadata': 'metadata.json',
            'license': 'LICENSE',
            'funding': 'FUNDING.yml',
            'labels': 'labels.yaml',
            'labels_pr': 'labels_pr.yaml',
            'code_of_conduct': "CODE_OF_CONDUCT.md",
            'codeowners': "CODEOWNERS",
            'contributing': "CONTRIBUTING.md",
            'governance': "GOVERNANCE.md",
            'security': "SECURITY.md",
            'support': "SUPPORT.md",
            'pyproject': 'pyproject.toml',
            'docstring': '__init__.py',
            'dir': 'Package Directory',
        }
        self._results = {}
        self._applied: bool = False
        self._commit_hash: str = ""
        return

    def write(
        self,
        updates: list[dict],
        action: Literal['report', 'apply', 'commit']
    ):
        if action not in ['report', 'apply', 'commit']:
            self._logger.error(f"Action '{action}' not recognized.")
        self._results = {}
        self._applied = False
        self._commit_hash = ""
        self._register(updates)
        changes = self._changes()
        if changes['any']:
            if action != 'report':
                self._apply()
                self._applied = True
            if action == 'commit':
                self._commit_hash = git.Git(path_repo=self.path_root).commit(
                    message="Update dynamic files",
                    stage="all"
                )
        output = {
            "passed": not changes["any"],
            "modified": self._applied,
            "changes": changes,
            "summary": self._summary(changes),
            "commit_hash": self._commit_hash
        }
        return output

    def _register(
        self,
        updates: list[dict],
    ):
        package_update = {}
        for update in updates:
            if update['category'] not in self._categories:
                self._logger.error(f"Category '{update['category']}' not recognized.")
            if update['category'] == "health_file":
                self._add_result(
                    category="health_file",
                    name=update['name'],
                    result=self._update_health_file(
                        name=update['name'],
                        target_path=update['target_path'],
                        content=update['content']
                    )
                )
                continue
            if update['category'] == "package" and update['name'] in ['dir', 'docstring']:
                package_update[update['name']] = update['content']
                continue
            path = self._path[(update['category'], update['name'])]
            self._add_result(
                category=update['category'],
                name=update['name'],
                result=self._update_file(path=path, content=update['content'])
            )
        if package_update:
            package_dir_result = self._update_package_dir(package_update['dir'])
            self._add_result(
                category="package",
                name="dir",
                result=package_dir_result
            )
            self._add_result(
                category="package",
                name="docstring",
                result=self._write_package_init(
                    docstring=package_update['docstring'],
                    path=(package_dir_result['path_before'] or package_dir_result['path']) / "__init__.py"
                )
            )
        return self._results

    def _apply(self):
        for category_dict in self._results.values():
            for result in category_dict.values():
                if result['status'] in ['disabled', 'unchanged']:
                    continue
                if result['status'] == "removed":
                    result['path'].unlink() if result['type'] == 'file' else shutil.rmtree(result['path'])
                    continue
                if result['status'] == "moved":
                    result['path_before'].rename(result['path'])
                    continue
                if result['type'] == "dir":
                    result['path'].mkdir(parents=True, exist_ok=True)
                else:
                    result['path'].parent.mkdir(parents=True, exist_ok=True)
                    if result['status'] == "moved/modified":
                        result['path_before'].unlink()
                    with open(result['path'], "w") as f:
                        f.write(result['after'])
        return

    def _changes(self):
        changes = {"any": False} | {category: False for category in self._categories}
        for category, category_dict in self._results.items():
            for item_name, changes_dict in category_dict.items():
                if changes_dict['status'] not in ["unchanged", "disabled"]:
                    changes["any"] = True
                    changes[category] = True
        return changes

    def _summary(self, changes):
        results = []
        if not changes["any"]:
            results.append(
                html.li("✅ All dynamic files are in sync with source files; nothing to change.")
            )
        else:
            emoji = "🔄" if self._applied else "❌"
            results.append(
                html.li(f"{emoji} Following groups were out of sync with source files:")
            )
            results.append(
                html.ul([self._categories[category] for category in self._categories if changes[category]])
            )
            if self._applied:
                results.append(
                    html.li("✏️ Changed files were updated successfully.")
                )
            if self._commit_hash:
                results.append(
                    html.li(f"✅ Updates were committed with commit hash '{self._commit_hash}'.")
                )
            else:
                results.append(html.li(f"❌ Commit mode was not selected; updates were not committed."))
        summary = html.ElementCollection(
            [
                html.h(2, "Meta"),
                html.h(3, "Summary"),
                html.ul(results),
                html.h(3, "Details"),
                self._color_legend(),
                self._summary_section_details(),
                html.h(3, "Log"),
                html.details(self._logger.file_log, "Log"),
            ]
        )
        return summary

    def _summary_section_details(self):
        details = html.ElementCollection()
        for category, category_dict in self._results.items():
            details.append(html.h(4, self._categories[category]))
            for item_name, changes_dict in category_dict.items():
                details.append(self._item_summary(item_name, changes_dict))
        return details

    def _add_result(
        self,
        category: Literal['metadata', 'license', 'config', 'health_file', 'package'],
        name: str,
        result: dict
    ):
        if category not in self._categories:
            self._logger.error(f"Category '{category}' not recognized.")
        category_dict = self._results.setdefault(category, dict())
        category_dict[name] = result
        return

    def _update_file(self, path: Path, content: str) -> dict:
        content = f"{content.rstrip()}\n"
        output = {"status": "", "before": "", "after": content, "path": path, "type": "file"}
        if not path.exists():
            output['status'] = "created" if content else "disabled"
            return output
        if not path.is_file():
            self._logger.error(f"Path '{path}' is not a file.")
        with open(path) as f:
            old_content = output['before'] = f.read()
        output['status'] = "unchanged" if old_content == content else (
            "modified" if content else "removed"
        )
        return output

    def _update_health_file(
        self, name: str, target_path: Literal['.', 'docs', '.github'], content: str
    ) -> dict:
        allowed_paths = ['.', 'docs', '.github']
        # Health files are only allowed in the root, docs, and .github directories
        if target_path not in allowed_paths:
            self._logger.error(f"Path '{target_path}' not recognized.")
        allowed_paths.remove(target_path)
        target_path = self.path_root / target_path / self._filename[name]
        alt_paths = [self.path_root / allowed_path / self._filename[name] for allowed_path in allowed_paths]
        alts = self._remove_alts(alt_paths)
        main = self._update_file(target_path, content)
        if not alts:
            return main
        filename = target_path.name
        err = f"File '{filename}' found in multiple paths"
        alt_paths_str = '\n'.join([str(alt['path'].relative_to(self.path_root)) for alt in alts])
        if len(alts) > 1:
            self._logger.error(err, alt_paths_str)
        alt = alts[0]
        if main['status'] not in ["created", "disabled"]:
            main_path_str = str(target_path.relative_to(self.path_root))
            self._logger.error(err, f"{main_path_str}\n{alt_paths_str}")
        if main['status'] == "disabled":
            main['status'] = "removed"
            return main | alt
        main['path_before'] = alt['path']
        main['before'] = alt['before']
        main['status'] = "moved" if content == alt['before'] else "moved/modified"
        return main

    def _write_package_init(self, docstring: str, path: Path):
        output = {"status": "", "before": "", "after": docstring, "path": path, "type": "file"}
        docstring_full = f'"""{docstring.strip()}\n"""'
        if not path.exists():
            if docstring:
                output['after'] = f'{docstring_full}\n'
                output['status'] = "created"
            else:
                output['status'] = "disabled"
            return output
        if not path.is_file():
            self._logger.error(f"Path '{path}' is not a file.")
        with open(path) as f:
            output['before'] = f.read()
        docstring_pattern = r'^\s*"""(.*?)"""'
        match = re.search(docstring_pattern, output['before'], re.DOTALL)
        if match:
            # Replace the existing docstring with the new one
            output['after'] = re.sub(docstring_pattern, docstring_full, output['before'], flags=re.DOTALL)
        else:
            # If no docstring found, add the new docstring at the beginning of the file
            output['after'] = f"{docstring_full}\n\n\n{output['before'].strip()}".strip() + "\n"
        output['status'] = "unchanged" if output['before'] == output['after'] else "modified"
        return output

    @staticmethod
    def _update_package_dir(content: tuple[Path, Path]):
        old_path, new_path = content
        output = {"status": "", "path": new_path, "path_before": old_path, "type": "dir"}
        if old_path == new_path:
            output['status'] = "unchanged"
        elif not old_path:
            output['status'] = "created"
        else:
            output['status'] = "moved"
        return output

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

    def _color_legend(self):
        legend = [
            "🔴  Removed",
            "🟢  Created",
            "🟣  Modified",
            "🟡  Moved",
            "🟠  Moved & Modified",
            "⚪️  Unchanged",
            "⚫  Disabled",
        ]
        color_legend = html.details(content=html.ul(legend), summary="Color Legend")
        return color_legend

    def _item_summary(self, name, dic):
        emoji = {
            "removed": "🔴",
            "created": "🟢",
            "modified": "🟣",
            "moved": "🟡",
            "moved/modified": "🟠",
            "unchanged": "⚪️",
            "disabled": "⚫",
        }
        details = html.ElementCollection()
        output = html.details(
            content=details,
            summary=f"{emoji[dic['status']]}  {self._filename[name]}"
        )
        typ = "File" if dic['type'] == "file" else "Directory"
        status = f"{typ} {dic['status']}{':' if dic['status'] != 'disabled' else ''}"
        details.append(status)
        if dic["status"] == "disabled":
            return output
        details_ = [
            f"Old Path: <code>{dic['path_before']}</code>", f"New Path: <code>{dic['path']}</code>"
        ] if dic['status'] in ["moved", "moved/modified"] else [
            f"Path: <code>{dic['path']}</code>"
        ]
        if dic['type'] == 'file':
            if name == "metadata":
                before, after = [
                    json.dumps(json.loads(dic[i]), indent=3) if dic[i] else ""
                    for i in ['before', 'after']
                ]
            else:
                before, after = dic['before'], dic['after']
            diff_lines = list(difflib.ndiff(before.splitlines(), after.splitlines()))
            diff = "\n".join([line for line in diff_lines if line[:2] != "? "])
            details_.append(html.details(content=md.code_block(diff, "diff"), summary="Content"))
        details.append(html.ul(details_))
        return output
