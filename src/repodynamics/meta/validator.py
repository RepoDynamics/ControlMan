import re

from repodynamics.logger import Logger


class MetaValidator:
    def __init__(self, metadata: dict, logger: Logger = None):
        self._data = metadata
        self._logger = logger or Logger()
        return

    def validate(self):
        self.issue_forms()
        self.branch_names()
        self.changelogs()
        return

    def branch_names(self):
        """Verify that branch names and prefixes are unique."""
        branch_names = [self._data["branch"]["default"]["name"]]
        for group_name, branch_data in self._data["branch"]["group"].items():
            for branch_name in branch_names:
                if branch_name.startswith(branch_data["prefix"]):
                    self._logger.error(
                        f"Duplicate branch name: {branch_name}",
                        f"The branch name '{branch_name}' starts with "
                        f"the prefix of branch group '{group_name}'.",
                    )
            branch_names.append(branch_data["prefix"])
        return

    def changelogs(self):
        """Verify that changelog paths, names and sections are unique."""
        changelog_paths = []
        changelog_names = []
        for changelog_id, changelog_data in self._data["changelog"].items():
            if changelog_data["path"] in changelog_paths:
                self._logger.error(
                    f"Duplicate changelog path: {changelog_data['path']}",
                    f"The path '{changelog_data['path']}' set for changelog '{changelog_id}' "
                    f"is already used by another earlier changelog.",
                )
            changelog_paths.append(changelog_data["path"])
            if changelog_data["name"] in changelog_names:
                self._logger.error(
                    f"Duplicate changelog name: {changelog_data['name']}",
                    f"The name '{changelog_data['name']}' set for changelog '{changelog_id}' "
                    f"is already used by another earlier changelog.",
                )
            changelog_names.append(changelog_data["name"])
            section_ids = []
            for section in changelog_data["sections"]:
                if section["id"] in section_ids:
                    self._logger.error(
                        f"Duplicate changelog section ID: {section['id']}",
                        f"The section ID '{section['id']}' set for changelog '{changelog_id}' "
                        f"is already used by another earlier section.",
                    )
                section_ids.append(section["id"])
        return

    def commits(self):
        """Verify that commit types are unique, and that subtypes are defined."""
        commit_types = []
        for main_type in ("primary_action", "primary_custom"):
            for commit_id, commit_data in self._data["commit"][main_type].items():
                if commit_data["type"] in commit_types:
                    self._logger.error(
                        f"Duplicate commit type: {commit_data['type']}",
                        f"The type '{commit_data['type']}' set for commit '{main_type}.{commit_id}' "
                        f"is already used by another earlier commit.",
                    )
                commit_types.append(commit_data["type"])
                for subtype_type, subtypes in commit_data["subtypes"]:
                    for subtype in subtypes:
                        if subtype not in self._data["commit"]["secondary_custom"]:
                            self._logger.error(
                                f"Invalid commit subtype: {subtype}",
                                f"The subtype '{subtype}' set for commit '{main_type}.{commit_id}' "
                                f"in 'subtypes.{subtype_type}' is not defined in 'commit.secondary_custom'.",
                            )
        for commit_id, commit_data in self._data["commit"]["secondary_action"].items():
            if commit_data["type"] in commit_types:
                self._logger.error(
                    f"Duplicate commit type: {commit_data['type']}",
                    f"The type '{commit_data['type']}' set for commit 'secondary_action.{commit_id}' "
                    f"is already used by another earlier commit.",
                )
            commit_types.append(commit_data["type"])
        changelog_sections = {}
        for commit_type, commit_data in self._data["commit"]["secondary_custom"].items():
            if commit_type in commit_types:
                self._logger.error(
                    f"Duplicate commit type: {commit_type}",
                    f"The type '{commit_type}' set in 'secondary_custom' "
                    f"is already used by another earlier commit.",
                )
            commit_types.append(commit_type)
            # Verify that linked changelogs are defined
            changelog_id = commit_data["changelog_id"]
            if changelog_id not in self._data["changelog"]:
                self._logger.error(
                    f"Invalid commit changelog ID: {changelog_id}",
                    f"The changelog ID '{changelog_id}' set for commit "
                    f"'secondary_custom.{commit_type}' is not defined in 'changelog'.",
                )
            if changelog_id not in changelog_sections:
                changelog_sections[changelog_id] = [
                    section["id"] for section in self._data["changelog"][changelog_id]["sections"]
                ]
            if commit_data["changelog_section_id"] not in changelog_sections[changelog_id]:
                self._logger.error(
                    f"Invalid commit changelog section ID: {commit_data['changelog_section_id']}",
                    f"The changelog section ID '{commit_data['changelog_section_id']}' set for commit "
                    f"'secondary_custom.{commit_type}' is not defined in 'changelog.{changelog_id}.sections'.",
                )
        return

    def issue_forms(self):
        form_ids = []
        form_identifying_labels = []
        for form_idx, form in enumerate(self._data["issue"]["forms"]):
            if form["id"] in form_ids:
                self._logger.error(
                    f"Duplicate issue-form ID: {form['id']}",
                    f"The issue-form number {form_idx} has an ID that is already used by another earlier form.",
                )
            form_ids.append(form["id"])
            identifying_labels = (form["primary_type"], form.get("subtype"))
            if identifying_labels in form_identifying_labels:
                self._logger.error(
                    f"Duplicate issue-form identifying labels: {identifying_labels}",
                    f"The issue-form number {form_idx} has the same identifying labels as another earlier form.",
                )
            form_identifying_labels.append(identifying_labels)
            element_ids = []
            element_labels = []
            for elem_idx, elem in enumerate(form["body"]):
                if elem["type"] == "markdown":
                    continue
                elem_id = elem.get("id")
                if elem_id:
                    if elem_id in element_ids:
                        self._logger.error(
                            f"Duplicate issue-form body-element ID: {elem_id}",
                            f"The element number {elem_idx} has an ID that is "
                            f"already used by another earlier element.",
                        )
                    else:
                        element_ids.append(elem["id"])
                if elem["attributes"]["label"] in element_labels:
                    self._logger.error(
                        f"Duplicate issue-form body-element label: {elem['attributes']['label']}",
                        f"The element number {elem_idx} has a label that is already used by another earlier element.",
                    )
                element_labels.append(elem["attributes"]["label"])
            if not any(element_id in ("version", "branch") for element_id in element_ids):
                self._logger.error(
                    f"Missing issue-form body-element: version or branch",
                    f"The issue-form number {form_idx} is missing a body-element "
                    f"with ID 'version' or 'branch'.",
                )
            form_post_process = form.get("post_process")
            if form_post_process:
                if form_post_process.get("body"):
                    pattern = r"{([a-zA-Z_][a-zA-Z0-9_]*)}"
                    var_names = re.findall(pattern, form_post_process["body"])
                    for var_name in var_names:
                        if var_name not in element_ids:
                            self._logger.error(
                                f"Unknown issue-form post-process body variable: {var_name}",
                                f"The variable '{var_name}' is not a valid element ID within the issue body.",
                            )
                assign_creator = form_post_process.get("assign_creator")
                if assign_creator:
                    if_checkbox = assign_creator.get("if_checkbox")
                    if if_checkbox:
                        if if_checkbox["id"] not in element_ids:
                            self._logger.error(
                                f"Unknown issue-form post-process assign_creator if_checkbox ID: {if_checkbox}",
                                f"The ID '{if_checkbox}' is not a valid element ID within the issue body.",
                            )
                        for elem in form["body"]:
                            elem_id = elem.get("id")
                            if elem_id and elem_id == if_checkbox["id"]:
                                if elem["type"] != "checkboxes":
                                    self._logger.error(
                                        f"Invalid issue-form post-process assign_creator if_checkbox ID: {if_checkbox}",
                                        f"The ID '{if_checkbox}' is not a checkbox element.",
                                    )
                                if len(elem["attributes"]["options"]) < if_checkbox["number"]:
                                    self._logger.error(
                                        f"Invalid issue-form post-process assign_creator if_checkbox number: {if_checkbox}",
                                        f"The number '{if_checkbox['number']}' is greater than the number of "
                                        f"checkbox options.",
                                    )
                                break
        # Verify that identifying labels are defined in 'label.group' metadata
        for primary_type_id, subtype_id in form_identifying_labels:
            if primary_type_id not in self._data["label"]["group"]["primary_type"]["labels"]:
                self._logger.error(
                    f"Unknown issue-form `primary_type`: {primary_type_id}",
                    f"The ID '{primary_type_id}' does not exist in 'label.group.primary_type.labels'.",
                )
            if subtype_id and subtype_id not in self._data["label"]["group"]["subtype"]["labels"]:
                self._logger.error(
                    f"Unknown issue-form subtype: {subtype_id}",
                    f"The ID '{subtype_id}' does not exist in 'label.group.subtype.labels'.",
                )
        return

    def labels(self):
        """Verify that label names and prefixes are unique."""
        labels = []
        for main_type in ("auto_group", "group", "single"):
            for label_id, label_data in self._data["label"].get(main_type, {}).items():
                label = label_data["name"] if main_type == "single" else label_data["prefix"]
                label_type = "name" if main_type == "single" else "prefix"
                for set_label in labels:
                    if set_label.startswith(label) or label.startswith(set_label):
                        self._logger.error(
                            f"Ambiguous label {label_type}: {label}",
                            f"The {label_type} '{label}' set for label '{main_type}.{label_id}' "
                            f"is ambiguous as it overlaps with the already set name/prefix '{set_label}'.",
                        )
                labels.append(label)
        if len(labels) > 1000:
            self._logger.error(
                f"Too many labels: {len(labels)}",
                f"The maximum number of labels allowed by GitHub is 1000.",
            )
        for label_id, label_data in self._data["label"]["group"].items():
            suffixes = []
            for label_type, suffix_data in label_data["labels"].items():
                suffix = suffix_data["suffix"]
                if suffix in suffixes:
                    self._logger.error(
                        f"Duplicate label suffix: {suffix}",
                        f"The suffix '{suffix}' set for label 'group.{label_id}.labels.{label_type}' "
                        f"is already used by another earlier label.",
                    )
                suffixes.append(suffix)
        return

    def maintainers(self):
        issue_ids = [issue["id"] for issue in self._data.get("issue", {}).get("forms", [])]
        for issue_id in self._data.get("maintainer", {}).get("issue", {}).keys():
            if issue_id not in issue_ids:
                self._logger.error(
                    f"Issue ID '{issue_id}' defined in 'maintainer.issue' but not found in 'issue.forms'."
                )
        return
