from repodynamics.actions.init import ModifyingEventHandler


class PullRequestEventHandler(ModifyingEventHandler):


    def run(self):
        if action == WorkflowTriggeringAction.OPENED:
            self.event_pull_opened()
        elif action == WorkflowTriggeringAction.REOPENED:
            self.event_pull_reopened()
        elif action == WorkflowTriggeringAction.SYNCHRONIZE:
            self.event_pull_synchronize()
        elif action == WorkflowTriggeringAction.LABELED:
            self.event_pull_labeled()
        else:
            self.logger.error(action_err_msg, action_err_details)

    def event_pull_reopened(self):
        return

    def event_pull_synchronize(self):
        if self.event_name == "pull_request" and action != "fail" and not self.pull_is_internal:
            self._logger.attention(
                "Hook fixes cannot be applied as pull request is from a forked repository; "
                f"switching action from '{action}' to 'fail'."
            )
            action = "fail"
        return

    def event_pull_labeled(self):
        return

    def event_pull_request(self):
        self.event_type = EventType.PULL_MAIN
        branch = self.resolve_branch(self.pull_head_ref_name)
        if branch.type == BranchType.DEV and branch.suffix == 0:
            return
        for job_id in ("package_build", "package_test_local", "package_lint", "website_build"):
            self.set_job_run(job_id)
        self.git.checkout(branch=self.pull_base_ref_name)
        latest_base_hash = self.git.commit_hash_normal()
        base_ver, dist = self.get_latest_version()
        self.git.checkout(branch=self.pull_head_ref_name)

        self.action_file_change_detector()
        self.action_meta()
        self._action_hooks()

        branch = self.resolve_branch(self.pull_head_ref_name)
        issue_labels = [label["name"] for label in self.gh_api.issue_labels(number=branch.suffix)]
        issue_data = self.metadata_main.get_issue_data_from_labels(issue_labels)

        if issue_data.group_data.group == CommitGroup.PRIMARY_CUSTOM or issue_data.group_data.action in [
            PrimaryActionCommitType.WEBSITE,
            PrimaryActionCommitType.META,
        ]:
            ver_dist = f"{base_ver}+{dist+1}"
        else:
            ver_dist = str(self.get_next_version(base_ver, issue_data.group_data.action))

        changelog_manager = ChangelogManager(
            changelog_metadata=self.metadata_main["changelog"],
            ver_dist=ver_dist,
            commit_type=issue_data.group_data.conv_type,
            commit_title=self.pull_title,
            parent_commit_hash=latest_base_hash,
            parent_commit_url=self._gh_link.commit(latest_base_hash),
            logger=self.logger,
        )

        commits = self.get_commits()
        self.logger.success(f"Found {len(commits)} commits.")
        for commit in commits:
            self.logger.info(f"Processing commit: {commit}")
            if commit.group_data.group == CommitGroup.SECONDARY_CUSTOM:
                changelog_manager.add_change(
                    changelog_id=commit.group_data.changelog_id,
                    section_id=commit.group_data.changelog_section_id,
                    change_title=commit.msg.title,
                    change_details=commit.msg.body,
                )
        entries = changelog_manager.get_all_entries()
        self.logger.success(f"Found {len(entries)} changelog entries.", str(entries))
        curr_body = self.pull_body.strip() if self.pull_body else ""
        if curr_body:
            curr_body += "\n\n"
        for entry, changelog_name in entries:
            curr_body += f"# Changelog: {changelog_name}\n\n{entry}\n\n"
        self.gh_api.pull_update(
            number=self.pull_number,
            title=f"{issue_data.group_data.conv_type}: {self.pull_title.removeprefix(f'{issue_data.group_data.conv_type}: ')}",
            body=curr_body,
        )
        return

    def event_pull_opened(self):
        if self.event_name == "pull_request" and action != "fail" and not self.pull_is_internal:
            self._logger.attention(
                "Meta synchronization cannot be performed as pull request is from a forked repository; "
                f"switching action from '{action}' to 'fail'."
            )
            action = "fail"
        return