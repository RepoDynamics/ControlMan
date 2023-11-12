import time

from pylinks.http import WebAPIError

from repodynamics import meta
from repodynamics.actions.events._base import ModifyingEventHandler
from repodynamics.actions.context_manager import ContextManager, PullRequestPayload
from repodynamics.datatype import (
    WorkflowTriggeringAction,
    EventType,
    PrimaryActionCommitType,
    CommitGroup,
    BranchType,
    IssueStatus
)
from repodynamics.logger import Logger
from repodynamics.meta.manager import MetaManager
from repodynamics.actions._changelog import ChangelogManager
from repodynamics.actions import _helpers


class PullRequestEventHandler(ModifyingEventHandler):
    def __init__(
        self,
        context_manager: ContextManager,
        admin_token: str,
        logger: Logger | None = None,
    ):
        super().__init__(context_manager=context_manager, admin_token=admin_token, logger=logger)
        self._payload: PullRequestPayload = self._context.payload
        self._branch_base = self.resolve_branch(self._context.github.base_ref)
        self._branch_head = self.resolve_branch(self._context.github.head_ref)
        self._git_base.fetch_remote_branches_by_name(branch_names=self._context.github.base_ref)
        self._git_head.fetch_remote_branches_by_name(branch_names=self._context.github.head_ref)
        return

    def run_event(self):
        action = self._context.payload.action
        if action == WorkflowTriggeringAction.OPENED:
            self._run_opened()
        elif action == WorkflowTriggeringAction.REOPENED:
            self._run_reopened()
        elif action == WorkflowTriggeringAction.SYNCHRONIZE:
            self._run_synchronize()
        elif action == WorkflowTriggeringAction.LABELED:
            self._run_labeled()
        elif action == WorkflowTriggeringAction.READY_FOR_REVIEW:
            self._run_ready_for_review()
        else:
            _helpers.error_unsupported_triggering_action(
                event_name="pull_request", action=action, logger=self._logger
            )
        return

    def _run_opened(self):
        if self.event_name == "pull_request" and action != "fail" and not self.pull_is_internal:
            self._logger.attention(
                "Meta synchronization cannot be performed as pull request is from a forked repository; "
                f"switching action from '{action}' to 'fail'."
            )
            action = "fail"
        return

    def _run_reopened(self):
        return

    def _run_synchronize(self):
        if self.event_name == "pull_request" and action != "fail" and not self.pull_is_internal:
            self._logger.attention(
                "Hook fixes cannot be applied as pull request is from a forked repository; "
                f"switching action from '{action}' to 'fail'."
            )
            action = "fail"
        return

    def _run_labeled(self):
        label_name = self._payload.label["name"]
        if label_name.startswith(self._metadata_main["label"]["group"]["status"]["prefix"]):
            self._run_labeled_status()
        return

    def _run_labeled_status(self):
        status = self._metadata_main.get_issue_status_from_status_label(self._payload.label["name"])
        if status in (IssueStatus.ALPHA, IssueStatus.BETA, IssueStatus.RC):
            self._run_labeled_status_pre()
        elif status == IssueStatus.FINAL:
            self._run_labeled_status_final()
        return

    def _run_labeled_status_pre(self):
        if self._branch_head.type != BranchType.DEV or self._branch_base.type not in (BranchType.RELEASE, BranchType.DEFAULT):
            self._logger.error(
                "Merge not allowed",
                f"Merge from a head branch of type '{self._branch_head.type.value}' "
                f"to a branch of type '{self._branch_base.type.value}' is not allowed.",
            )
            return
        if not self._payload.internal:
            self._logger.error(
                "Merge not allowed",
                "Merge from a forked repository is only allowed "
                "from a development branch to the corresponding development branch.",
            )
            return


    def _run_labeled_status_final(self):
        if self._branch_head.type == BranchType.DEV:
            if self._branch_base.type in (BranchType.RELEASE, BranchType.DEFAULT):
                return self._run_merge_dev_to_release()
            elif self._branch_base.type == BranchType.PRE_RELEASE:
                return self._run_merge_dev_to_pre()
        elif self._branch_head.type == BranchType.PRE_RELEASE:
            if self._branch_base.type in (BranchType.RELEASE, BranchType.DEFAULT):
                return self._run_merge_pre_to_release()
        elif self._branch_head.type == BranchType.CI_PULL:
            return self._run_merge_ci_pull()
        self._logger.error(
            "Merge not allowed",
            f"Merge from a head branch of type '{self._branch_head.type.value}' "
            f"to a branch of type '{self._branch_base.type.value}' is not allowed.",
        )
        return

    def _run_merge_dev_to_release(self):
        if not self._payload.internal:
            self._logger.error(
                "Merge not allowed",
                "Merge from a forked repository is only allowed "
                "from a development branch to the corresponding development branch.",
            )
            return
        self._git_base.checkout(branch=self._branch_base.name)
        hash_bash = self._git_base.commit_hash_normal()
        ver_base, dist_base = self._get_latest_version()
        labels = self._payload.label_names
        primary_commit_type = self._metadata_main.get_issue_data_from_labels(labels).group_data
        if primary_commit_type.group == CommitGroup.PRIMARY_CUSTOM or primary_commit_type.action in (
            PrimaryActionCommitType.WEBSITE,
            PrimaryActionCommitType.META,
        ):
            ver_dist = f"{ver_base}+{dist_base + 1}"
            next_ver = None
        else:
            next_ver = self._get_next_version(ver_base, primary_commit_type.action)
            ver_dist = str(next_ver)
        changelog_manager = ChangelogManager(
            changelog_metadata=self._metadata_main["changelog"],
            ver_dist=ver_dist,
            commit_type=primary_commit_type.conv_type,
            commit_title=self._payload.title,
            parent_commit_hash=hash_bash,
            parent_commit_url=self._gh_link.commit(hash_bash),
            logger=self._logger,
        )
        self._git_base.checkout(branch=self._branch_head.name)
        commits = self._get_commits()
        for commit in commits:
            self._logger.info(f"Processing commit: {commit}")
            if commit.group_data.group == CommitGroup.SECONDARY_CUSTOM:
                changelog_manager.add_change(
                    changelog_id=commit.group_data.changelog_id,
                    section_id=commit.group_data.changelog_section_id,
                    change_title=commit.msg.title,
                    change_details=commit.msg.body,
                )
        changelog_manager.write_all_changelogs()
        commit_hash = self.commit(
            message="Update changelogs",
            push=True,
            set_upstream=True,
        )
        self._metadata_branch = meta.read_from_json_file(
            path_root="repo_self", logger=self._logger
        )
        # Wait 30 s to make sure the push is registered
        time.sleep(30)
        bare_title = self._payload.title.removeprefix(f'{primary_commit_type.conv_type}: ')
        commit_title = f"{primary_commit_type.conv_type}: {bare_title}"
        try:
            response = self._gh_api.pull_merge(
                number=self._payload.number,
                commit_title=commit_title,
                commit_message=self._payload.body,
                sha=commit_hash,
                merge_method="squash",
            )
        except WebAPIError as e:
            self._gh_api.pull_update(
                number=self._payload.number,
                title=commit_title,
            )
            self._logger.error("Failed to merge pull request using GitHub API. Please merge manually.", e, raise_error=False)
            self._failed = True
            return
        if not next_ver:
            self._set_job_run(
                package_build=True,
                package_lint=True,
                package_test_local=True,
                website_deploy=True,
                github_release=True,
            )
            return
        self._hash_latest = response["sha"]
        self._git_base.checkout(branch=self._branch_base.name)
        for i in range(10):
            self._git_base.pull()
            if self._git_base.commit_hash_normal() == self._hash_latest:
                break
            time.sleep(5)
        else:
            self._logger.error("Failed to pull changes from GitHub. Please pull manually.")
            self._failed = True
            return
        self._tag_version(ver=next_ver)
        self._set_job_run(
            package_lint=True,
            package_test_local=True,
            website_deploy=True,
            package_publish_testpypi=True,
            package_publish_pypi=True,
            github_release=True,
        )
        self._set_release(
            name=f"{self._metadata_main['name']} v{next_ver}",
            body=changelog_manager.get_entry(changelog_id="package_public")[0],
        )
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
        base_ver, dist = self._get_latest_version()
        self.git.checkout(branch=self.pull_head_ref_name)

        self.action_file_change_detector()
        self.action_meta()
        self._action_hooks()

        branch = self.resolve_branch(self.pull_head_ref_name)
        issue_labels = [label["name"] for label in self.gh_api.issue_labels(number=branch.suffix)]
        issue_data = self._metadata_main.get_issue_data_from_labels(issue_labels)

        if issue_data.group_data.group == CommitGroup.PRIMARY_CUSTOM or issue_data.group_data.action in [
            PrimaryActionCommitType.WEBSITE,
            PrimaryActionCommitType.META,
        ]:
            ver_dist = f"{base_ver}+{dist+1}"
        else:
            ver_dist = str(self._get_next_version(base_ver, issue_data.group_data.action))

        changelog_manager = ChangelogManager(
            changelog_metadata=self.metadata_main["changelog"],
            ver_dist=ver_dist,
            commit_type=issue_data.group_data.conv_type,
            commit_title=self.pull_title,
            parent_commit_hash=latest_base_hash,
            parent_commit_url=self._gh_link.commit(latest_base_hash),
            logger=self.logger,
        )

        commits = self._get_commits()
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


