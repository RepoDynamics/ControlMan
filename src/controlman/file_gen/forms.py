from pathlib import Path as _Path

import pyserials
from loggerman import logger

from controlman.datatype import DynamicFile_, GeneratedFile
from controlman.nested_dict import NestedDict as _NestedDict
from controlman import const as _const


class FormGenerator:
    def __init__(
        self,
        data: _NestedDict,
        data_before: _NestedDict,
        repo_path: _Path,
    ):
        self._data = data
        self._repo_path = repo_path
        return

    def generate(self) -> list[GeneratedFile]:
        return self.issue_forms() + self.discussion_forms() + self.pull_request_templates()

    @logger.sectioner("Generate Issue Forms")
    def issue_forms(self) -> list[GeneratedFile]:
        out = []
        forms = self._data.get("issue.forms", [])
        maintainers = self._data.get("maintainer.issue", {})
        paths = []
        for form_idx, form in enumerate(forms):
            logger.section(f"Issue Form {form_idx + 1}")
            pre_process = form.get("pre_process")
            if pre_process and not pre_process_existence(pre_process):
                logger.section_end()
                continue
            form_output = {
                key: val
                for key, val in form.items()
                if key not in ["id", "type", "subtype", "body", "pre_process", "post_process"]
            }
            labels = form_output.setdefault("labels", [])
            type_label_prefix = self._data["label.type.prefix"]
            type_label_suffix = self._data["label.type.label"][form["type"]]["suffix"]
            labels.append(f"{type_label_prefix}{type_label_suffix}")
            if form["subtype"]:
                subtype_label_prefix = self._data["label.subtype.prefix"]
                subtype_label_suffix = self._data["label.subtype.label"][form["subtype"]]["suffix"]
                labels.append(f"{subtype_label_prefix}{subtype_label_suffix}")
            status_label_prefix = self._data["label.status.prefix"]
            status_label_suffix = self._data["label.status.label.triage.suffix"]
            labels.append(f"{status_label_prefix}{status_label_suffix}")
            if form["id"] in maintainers.keys():
                form_output["assignees"] = [maintainer["github"]["user"] for maintainer in maintainers[form["id"]]]
            form_output["body"] = []
            for elem in form["body"]:
                pre_process = elem.get("pre_process")
                if pre_process and not pre_process_existence(pre_process):
                    continue
                form_output["body"].append(
                    {key: val for key, val in elem.items() if key not in ["pre_process", "post_process"]}
                )
            file_content = pyserials.write.to_yaml_string(data=form_output, end_of_file_newline=True)
            filename = f"{form_idx + 1:02}_{form['id']}.yaml"
            path = f"{_const.DIRPATH_ISSUES}/{filename}"
            out.append(
                GeneratedFile(
                    type=(DynamicFile_.GITHUB_ISSUE_FORM, filename.removesuffix(".yaml")),
                    content=file_content,
                    path=path,
                    path_before=path,
                )
            )
            paths.append(path)
            logger.debug(code_title="File content", code=file_content)
            logger.section_end()
        dir_issues = self._repo_path / _const.DIRPATH_ISSUES
        if dir_issues.is_dir():
            for file in dir_issues.glob("*.yaml"):
                file_relpath = str(file.relative_to(self._repo_path))
                if file_relpath not in paths and file_relpath != _const.FILEPATH_ISSUES_CONFIG:
                    logger.info(f"Outdated Issue Form: {file.name}")
                    out.append(
                        GeneratedFile(
                            type=(DynamicFile_.GITHUB_ISSUE_FORM, file.stem),
                            content="",
                            path=None,
                            path_before=file_relpath,
                        )
                    )
        return out

    @logger.sectioner("Generate Discussion Forms")
    def discussion_forms(self) -> list[GeneratedFile]:
        out = []
        paths = []
        forms = self._data.get("discussion.category", [])
        for slug, category_data in forms.items():
            logger.section(f"Discussion Form '{slug}'")
            filename = f"{slug}.yaml"
            path = f"{_const.DIRPATH_DISCUSSIONS}/{filename}"
            file_content = pyserials.write.to_yaml_string(data=category_data["form"], end_of_file_newline=True)
            out.append(
                GeneratedFile(
                    type=(DynamicFile_.GITHUB_DISCUSSION_FORM, filename.removesuffix(".yaml")),
                    content=file_content,
                    path=path,
                    path_before=path,
                )
            )
            paths.append(filename)
            logger.debug(code_title="File content", code=file_content)
            logger.section_end()
        dir_discussions = self._repo_path / _const.DIRPATH_DISCUSSIONS
        if dir_discussions.is_dir():
            for file in dir_discussions.glob("*.yaml"):
                file_relpath = str(file.relative_to(self._repo_path))
                if file_relpath not in paths:
                    logger.section(f"Outdated Discussion Form: {file.name}")
                    out.append(
                        GeneratedFile(
                            type=(DynamicFile_.GITHUB_DISCUSSION_FORM, file.stem),
                            content="",
                            path=None,
                            path_before=file_relpath,
                        )
                    )
                    logger.section_end()
        return out

    @logger.sectioner("Generate Pull Request Templates")
    def pull_request_templates(self) -> list[GeneratedFile]:
        out = []
        paths = []
        templates = self._data.get("pull.template", {})
        for name, file_content in templates.items():
            logger.section(f"Template '{name}'")
            path = _const.FILEPATH_PULL_TEMPLATE_MAIN if name == "default" else f"{_const.DIRPATH_PULL_TEMPLATES}/{name}.md"
            out.append(
                GeneratedFile(
                    type=(DynamicFile_.GITHUB_PULL_TEMPLATE, name),
                    content=file_content,
                    path=path,
                    path_before=path,
                )
            )
            paths.append(path)
            logger.debug(code_title="File content", code=file_content)
            logger.section_end()
        dir_templates = self._repo_path / _const.DIRPATH_PULL_TEMPLATES
        if dir_templates.is_dir():
            for file in dir_templates.glob("*.md"):
                file_relpath = str(file.relative_to(self._repo_path))
                if file_relpath not in paths and file.name != "README.md":
                    logger.section(f"Outdated Template: {file.name}")
                    out.append(
                        GeneratedFile(
                            type=(DynamicFile_.GITHUB_PULL_TEMPLATE, file.stem),
                            content="",
                            path=None,
                            path_before=file_relpath,
                        )
                    )
                    logger.section_end()
        return out


def pre_process_existence(commands: dict) -> bool:
    if "if_any" in commands:
        return any(commands["if_any"])
    if "if_all" in commands:
        return all(commands["if_all"])
    if "if_none" in commands:
        return not any(commands["if_none"])
    if "if_equal" in commands:
        return all([commands["if_equal"][0] == elem for elem in commands["if_equal"][1:]])
    return True
