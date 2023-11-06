from repodynamics.datatype import (
    BranchType,
    Branch,
    PrimaryActionCommit,
    PrimaryActionCommitType,
    PrimaryCustomCommit,
    SecondaryActionCommit,
    SecondaryActionCommitType,
    SecondaryCustomCommit,
    Issue,
    IssueStatus,
)


class MetaManager:
    def __init__(self, metadata: dict):
        self._data = metadata
        self._commit_data: dict = {}
        self._issue_data: dict = {}
        self._version_to_branch_map: dict[str, str] = {}
        return

    @property
    def dict(self) -> dict:
        return self._data

    @property
    def branch(self) -> dict:
        return self._data["branch"]

    @property
    def branch__group(self) -> dict:
        return self.branch["group"]

    @property
    def workflow__init__schedule(self) -> dict[str, str]:
        return self._data["workflow"]["init"]["schedule"]

    @property
    def workflow__init__schedule__test(self) -> str:
        return self.workflow__init__schedule["test"]

    @property
    def workflow__init__schedule__sync(self) -> str:
        return self.workflow__init__schedule["sync"]

    def get_branch_info_from_name(self, branch_name: str) -> Branch:
        if branch_name == self.branch["default"]["name"]:
            return Branch(type=BranchType.DEFAULT)
        for group_name, group_data in self.branch__group.items():
            prefix = group_data["prefix"]
            if branch_name.startswith(prefix):
                suffix_raw = branch_name.removeprefix(prefix)
                suffix = suffix_raw if group_name == "ci_pull" else int(suffix_raw)
                return Branch(type=BranchType(group_name), prefix=prefix, suffix=suffix)
        return Branch(type=BranchType.OTHER)

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
            "description": label["description"],
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

    def get_issue_data_from_labels(self, label_names: list[str]) -> Issue:
        type_prefix = {
            "primary_type": self._data["label"]["group"]["primary_type"]["prefix"],
            "sub_type": self._data["label"]["group"].get("sub_type", {}).get("prefix"),
        }
        label = {}
        for label_name in label_names:
            for label_type, prefix in type_prefix.items():
                if prefix and label_name.startswith(prefix):
                    if label.get(label_type) is not None:
                        raise ValueError(f"Label '{label_name}' with type {label_type} is a duplicate.")
                    label[label_type] = label_name
                    break
        if "primary_type" not in label:
            raise ValueError(f"Could not find primary type label in {label_names}.")

        key = (label["primary_type"], label.get("sub_type"))

        if not self._issue_data:
            self._issue_data = self._initialize_issue_data()

        issue_data = self._issue_data.get(key)

        if not issue_data:
            raise ValueError(
                f"Could not find issue type with primary type '{label['primary_type']}' "
                f"and sub type '{label.get('sub_type')}'."
            )
        return issue_data

    def get_all_conventional_commit_types(self) -> list[str]:
        if self._commit_data:
            return list(self._commit_data.keys())
        self._commit_data = self._initialize_commit_data()
        return list(self._commit_data.keys())

    def get_commit_type_from_conventional_type(
        self, conv_type: str
    ) -> PrimaryActionCommit | PrimaryCustomCommit | SecondaryActionCommit | SecondaryCustomCommit:
        if self._commit_data:
            return self._commit_data[conv_type]
        self._commit_data = self._initialize_commit_data()
        return self._commit_data[conv_type]

    def get_branch_from_version(self, version: str) -> str:
        if self._version_to_branch_map:
            return self._version_to_branch_map[version]
        if not self._data.get("package"):
            raise ValueError("No package metadata found.")
        self._version_to_branch_map = {
            release["version"]: release["branch"]
            for release in self._data["package"]["releases"]["per_branch"]
        }
        return self._version_to_branch_map[version]

    def get_issue_status_from_status_label(self, label_name: str):
        status_prefix = self._data["label"]["group"]["status"]["prefix"]
        if not label_name.startswith(status_prefix):
            raise ValueError(f"Label '{label_name}' is not a status label.")
        status = label_name.removeprefix(status_prefix)
        for status_label_id, status_label_info in self._data["label"]["group"]["status"]["labels"].items():
            if status_label_info["suffix"] == status:
                return IssueStatus(status_label_id)
        raise ValueError(f"Unknown status label suffix '{status}'.")

    def _initialize_commit_data(self):
        commit_type = {}
        for group_id, group_data in self._data["commit"]["primary_action"].items():
            commit_type[group_data["type"]] = PrimaryActionCommit(
                action=PrimaryActionCommitType(group_id),
                conv_type=group_data["type"],
            )
        for group_id, group_data in self._data["commit"]["primary_custom"].items():
            commit_type[group_data["type"]] = PrimaryCustomCommit(
                group_id=group_id,
                conv_type=group_data["type"],
            )
        for group_id, group_data in self._data["commit"]["secondary_action"].items():
            commit_type[group_data["type"]] = SecondaryActionCommit(
                action=SecondaryActionCommitType(group_id),
                conv_type=group_data["type"],
            )
        for conv_type, group_data in self._data["commit"]["secondary_custom"].items():
            commit_type[conv_type] = SecondaryCustomCommit(
                conv_type=conv_type,
                changelog_id=group_data["changelog_id"],
                changelog_section_id=group_data["changelog_section_id"],
            )
        return commit_type

    def _initialize_issue_data(self):
        issue_data = {}
        for issue in self._data["issue"]["forms"]:
            prim_id = issue["primary_commit_id"]

            prim_label_prefix = self._data["label"]["group"]["primary_type"]["prefix"]
            prim_label_suffix = self._data["label"]["group"]["primary_type"]["labels"][prim_id]["suffix"]
            prim_label = f"{prim_label_prefix}{prim_label_suffix}"

            type_labels = [prim_label]

            sub_id = issue.get("sub_type")
            if sub_id:
                sub_label_prefix = self._data["label"]["group"]["sub_type"]["prefix"]
                sub_label_suffix = self._data["label"]["group"]["sub_type"]["labels"][sub_id]["suffix"]
                sub_label = f"{sub_label_prefix}{sub_label_suffix}"
                type_labels.append(sub_label)
            else:
                sub_label = None

            key = (prim_label, sub_label)

            prim_commit = self._data["commit"]["primary_action"].get(prim_id)
            if prim_commit:
                commit = PrimaryActionCommit(
                    action=PrimaryActionCommitType(prim_id),
                    conv_type=prim_commit["type"],
                )
            else:
                commit = PrimaryCustomCommit(
                    group_id=prim_id,
                    conv_type=self._data["commit"]["primary_custom"][prim_id]["type"],
                )

            issue_data[key] = Issue(group_data=commit, type_labels=type_labels, form=issue)
        return issue_data
