import pyserials
from loggerman import logger

from controlman._path_manager import PathManager
from controlman.datatype import DynamicFile
from controlman import ControlCenterContentManager


def generate(
    content_manager: ControlCenterContentManager,
    path_manager: PathManager,
) -> list[tuple[DynamicFile, str]]:
    return _FormGenerator(content_manager=content_manager, path_manager=path_manager).generate()


class _FormGenerator:
    def __init__(self, content_manager: ControlCenterContentManager, path_manager: PathManager):
        self._ccm = content_manager
        self._pathman = path_manager
        return

    def generate(self) -> list[tuple[DynamicFile, str]]:
        return self.issue_forms() + self.discussion_forms() + self.pull_request_templates()

    @logger.sectioner("Generate Issue Forms")
    def issue_forms(self) -> list[tuple[DynamicFile, str]]:
        out = []
        issues = self._ccm["issue"]["forms"]
        issue_maintainers = self._ccm["maintainer"].get("issue", {})
        paths = []
        label_meta = self._ccm["label"]["group"]
        for idx, issue in enumerate(issues):
            logger.section(f"Issue Form {idx + 1}")
            file_info = self._pathman.issue_form(issue["id"], idx + 1)
            pre_process = issue.get("pre_process")
            if pre_process and not pre_process_existence(pre_process):
                continue
            form = {
                key: val
                for key, val in issue.items()
                if key not in ["id", "primary_type", "subtype", "body", "pre_process", "post_process"]
            }

            labels = form.setdefault("labels", [])
            type_label_prefix = label_meta["primary_type"]["prefix"]
            type_label_suffix = label_meta["primary_type"]["labels"][issue["primary_type"]]["suffix"]
            labels.append(f"{type_label_prefix}{type_label_suffix}")
            if issue["subtype"]:
                subtype_label_prefix = label_meta["subtype"]["prefix"]
                subtype_label_suffix = label_meta["subtype"]["labels"][issue["subtype"]]["suffix"]
                labels.append(f"{subtype_label_prefix}{subtype_label_suffix}")
            status_label_prefix = label_meta["status"]["prefix"]
            status_label_suffix = label_meta["status"]["labels"]["triage"]["suffix"]
            labels.append(f"{status_label_prefix}{status_label_suffix}")
            if issue["id"] in issue_maintainers.keys():
                form["assignees"] = issue_maintainers[issue["id"]]

            form["body"] = []
            for elem in issue["body"]:
                pre_process = elem.get("pre_process")
                if pre_process and not pre_process_existence(pre_process):
                    continue
                form["body"].append(
                    {key: val for key, val in elem.items() if key not in ["pre_process", "post_process"]}
                )
            file_content = pyserials.write.to_yaml_string(data=form, end_of_file_newline=True)
            out.append((file_info, file_content))
            paths.append(file_info.path)
            logger.info(code_title="File info", code=file_info)
            logger.debug(code_title="File content", code=file_content)
            logger.section_end()
        dir_issues = self._pathman.dir_issue_forms
        path_template_chooser = self._pathman.issue_template_chooser_config.path
        if dir_issues.is_dir():
            for file in dir_issues.glob("*.yaml"):
                if file not in paths and file != path_template_chooser:
                    logger.section(f"Outdated Issue Form: {file.name}")
                    file_info = self._pathman.issue_form_outdated(path=file)
                    file_content = ""
                    out.append((file_info, file_content))
                    logger.info(code_title="File info", code=str(file_info))
                    logger.debug(code_title="File content", code=file_content)
                    logger.section_end()
        return out

    @logger.sectioner("Generate Discussion Forms")
    def discussion_forms(self) -> list[tuple[DynamicFile, str]]:
        out = []
        paths = []
        forms = self._ccm["discussion"]["form"]
        for slug, form in forms.items():
            logger.section(f"Discussion Form '{slug}'")
            file_info = self._pathman.discussion_form(slug)
            file_content = pyserials.write.to_yaml_string(data=form, end_of_file_newline=True)
            out.append((file_info, file_content))
            paths.append(file_info.path)
            logger.info(code_title="File info", code=str(file_info))
            logger.debug(code_title="File content", code=file_content)
            logger.section_end()
        dir_discussions = self._pathman.dir_discussion_forms
        if dir_discussions.is_dir():
            for file in dir_discussions.glob("*.yaml"):
                if file not in paths:
                    logger.section(f"Outdated Discussion Form: {file.name}")
                    file_info = self._pathman.discussion_form_outdated(path=file)
                    file_content = ""
                    out.append((file_info, file_content))
                    logger.info(code_title="File info", code=str(file_info))
                    logger.debug(code_title="File content", code=file_content)
                    logger.section_end()
        return out

    @logger.sectioner("Generate Pull Request Templates")
    def pull_request_templates(self) -> list[tuple[DynamicFile, str]]:
        out = []
        paths = []
        templates = self._ccm["pull"]["template"]
        for name, file_content in templates.items():
            logger.section(f"Template '{name}'")
            file_info = self._pathman.pull_request_template(name=name)
            out.append((file_info, file_content))
            paths.append(file_info.path)
            logger.info(code_title="File info", code=str(file_info))
            logger.debug(code_title="File content", code=file_content)
            logger.section_end()
        dir_templates = self._pathman.dir_pull_request_templates
        if dir_templates.is_dir():
            for file in dir_templates.glob("*.md"):
                if file not in paths and file.name != "README.md":
                    logger.section(f"Outdated Template: {file.name}")
                    file_info = self._pathman.pull_request_template_outdated(path=file)
                    file_content = ""
                    out.append((file_info, file_content))
                    logger.info(code_title="File info", code=str(file_info))
                    logger.debug(code_title="File content", code=file_content)
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
