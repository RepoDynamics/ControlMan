from pathlib import Path as _Path

import pyserials as _ps
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

    @logger.sectioner("Generate Issue Forms")
    def issue_forms(self) -> list[DynamicFile]:
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
                form_output["assignees"] = [maintainer["github"]["id"] for maintainer in maintainers[form["id"]]]
            form_output["body"] = []
            for elem in form["body"]:
                pre_process = elem.get("pre_process")
                if pre_process and not pre_process_existence(pre_process):
                    continue
                form_output["body"].append(
                    {key: val for key, val in elem.items() if key not in ["pre_process", "post_process"]}
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
            logger.debug("File content", file_content)
            logger.section_end()
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

    @logger.sectioner("Generate Discussion Forms")
    def discussion_forms(self) -> list[DynamicFile]:
        out = []
        paths = []
        forms = self._data.get("discussion.category", [])
        for slug, category_data in forms.items():
            logger.section(f"Discussion Form '{slug}'")
            filename = f"{slug}.yaml"
            path = f"{_const.DIRPATH_DISCUSSIONS}/{filename}"
            file_content = _ps.write.to_yaml_string(data=category_data["form"], end_of_file_newline=True)
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
            logger.debug("File content", file_content)
            logger.section_end()
        outdated_files = self._remove_outdated(
            dir_path=self._repo_path / _const.DIRPATH_DISCUSSIONS,
            include_glob="*.yaml",
            exclude_filepaths=paths,
            filetype=DynamicFileType.DISCUSSION_FORM,
        )
        out.extend(outdated_files)
        return out

    @logger.sectioner("Generate Pull Request Templates")
    def pull_request_templates(self) -> list[DynamicFile]:
        out = []
        paths = []
        templates = self._data.get("pull.template", {})
        for name, file_content in templates.items():
            logger.section(f"Template '{name}'")
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
            logger.debug("File content", file_content)
            logger.section_end()
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
