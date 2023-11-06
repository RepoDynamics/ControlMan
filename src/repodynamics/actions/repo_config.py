

class RepoConfigAction:

    def action_repo_labels_sync(self, init: bool = False):
        name = "Repository Labels Synchronizer"
        self.logger.h1(name)
        current_labels = self.api.labels
        new_labels = self.metadata["label"]["compiled"]
        if init:
            for label in current_labels:
                self.api.label_delete(label["name"])
            for label in new_labels.values():
                self.api.label_create(**label)
            return
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

    def action_repo_settings_sync(self):
        data = self.metadata["repo"]["config"] | {
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

    def action_branch_names_sync(self):
        before = self.metadata_before["branch"]
        after = self.metadata["branch"]
        renamed = False
        if before["default"]["name"] != after["default"]["name"]:
            self.api_admin.branch_rename(
                old_name=before["default"]["name"],
                new_name=after["default"]["name"]
            )
            renamed = True
        branches = self.api_admin.branches
        branch_names = [branch["name"] for branch in branches]
        for group_name in ("release", "dev", "ci_pull"):
            prefix_before = before["group"][group_name]["prefix"]
            prefix_after = after["group"][group_name]["prefix"]
            if prefix_before != prefix_after:
                for branch_name in branch_names:
                    if branch_name.startswith(prefix_before):
                        self.api_admin.branch_rename(
                            old_name=branch_name,
                            new_name=f"{prefix_after}{branch_name.removeprefix(prefix_before)}"
                        )
                        renamed = True
        return renamed

    def action_repo_pages(self):
        if not self.api.info["has_pages"]:
            self.api_admin.pages_create(build_type="workflow")
        custom_url = self.metadata["web"].get("base_url")
        if custom_url:
            self.api_admin.pages_update(
                cname=custom_url.removeprefix("https://").removeprefix("http://"),
                https_enforced=custom_url.startswith("https://"),
                build_type="workflow"
            )
        return