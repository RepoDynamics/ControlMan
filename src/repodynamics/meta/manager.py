from repodynamics.meta.datastruct import ControlCenterOptions
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
    TemplateType,
    Label,
    LabelType
)
from repodynamics.version import PEP440SemVer


class MetaManager:
    def __init__(self, options: dict):
        self._dict = options
        self._options = ControlCenterOptions(options)

        self._commit_data: dict = {}
        self._issue_data: dict = {}
        self._version_to_branch_map: dict[str, str] = {}
        return

    def __getitem__(self, item):
        return self._dict[item]

    def __contains__(self, item):
        return item in self._dict

    @property
    def settings(self) -> ControlCenterOptions:
        return self._options

    @property
    def as_dict(self) -> dict:
        return self._dict

    @property
    def branch(self) -> dict:
        return self._dict["branch"]

    @property
    def branch__main(self) -> dict:
        return self.branch["main"]

    @property
    def branch__main__name(self) -> str:
        return self.branch__main["name"]

    @property
    def branch__release(self) -> dict:
        return self.branch["release"]

    @property
    def branch__prerelease(self) -> dict:
        return self.branch["pre-release"]

    @property
    def branch__implement(self) -> dict:
        return self.branch["implementation"]

    @property
    def branch__dev(self) -> dict:
        return self.branch["development"]

    @property
    def branch__groups__prefixes(self) -> dict[BranchType, str]:
        return {BranchType(key): val["prefix"] for key, val in self.branch.items() if key != "main"}

    @property
    def changelog(self) -> dict:
        return self._dict.get("changelog", {})

    @property
    def issue(self) -> dict:
        return self._dict["issue"]

    @property
    def issue__forms(self) -> list[dict]:
        return self.issue["forms"]

    @property
    def maintainer(self) -> dict:
        return self._dict["maintainer"]

    @property
    def maintainer__issue(self) -> dict:
        return self.maintainer["issue"]

    @property
    def repo__config(self) -> dict:
        return self._dict["repo"]["config"]

    @property
    def workflow__init__schedule(self) -> dict[str, str]:
        return self._dict["workflow"]["init"]["schedule"]

    @property
    def workflow__init__schedule__test(self) -> str:
        return self.workflow__init__schedule["test"]

    @property
    def workflow__init__schedule__sync(self) -> str:
        return self.workflow__init__schedule["sync"]

    @property
    def web(self) -> dict:
        return self._dict["web"]

    @property
    def web__base_url(self) -> str | None:
        return self.web.get("base_url", None)

    @property
    def package(self) -> dict:
        return self._dict.get("package", {})

    @property
    def config__template(self) -> TemplateType:
        return TemplateType(self._dict["config"]["template"])

    def get_branch_info_from_name(self, branch_name: str) -> Branch:
        if branch_name == self.branch__main__name:
            return Branch(type=BranchType.MAIN, name=branch_name)
        for branch_type, branch_prefix in self.branch__groups__prefixes.items():
            if branch_name.startswith(branch_prefix):
                suffix_raw = branch_name.removeprefix(branch_prefix)
                if branch_type is BranchType.RELEASE:
                    suffix = int(suffix_raw)
                elif branch_type is BranchType.PRERELEASE:
                    suffix = PEP440SemVer(suffix_raw)
                elif branch_type is BranchType.IMPLEMENT:
                    issue_num, target_branch = suffix_raw.split("/", 1)
                    suffix = (int(issue_num), target_branch)
                elif branch_type is BranchType.DEV:
                    issue_num, target_branch_and_task = suffix_raw.split("/", 1)
                    target_branch, task_nr = target_branch_and_task.rsplit("/", 1)
                    suffix = (int(issue_num), target_branch, int(task_nr))
                else:
                    suffix = suffix_raw
                return Branch(type=branch_type, name=branch_name, prefix=branch_prefix, suffix=suffix)
        return Branch(type=BranchType.OTHER, name=branch_name)

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
        group = self._dict["label"]["group"][group_id]
        label = group["labels"][label_id]
        out = {
            "name": f"{group['prefix']}{label['suffix']}",
            "color": group["color"],
            "description": label["description"],
        }
        return out

    def resolve_labels(self, names: list[str]) -> dict[LabelType, list[Label]]:
        """
        Resolve a list of label names to label objects.

        Parameters
        ----------
        names : list[str]
            List of label names.
        """
        labels = {}
        for name in names:
            label = self.resolve_label(name)
            labels.setdefault(label.category, []).append(label)
        return labels

    def resolve_label(self, name: str) -> Label:
        """
        Resolve a label name to a label object.

        Parameters
        ----------
        name : str
            Name of the label.
        """
        def get_label_id():
            for label_id, label_data in group["labels"].items():
                if label_data["suffix"] == label_suffix:
                    break
            else:
                raise ValueError(f"Unknown label suffix '{label_suffix}' for group '{group_id}'.")
            return label_id

        for autogroup_id, autogroup in self._dict["label"]["auto_group"].items():
            prefix = autogroup["prefix"]
            if name.startswith(prefix):
                return Label(
                    category=LabelType(autogroup_id),
                    name=name,
                    prefix=prefix,
                )
        for group_id, group in self._dict["label"]["group"].items():
            prefix = group["prefix"]
            if name.startswith(prefix):
                label_suffix = name.removeprefix(prefix)
                if group_id == "primary_type":
                    category = LabelType.TYPE
                    label_id = get_label_id()
                    try:
                        suffix_type = PrimaryActionCommitType(label_id)
                    except ValueError:
                        suffix_type = label_id
                elif group_id == "subtype":
                    category = LabelType.SUBTYPE
                    suffix_type = get_label_id()
                elif group_id == "status":
                    category = LabelType.STATUS
                    suffix_type = IssueStatus(get_label_id())
                else:
                    category = LabelType.CUSTOM_GROUP
                    suffix_type = get_label_id()
                return Label(
                    category=category,
                    name=name,
                    prefix=prefix,
                    type=suffix_type,
                )
        for label_id, label in self._dict["label"]["single"].items():
            if name == label["name"]:
                return Label(
                    category=LabelType.SINGLE,
                    name=name,
                    type=label_id,
                )
        return Label(category=LabelType.UNKNOWN, name=name)

    def get_issue_form_identifying_labels(self, issue_form_id: str) -> tuple[str, str | None]:
        """
        Get the identifying labels for an issue form.

        Each issue form is uniquely identified by a primary type label, and if necessary, a subtype label.

        Returns
        -------
        A tuple of (primary_type, subtype) label names for the issue.
        Note that `subtype` may be `None`.
        """
        for form in self._dict["issue"]["forms"]:
            if form["id"] == issue_form_id:
                issue_form = form
                break
        else:
            raise ValueError(f"Unknown issue form ID: {issue_form_id}")
        primary_type = issue_form["primary_type"]
        primary_type_label_name = self.get_label_grouped("primary_type", primary_type)["name"]
        subtype = issue_form.get("subtype")
        if subtype:
            subtype_label_name = self.get_label_grouped("subtype", subtype)["name"]
        else:
            subtype_label_name = None
        return primary_type_label_name, subtype_label_name

    def get_issue_form_from_labels(self, label_names: list[str]) -> dict:
        """
        Get the issue form from a list of label names.

        This is done by finding the primary type and subtype labels in the list of labels,
        finding their IDs, and then finding the issue form with the corresponding `primary_type`
        and `subtype`.

        Parameters
        ----------
        label_names : list[str]
            List of label names.

        Returns
        -------
        The corresponding form metadata in `issue.forms`.
        """
        prefix = {
            "primary_type": self._dict["label"]["group"]["primary_type"]["prefix"],
            "subtype": self._dict["label"]["group"].get("subtype", {}).get("prefix"),
        }
        suffix = {}
        for label_name in label_names:
            for label_type, prefix in prefix.items():
                if prefix and label_name.startswith(prefix):
                    if suffix.get(label_type) is not None:
                        raise ValueError(f"Label '{label_name}' with type {label_type} is a duplicate.")
                    suffix[label_type] = label_name.removeprefix(prefix)
                    break
        label_ids = {"primary_type": "", "subtype": ""}
        for label_id, label in self._dict["label"]["group"]["primary_type"]["labels"].items():
            if label["suffix"] == suffix["primary_type"]:
                label_ids["primary_type"] = label_id
                break
        else:
            raise ValueError(f"Unknown primary type label suffix '{suffix['primary_type']}'.")
        if suffix["subtype"]:
            for label_id, label in self._dict["label"]["group"]["subtype"]["labels"].items():
                if label["suffix"] == suffix["subtype"]:
                    label_ids["subtype"] = label_id
                    break
            else:
                raise ValueError(f"Unknown sub type label suffix '{suffix['subtype']}'.")
        for form in self._dict["issue"]["forms"]:
            if (
                form["primary_type"] == label_ids["primary_type"]
                and form.get("subtype", "") == label_ids["subtype"]
            ):
                return form
        raise ValueError(
            f"Could not find issue form with primary type '{label_ids['primary_type']}' "
            f"and sub type '{label_ids['subtype']}'."
        )

    def get_issue_data_from_labels(self, label_names: list[str]) -> Issue:
        type_prefix = {
            "primary_type": self._dict["label"]["group"]["primary_type"]["prefix"],
            "subtype": self._dict["label"]["group"].get("subtype", {}).get("prefix"),
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

        key = (label["primary_type"], label.get("subtype"))

        if not self._issue_data:
            self._issue_data = self._initialize_issue_data()

        issue_data = self._issue_data.get(key)

        if not issue_data:
            raise ValueError(
                f"Could not find issue type with primary type '{label['primary_type']}' "
                f"and sub type '{label.get('subtype')}'."
            )
        return issue_data

    def get_all_conventional_commit_types(self) -> list[str]:
        if not self._commit_data:
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
        if not self._dict.get("package"):
            raise ValueError("No package metadata found.")
        self._version_to_branch_map = {
            release["version"]: release["branch"]
            for release in self._dict["package"]["releases"]["per_branch"]
        }
        return self._version_to_branch_map[version]

    def get_issue_status_from_status_label(self, label_name: str):
        status_prefix = self._dict["label"]["group"]["status"]["prefix"]
        if not label_name.startswith(status_prefix):
            raise ValueError(f"Label '{label_name}' is not a status label.")
        status = label_name.removeprefix(status_prefix)
        for status_label_id, status_label_info in self._dict["label"]["group"]["status"]["labels"].items():
            if status_label_info["suffix"] == status:
                return IssueStatus(status_label_id)
        raise ValueError(f"Unknown status label suffix '{status}'.")

    def create_label_branch(self, source: Label | str) -> Label:
        prefix = self._dict["label"]["auto_group"]["branch"]["prefix"]
        if isinstance(source, str):
            branch_name = source
        elif isinstance(source, Label):
            if source.category is not LabelType.VERSION:
                raise ValueError(f"Label '{source.name}' is not a version label.")
            branch_name = self.get_branch_from_version(version=source.suffix)
        else:
            raise TypeError(f"Invalid type for source: {type(source)}")
        return Label(
            category=LabelType.BRANCH,
            name=f'{prefix}{branch_name}',
            prefix=prefix,
        )

    def _initialize_commit_data(self):
        commit_type = {}
        for group_id, group_data in self._dict["commit"]["primary_action"].items():
            commit_type[group_data["type"]] = PrimaryActionCommit(
                action=PrimaryActionCommitType(group_id),
                conv_type=group_data["type"],
            )
        for group_id, group_data in self._dict["commit"]["primary_custom"].items():
            commit_type[group_data["type"]] = PrimaryCustomCommit(
                group_id=group_id,
                conv_type=group_data["type"],
            )
        for group_id, group_data in self._dict["commit"]["secondary_action"].items():
            commit_type[group_data["type"]] = SecondaryActionCommit(
                action=SecondaryActionCommitType(group_id),
                conv_type=group_data["type"],
            )
        for conv_type, group_data in self._dict["commit"]["secondary_custom"].items():
            commit_type[conv_type] = SecondaryCustomCommit(
                conv_type=conv_type,
                changelog_id=group_data["changelog_id"],
                changelog_section_id=group_data["changelog_section_id"],
            )
        return commit_type

    def _initialize_issue_data(self):
        issue_data = {}
        for issue in self._dict["issue"]["forms"]:
            prim_id = issue["primary_type"]

            prim_label_prefix = self._dict["label"]["group"]["primary_type"]["prefix"]
            prim_label_suffix = self._dict["label"]["group"]["primary_type"]["labels"][prim_id]["suffix"]
            prim_label = f"{prim_label_prefix}{prim_label_suffix}"

            type_labels = [prim_label]

            sub_id = issue.get("subtype")
            if sub_id:
                sub_label_prefix = self._dict["label"]["group"]["subtype"]["prefix"]
                sub_label_suffix = self._dict["label"]["group"]["subtype"]["labels"][sub_id]["suffix"]
                sub_label = f"{sub_label_prefix}{sub_label_suffix}"
                type_labels.append(sub_label)
            else:
                sub_label = None

            key = (prim_label, sub_label)

            prim_commit = self._dict["commit"]["primary_action"].get(prim_id)
            if prim_commit:
                commit = PrimaryActionCommit(
                    action=PrimaryActionCommitType(prim_id),
                    conv_type=prim_commit["type"],
                )
            else:
                commit = PrimaryCustomCommit(
                    group_id=prim_id,
                    conv_type=self._dict["commit"]["primary_custom"][prim_id]["type"],
                )

            issue_data[key] = Issue(group_data=commit, type_labels=type_labels, form=issue)
        return issue_data
