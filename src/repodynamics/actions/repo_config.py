from pylinks.api.github import Repo
from repodynamics.logger import Logger
from repodynamics.meta.manager import MetaManager


class RepoConfigAction:

    def __init__(
        self,
        workflow_api: Repo,
        admin_api: Repo,
        metadata: MetaManager,
        metadata_before: MetaManager | None = None,
        logger: Logger | None = None
    ):
        self.api = workflow_api
        self.api_admin = admin_api
        self.metadata = metadata
        self.metadata_before = metadata_before
        self.logger = logger or Logger()
        return

    def replace_repo_labels(self):
        for label in self.api.labels:
            self.api.label_delete(label["name"])
        for label in self.metadata.label__compiled.values():
            self.api.label_create(**label)
        return

    def update_repo_labels(self, init: bool = False):
        name = "Repository Labels Synchronizer"
        self.logger.h1(name)
        current_labels = self.api.labels
        new_labels = self.metadata["label"]["compiled"]

        old_labels = self.metadata_before["label"]["compiled"]
        old_labels_not_versions = {}
        old_labels_versions = {}
        for label_id in old_labels.keys():
            if label_id[:2] == ("auto_group", "version"):
                old_labels_versions[label_id[2]] = old_labels[label_id]
            else:
                old_labels_not_versions[label_id] = old_labels[label_id]
        new_labels_versions = {}
        new_labels_not_versions = {}
        for label_id in new_labels.keys():
            if label_id[:2] == ("auto_group", "version"):
                new_labels_versions[label_id[2]] = new_labels[label_id]
            else:
                new_labels_not_versions[label_id] = new_labels[label_id]
        old_ids = set(old_labels_not_versions.keys())
        new_ids = set(new_labels_not_versions.keys())
        deleted_ids = old_ids - new_ids
        added_ids = new_ids - old_ids
        added_version_ids = set(new_labels_versions.keys()) - set(old_labels_versions.keys())
        deleted_version_ids = sorted(
            [PEP440SemVer(ver) for ver in set(old_labels_versions.keys()) - set(new_labels_versions.keys())],
            reverse=True
        )
        remaining_allowed_number = 1000 - len(new_labels)
        still_allowed_version_ids = deleted_version_ids[:remaining_allowed_number]
        outdated_version_ids = deleted_version_ids[remaining_allowed_number:]
        for outdated_version_id in outdated_version_ids:
            self.api.label_delete(old_labels_versions[str(outdated_version_id)]["name"])
        for deleted_id in deleted_ids:
            self.api.label_delete(old_labels[deleted_id]["name"])
        for new_label_version_id in added_version_ids:
            self.api.label_create(**new_labels_versions[new_label_version_id])
        for added_id in added_ids:
            self.api.label_create(**new_labels[added_id])
        possibly_modified_ids = set(old_labels.keys()) & set(new_labels.keys())
        for possibly_modified_id in possibly_modified_ids:
            old_label = old_labels[possibly_modified_id]
            new_label = new_labels[possibly_modified_id]
            if old_label != new_label:
                self.api.label_update(
                    name=old_label["name"],
                    new_name=new_label["name"],
                    description=new_label["description"],
                    color=new_label["color"]
                )
        if not still_allowed_version_ids:
            return
        if self.metadata_before["label"]["auto_group"]["version"] == self.metadata["label"]["auto_group"]["version"]:
            return
        new_prefix = self.metadata["label"]["auto_group"]["version"]["prefix"]
        new_color = self.metadata["label"]["auto_group"]["version"]["color"]
        new_description = self.metadata["label"]["auto_group"]["version"]["description"]
        for still_allowed_version_id in still_allowed_version_ids:
            self.api.label_update(
                name=old_labels_versions[str(still_allowed_version_id)]["name"],
                new_name=f"{new_prefix}{still_allowed_version_id}",
                description=new_description,
                color=new_color
            )
        return

    def update_repo_settings(self):
        data = self.metadata.repo__config | {
            "has_issues": True,
            "allow_squash_merge": True,
            "squash_merge_commit_title": "PR_TITLE",
            "squash_merge_commit_message": "PR_BODY",
        }
        topics = data.pop("topics")
        self.api_admin.repo_update(**data)
        self.api_admin.repo_topics_replace(topics=topics)
        if not self.api_admin.actions_permissions_workflow_default()['can_approve_pull_request_reviews']:
            self.api_admin.actions_permissions_workflow_default_set(can_approve_pull_requests=True)
        return

    def update_branch_names(self) -> dict:
        if not self.metadata_before:
            self.logger.error("Cannot update branch names as no previous metadata is available.")
        before = self.metadata_before.branch
        after = self.metadata.branch
        old_to_new_map = {}
        if before["default"]["name"] != after["default"]["name"]:
            self.api_admin.branch_rename(
                old_name=before["default"]["name"],
                new_name=after["default"]["name"]
            )
            old_to_new_map[before["default"]["name"]] = after["default"]["name"]
        branches = self.api_admin.branches
        branch_names = [branch["name"] for branch in branches]
        for group_name in ("release", "dev", "ci_pull"):
            prefix_before = before["group"][group_name]["prefix"]
            prefix_after = after["group"][group_name]["prefix"]
            if prefix_before != prefix_after:
                for branch_name in branch_names:
                    if branch_name.startswith(prefix_before):
                        new_name = f"{prefix_after}{branch_name.removeprefix(prefix_before)}"
                        self.api_admin.branch_rename(old_name=branch_name, new_name=new_name)
                        old_to_new_map[branch_name] = new_name
        return old_to_new_map

    def update_pages_settings(self) -> None:
        """Activate GitHub Pages (source: workflow) if not activated, update custom domain."""
        if not self.api.info["has_pages"]:
            self.api_admin.pages_create(build_type="workflow")
        cname = self.metadata.web__base_url
        self.api_admin.pages_update(
            cname=cname.removeprefix("https://").removeprefix("http://") if cname else None,
            https_enforced=cname.startswith("https://") if cname else True,
            build_type="workflow"
        )
        return
