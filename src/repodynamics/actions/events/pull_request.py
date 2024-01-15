import time
import re

from pylinks.exceptions import WebAPIError
from github_contexts import GitHubContext
from github_contexts.github.payloads.pull_request import PullRequestPayload
from github_contexts.github.enums import ActionType

from repodynamics import meta
from repodynamics.meta.meta import Meta
from repodynamics.meta import read_from_json_file
from repodynamics.actions.events._base import EventHandler
from repodynamics.path import RelativePath
from repodynamics.version import PEP440SemVer
from repodynamics.datatype import (
    EventType,
    PrimaryActionCommit,
    PrimaryCustomCommit,
    PrimaryActionCommitType,
    CommitGroup,
    BranchType,
    IssueStatus,
    TemplateType,
    RepoFileType,
    InitCheckAction,
    LabelType,
)
from repodynamics.commit import CommitParser
from repodynamics.logger import Logger
from repodynamics.meta.manager import MetaManager
from repodynamics.actions._changelog import ChangelogManager


class PullRequestEventHandler(EventHandler):

    def __init__(
        self,
        template_type: TemplateType,
        context_manager: GitHubContext,
        admin_token: str,
        path_root_base: str,
        path_root_head: str | None = None,
        logger: Logger | None = None,
    ):
        super().__init__(
            template_type=template_type,
            context_manager=context_manager,
            admin_token=admin_token,
            path_root_base=path_root_base,
            path_root_head=path_root_head,
            logger=logger
        )
        self._payload: PullRequestPayload = self._context.event
        self._pull = self._payload.pull_request
        self._branch_base = self.resolve_branch(self._context.base_ref)
        self._branch_head = self.resolve_branch(self._context.head_ref)
        self._git_base.fetch_remote_branches_by_name(branch_names=self._context.base_ref)
        self._git_base.checkout(branch=self._context.base_ref)
        # self._git_head.fetch_remote_branches_by_name(branch_names=self._context.head_ref)
        return

    def run_event(self):
        name = "Event Handler"
        error_title = "Unsupported pull request."
        if self._payload.internal:
            if self._branch_head.type is BranchType.AUTOUPDATE:
                if self._branch_base.type not in (BranchType.MAIN, BranchType.RELEASE, BranchType.PRERELEASE):
                    error_msg = (
                        "Pull requests from an auto-update (head) branch "
                        "are only supported to a main, release, or pre-release (base) branch, "
                        f"but the base branch has type '{self._branch_base.type.value}'."
                    )
                    self._logger.error(error_title, error_msg, raise_error=False)
                    self.add_summary(name=name, status="fail", oneliner=error_title, details=error_msg)
                    return
            elif self._branch_head.type is BranchType.DEV:
                if self._branch_base.type is not BranchType.IMPLEMENT:
                    error_msg = (
                        "Pull requests from a development (head) branch "
                        "are only supported to an implementation (base) branch, "
                        f"but the base branch has type '{self._branch_base.type.value}'."
                    )
                    self._logger.error(error_title, error_msg, raise_error=False)
                    self.add_summary(name=name, status="fail", oneliner=error_title, details=error_msg)
                    return
            elif self._branch_head.type is BranchType.IMPLEMENT:
                if self._branch_base.type not in (BranchType.MAIN, BranchType.RELEASE, BranchType.PRERELEASE):
                    error_msg = (
                        "Pull requests from an implementation (head) branch "
                        "are only supported to a main, release, or pre-release (base) branch, "
                        f"but the base branch has type '{self._branch_base.type.value}'."
                    )
                    self._logger.error(error_title, error_msg, raise_error=False)
                    self.add_summary(name=name, status="fail", oneliner=error_title, details=error_msg)
                    return
            elif self._branch_head.type is BranchType.PRERELEASE:
                if self._branch_base.type not in (BranchType.RELEASE, BranchType.MAIN):
                    error_msg = (
                        "Pull requests from a pre-release (head) branch "
                        "are only supported to a release or main (base) branch, "
                        f"but the base branch has type '{self._branch_base.type.value}'."
                    )
                    self._logger.error(error_title, error_msg, raise_error=False)
                    self.add_summary(name=name, status="fail", oneliner=error_title, details=error_msg)
                    return
            else:
                error_msg = (
                    "Pull requests from a head branch of type "
                    f"'{self._branch_head.type.value}' are not supported."
                )
                self._logger.error(error_title, error_msg, raise_error=False)
                self.add_summary(name=name, status="fail", oneliner=error_title, details=error_msg)
                return
        else:
            if self._branch_base.type is not BranchType.IMPLEMENT or self._branch_head.type is not BranchType.IMPLEMENT:
                error_msg = (
                    "Pull requests from a forked repository are only supported "
                    "from an implementation (head) branch to an implementation (base) branch."
                )
                self._logger.error(error_title, error_msg, raise_error=False)
                self.add_summary(name=name, status="fail", oneliner=error_title, details=error_msg)
                return

        action = self._payload.action
        if action is ActionType.OPENED:
            self._run_action_opened()
        elif action is ActionType.REOPENED:
            self._run_action_reopened()
        elif action is ActionType.SYNCHRONIZE:
            self._run_action_synchronize()
        elif action is ActionType.LABELED:
            self._run_action_labeled()
        elif action is ActionType.READY_FOR_REVIEW:
            self._run_action_ready_for_review()
        else:
            self.error_unsupported_triggering_action()
        return

    def _run_action_labeled(self):
        label = self._ccm_main.resolve_label(self._payload.label.name)
        if label.category is LabelType.STATUS:
            self._run_action_labeled_status(status=label.type)
        else:
            pass
        return

    def _run_action_labeled_status(self, status: IssueStatus):
        if status in (IssueStatus.DEPLOY_ALPHA, IssueStatus.DEPLOY_BETA, IssueStatus.DEPLOY_RC):
            self._run_labeled_status_pre(status=status)
        elif status is IssueStatus.DEPLOY_FINAL:
            self._run_action_labeled_status_final()
        else:
            self._logger.error(
                "Unsupported status label for pull request",
                f"Label '{self._payload.label.name}' is not supported for pull requests.",
            )
        return

    def _run_action_labeled_status_final(self):
        if self._branch_head.type is BranchType.AUTOUPDATE:
            if not self._payload.internal:
                self._logger.error(
                    "Merge not allowed",
                    "Merge from a forked repository is only allowed "
                    "from an implementation branch to the corresponding implementation branch.",
                )
                return
            if self._branch_base.type not in (
                BranchType.MAIN, BranchType.RELEASE, BranchType.PRERELEASE):
                self._logger.error(
                    "Merge not allowed",
                    f"Merge from a head branch of type '{self._branch_head.type.value}' "
                    f"to a branch of type '{self._branch_base.type.value}' is not allowed.",
                )
                return
            return self._run_merge_autoupdate()
        elif self._branch_head.type is BranchType.DEV:
            if not self._payload.internal:
                self._logger.error(
                    "Merge not allowed",
                    "Merge from a forked repository is only allowed "
                    "from an implementation branch to the corresponding implementation branch.",
                )
                return
            if self._branch_base.type is not BranchType.IMPLEMENT:
                self._logger.error(
                    "Merge not allowed",
                    f"Merge from a head branch of type '{self._branch_head.type.value}' "
                    f"to a branch of type '{self._branch_base.type.value}' is not allowed.",
                )
                return
            return self._run_merge_dev_to_implement()
        elif self._branch_head.type is BranchType.IMPLEMENT:
            if self._payload.internal:
                if self._branch_base.type in (BranchType.RELEASE, BranchType.MAIN):
                    return self._run_merge_implementation_to_release()
                elif self._branch_base.type is BranchType.PRERELEASE:
                    return self._run_merge_implementation_to_pre()
                else:
                    self._logger.error(
                        "Merge not allowed",
                        f"Merge from a head branch of type '{self._branch_head.type.value}' "
                        f"to a branch of type '{self._branch_base.type.value}' is not allowed.",
                    )
            else:
                if self._branch_base.type is BranchType.IMPLEMENT:
                    return self._run_merge_fork_to_implement()
                else:
                    self._logger.error(
                        "Merge not allowed",
                        f"Merge from a head branch of type '{self._branch_head.type.value}' "
                        f"to a branch of type '{self._branch_base.type.value}' is not allowed.",
                    )
        elif self._branch_head.type is BranchType.PRERELEASE:
            if self._branch_base.type in (BranchType.RELEASE, BranchType.MAIN):
                return self._run_merge_pre_to_release()
            else:
                self._logger.error(
                    "Merge not allowed",
                    f"Merge from a head branch of type '{self._branch_head.type.value}' "
                    f"to a branch of type '{self._branch_base.type.value}' is not allowed.",
                )
        else:
            self._logger.error(
                "Merge not allowed",
                f"Merge from a head branch of type '{self._branch_head.type.value}' "
                f"to a branch of type '{self._branch_base.type.value}' is not allowed.",
            )

    def _run_action_opened(self):
        # if self.event_name == "pull_request" and action != "fail" and not self.pull_is_internal:
        #     self._logger.attention(
        #         "Meta synchronization cannot be performed as pull request is from a forked repository; "
        #         f"switching action from '{action}' to 'fail'."
        #     )
        #     action = "fail"
        return

    def _run_action_reopened(self):
        return

    def _run_action_synchronize(self):
        meta_and_hooks_action_type = InitCheckAction.COMMIT if self._payload.internal else InitCheckAction.FAIL
        meta = Meta(
            path_root=self._path_root_head,
            github_token=self._context.token,
            hash_before=self._context.hash_before,
            logger=self._logger,
        )
        changed_file_groups = self._action_file_change_detector(meta=meta)
        hash_hooks = self._action_hooks(
            action=meta_and_hooks_action_type,
            branch=self._branch_head,
            base=False,
            ref_range=(self._context.hash_before, self._context.hash_after),
        )
        for file_type in (RepoFileType.SUPERMETA, RepoFileType.META, RepoFileType.DYNAMIC):
            if changed_file_groups[file_type]:
                hash_meta = self._action_meta(
                    action=meta_and_hooks_action_type, meta=meta, base=False, branch=self._branch_head
                )
                ccm_branch = meta.read_metadata_full()
                break
        else:
            hash_meta = None
            ccm_branch = read_from_json_file(
                path_root=self._path_root_base, git=self._git_head, logger=self._logger
            )
        latest_hash = self._git_head.push() if hash_hooks or hash_meta else self._context.hash_after

        tasks_complete = self._update_implementation_tasklist()
        if tasks_complete and not self._failed:
            self._gh_api.pull_update(
                number=self._payload.number,
                draft=False,
            )
        final_commit_type = self._ccm_main.get_issue_data_from_labels(self._pull.label_names).group_data
        job_runs = self._determine_job_runs(
            changed_file_groups=changed_file_groups, final_commit_type=final_commit_type
        )
        if job_runs["package_publish_testpypi"]:
            next_ver = self._calculate_next_dev_version(final_commit_type=final_commit_type)
            job_runs["version"] = str(next_ver)
            self._tag_version(
                ver=next_ver,
                base=False,
                msg=f"Developmental release (issue: #{self._branch_head.suffix[0]}, target: {self._branch_base.name})",
            )
        self._set_output(
            ccm_branch=ccm_branch,
            ref=latest_hash,
            ref_before=self._context.hash_before,
            **job_runs,
        )
        return

    def _run_labeled_status_pre(self, status: IssueStatus):
        if self._branch_head.type is not BranchType.IMPLEMENT or self._branch_base.type not in (
            BranchType.RELEASE, BranchType.MAIN
        ):
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
        primary_commit_type = self._ccm_main.get_issue_data_from_labels(self._pull.label_names).group_data
        if primary_commit_type.group != CommitGroup.PRIMARY_ACTION or primary_commit_type.action not in (
            PrimaryActionCommitType.RELEASE_MAJOR,
            PrimaryActionCommitType.RELEASE_MINOR,
            PrimaryActionCommitType.RELEASE_PATCH,
        ):
            self._logger.error(
                "Merge not allowed",
                "Merge from a development branch to a release branch is only allowed "
                "for release commits.",
            )
            return
        self._git_base.checkout(branch=self._branch_base.name)
        hash_base = self._git_base.commit_hash_normal()
        ver_base, dist_base = self._get_latest_version()
        next_ver_final = self._get_next_version(ver_base, primary_commit_type.action)
        pre_segment = {
            IssueStatus.DEPLOY_ALPHA: "a",
            IssueStatus.DEPLOY_BETA: "b",
            IssueStatus.DEPLOY_RC: "rc",
        }[status]
        next_ver_pre = PEP440SemVer(f"{next_ver_final}.{pre_segment}{self._branch_head.suffix[0]}")
        pre_release_branch_name = self.create_branch_name_prerelease(version=next_ver_pre)
        self._git_base.checkout(branch=pre_release_branch_name, create=True)
        self._git_base.commit(
            message=(
                f"init: Create pre-release branch '{pre_release_branch_name}' "
                f"from base branch '{self._branch_base.name}'."
            ),
            allow_empty=True,
        )
        self._git_base.push(target="origin", set_upstream=True)
        return

    def _run_merge_implementation_to_release(self):
        ver_base, dist_base = self._get_latest_version(base=False)
        primary_commit_type = self._ccm_main.get_issue_data_from_labels(self._pull.label_names).group_data
        if self._primary_type_is_package_publish(commit_type=primary_commit_type):
            next_ver = self._get_next_version(ver_base, primary_commit_type.action)
            ver_dist = str(next_ver)
        else:
            ver_dist = f"{ver_base}+{dist_base + 1}"
            next_ver = None

        parser = CommitParser(types=self._ccm_main.get_all_conventional_commit_types(), logger=self._logger)
        hash_base = self._git_base.commit_hash_normal()
        changelog_manager = ChangelogManager(
            changelog_metadata=self._ccm_main["changelog"],
            ver_dist=ver_dist,
            commit_type=primary_commit_type.conv_type,
            commit_title=self._pull.title,
            parent_commit_hash=hash_base,
            parent_commit_url=self._gh_link.commit(hash_base),
            path_root=self._path_root_head,
            logger=self._logger,
        )
        tasklist = self._extract_tasklist(body=self._pull.body)
        for task in tasklist:
            conv_msg = parser.parse(msg=task["summary"])
            if conv_msg:
                group_data = self._ccm_main.get_commit_type_from_conventional_type(conv_type=conv_msg.type)
                changelog_manager.add_change(
                    changelog_id=group_data.changelog_id,
                    section_id=group_data.changelog_section_id,
                    change_title=conv_msg.title,
                    change_details=task["description"],
                )
        changelog_manager.write_all_changelogs()
        self._git_head.commit(
            message="auto: Update changelogs",
            stage="all"
        )
        latest_hash = self._git_head.push()
        # Wait 30 s to make sure the push is registered
        time.sleep(30)
        bare_title = self._pull.title.removeprefix(f'{primary_commit_type.conv_type}: ')
        commit_title = f"{primary_commit_type.conv_type}: {bare_title}"
        try:
            response = self._gh_api_admin.pull_merge(
                number=self._payload.number,
                commit_title=commit_title,
                commit_message=self._pull.body,
                sha=latest_hash,
                merge_method="squash",
            )
        except WebAPIError as e:
            self._gh_api.pull_update(
                number=self._payload.number,
                title=commit_title,
            )
            self._logger.error(
                "Failed to merge pull request using GitHub API. Please merge manually.", e, raise_error=False
            )
            self._failed = True
            return
        ccm_branch = meta.read_from_json_file(
            path_root=self._path_root_head, logger=self._logger
        )
        hash_latest = response["sha"]
        if not next_ver:
            self._set_output(
                ccm_branch=ccm_branch,
                ref=hash_latest,
                ref_before=hash_base,
                website_deploy=True,
                package_lint=True,
                package_test=True,
                package_build=True,
            )
            return
        for i in range(10):
            self._git_base.pull()
            if self._git_base.commit_hash_normal() == hash_latest:
                break
            time.sleep(5)
        else:
            self._logger.error("Failed to pull changes from GitHub. Please pull manually.")
            self._failed = True
            return
        tag = self._tag_version(ver=next_ver, base=True)
        self._set_output(
            ccm_branch=ccm_branch,
            ref=hash_latest,
            ref_before=hash_base,
            version=str(next_ver),
            release_name=f"{ccm_branch['name']} v{next_ver}",
            release_tag=tag,
            release_body=changelog_manager.get_entry(changelog_id="package_public")[0],
            website_deploy=True,
            package_lint=True,
            package_test=True,
            package_publish_testpypi=True,
            package_publish_pypi=True,
            package_release=True,
        )
        return

    def _run_merge_dev_to_implement(self):
        tasklist_head = self._extract_tasklist(body=self._pull.body)
        if not tasklist_head or len(tasklist_head) != 1:
            self._logger.error(
                "Failed to find tasklist",
                "Failed to find tasklist in pull request body.",
            )
            self._failed = True
            return
        task = tasklist_head[0]

        matching_pulls = self._gh_api.pull_list(
            state="open",
            head=f"{self._context.repository_owner}:{self._context.base_ref}",
        )
        if not matching_pulls or len(matching_pulls) != 1:
            self._logger.error(
                "Failed to find matching pull request",
                "Failed to find matching pull request for the development branch.",
            )
            self._failed = True
            return
        parent_pr = self._gh_api.pull(number=matching_pulls[0]["number"])

        tasklist_base = self._extract_tasklist(body=parent_pr["body"])
        task_nr = self._branch_head.suffix[2]
        tasklist_base[task_nr - 1] = task
        self._update_tasklist(entries=tasklist_base, body=parent_pr["body"], number=parent_pr["number"])
        response = self._gh_api.pull_merge(
            number=self._payload.number,
            commit_title=task["summary"],
            commit_message=self._pull.body,
            sha=self._pull.head.sha,
            merge_method="squash",
        )
        return

    def _determine_job_runs(self, changed_file_groups, final_commit_type):
        package_setup_files_changed = any(
            filepath in changed_file_groups[RepoFileType.DYNAMIC]
            for filepath in (
                RelativePath.file_python_pyproject,
                RelativePath.file_python_manifest,
            )
        )
        out = {
            "website_build": (
                bool(changed_file_groups[RepoFileType.WEBSITE])
                or bool(changed_file_groups[RepoFileType.PACKAGE])
            ),
            "package_test": (
                bool(changed_file_groups[RepoFileType.TEST])
                or bool(changed_file_groups[RepoFileType.PACKAGE])
                or package_setup_files_changed
            ),
            "package_build": bool(changed_file_groups[RepoFileType.PACKAGE]) or package_setup_files_changed,
            "package_lint": bool(changed_file_groups[RepoFileType.PACKAGE]) or package_setup_files_changed,
            "package_publish_testpypi": (
                self._branch_head.type is BranchType.IMPLEMENT
                and self._payload.internal
                and (bool(changed_file_groups[RepoFileType.PACKAGE]) or package_setup_files_changed)
                and self._primary_type_is_package_publish(commit_type=final_commit_type)
            ),
        }
        return out

    def _calculate_next_dev_version(self, final_commit_type):
        ver_last_base, _ = self._get_latest_version(dev_only=False, base=True)
        ver_last_head, _ = self._get_latest_version(dev_only=True, base=False)
        if ver_last_base.pre:
            # The base branch is a pre-release branch
            next_ver = ver_last_base.next_post
            if not ver_last_head or (
                ver_last_head.release != next_ver.release or ver_last_head.pre != next_ver.pre
            ):
                dev = 0
            else:
                dev = (ver_last_head.dev or -1) + 1
            next_ver_str = f"{next_ver}.dev{dev}"
        else:
            next_ver = self._get_next_version(ver_last_base, final_commit_type.action)
            next_ver_str = str(next_ver)
            if final_commit_type.action != PrimaryActionCommitType.RELEASE_POST:
                next_ver_str += f".a{self._branch_head.suffix[0]}"
            if not ver_last_head:
                dev = 0
            elif final_commit_type.action == PrimaryActionCommitType.RELEASE_POST:
                if ver_last_head.post is not None and ver_last_head.post == next_ver.post:
                    dev = ver_last_head.dev + 1
                else:
                    dev = 0
            elif ver_last_head.pre is not None and ver_last_head.pre == ("a", self._branch_head.suffix[0]):
                dev = ver_last_head.dev + 1
            else:
                dev = 0
            next_ver_str += f".dev{dev}"
        return PEP440SemVer(next_ver_str)

    @staticmethod
    def _primary_type_is_package_publish(commit_type: PrimaryActionCommit | PrimaryCustomCommit):
        return commit_type.group is CommitGroup.PRIMARY_ACTION and commit_type.action in (
            PrimaryActionCommitType.RELEASE_MAJOR,
            PrimaryActionCommitType.RELEASE_MINOR,
            PrimaryActionCommitType.RELEASE_PATCH,
            PrimaryActionCommitType.RELEASE_POST,
        )

    # def event_pull_request(self):
    #     self.event_type = EventType.PULL_MAIN
    #     branch = self.resolve_branch(self.pull_head_ref_name)
    #     if branch.type == BranchType.DEV and branch.suffix == 0:
    #         return
    #     for job_id in ("package_build", "package_test_local", "package_lint", "website_build"):
    #         self.set_job_run(job_id)
    #     self.git.checkout(branch=self.pull_base_ref_name)
    #     latest_base_hash = self.git.commit_hash_normal()
    #     base_ver, dist = self._get_latest_version()
    #     self.git.checkout(branch=self.pull_head_ref_name)
    #
    #     self.action_file_change_detector()
    #     self.action_meta()
    #     self._action_hooks()
    #
    #     branch = self.resolve_branch(self.pull_head_ref_name)
    #     issue_labels = [label["name"] for label in self.gh_api.issue_labels(number=branch.suffix)]
    #     issue_data = self._ccm_main.get_issue_data_from_labels(issue_labels)
    #
    #     if issue_data.group_data.group == CommitGroup.PRIMARY_CUSTOM or issue_data.group_data.action in [
    #         PrimaryActionCommitType.WEBSITE,
    #         PrimaryActionCommitType.META,
    #     ]:
    #         ver_dist = f"{base_ver}+{dist+1}"
    #     else:
    #         ver_dist = str(self._get_next_version(base_ver, issue_data.group_data.action))
    #
    #     changelog_manager = ChangelogManager(
    #         changelog_metadata=self.metadata_main["changelog"],
    #         ver_dist=ver_dist,
    #         commit_type=issue_data.group_data.conv_type,
    #         commit_title=self.pull_title,
    #         parent_commit_hash=latest_base_hash,
    #         parent_commit_url=self._gh_link.commit(latest_base_hash),
    #         path_root=self._path_root_base,
    #         logger=self.logger,
    #     )
    #
    #     commits = self._get_commits()
    #     self.logger.success(f"Found {len(commits)} commits.")
    #     for commit in commits:
    #         self.logger.info(f"Processing commit: {commit}")
    #         if commit.group_data.group == CommitGroup.SECONDARY_CUSTOM:
    #             changelog_manager.add_change(
    #                 changelog_id=commit.group_data.changelog_id,
    #                 section_id=commit.group_data.changelog_section_id,
    #                 change_title=commit.msg.title,
    #                 change_details=commit.msg.body,
    #             )
    #     entries = changelog_manager.get_all_entries()
    #     self.logger.success(f"Found {len(entries)} changelog entries.", str(entries))
    #     curr_body = self.pull_body.strip() if self.pull_body else ""
    #     if curr_body:
    #         curr_body += "\n\n"
    #     for entry, changelog_name in entries:
    #         curr_body += f"# Changelog: {changelog_name}\n\n{entry}\n\n"
    #     self.gh_api.pull_update(
    #         number=self.pull_number,
    #         title=f"{issue_data.group_data.conv_type}: {self.pull_title.removeprefix(f'{issue_data.group_data.conv_type}: ')}",
    #         body=curr_body,
    #     )
    #     return

    def _update_implementation_tasklist(self) -> bool:

        def apply(commit_details, tasklist_entries):
            for entry in tasklist_entries:
                if entry['complete'] or entry['summary'].casefold() != commit_details[0].casefold():
                    continue
                if (
                    not entry['sublist']
                    or len(commit_details) == 1
                    or commit_details[1].casefold() not in [subentry['summary'].casefold() for subentry in entry['sublist']]
                ):
                    entry['complete'] = True
                    return
                apply(commit_details[1:], entry['sublist'])
            return

        def update_complete(tasklist_entries):
            for entry in tasklist_entries:
                if entry['sublist']:
                    entry['complete'] = update_complete(entry['sublist'])
            return all([entry['complete'] for entry in tasklist_entries])

        commits = self._get_commits()
        tasklist = self._extract_tasklist(body=self._pull.body)
        if not tasklist:
            return False
        for commit in commits:
            commit_details = (
                commit.msg.splitlines() if commit.group_data.group == CommitGroup.NON_CONV
                else [commit.msg.summary, *commit.msg.body.splitlines()]
            )
            apply(commit_details, tasklist)
        complete = update_complete(tasklist)
        self._update_tasklist(tasklist)
        return complete

    def _update_tasklist(
        self,
        entries: list[dict[str, bool | str | list]],
        body: str | None = None,
        number: int | None = None,
    ) -> None:
        """
        Update the implementation tasklist in the pull request body.

        Parameters
        ----------
        entries : list[dict[str, bool | str | list]]
            A list of dictionaries, each representing a tasklist entry.
            The format of each dictionary is the same as that returned by
            `_extract_tasklist_entries`.
        """
        tasklist_string = self._write_tasklist(entries)
        pattern = rf"({self._MARKER_TASKLIST_START}).*?({self._MARKER_TASKLIST_END})"
        replacement = rf"\1\n{tasklist_string}\n\2"
        new_body = re.sub(pattern, replacement, body or self._pull.body, flags=re.DOTALL)
        self._gh_api.pull_update(
            number=number or self._payload.number,
            body=new_body,
        )
        return
