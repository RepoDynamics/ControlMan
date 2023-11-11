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
        logger: Logger | None = None,
    ):
        self.api = workflow_api
        self.api_admin = admin_api
        self.metadata = metadata
        self.metadata_before = metadata_before
        self.logger = logger or Logger()
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
            reverse=True,
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
                    color=new_label["color"],
                )
        if not still_allowed_version_ids:
            return
        if (
            self.metadata_before["label"]["auto_group"]["version"]
            == self.metadata["label"]["auto_group"]["version"]
        ):
            return
        new_prefix = self.metadata["label"]["auto_group"]["version"]["prefix"]
        new_color = self.metadata["label"]["auto_group"]["version"]["color"]
        new_description = self.metadata["label"]["auto_group"]["version"]["description"]
        for still_allowed_version_id in still_allowed_version_ids:
            self.api.label_update(
                name=old_labels_versions[str(still_allowed_version_id)]["name"],
                new_name=f"{new_prefix}{still_allowed_version_id}",
                description=new_description,
                color=new_color,
            )
        return
