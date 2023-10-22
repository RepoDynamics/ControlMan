import re

from repodynamics.logger import Logger


class MetaValidator:

    def __init__(self, metadata: dict, logger: Logger = None):
        self._data = metadata
        self._logger = logger or Logger()
        return

    def validate(self):
        self.issue_forms()
        return

    def issue_forms(self):
        form_ids = []
        form_identifying_labels = []
        for form_idx, form in enumerate(self._data["issue"]["forms"]):
            if form["id"] in form_ids:
                self._logger.error(
                    f"Duplicate issue-form ID: {form['id']}",
                    f"The issue-form number {form_idx} has an ID that is already used by another earlier form."
                )
            form_ids.append(form["id"])
            identifying_labels = (
                form["primary_commit_id"],
                form.get("sub_type")
            )
            if identifying_labels in form_identifying_labels:
                self._logger.error(
                    f"Duplicate issue-form identifying labels: {identifying_labels}",
                    f"The issue-form number {form_idx} has the same identifying labels as another earlier form."
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
                            f"already used by another earlier element."
                        )
                    else:
                        element_ids.append(elem["id"])
                if elem["attributes"]["label"] in element_labels:
                    self._logger.error(
                        f"Duplicate issue-form body-element label: {elem['attributes']['label']}",
                        f"The element number {elem_idx} has a label that is already used by another earlier element."
                    )
                element_labels.append(elem["attributes"]["label"])
            form_post_process = form.get("post_process")
            if form_post_process:
                if form_post_process.get("body"):
                    pattern = r'{([a-zA-Z_][a-zA-Z0-9_]*)}'
                    var_names = re.findall(pattern, form_post_process["body"])
                    for var_name in var_names:
                        if var_name not in element_ids:
                            self._logger.error(
                                f"Unknown issue-form post-process body variable: {var_name}",
                                f"The variable '{var_name}' is not a valid element ID within the issue body."
                            )
                assign_creator = form_post_process.get("assign_creator")
                if assign_creator:
                    if_checkbox = assign_creator.get("if_checkbox")
                    if if_checkbox:
                        if if_checkbox["id"] not in element_ids:
                            self._logger.error(
                                f"Unknown issue-form post-process assign_creator if_checkbox ID: {if_checkbox}",
                                f"The ID '{if_checkbox}' is not a valid element ID within the issue body."
                            )
                        for elem in form["body"]:
                            elem_id = elem.get("id")
                            if elem_id and elem_id == if_checkbox["id"]:
                                if elem["type"] != "checkboxes":
                                    self._logger.error(
                                        f"Invalid issue-form post-process assign_creator if_checkbox ID: {if_checkbox}",
                                        f"The ID '{if_checkbox}' is not a checkbox element."
                                    )
                                if len(elem["attributes"]["options"]) < if_checkbox["number"]:
                                    self._logger.error(
                                        f"Invalid issue-form post-process assign_creator if_checkbox number: {if_checkbox}",
                                        f"The number '{if_checkbox['number']}' is greater than the number of "
                                        f"checkbox options."
                                    )
                                break
        for primary_type_id, sub_type_id in form_identifying_labels:
            if primary_type_id not in self._data["label"]["group"]["primary_type"]["labels"]:
                self._logger.error(
                    f"Unknown issue-form primary_commit_id: {primary_type_id}",
                    f"The ID '{primary_type_id}' does not exist in 'label.group.primary_type.labels'."
                )
            if sub_type_id and sub_type_id not in self._data["label"]["group"]["sub_type"]["labels"]:
                self._logger.error(
                    f"Unknown issue-form sub_type: {sub_type_id}",
                    f"The ID '{sub_type_id}' does not exist in 'label.group.sub_type.labels'."
                )
        return

