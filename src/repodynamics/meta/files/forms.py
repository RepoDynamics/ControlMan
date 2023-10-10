from pathlib import Path
from ruamel.yaml import YAML

from repodynamics.logger import Logger
from repodynamics.meta.writer import OutputFile, OutputPaths


class FormGenerator:

    def __init__(self, metadata: dict, path_root: str | Path = ".", logger: Logger = None):
        self._logger = logger or Logger()
        self._path_root = Path(path_root).resolve()
        self._out_db = OutputPaths(path_root=self._path_root, logger=self._logger)
        self._meta = metadata
        return

    def issue_forms(self) -> list[tuple[OutputFile, str]]:
        out = []
        issues = self._meta["issue"]["forms"]
        issue_maintainers = self._meta.get("maintainer", {}).get("issue", {})
        for idx, issue in enumerate(issues):
            info = self._out_db.issue_form(issue["id"], idx + 1)
            form = {key: val for key, val in issue.items() if key not in ["id", "primary_commit_id"]}
            if issue["id"] in issue_maintainers.keys():
                form["assignees"] = issue_maintainers[issue["id"]]
            text = YAML(typ=['rt', 'string']).dumps(form, add_final_eol=True)
            out.append((info, text))
        return out

    def discussion_forms(self) -> list[tuple[OutputFile, str]]:
        out = []
        forms = self._meta["discussion"]["forms"]
        for discussion in forms:
            info = self._out_db.discussion_form(discussion["slug"])
            form = {key: val for key, val in discussion.items() if key not in ["id"]}
            text = YAML(typ=['rt', 'string']).dumps(form, add_final_eol=True)
            out.append((info, text))
        return out

