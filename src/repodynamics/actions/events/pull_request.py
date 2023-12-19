import time
import re

from pylinks.http import WebAPIError

from repodynamics import meta
from repodynamics.meta import read_from_json_file
from repodynamics.actions.events._base import ModifyingEventHandler
from repodynamics.actions.context_manager import ContextManager, PullRequestPayload
from repodynamics.datatype import (
    WorkflowTriggeringAction,
    EventType,
    PrimaryActionCommitType,
    CommitGroup,
    BranchType,
    IssueStatus,
    TemplateType,
    RepoFileType,
)
from repodynamics.logger import Logger
from repodynamics.meta.manager import MetaManager
from repodynamics.actions._changelog import ChangelogManager
from repodynamics.actions import _helpers


class PullRequestEventHandler(ModifyingEventHandler):

    def __init__(
        self,
        template_type: TemplateType,
        context_manager: ContextManager,
        admin_token: str,
        path_root_self: str,
        path_root_fork: str | None = None,
        logger: Logger | None = None,
    ):
        super().__init__(
            template_type=template_type,
            context_manager=context_manager,
            admin_token=admin_token,
            path_root_self=path_root_self,
            path_root_fork=path_root_fork,
            logger=logger
        )
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
        changed_file_groups = self._action_file_change_detector()
        for file_type in (RepoFileType.SUPERMETA, RepoFileType.META, RepoFileType.DYNAMIC):
            if changed_file_groups[file_type]:
                self._action_meta()
                break
        else:
            self._metadata_branch = read_from_json_file(path_root=self._path_root_self, logger=self._logger)
        self._action_hooks()
        tasks_complete = self._update_implementation_tasklist()





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
        if status in (IssueStatus.DEPLOY_ALPHA, IssueStatus.DEPLOY_BETA, IssueStatus.DEPLOY_RC):
            self._run_labeled_status_pre()
        elif status == IssueStatus.DEPLOY_FINAL:
            self._run_labeled_status_final()
        return

    def _run_labeled_status_pre(self):
        if self._branch_head.type != BranchType.DEV or self._branch_base.type not in (BranchType.RELEASE, BranchType.MAIN):
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
            if self._branch_base.type in (BranchType.RELEASE, BranchType.MAIN):
                return self._run_merge_dev_to_release()
            elif self._branch_base.type == BranchType.PRERELEASE:
                return self._run_merge_dev_to_pre()
        elif self._branch_head.type == BranchType.PRERELEASE:
            if self._branch_base.type in (BranchType.RELEASE, BranchType.MAIN):
                return self._run_merge_pre_to_release()
        elif self._branch_head.type == BranchType.AUTOUPDATE:
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
            path_root=self._path_root_self,
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
            path_root=self._path_root_self, logger=self._logger
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
                # github_release=True,
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
            path_root=self._path_root_self,
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

    def _update_implementation_tasklist(self):

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
        tasklist = self._extract_tasklist_entries()
        for commit in commits:
            commit_details = (
                commit.msg.splitlines() if commit.group_data.group == CommitGroup.NON_CONV
                else [commit.msg.summary, *commit.msg.body.splitlines()]
            )
            apply(commit_details, tasklist)
        complete = update_complete(tasklist)
        self._write_tasklist(tasklist)
        return complete

    def _extract_tasklist_entries(self) -> list[dict[str, bool | str | list]]:
        """
        Extract the implementation tasklist from the pull request body.
        
        Returns
        -------
        A list of dictionaries, each representing a tasklist entry.
        Each dictionary has the following keys:
        - complete : bool
            Whether the task is complete.
        - summary : str
            The summary of the task.
        - description : str
            The description of the task.
        - sublist : list[dict[str, bool | str | list]]
            A list of dictionaries, each representing a subtask entry, if any.
            Each dictionary has the same keys as the parent dictionary.
        """

        def extract(tasklist_string: str, level: int = 0):
            # Regular expression pattern to match each task item
            pattern = rf'{" " * level * 2}- \[(X| )\] (.+?)(?=\n{" " * level * 2}- \[|\Z)'
            # Find all matches
            matches = re.findall(pattern, tasklist_string, flags=re.DOTALL)
            # Process each match into the required dictionary format
            tasklist_entries = []
            for match in matches:
                complete, summary_and_desc = match
                summary_and_desc_split = summary_and_desc.split('\n', 1)
                summary = summary_and_desc_split[0]
                description = summary_and_desc_split[1] if len(summary_and_desc_split) > 1 else ''
                if description:
                    sublist_pattern = r'^( *- \[(?:X| )\])'
                    parts = re.split(sublist_pattern, description, maxsplit=1, flags=re.MULTILINE)
                    description = parts[0]
                    if len(parts) > 1:
                        sublist_str = ''.join(parts[1:])
                        sublist = extract(sublist_str, level + 1)
                    else:
                        sublist = []
                else:
                    sublist = []
                tasklist_entries.append({
                    'complete': complete == 'X',
                    'summary': summary.strip(),
                    'description': description.rstrip(),
                    'sublist': sublist
                })
            return tasklist_entries

        pattern = rf"{self._MARKER_TASKLIST_START}(.*?){self._MARKER_TASKLIST_END}"
        match = re.search(pattern, self._payload.body, flags=re.DOTALL)
        return extract(match.group(1).strip() if match else "")

    def _write_tasklist(self, tasklist_entries: list[dict[str, bool | str | list]]) -> None:
        """
        Update the implementation tasklist in the pull request body.

        Parameters
        ----------
        tasklist_entries : list[dict[str, bool | str | list]]
            A list of dictionaries, each representing a tasklist entry.
            The format of each dictionary is the same as that returned by
            `_extract_tasklist_entries`.
        """
        string = []

        def write(entries, level=0):
            for entry in entries:
                description = f"{entry['description']}\n" if entry['description'] else ''
                check = 'X' if entry['complete'] else ' '
                string.append(f"{' ' * level * 2}- [{check}] {entry['summary']}\n{description}")
                write(entry['sublist'], level + 1)

        write(tasklist_entries)
        tasklist_string = "".join(string).rstrip()
        pattern = rf"({self._MARKER_TASKLIST_START}).*?({self._MARKER_TASKLIST_END})"
        replacement = rf"\1\n{tasklist_string}\n\2"
        new_body = re.sub(pattern, replacement, self._payload.body, flags=re.DOTALL)
        self._gh_api.pull_update(
            number=self._payload.number,
            body=new_body,
        )
        return

