from typing import Literal, Optional, Sequence, Callable
from pathlib import Path
import json
import difflib
from importlib_resources import files

from markitup import html, md

from repodynamics.logger import Logger


class MetaManager:

    def __init__(
            self,
            path_root: str | Path = ".",
            paths_ext: Optional[Sequence[str | Path]] = None,
            logger: Logger = None
    ):
        self.path_root = Path(path_root).resolve()
        self.path_meta = self.path_root / "meta"
        self.path_extensions = [Path(path_ext).resolve() for path_ext in paths_ext] if paths_ext else []
        self.path_templates = [self.path_root / "meta" / "template"] + [
            path_ext / "template" for path_ext in self.path_extensions
        ]
        self.logger = logger or Logger("console")
        self._metadata = {}
        self._summary = {}
        self._categories = {
            'metadata': "Metadata Files",
            'license': "License Files",
            'config': "Configuration Files",
            'health_file': "Health Files",
            'package': "Package Files"
        }
        path_schema = files('repodynamics.meta').joinpath('schema.json')
        with open(path_schema) as f:
            self.schema = json.load(f)
        return

    def update(
        self,
        category: Literal['metadata', 'license', 'config', 'health_file', 'package'],
        name: str,
        path: str | Path,
        new_content: str | Callable = None,
        alt_paths: Sequence[str | Path] = None,
    ):
        if category not in self._categories:
            self.logger.error(f"Category '{category}' not recognized.")
        output = {"status": "", "path": "", "path_before": "", "before": "", "after": "", "alts_removed": []}
        if alt_paths:
            output['alts_removed'] = self._remove_alts(alt_paths)
        path = self.path_root / path
        output['path'] = str(path.relative_to(self.path_root))
        exists = path.exists()
        if exists:
            with open(path) as f:
                output['before'] = f.read()
            if category == "metadata" and name == "metadata.json":
                output["before"] = json.dumps(json.loads(output["before"]), indent=3)
        if not new_content:
            path.unlink(missing_ok=True)
            if exists:
                output['status'] = "removed"
            elif output['alts_removed']:
                output['status'] = "removed"
                alt = output['alts_removed'].pop(0)
                output['path'] = alt["path"]
                output["before"] = alt['before']
            else:
                output['status'] = "disabled"
            self.add_result(category, name, output)
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            if isinstance(new_content, str):
                f.write(new_content)
            elif callable(new_content):
                new_content(f)
            else:
                self.logger.error(
                    f"Argument 'new_content' must be a string or a callable, but got {type(new_content)}."
                )
        with open(path) as f:
            output['after'] = f.read()
        if category == "metadata" and name == "metadata.json":
            output["after"] = json.dumps(json.loads(output["after"]), indent=3)
        if exists:
            output["status"] = "unchanged" if output['before'] == output['after'] else "modified"
        elif not output["alts_removed"]:
            output['status'] = "created"
        else:
            for entry in output['alts_removed']:
                if entry['before'] == output['after']:
                    output['status'] = "moved"
                    output["path_before"] = entry["path"]
                    output['alts_removed'].remove(entry)
                    break
            else:
                output['status'] = "created"
        self.add_result(category, name, output)
        return

    def add_result(
        self,
        category: Literal['metadata', 'license', 'config', 'health_file', 'package'],
        name: str,
        result: dict
    ):
        if category not in self._categories:
            self.logger.error(f"Category '{category}' not recognized.")
        category_dict = self._summary.setdefault(category, dict())
        category_dict[name] = result
        return

    def _remove_alts(self, alt_paths: Sequence[str | Path] = None):
        alts = []
        for alt_path in alt_paths:
            alt_path = self.path_root / alt_path
            if alt_path.exists():
                with open(alt_path) as f:
                    alts.append(
                        {"path": str(alt_path.relative_to(self.path_root)), "before": f.read()}
                    )
                alt_path.unlink()
        return alts

    def template(
            self,
            category: Literal['health_file', 'license', 'issue_form', 'discussion_form'],
            name: str
    ):
        ext = {
            'health_file': '.md',
            'license': '.txt',
            'issue_form': '.yaml',
            'discussion_form': '.yaml',
        }
        for path in self.path_templates:
            path_template = (path / category / name).with_suffix(ext[category])
            if path_template.exists():
                with open(path_template) as f:
                    return f.read().format(**self._metadata)
        self.logger.error(f"Template '{name}' not found in any of template sources.")

    @property
    def metadata(self):
        return self._metadata

    @metadata.setter
    def metadata(self, metadata: dict):
        self._metadata = metadata
        return

    def summary(self):
        summary = html.ElementCollection()
        details = html.ElementCollection()
        details.append(
            html.details(
                content=html.ul(
                    [
                        "🔴  Removed from alternate location",
                        "🟠  Removed"
                        "🟢  Created",
                        "🟣  Modified",
                        "🟡  Renamed"
                        "⚪️  Unchanged",
                        "⚫  Disabled",
                    ]
                ),
                summary="Color legend",
            )
        )
        job_summary = html.ElementCollection(
            [
                html.h(2, "Meta"),
                html.h(3, "Summary"),
                summary,
                html.h(3, "Details"),
                details,
            ]
        )
        changes = {"any": False} | {category: False for category in self._categories}
        for category, category_dict in self._summary.items():
            details.append(html.h(4, self._categories[category]))
            for item_name, changes_dict in category_dict.items():
                details.append(self._item_summary(item_name, changes_dict))
                if changes_dict['status'] not in ["unchanged", "disabled"] or (
                    changes_dict.get('alts_removed')
                ):
                    changes["any"] = True
                    changes[category] = True
        if not changes["any"]:
            summary.append("No changes detected; all dynamic files and metadata are in sync with source files.")
        else:
            summary.append("Following groups were out of sync with the source files (see below for details):")
            summary.append(
                html.ul([self._categories[category] for category in self._categories if changes[category]])
            )
        return {"summary": str(job_summary), "changes": changes}

    @staticmethod
    def _item_summary(name, dic):
        emoji = {
            "removed": "🔴",
            "created": "🟢",
            "modified": "🟣",
            "moved": "🟡",
            "unchanged": "⚪️",
            "disabled": "⚫",
        }
        summary = f"{emoji[dic['status']]}{' ⚠️' if dic['alts_removed'] else ''}  {name}"
        details = html.ElementCollection()
        if dic["status"] == "disabled":
            details.append("Disabled")
        elif dic["status"] != "moved":
            details.append(f"Path: {dic['path']}")
            diff_lines = list(difflib.ndiff(dic["before"].splitlines(), dic["after"].splitlines()))
            diff = "\n".join([line for line in diff_lines if line[:2] != "? "])
            details.append(md.code_block(diff, "diff"))
        else:
            details.append(f"Old path: {dic['path_before']}")
            details.append(f"New path: {dic['path']}")
        if dic["alts_removed"]:
            details.append(html.h(4, "Removed from alternate locations:"))
            for alt in dic["alts_removed"]:
                details.append(
                    html.details(
                        content=md.code_block(alt["before"], "diff"),
                        summary=alt["path"]
                    )
                )
        return html.details(content=details, summary=summary)
