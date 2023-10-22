

class MetaManager:

    def __init__(self, metadata: dict):
        self._data = metadata
        return

    def get_label_grouped(self, group_id: str, label_id: str) -> dict[str, str]:
        """
        Get information for a label in a label group.

        Returns
        -------
        A dictionary with the following keys:

        name : str
            Name of the label.
        color: str
            Color of the label in hex format.
        description: str
            Description of the label.
        """
        group = self._data["label"]["group"][group_id]
        label = group["labels"][label_id]
        out = {
            "name": f"{group['prefix']}{label['suffix']}",
            "color": group["color"],
            "description": label["description"]
        }
        return out

    def get_issue_form_identifying_labels(self, issue_form_id: str) -> tuple[str, str | None]:
        """
        Get the identifying labels for an issue form.

        Each issue form is uniquely identified by a primary type label, and if necessary, a subtype label.

        Returns
        -------
        A tuple of (primary_type, sub_type) label names for the issue.
        Note that `sub_type` may be `None`.
        """
        for form in self._data["issue"]["forms"]:
            if form["id"] == issue_form_id:
                issue_form = form
                break
        else:
            raise ValueError(f"Unknown issue form ID: {issue_form_id}")
        primary_type = issue_form["primary_commit_id"]
        primary_type_label_name = self.get_label_grouped("primary_type", primary_type)["name"]
        sub_type = issue_form.get("sub_type")
        if sub_type:
            sub_type_label_name = self.get_label_grouped("sub_type", sub_type)["name"]
        else:
            sub_type_label_name = None
        return primary_type_label_name, sub_type_label_name

    def get_issue_form_from_labels(self, label_names: list[str]) -> dict:
        """
        Get the issue form from a list of label names.

        This is done by finding the primary type and subtype labels in the list of labels,
        finding their IDs, and then finding the issue form with the corresponding `primary_commit_id`
        and `sub_type`.

        Parameters
        ----------
        label_names : list[str]
            List of label names.

        Returns
        -------
        The corresponding form metadata in `issue.forms`.
        """
        prefix = {
            "primary_type": self._data["label"]["group"]["primary_type"]["prefix"],
            "sub_type": self._data["label"]["group"].get("sub_type", {}).get("prefix"),
        }
        suffix = {}
        for label_name in label_names:
            for label_type, prefix in prefix.items():
                if prefix and label_name.startswith(prefix):
                    if suffix.get(label_type) is not None:
                        raise ValueError(f"Label '{label_name}' with type {label_type} is a duplicate.")
                    suffix[label_type] = label_name.removeprefix(prefix)
                    break
        label_ids = {"primary_type": "", "sub_type": ""}
        for label_id, label in self._data["label"]["group"]["primary_type"]["labels"].items():
            if label["suffix"] == suffix["primary_type"]:
                label_ids["primary_type"] = label_id
                break
        else:
            raise ValueError(f"Unknown primary type label suffix '{suffix['primary_type']}'.")
        if suffix["sub_type"]:
            for label_id, label in self._data["label"]["group"]["sub_type"]["labels"].items():
                if label["suffix"] == suffix["sub_type"]:
                    label_ids["sub_type"] = label_id
                    break
            else:
                raise ValueError(f"Unknown sub type label suffix '{suffix['sub_type']}'.")
        for form in self._data["issue"]["forms"]:
            if (
                form["primary_commit_id"] == label_ids["primary_type"]
                and form.get("sub_type", "") == label_ids["sub_type"]
            ):
                return form
        raise ValueError(
            f"Could not find issue form with primary type '{label_ids['primary_type']}' "
            f"and sub type '{label_ids['sub_type']}'."
        )
