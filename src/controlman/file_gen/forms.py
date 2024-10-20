from pathlib import Path as _Path

import pyserials as _ps
from controlman.exception.load import ControlManSchemaValidationError
from loggerman import logger

from controlman.datatype import DynamicFileType, DynamicFile
from controlman import const as _const


class FormGenerator:
    def __init__(
        self,
        data: _ps.NestedDict,
        repo_path: _Path,
    ):
        self._data = data
        self._repo_path = repo_path
        return

    def generate(self) -> list[DynamicFile]:
        return self.issue_forms() + self.discussion_forms() + self.pull_request_templates()

    def issue_forms(self) -> list[DynamicFile]:
        out = []
        forms = self._data.get("issue.forms", [])
        paths = []
        for form_idx, form in enumerate(forms):
            pre_process = form.get("pre_process")
            if pre_process and not pre_process_existence(pre_process):
                continue
            form_output = {
                key: val for key, val in form.items() if key in _const.ISSUE_FORM_TOP_LEVEL_KEYS
            }
            form_output[_const.ISSUE_FORM_BODY_KEY] = []
            marker_added = False
            for elem in form[_const.ISSUE_FORM_BODY_KEY]:
                pre_process = elem.get("pre_process")
                if pre_process and not pre_process_existence(pre_process):
                    continue
                if not marker_added and elem["type"] == "checkboxes":
                    elem["attributes"]["options"][0]["label"] += f"<!-- ISSUE-ID: {form['id']} -->"
                    marker_added = True
                form_output["body"].append(
                    {key: val for key, val in elem.items() if key in _const.ISSUE_FORM_BODY_TOP_LEVEL_KEYS}
                )
            if not marker_added:
                logger.critical(
                    "Issue Form Marker",
                    f"No marker added to issue form with ID: {form["id"]}.",
                )
                raise ControlManSchemaValidationError(
                    source="compiled",
                    problem=f"Issue form {form["id"]} does not have a 'checkboxes' element; no marker could be added.",
                    json_path=f"issue.forms[{form_idx}].body",
                )
            file_content = _ps.write.to_yaml_string(data=form_output, end_of_file_newline=True)
            filename = f"{form_idx + 1:02}_{form['id']}.yaml"
            path = f"{_const.DIRPATH_ISSUES}/{filename}"
            out.append(
                DynamicFile(
                    type=DynamicFileType.ISSUE_FORM,
                    subtype=(filename.removesuffix(".yaml"), form["name"]),
                    content=file_content,
                    path=path,
                    path_before=path,
                )
            )
            paths.append(path)
        # Check for outdated issue forms to be removed
        paths.append(_const.FILEPATH_ISSUES_CONFIG)
        outdated_files = self._remove_outdated(
            dir_path=self._repo_path / _const.DIRPATH_ISSUES,
            include_glob="*.yaml",
            exclude_filepaths=paths,
            filetype=DynamicFileType.ISSUE_FORM,
        )
        out.extend(outdated_files)
        return out

    def discussion_forms(self) -> list[DynamicFile]:
        out = []
        paths = []
        forms = self._data.get("discussion.category", {})
        for slug, category_data in forms.items():
            form = category_data.get("form")
            if not form:
                continue
            filename = f"{slug}.yaml"
            path = f"{_const.DIRPATH_DISCUSSIONS}/{filename}"
            file_content = _ps.write.to_yaml_string(data=form, end_of_file_newline=True)
            out.append(
                DynamicFile(
                    type=DynamicFileType.DISCUSSION_FORM,
                    subtype=(slug, slug),
                    content=file_content,
                    path=path,
                    path_before=path,
                )
            )
            paths.append(path)
        outdated_files = self._remove_outdated(
            dir_path=self._repo_path / _const.DIRPATH_DISCUSSIONS,
            include_glob="*.yaml",
            exclude_filepaths=paths,
            filetype=DynamicFileType.DISCUSSION_FORM,
        )
        out.extend(outdated_files)
        return out

    def pull_request_templates(self) -> list[DynamicFile]:
        out = []
        paths = []
        templates = self._data.get("pull.template", {})
        for name, file_content in templates.items():
            path = _const.FILEPATH_PULL_TEMPLATE_MAIN if name == "default" else f"{_const.DIRPATH_PULL_TEMPLATES}/{name}.md"
            out.append(
                DynamicFile(
                    type=DynamicFileType.PULL_TEMPLATE,
                    subtype=(name, name),
                    content=file_content,
                    path=path,
                    path_before=path,
                )
            )
            paths.append(path)
        outdated_files = self._remove_outdated(
            dir_path=self._repo_path / _const.DIRPATH_PULL_TEMPLATES,
            include_glob="*.md",
            exclude_filepaths=paths,
            filetype=DynamicFileType.PULL_TEMPLATE,
        )
        out.extend(outdated_files)
        return out

    def _remove_outdated(
        self,
        dir_path: _Path,
        include_glob: str,
        exclude_filepaths: list[str],
        filetype: DynamicFileType,
        subtype: str | bool = True,
    ) -> list[DynamicFile]:
        out = []
        if not dir_path.is_dir():
            return out
        for file in dir_path.glob(include_glob):
            file_relpath = str(file.relative_to(self._repo_path))
            if file_relpath not in exclude_filepaths:
                subtype = subtype if isinstance(subtype, str) else (file.stem if subtype else None)
                out.append(
                    DynamicFile(
                        type=filetype,
                        subtype=(subtype, subtype),
                        path_before=file_relpath,
                    )
                )
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
