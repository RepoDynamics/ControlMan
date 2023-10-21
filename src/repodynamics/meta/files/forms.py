import copy

from ruamel.yaml import YAML

from repodynamics.logger import Logger
from repodynamics.path import OutputPath
from repodynamics.datatype import DynamicFile


class FormGenerator:

    def __init__(self, metadata: dict, output_path: OutputPath, logger: Logger = None):
        self._logger = logger or Logger()
        self._out_db = output_path
        self._meta = metadata
        return

    def generate(self) -> list[tuple[DynamicFile, str]]:
        # label_syncer, pr_labeler = self._labels()
        return (
            self.issue_forms()
            + self.discussion_forms()
            + self.pull_request_templates()
        )

    def issue_forms(self) -> list[tuple[DynamicFile, str]]:
        out = []
        issues = self._meta["issue"]["forms"]
        issue_maintainers = self._meta.get("maintainer", {}).get("issue", {})
        paths = []
        label_meta = self._meta["label"]["group"]
        for idx, issue in enumerate(issues):
            pre_process = issue.get("pre_process")
            if pre_process and not self._pre_process_existence(pre_process):
                continue
            info = self._out_db.issue_form(issue["id"], idx + 1)
            form = {
                key: val for key, val in issue.items()
                if key not in ["id", "primary_commit_id", "body", "pre_process", "post_process"]
            }

            labels = form.setdefault("labels", [])
            type_label_prefix = label_meta["primary_type"]["prefix"]
            type_label_suffix = label_meta["primary_type"]["labels"][issue["primary_commit_id"]]["suffix"]
            labels.append(f"{type_label_prefix}{type_label_suffix}")
            status_label_prefix = label_meta["status"]["prefix"]
            status_label_suffix = label_meta["status"]["labels"]["triage"]["suffix"]
            labels.append(f"{status_label_prefix}{status_label_suffix}")
            if issue["id"] in issue_maintainers.keys():
                form["assignees"] = issue_maintainers[issue["id"]]

            form["body"] = []
            for elem in issue["body"]:
                pre_process = elem.get("pre_process")
                if not pre_process or self._pre_process_existence(pre_process):
                    form["body"].append(
                        {key: val for key, val in elem.items() if key not in ["pre_process", "post_process"]}
                    )

            text = YAML(typ=['rt', 'string']).dumps(form, add_final_eol=True)
            out.append((info, text))
            paths.append(info.path)
        dir_issues = self._out_db.dir_issue_forms
        path_template_chooser = self._out_db.issue_template_chooser_config.path
        if dir_issues.is_dir():
            for file in dir_issues.glob("*.yaml"):
                if file not in paths and file != path_template_chooser:
                    out.append((self._out_db.issue_form_outdated(path=file), ""))
        return out

    def discussion_forms(self) -> list[tuple[DynamicFile, str]]:
        out = []
        paths = []
        forms = self._meta.get("discussion", {}).get("forms", [])
        for discussion in forms:
            info = self._out_db.discussion_form(discussion["slug"])
            form = {key: val for key, val in discussion.items() if key not in ["slug"]}
            text = YAML(typ=['rt', 'string']).dumps(form, add_final_eol=True)
            out.append((info, text))
            paths.append(info.path)
        dir_discussions = self._out_db.dir_discussion_forms
        if dir_discussions.is_dir():
            for file in dir_discussions.glob("*.yaml"):
                if file not in paths:
                    out.append((self._out_db.discussion_form_outdated(path=file), ""))
        return out

    def pull_request_templates(self) -> list[tuple[DynamicFile, str]]:
        out = []
        paths = []
        templates = self._meta["pull"]["template"]
        for name, text in templates.items():
            info = self._out_db.pull_request_template(name=name)
            out.append((info, text))
            paths.append(info.path)
        dir_templates = self._out_db.dir_pull_request_templates
        if dir_templates.is_dir():
            for file in dir_templates.glob("*.md"):
                if file not in paths and file.name != "README.md":
                    out.append((self._out_db.pull_request_template_outdated(path=file), ""))
        return out

    @staticmethod
    def _pre_process_existence(commands: dict) -> bool:
        if "if_any" in commands:
            return any(commands["if_any"])
        if "if_all" in commands:
            return all(commands["if_all"])
        if "if_none" in commands:
            return not any(commands["if_none"])
        if "if_equal" in commands:
            return all([commands["if_equal"][0] == elem for elem in commands["if_equal"][1:]])
        return True

