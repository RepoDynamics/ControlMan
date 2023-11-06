from pathlib import Path
import json
from typing import Literal, NamedTuple
import re
import datetime
from enum import Enum
import shutil

from markitup import html, md
import pylinks
from ruamel.yaml import YAML

from repodynamics import meta
from repodynamics.logger import Logger
from repodynamics.git import Git
from repodynamics.meta.meta import Meta
from repodynamics import hook, _util
from repodynamics.commit import CommitParser
from repodynamics.version import PEP440SemVer
from repodynamics.actions._changelog import ChangelogManager
from repodynamics.meta.files.forms import FormGenerator
from repodynamics.actions.context import ContextManager
from repodynamics.datatype import (
    Branch,
    BranchType,
    DynamicFileType,
    EventType,
    CommitGroup,
    Commit,
    CommitMsg,
    RepoFileType,
    PrimaryActionCommitType,
    SecondaryActionCommitType,
    PrimaryActionCommit,
    PrimaryCustomCommit,
    SecondaryActionCommit,
    SecondaryCustomCommit,
    WorkflowTriggeringAction,
    NonConventionalCommit,
    FileChangeType,
    Emoji,
    IssueStatus,
)


class Init:
    SUPPORTED_EVENTS_NON_MODIFYING = [
        "issue_comment",
        "issues",
        "pull_request_review",
        "pull_request_review_comment",
        "pull_request_target",
        "schedule",
        "workflow_dispatch",
    ]
    SUPPORTED_EVENTS_MODIFYING = ["pull_request", "push"]

    def __init__(
        self,
        context: dict,
        admin_token: str = "",
        package_build: bool = False,
        package_lint: bool = False,
        package_test: bool = False,
        website_build: bool = False,
        meta_sync: Literal["report", "amend", "commit", "pull", "none"] = "none",
        hooks: Literal["report", "amend", "commit", "pull", "none"] = "none",
        website_announcement: str = "",
        website_announcement_msg: str = "",
        logger: Logger | None = None,
    ):
        self.context = ContextManager(github_context=context)

        # Inputs when event is triggered by a workflow dispatch
        self._meta_sync = meta_sync
        self._hooks = hooks
        self._website_announcement = website_announcement
        self._website_announcement_msg = website_announcement_msg

        self.logger = logger or Logger("github")
        self.git: Git = Git(
            path_repo="repo_self",
            user=(self.context.triggering_actor_username, self.context.triggering_actor_email),
            logger=self.logger,
        )
        self.gh_api = pylinks.api.github(
            token=self.context.github_token
        ).user(self.context.repo_owner).repo(self.context.repo_name)
        self.gh_api_admin = pylinks.api.github(
            token=admin_token
        ).user(self.context.repo_owner).repo(self.context.repo_name)
        self.gh_link = pylinks.site.github.user(self.context.repo_owner).repo(self.context.repo_name)

        self.meta_main = Meta(
            path_root="repo_self",
            github_token=self.context.github_token,
            hash_before=self.context.hash_before,
            logger=self.logger
        )

        self.metadata_main = meta.read_from_json_file(path_root="repo_self", logger=self.logger)
        self.metadata_branch: dict = {}
        self.metadata_branch_before: dict = {}

        self.last_ver_main, self.dist_ver_main = self.get_latest_version()

        self.changed_files: dict[RepoFileType, list[str]] = {}
        self._amended: bool = False
        self._tag: str = ""
        self._version: str = ""
        self._fail: bool = False
        self._internal_config = {"finit": False, "repository": "", "ref": ""}
        self._run_job = {
            "package_build": package_build,
            "package_test_local": package_test,
            "package_lint": package_lint,
            "website_build": website_build,
            "website_deploy": False,
            "website_rtd_preview": False,
            "package_publish_testpypi": False,
            "package_publish_pypi": False,
            "package_test_testpypi": False,
            "package_test_pypi": False,
            "github_release": False,
        }
        self._release_info = {
            "name": "",
            "body": "",
            "prerelease": False,
            "make_latest": "legacy",
        }
        self.summary_oneliners: list[str] = []
        self.summary_sections: list[str | html.ElementCollection | html.Element] = []
        self.meta_results = []
        self.meta_changes = {}
        self.event_type: EventType | None = None
        self._hash_latest: str | None = None
        return

    def run(self):
        self.logger.h2("Analyze Triggering Event")
        event_name = self.context.event_name
        action = self.context.triggering_action
        action_err_msg = f"Unsupported triggering action for '{event_name}' event."
        action_err_details_sub = f"but the triggering action '{self.context.payload.get('action')}' is not supported."
        action_err_details = f"The workflow was triggered by an '{event_name}' event, {action_err_details_sub}"

        if event_name == "issue_comment":
            is_pull = self.context.issue_payload.get("pull_request")
            state = (is_pull, action)
            if state == (True, WorkflowTriggeringAction.CREATED):
                self.event_comment_pull_created()
            elif state == (True, WorkflowTriggeringAction.EDITED):
                self.event_comment_pull_edited()
            elif state == (True, WorkflowTriggeringAction.DELETED):
                self.event_comment_pull_deleted()
            elif state == (False, WorkflowTriggeringAction.CREATED):
                self.event_comment_issue_created()
            elif state == (False, WorkflowTriggeringAction.EDITED):
                self.event_comment_issue_edited()
            elif state == (False, WorkflowTriggeringAction.DELETED):
                self.event_comment_issue_deleted()
            else:
                action_err_details = "The workflow was triggered by a comment on " + (
                    "a pull request ('issue_comment' event with 'pull_request' payload)"
                    if is_pull else "an issue ('issue_comment' event without 'pull_request' payload)"
                ) + f", {action_err_details_sub}"
                self.logger.error(action_err_msg, action_err_details)
        elif event_name == "issues":
            if action == WorkflowTriggeringAction.OPENED:
                self.event_issue_opened()
            elif action == WorkflowTriggeringAction.LABELED:
                self.event_issue_labeled()
            else:
                self.logger.error(action_err_msg, action_err_details)
        elif event_name == "pull_request_target":
            if action == WorkflowTriggeringAction.OPENED:
                self.event_pull_target_opened()
            elif action == WorkflowTriggeringAction.REOPENED:
                self.event_pull_target_reopened()
            elif action == WorkflowTriggeringAction.SYNCHRONIZE:
                self.event_pull_target_synchronize()
            else:
                self.logger.error(action_err_msg, action_err_details)
        elif event_name == "schedule":
            cron = self.context.payload["schedule"]
            if cron == self.metadata_main.workflow__init__schedule__sync:
                self.event_schedule_sync()
            elif cron == self.metadata_main.workflow__init__schedule__test:
                self.event_schedule_test()
            else:
                self.logger.error(
                    f"Unknown cron expression for scheduled workflow: {cron}",
                    f"Valid cron expressions defined in 'workflow.init.schedule' metadata are:\n"
                    f"{self.metadata_main.workflow__init__schedule}",
                )
        elif event_name == "workflow_dispatch":
            self.event_workflow_dispatch()
        elif event_name == "pull_request":
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
        elif event_name == "push":
            if self.context.payload["created"]:
                triggering_action = "created"
            elif self.context.payload["deleted"]:
                triggering_action = "deleted"
            else:
                triggering_action = "modified"
            state = (self.context.ref_type, triggering_action)
            if state == ("tag", "created"):
                self.event_push_tag_created()
            elif state == ("tag", "deleted"):
                self.event_push_tag_deleted()
            elif state == ("tag", "modified"):
                self.event_push_tag_modified()
            elif state == ("branch", "created"):
                self.event_push_branch_created()
            elif state == ("branch", "deleted"):
                self.event_push_branch_deleted()
            elif state == ("branch", "modified"):
                branch = self.resolve_branch()
                if branch.type == BranchType.DEFAULT:
                    self.event_push_branch_modified_default()
                elif branch.type == BranchType.RELEASE:
                    self.event_push_branch_modified_release()
                elif branch.type == BranchType.DEV:
                    self.event_push_branch_modified_dev()
                elif branch.type == BranchType.CI_PULL:
                    self.event_push_branch_modified_ci_pull()
                else:
                    self.event_push_branch_modified_other()
            else:
                self.logger.error(
                    f"Unknown ref type '{self.context.ref_type}' and triggering action '{triggering_action}'",
                    "Valid ref types are 'tag' and 'branch'. "
                    "Valid triggering actions are 'created', 'deleted', and 'modified'.",
                )
        else:
            self.logger.error(f"Event '{self.context.event_name}' is not supported.")
        return self.finalize()

    def finalize(self):
        self.logger.h1("Finalization")
        if self.fail:
            # Just to be safe, disable publish/deploy/release jobs if fail is True
            for job_id in (
                "website_deploy",
                "package_publish_testpypi",
                "package_publish_pypi",
                "github_release",
            ):
                self.set_job_run(job_id, False)
        summary, path_logs = self.assemble_summary()
        output = self.output
        output["path_log"] = path_logs
        return output, None, summary

    def event_push_branch_created(self):
        branch = self.resolve_branch()
        if branch.type == BranchType.DEFAULT:
            if not self.last_ver_main:
                self.event_push_repository_created()
            else:
                self.logger.skip(
                    "Creation of default branch detected while a version tag is present; skipping.",
                    "This is likely a result of a repository transfer, or renaming of the default branch.",
                )
        else:
            self.logger.skip(
                "Creation of non-default branch detected; skipping.",
            )
        return

    def event_push_repository_created(self):
        self.logger.info("Detected event: repository creation")
        shutil.rmtree(self.meta_main.input_path.dir_source)
        shutil.rmtree(self.meta_main.input_path.dir_tests)
        shutil.rmtree(self.meta_main.input_path.dir_local)
        for item in self.meta_main.input_path.dir_meta.iterdir():
            if item.is_dir():
                if item.name not in ("__examples__", "__new__"):
                    shutil.rmtree(item)
            else:
                item.unlink()
        path_meta_new = self.meta_main.input_path.dir_meta / "__new__"
        for item in path_meta_new.iterdir():
            item.rename(self.meta_main.input_path.dir_meta / item.name)
        path_meta_new.rmdir()
        (self.meta_main.input_path.dir_github / ".repodynamics_meta_path.txt").unlink(missing_ok=True)
        for path_dynamic_file in self.meta_main.output_path.all_files:
            path_dynamic_file.unlink(missing_ok=True)
        for changelog_data in self.metadata_main.dict.get("changelog", {}).values():
            path_changelog_file = self.meta_main.input_path.root / changelog_data["path"]
            path_changelog_file.unlink(missing_ok=True)
        with open(self.meta_main.input_path.dir_website / "announcement.html", "w") as f:
            f.write("")
        self.commit(
            message="init: Create repository from RepoDynamics PyPackIT template", amend=True, push=True
        )
        self.add_summary(
            name="Init",
            status="pass",
            oneliner="Repository created from RepoDynamics PyPackIT template.",
        )
        return

    def check_for_version_tags(self):
        tags_lists = self.git.get_tags()
        if not tags_lists:
            return False, False
        ver_tag_prefix = self.metadata_main["tag"]["group"]["version"]["prefix"]
        for tags_list in tags_lists:
            ver_tags = []
            for tag in tags_list:
                if tag.startswith(ver_tag_prefix):
                    ver_tags.append(tag.removeprefix(ver_tag_prefix))
            if ver_tags:
                max_version = max(PEP440SemVer(ver_tag) for ver_tag in ver_tags)
                distance = self.git.get_distance(ref_start=f"refs/tags/{ver_tag_prefix}{max_version.input}")
                return max_version, distance
        return

    def event_push_branch_modified_default(self):
        self.metadata_branch = self.meta_main.read_metadata_full()

        self.metadata_branch_before = meta.read_from_json_string(
            content=self.git.file_at_hash(
                commit_hash=self.context.hash_before,
                path=self.meta_main.output_path.metadata.rel_path
            ),
            logger=self.logger
        )
        if not self.last_ver_main:
            self.event_first_release()
        else:
            self.event_push_branch_modified_main()

    def event_push_branch_modified_main(self):
        self.event_type = EventType.PUSH_MAIN
        self.metadata_branch_before = self.git.file_at_hash(
            commit_hash=self.hash_before, path=self.meta_main.output_path.metadata.rel_path
        )
        self.action_repo_labels_sync()

        self.action_file_change_detector()
        for job_id in ("package_build", "package_test_local", "package_lint", "website_build"):
            self.set_job_run(job_id)

        self.action_meta()
        self.action_hooks()
        self.last_ver_main, self.dist_ver_main = self.get_latest_version()
        commits = self.get_commits()
        if len(commits) != 1:
            self.logger.error(
                f"Push event on main branch should only contain a single commit, but found {len(commits)}.",
                raise_error=False,
            )
            self.fail = True
            return
        commit = commits[0]
        if commit.group_data.group not in [CommitGroup.PRIMARY_ACTION, CommitGroup.PRIMARY_CUSTOM]:
            self.logger.error(
                f"Push event on main branch should only contain a single conventional commit, but found {commit}.",
                raise_error=False,
            )
            self.fail = True
            return
        if self.fail:
            return

        if commit.group_data.group == CommitGroup.PRIMARY_CUSTOM or commit.group_data.action in [
            PrimaryActionCommitType.WEBSITE,
            PrimaryActionCommitType.META,
        ]:
            ver_dist = f"{self.last_ver_main}+{self.dist_ver_main + 1}"
            next_ver = None
        else:
            next_ver = self.get_next_version(self.last_ver_main, commit.group_data.action)
            ver_dist = str(next_ver)

        changelog_manager = ChangelogManager(
            changelog_metadata=self.metadata_main["changelog"],
            ver_dist=ver_dist,
            commit_type=commit.group_data.conv_type,
            commit_title=commit.msg.title,
            parent_commit_hash=self.hash_before,
            parent_commit_url=self.gh_link.commit(self.hash_before),
        )
        changelog_manager.add_from_commit_body(commit.msg.body)
        changelog_manager.write_all_changelogs()
        self.commit(amend=True, push=True)

        if next_ver:
            self.tag_version(ver=next_ver)
            for job_id in ("package_publish_testpypi", "package_publish_pypi", "github_release"):
                self.set_job_run(job_id)
            self._release_info["body"] = changelog_manager.get_entry("package_public")[0]
            self._release_info["name"] = f"{self.metadata_main['name']} {next_ver}"

        if commit.group_data.group == CommitGroup.PRIMARY_ACTION:
            self.set_job_run("website_deploy")
        return

    def event_push_branch_modified_release(self):
        self.event_type = EventType.PUSH_RELEASE
        return

    def event_push_branch_modified_dev(self):
        self.event_type = EventType.PUSH_DEV
        self.action_meta()
        self.action_hooks()
        return

    def event_push_branch_modified_other(self):
        self.event_type = EventType.PUSH_OTHER
        self.action_meta()
        self.action_hooks()
        return

    def event_push_branch_deleted(self):
        return

    def event_comment_pull_created(self):
        return

    def event_comment_pull_edited(self):
        return

    def event_comment_pull_deleted(self):
        return

    def event_comment_issue_created(self):
        return

    def event_comment_issue_edited(self):
        return

    def event_comment_issue_deleted(self):
        return

    def event_issue_opened(self):
        return

    def event_issue_labeled(self):
        label = self.payload["label"]["name"]
        if label.startswith(self.metadata_main["label"]["group"]["status"]["prefix"]):
            status = self.meta_main.manager.get_issue_status_from_status_label(label)
            if status == IssueStatus.IN_DEV:
                target_label_prefix = self.metadata_main["label"]["auto_group"]["target"]["prefix"]
                dev_branch_prefix = self.metadata_main["branch"]["group"]["dev"]["prefix"]
                branches = self.gh_api.branches
                branch_sha = {branch["name"]: branch["commit"]["sha"] for branch in branches}
                for issue_label in self.issue_labels:
                    if issue_label["name"].startswith(target_label_prefix):
                        base_branch_name = issue_label["name"].removeprefix(target_label_prefix)
                        if base_branch_name.startswith(dev_branch_prefix):
                            pass
                        else:
                            new_branch = self.gh_api.branch_create_linked(
                                issue_id=self.issue_payload["node_id"],
                                base_sha=branch_sha[base_branch_name],
                                name=f"{dev_branch_prefix}{self.issue_number}/{base_branch_name}",
                            )
                            pull_data = self.gh_api.pull_create(
                                head=new_branch["name"],
                                base=base_branch_name,
                                title=self.issue_title,
                                body=f"This is a draft pull request for the issue #{self.issue_number}.",
                                maintainer_can_modify=True,
                                draft=True
                            )
                            self.gh_api.issue_labels_set(
                                number=pull_data["number"],
                                labels=[label["name"] for label in self.issue_labels]
                            )
        return

    def event_pull_opened(self):
        return

    def event_pull_reopened(self):
        return

    def event_pull_synchronize(self):
        return

    def event_pull_labeled(self):
        return

    def event_pull_target_opened(self):
        return

    def event_pull_target_reopened(self):
        return

    def event_pull_target_synchronize(self):
        return

    def event_push_tag_created(self):
        return

    def event_push_tag_deleted(self):
        return

    def event_push_tag_modified(self):
        return

    def event_workflow_dispatch(self):
        self.event_type = EventType.DISPATCH
        self.action_website_announcement_update()
        self.action_meta()
        self.action_hooks()
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
        self.action_hooks()

        branch = self.resolve_branch(self.pull_head_ref_name)
        issue_labels = [label["name"] for label in self.gh_api.issue_labels(number=branch.suffix)]
        issue_data = self.meta_main.manager.get_issue_data_from_labels(issue_labels)

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
            parent_commit_url=self.gh_link.commit(latest_base_hash),
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

    def event_pull_request_target(self):
        self.set_job_run("website_rtd_preview")
        return

    def event_schedule_sync(self):
        self.event_type = EventType.SCHEDULE
        self.action_website_announcement_check()
        self.action_meta()
        return

    def event_schedule_test(self):
        self.event_type = EventType.SCHEDULE
        return

    def event_issues_opened(self):
        self.gh_api.issue_comment_create(number=self.issue_number, body="This post tracks the issue.")
        self.action_post_process_issue()

        return



    def event_first_release(self):

        tag_prefix = self.metadata_main["tag"]["group"]["version"]["prefix"]
        self._version = "0.0.0"
        self._tag = f"{tag_prefix}{self._version}"
        commit_msg = CommitMsg(
            typ="init",
            title="Initialize package and website",
            body="This is an initial release of the website, and the yet empty package on PyPI and TestPyPI.",
        )
        self.commit(
            message=str(commit_msg),
            amend=True,
            push=True,
        )
        self.git.create_tag(tag=self._tag, message="First release")
        self.gh_api_admin.activate_pages("workflow")
        self.action_repo_settings_sync()
        self.action_repo_labels_sync(init=True)
        for job_id in [
            "package_build",
            "package_test_local",
            "package_lint",
            "website_build",
            "website_deploy",
            "package_publish_testpypi",
            "package_publish_pypi",
            "package_test_testpypi",
            "package_test_pypi",
        ]:
            self.set_job_run(job_id)
        return

    def get_commits(self) -> list[Commit]:
        # primary_action = {}
        # primary_action_types = []
        # for primary_action_id, primary_action_commit in self.metadata["commit"]["primary_action"].items():
        #     conv_commit_type = primary_action_commit["type"]
        #     primary_action_types.append(conv_commit_type)
        #     primary_action[conv_commit_type] = PrimaryActionCommitType[primary_action_id.upper()]
        # secondary_action = {}
        # secondary_action_types = []
        # for secondary_action_id, secondary_action_commit in self.metadata["commit"]["secondary_action"].items():
        #     conv_commit_type = secondary_action_commit["type"]
        #     secondary_action_types.append(conv_commit_type)
        #     secondary_action[conv_commit_type] = SecondaryActionCommitType[secondary_action_id.upper()]
        # primary_custom_types = []
        # for primary_custom_commit in self.metadata["commit"]["primary_custom"].values():
        #     conv_commit_type = primary_custom_commit["type"]
        #     primary_custom_types.append(conv_commit_type)
        # all_conv_commit_types = (
        #     primary_action_types
        #     + secondary_action_types
        #     + primary_custom_types
        #     + list(self.metadata["commit"]["secondary_custom"].keys())
        # )
        commits = self.git.get_commits(f"{self.hash_before}..{self.hash_after}")
        self.logger.success("Read commits from git history", json.dumps(commits, indent=4))
        parser = CommitParser(types=self.meta_main.manager.get_all_conventional_commit_types(), logger=self.logger)
        parsed_commits = []
        for commit in commits:
            conv_msg = parser.parse(msg=commit["msg"])
            if not conv_msg:
                parsed_commits.append(Commit(**commit, group_data=NonConventionalCommit()))
            else:
                group = self.meta_main.manager.get_commit_type_from_conventional_type(conv_type=conv_msg.type)
                commit["msg"] = conv_msg
                parsed_commits.append(Commit(**commit, group_data=group))
            # elif conv_msg.type in primary_action_types:
            #     parsed_commits.append(
            #         Commit(**commit, typ=CommitGroup.PRIMARY_ACTION, action=primary_action[conv_msg.type])
            #     )
            # elif conv_msg.type in secondary_action_types:
            #     parsed_commits.append(
            #         Commit(**commit, typ=CommitGroup.SECONDARY_ACTION, action=secondary_action[conv_msg.type])
            #     )
            # elif conv_msg.type in primary_custom_types:
            #     parsed_commits.append(Commit(**commit, typ=CommitGroup.PRIMARY_CUSTOM))
            # else:
            #     parsed_commits.append(Commit(**commit, typ=CommitGroup.SECONDARY_CUSTOM))
        return parsed_commits

    def get_latest_version(self) -> tuple[PEP440SemVer | None, int | None]:
        tags_lists = self.git.get_tags()
        if not tags_lists:
            return None, None
        ver_tag_prefix = self.metadata_main["tag"]["group"]["version"]["prefix"]
        for tags_list in tags_lists:
            ver_tags = []
            for tag in tags_list:
                if tag.startswith(ver_tag_prefix):
                    ver_tags.append(tag.removeprefix(ver_tag_prefix))
            if ver_tags:
                max_version = max(PEP440SemVer(ver_tag) for ver_tag in ver_tags)
                distance = self.git.get_distance(ref_start=f"refs/tags/{ver_tag_prefix}{max_version.input}")
                return max_version, distance
        self.logger.error(f"No version tags found with prefix '{ver_tag_prefix}'.")

    def categorize_labels(self, label_names: list[str]):
        label_dict = {
            label_data["name"]: label_key
            for label_key, label_data in self.metadata_main["label"]["compiled"].items()
        }
        out = {}
        for label in label_names:
            out[label] = label_dict[label]
        return out

    def resolve_branch(self, branch_name: str | None = None) -> Branch:
        if not branch_name:
            branch_name = self.context.ref_name
        if branch_name == self.context.default_branch:
            return Branch(type=BranchType.DEFAULT)
        return self.metadata_main.get_branch_info_from_name(branch_name=branch_name)

    def switch_to_ci_branch(self, typ: Literal["hooks", "meta"]):
        current_branch = self.git.current_branch_name()
        new_branch_prefix = self.metadata_main["branch"]["group"]["ci_pull"]["prefix"]
        new_branch_name = f"{new_branch_prefix}{current_branch}/{typ}"
        self.git.checkout(branch=new_branch_name, reset=True)
        self.logger.success(f"Switch to CI branch '{new_branch_name}' and reset it to '{current_branch}'.")
        return new_branch_name

    def switch_to_original_branch(self):
        self.git.checkout(branch=self.ref_name)
        return

    def assemble_summary(self) -> tuple[str, str]:
        github_context, event_payload = (
            html.details(
                content=md.code_block(
                    YAML(typ=["rt", "string"]).dumps(dict(sorted(data.items())), add_final_eol=True), "yaml"
                ),
                summary=summary,
            )
            for data, summary in ((self.context, "🎬 GitHub Context"), (self.payload, "📥 Event Payload"))
        )
        intro = [f"{Emoji.PLAY} The workflow was triggered by a <code>{self.event_name}</code> event."]
        if self.fail:
            intro.append(f"{Emoji.FAIL} The workflow failed.")
        else:
            intro.append(f"{Emoji.PASS} The workflow passed.")
        intro = html.ul(intro)
        summary = html.ElementCollection(
            [
                html.h(1, "Workflow Report"),
                intro,
                html.ul([github_context, event_payload]),
                html.h(2, "🏁 Summary"),
                html.ul(self.summary_oneliners),
            ]
        )
        logs = html.ElementCollection(
            [
                html.h(2, "🪵 Logs"),
                html.details(self.logger.file_log, "Log"),
            ]
        )
        summaries = html.ElementCollection(self.summary_sections)
        path_logs = self.meta_main.input_path.dir_local_report_repodynamics
        path_logs.mkdir(parents=True, exist_ok=True)
        with open(path_logs / "log.html", "w") as f:
            f.write(str(logs))
        with open(path_logs / "report.html", "w") as f:
            f.write(str(summaries))
        return str(summary), str(path_logs)

    def add_summary(
        self,
        name: str,
        status: Literal["pass", "fail", "skip", "warning"],
        oneliner: str,
        details: str | html.Element | html.ElementCollection | None = None,
    ):
        self.summary_oneliners.append(f"{Emoji[status]}&nbsp;<b>{name}</b>: {oneliner}")
        if details:
            self.summary_sections.append(f"<h2>{name}</h2>\n\n{details}\n\n")
        return

    def commit(
        self,
        message: str = "",
        stage: Literal["all", "staged", "unstaged"] = "all",
        amend: bool = False,
        push: bool = False,
        set_upstream: bool = False,
    ):
        commit_hash = self.git.commit(message=message, stage=stage, amend=amend)
        if amend:
            self._amended = True
        if push:
            commit_hash = self.push(set_upstream=set_upstream)
        return commit_hash

    def tag_version(self, ver: str | PEP440SemVer, msg: str = ""):
        tag_prefix = self.metadata_main["tag"]["group"]["version"]["prefix"]
        tag = f"{tag_prefix}{ver}"
        if not msg:
            msg = f"Release version {ver}"
        self.git.create_tag(tag=tag, message=msg)
        self._tag = tag
        return

    def push(self, amend: bool = False, set_upstream: bool = False):
        new_hash = self.git.push(
            target="origin", set_upstream=set_upstream, force_with_lease=self._amended or amend
        )
        self._amended = False
        if new_hash and self.git.current_branch_name() == self.ref_name:
            self._hash_latest = new_hash
        return new_hash

    @staticmethod
    def get_next_version(version: PEP440SemVer, action: PrimaryActionCommitType):
        if action == PrimaryActionCommitType.PACKAGE_MAJOR:
            return version.next_major
        if action == PrimaryActionCommitType.PACKAGE_MINOR:
            return version.next_minor
        if action == PrimaryActionCommitType.PACKAGE_PATCH:
            return version.next_patch
        if action == PrimaryActionCommitType.PACKAGE_POST:
            return version.next_post
        return version

    @property
    def output(self):
        package_name = self.metadata_main.get("package", {}).get("name", "")
        out = {
            "internal": self._internal_config,
            "config": {
                "fail": self.fail,
                "checkout": {
                    "ref": self.hash_latest,
                    "ref_before": self.hash_before,
                    "repository": self.target_repo_fullname,
                },
                "run": self._run_job,
                "package": {
                    "version": self._version,
                    "upload_url_testpypi": "https://test.pypi.org/legacy/",
                    "upload_url_pypi": "https://upload.pypi.org/legacy/",
                    "download_url_testpypi": f"https://test.pypi.org/project/{package_name}/{self._version}",
                    "download_url_pypi": f"https://pypi.org/project/{package_name}/{self._version}",
                },
                "release": {
                    "tag_name": self._tag,
                    "discussion_category_name": "",
                }
                | self._release_info,
            },
            "metadata_ci": self._generate_metadata_ci(),
        }
        for job_id, dependent_job_id in (
            ("package_publish_testpypi", "package_test_testpypi"),
            ("package_publish_pypi", "package_test_pypi"),
        ):
            if self._run_job[job_id]:
                out["config"]["run"][dependent_job_id] = True
        return out

    def _generate_metadata_ci(self) -> dict:
        out = {}
        metadata = self.metadata_main
        out["path"] = metadata["path"]
        out["web"] = {
            "readthedocs": {"name": metadata["web"].get("readthedocs", {}).get("name")},
        }
        out["url"] = {"website": {"base": metadata["url"]["website"]["base"]}}
        if metadata.get("package"):
            pkg = metadata["package"]
            out["package"] = {
                "name": pkg["name"],
                "github_runners": pkg["github_runners"],
                "python_versions": pkg["python_versions"],
                "python_version_max": pkg["python_version_max"],
                "pure_python": pkg["pure_python"],
                "cibw_matrix_platform": pkg.get("cibw_matrix_platform", []),
                "cibw_matrix_python": pkg.get("cibw_matrix_python", []),
            }
        return out

    @property
    def fail(self):
        return self._fail

    @fail.setter
    def fail(self, value: bool):
        self._fail = value
        return

    def set_job_run(self, job_id: str, run: bool = True):
        if job_id not in self._run_job:
            self.logger.error(f"Invalid job ID: {job_id}")
        self._run_job[job_id] = run
        return

    @property
    def hash_latest(self) -> str:
        """The SHA hash of the most recent commit on the branch,
        including commits made during the workflow run.
        """
        if self._hash_latest:
            return self._hash_latest
        return self.hash_after


def init(
    context: dict,
    admin_token: str = "",
    package_build: bool = False,
    package_lint: bool = False,
    package_test: bool = False,
    website_build: bool = False,
    meta_sync: str = "none",
    hooks: str = "none",
    website_announcement: str = "",
    website_announcement_msg: str = "",
    logger=None,
):
    for arg_name, arg in (("meta_sync", meta_sync), ("hooks", hooks)):
        if arg not in ["report", "amend", "commit", "pull", "none", ""]:
            raise ValueError(
                f"Invalid input argument for '{arg_name}': "
                f"Expected one of 'report', 'amend', 'commit', 'pull', or 'none', but got '{arg}'."
            )

    return Init(
        context=context,
        admin_token=admin_token,
        package_build=package_build,
        package_lint=package_lint,
        package_test=package_test,
        website_build=website_build,
        meta_sync=meta_sync or "none",
        hooks=hooks or "none",
        website_announcement=website_announcement,
        website_announcement_msg=website_announcement_msg,
        logger=logger,
    ).run()
