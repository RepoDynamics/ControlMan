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

from repodynamics.logger import Logger
from repodynamics.git import Git
from repodynamics.meta.meta import Meta, FileCategory
from repodynamics import hooks, _util
from repodynamics.commits import CommitParser
from repodynamics.versioning import PEP440SemVer
from repodynamics.actions._changelog import ChangelogManager
from repodynamics.datatypes import (
    EventType,
    CommitGroup,
    Commit,
    CommitMsg,
    RepoFileType,
    PrimaryCommitAction,
    SecondaryCommitAction,
    FileChangeType,
    Emoji
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
        meta_sync: Literal['report', 'amend', 'commit', 'pull', 'none'] = 'none',
        hooks: Literal['report', 'amend', 'commit', 'pull', 'none'] = 'none',
        website_announcement: str = "",
        website_announcement_msg: str = "",
        logger: Logger | None = None
    ):
        self._github_token = context.pop("token")
        self._payload = context.pop("event")
        self._context = context
        self._admin_token = admin_token

        # Inputs when event is triggered by a workflow dispatch
        self._package_build = package_build
        self._package_lint = package_lint
        self._package_test = package_test
        self._website_build = website_build
        self._meta_sync = meta_sync
        self._hooks = hooks
        self._website_announcement = website_announcement
        self._website_announcement_msg = website_announcement_msg

        self.logger = logger or Logger("github")
        self.git: Git = Git(logger=self.logger)
        self.api = pylinks.api.github(token=self._github_token).user(self.repo_owner).repo(self.repo_name)
        self.api_admin = pylinks.api.github(token=self._admin_token).user(self.repo_owner).repo(self.repo_name)
        self.gh_link = pylinks.site.github.user(self.repo_owner).repo(self.repo_name)
        self.meta = Meta(path_root=".", github_token=self._github_token, logger=self.logger)

        self.metadata: dict = {}
        self.metadata_ci: dict = {}
        self.last_ver: PEP440SemVer | None = None
        self.dist_ver: int = 0
        self.changed_files: dict[RepoFileType, list[str]] = {}

        self.summary_oneliners: list[str] = []
        self.summary_sections: list[str | html.ElementCollection | html.Element] = []

        self.meta_results = []
        self.meta_changes = {}
        self.event_type: EventType | None = None
        self._hash_latest: str | None = None

        self.output = {
            "config": {
                "fail": False,
                "checkout": {
                    "ref": "",
                    "ref_before": "",
                    "repository": "",
                },
                "run": {
                    "package_build": False,
                    "package_test_local": False,
                    "package_lint": False,
                    "website_build": False,
                    "website_deploy": False,
                    "website_rtd_preview": False,
                    "package_publish_testpypi": False,
                    "package_publish_pypi": False,
                    "package_test_testpypi": False,
                    "package_test_pypi": False,
                    "github_release": False,
                },
                "package": {
                    "version": "",
                    "upload_url_testpypi": "https://test.pypi.org/legacy/",
                    "upload_url_pypi": "https://upload.pypi.org/legacy/",
                    "download_url_testpypi": "",
                    "download_url_pypi": "",
                },
                "release": {
                    "tag_name": "",
                    "name": "",
                    "body": "",
                    "prerelease": False,
                    "discussion_category_name": "",
                    "make_latest": "legacy",
                }
            },
            "metadata_ci": self.metadata_ci,
        }
        return

    def run(self):
        if self.event_name in self.SUPPORTED_EVENTS_NON_MODIFYING:
            self.metadata, self.metadata_ci = self.meta.read_metadata_output()
            self.last_ver, self.dist_ver = self.get_latest_version()
        elif self.event_name not in self.SUPPORTED_EVENTS_MODIFYING:
            self.logger.error(f"Event '{self.event_name}' is not supported.")

        event_handler = {
            "issue_comment": self.event_issue_comment,
            "issues": self.event_issues,
            "pull_request_review": self.event_pull_request_review,
            "pull_request_review_comment": self.event_pull_request_review_comment,
            "pull_request_target": self.event_pull_request_target,
            "schedule": self.event_schedule,
            "workflow_dispatch": self.event_workflow_dispatch,
            "pull_request": self.event_pull_request,
            "push": self.event_push,
        }
        event_handler[self.event_name]()

        if self.fail:
            # Just to be safe, disable publish/deploy/release jobs if fail is True
            for job_id in (
                "website_deploy", "package_publish_testpypi", "package_publish_pypi", "github_release"
            ):
                self.output["config"]["run"][job_id] = False
        summary = self.assemble_summary()
        self.logger.h1("Finalization")
        return self.output, None, summary

    def event_push(self):

        def ref_type() -> Literal["tag", "branch"]:
            if self.ref.startswith("refs/tags/"):
                return "tag"
            if self.ref.startswith("refs/heads/"):
                return "branch"
            self.logger.error(f"Invalid ref: {self.context['ref']}")

        def change_type() -> Literal["created", "deleted", "modified"]:
            if self.payload["created"]:
                return "created"
            if self.payload["deleted"]:
                return "deleted"
            return "modified"

        event_handler = {
            ("tag", "created"): self.event_push_tag_created,
            ("tag", "deleted"): self.event_push_tag_deleted,
            ("tag", "modified"): self.event_push_tag_modified,
            ("branch", "created"): self.event_push_branch_created,
            ("branch", "deleted"): self.event_push_branch_deleted,
            ("branch", "modified"): self.event_push_branch_modified,
        }
        event_handler[(ref_type(), change_type())]()
        return

    def event_push_branch_modified(self):
        self.action_file_change_detector()
        if self.ref_is_main:
            if not self.git.get_tags():
                self.event_first_release()
            else:
                self.event_push_branch_modified_main()
        else:
            metadata = self.meta.read_metadata_raw()
            branch_group = metadata["branch"]["group"]
            if self.ref_name.startswith(branch_group["release"]["prefix"]):
                self.event_push_branch_modified_release()
            elif self.ref_name.startswith(branch_group["dev"]["prefix"]):
                self.event_push_branch_modified_dev()
            else:
                self.event_push_branch_modified_other()
        return

    def event_push_branch_modified_main(self):
        self.event_type = EventType.PUSH_MAIN
        self.action_meta()
        self.action_hooks()
        self.last_ver, self.dist_ver = self.get_latest_version()
        commits = self.get_commits()
        # commit: Commit
        # if commit.action == PrimaryCommitAction.PACKAGE_MAJOR:
        #     self.event_push_branch_modified_main_package_major(commit)

        return

    def event_push_branch_created(self):
        if self.ref_is_main:
            if not self.git.get_tags():
                self.event_repository_created()
            else:
                self.logger.skip(
                    "Creation of default branch detected while a version tag is present; skipping.",
                    "This is likely a result of a repository transfer, or renaming of the default branch."
                )
        else:
            self.logger.skip(
                "Creation of non-default branch detected; skipping.",
            )
        return

    def event_push_branch_modified_release(self):
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

    def event_push_tag_created(self):
        return

    def event_push_tag_deleted(self):
        return

    def event_push_tag_modified(self):
        return

    def event_pull_request(self):
        return

    def event_pull_request_target(self):
        self.enable_job_run("website_rtd_preview")
        return

    def event_schedule(self):
        cron = self.payload["schedule"]
        schedule_type = self.metadata["workflow"]["init"]["schedule"]
        if cron == schedule_type["sync"]:
            return self.event_schedule_sync()
        if cron == schedule_type["test"]:
            return self.event_schedule_test()
        self.logger.error(
            f"Unknown cron expression for scheduled workflow: {cron}",
            f"Valid cron expressions defined in 'workflow.init.schedule' metadata are:\n"
            f"{schedule_type}"
        )
        return

    def event_schedule_sync(self):
        self.action_website_announcement_check()
        self.action_meta()
        return

    def event_schedule_test(self):
        return

    def event_workflow_dispatch(self):
        self.action_website_announcement_update()
        return

    def event_issue_comment(self):
        return

    def event_issues(self):
        return

    def event_pull_request_review(self):
        return

    def event_pull_request_review_comment(self):
        return

    def event_repository_created(self):
        shutil.rmtree(self.meta.output_paths.input_paths["dir"]["source"])
        shutil.rmtree(self.meta.output_paths.input_paths["dir"]["tests"])
        for path_dynamic_file in self.meta.output_paths.all_files:
            path_dynamic_file.unlink(missing_ok=True)
        for changelog_data in self.metadata["changelog"].values():
            path_changelog_file = Path(changelog_data["path"])
            path_changelog_file.unlink(missing_ok=True)
        self.git.commit(message="init: Create repository from RepoDynamics PyPackIT template", amend=True)
        self.add_summary(
            name="Init",
            status="pass",
            oneliner="Repository created from RepoDynamics PyPackIT template.",
        )
        return

    def event_first_release(self):
        self.api_admin.activate_pages("workflow")
        self.action_repo_settings_sync()
        self.action_repo_labels_sync(init=True)
        tag_prefix = self.metadata["tag"]["group"]["version"]["prefix"]
        version = "0.0.0"
        tag = f"{tag_prefix}{version}"
        commit_msg = CommitMsg(
            typ="init",
            title="Initialize package and website",
            body="This is an initial release of the website, and the yet empty package on PyPI and TestPyPI."
        )
        self._hash_latest = self.git.commit(
            message=str(commit_msg),
            amend=True
        )
        self.git.create_tag(tag=tag, message="First release")
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
            self.enable_job_run(job_id)
        self.output["config"]["package"]["version"] = version
        package_name = self.metadata["package"]["name"]
        self.output["config"]["package"]["download_url_testpypi"] = f"https://test.pypi.org/project/{package_name}/{version}"
        self.output["config"]["package"]["download_url_pypi"] = f"https://pypi.org/project/{package_name}/{version}"
        self.output["config"]["ref"] = self.hash_latest
        return

    def action_file_change_detector(self) -> list[str]:
        name = "File Change Detector"
        self.logger.h1(name)
        change_type_map = {
            "added": FileChangeType.CREATED,
            "deleted": FileChangeType.REMOVED,
            "modified": FileChangeType.MODIFIED,
            "unmerged": FileChangeType.UNMERGED,
            "unknown": FileChangeType.UNKNOWN,
            "broken": FileChangeType.BROKEN,
            "copied_to": FileChangeType.CREATED,
            "renamed_from": FileChangeType.REMOVED,
            "renamed_to": FileChangeType.CREATED,
            "copied_modified_to": FileChangeType.CREATED,
            "renamed_modified_from": FileChangeType.REMOVED,
            "renamed_modified_to": FileChangeType.CREATED,
        }
        summary_detail = {file_type: [] for file_type in RepoFileType}
        change_group = {file_type: [] for file_type in RepoFileType}
        changes = self.git.changed_files(ref_start=self.hash_before, ref_end=self.hash_after)
        self.logger.success("Detected changed files", json.dumps(changes, indent=3))
        input_path = self.meta.output_paths.input_paths
        fixed_paths = [outfile.rel_path for outfile in self.meta.output_paths.fixed_files]
        for change_type, changed_paths in changes.items():
            # if change_type in ["unknown", "broken"]:
            #     self.logger.warning(
            #         f"Found {change_type} files",
            #         f"Running 'git diff' revealed {change_type} changes at: {changed_paths}. "
            #         "These files will be ignored."
            #     )
            #     continue
            if change_type.startswith("copied") and change_type.endswith("from"):
                continue
            for path in changed_paths:
                if path.endswith("/README.md") or path == ".github/_README.md":
                    typ = RepoFileType.README
                elif path.startswith(f'{input_path["dir"]["source"]}/'):
                    typ = RepoFileType.PACKAGE
                elif path in fixed_paths:
                    typ = RepoFileType.DYNAMIC
                elif path.startswith(f'{input_path["dir"]["website"]}/'):
                    typ = RepoFileType.WEBSITE
                elif path.startswith(f'{input_path["dir"]["tests"]}/'):
                    typ = RepoFileType.TEST
                elif path.startswith(".github/workflows/"):
                    typ = RepoFileType.WORKFLOW
                elif (
                    path.startswith(".github/DISCUSSION_TEMPLATE/")
                    or path.startswith(".github/ISSUE_TEMPLATE/")
                    or path.startswith(".github/PULL_REQUEST_TEMPLATE/")
                    or path.startswith(".github/workflow_requirements")
                ):
                    typ = RepoFileType.DYNAMIC
                elif path.startswith(f'{input_path["dir"]["meta"]}/'):
                    typ = RepoFileType.META
                elif path == ".path.json":
                    typ = RepoFileType.SUPERMETA
                else:
                    typ = RepoFileType.OTHER
                summary_detail[typ].append(f"{change_type_map[change_type].value.emoji} {path}")
                change_group[typ].append(path)

        self.changed_files = change_group
        summary_details = []
        changed_groups_str = ""
        for file_type, summaries in summary_detail.items():
            if summaries:
                summary_details.append(html.h(3, file_type.value.title))
                summary_details.append(html.ul(summaries))
                changed_groups_str += f", {file_type.value.title}"
        if changed_groups_str:
            oneliner = f"Found changes in following groups: {changed_groups_str[2:]}."
            if summary_detail[RepoFileType.SUPERMETA]:
                oneliner = (
                    f"This event modified SuperMeta files; "
                    f"make sure to double-check that everything is correct❗ {oneliner}"
                )
        else:
            oneliner = "No changes were found."
        legend = [f"{status.value.emoji}  {status.value.title}" for status in FileChangeType]
        color_legend = html.details(content=html.ul(legend), summary="Color Legend")
        summary_details.insert(0, html.ul([oneliner, color_legend]))
        self.add_summary(
            name=name,
            status="warning" if summary_detail[RepoFileType.SUPERMETA] else (
                "pass" if changed_groups_str else "skip"
            ),
            oneliner=oneliner,
            details=html.ElementCollection(summary_details)
        )
        return

    def action_meta(self):
        name = "Meta Sync"
        self.logger.h1(name)
        if self.event_type == EventType.DISPATCH:
            action = self._meta_sync
            self.logger.input(f"Read action from workflow dispatch input: {action}")
        else:
            metadata_raw = self.meta.read_metadata_raw()
            action = metadata_raw["workflow"]["init"]["meta_check_action"][self.event_type.value]
            self.logger.input(
                f"Read action from 'meta.workflow.init.meta_check_action.{self.event_type.value}': {action}"
            )
        if action == "none":
            self.add_summary(
                name=name,
                status="skip",
                oneliner="Meta synchronization is disabled for this event type❗",
            )
            self.logger.skip("Meta synchronization is disabled for this event type; skip❗")
            return
        if self.event_name == "pull_request" and action != "fail" and not self.pull_is_internal:
            self.logger.attention(
                "Meta synchronization cannot be performed as pull request is from a forked repository; "
                f"switching action from '{action}' to 'fail'."
            )
            action = "fail"
        if action == "pull":
            pr_branch = self.switch_to_ci_branch("meta")
        self.metadata, self.metadata_ci = self.meta.read_metadata_full()
        self.meta_results, self.meta_changes, meta_summary = self.meta.compare_files()
        meta_changes_any = any(any(change.values()) for change in self.meta_changes.values())

        # Push/amend/pull if changes are made and action is not 'fail' or 'report'
        if action not in ["fail", "report"] and meta_changes_any:
            self.meta.apply_changes()
            if action == "amend":
                self.git.commit(stage="all", amend=True)
                latest_hash = self.git.push(force_with_lease=True)
            else:
                commit_msg = CommitMsg(
                    typ=self.metadata["commit"]["secondary_action"]["meta_sync"]["type"],
                    title="Sync dynamic files with meta content",
                )
                self.git.commit(message=str(commit_msg), stage="all")
                latest_hash = self.git.push()
            if action == "pull":
                pull_data = self.api.pull_create(
                    head=self.git.current_branch_name(),
                    base=self.ref_name,
                    title=commit_msg.summary,
                    body=commit_msg.body,
                )
                self.switch_to_original_branch()
            else:
                self._hash_latest = latest_hash

        if meta_changes_any and action in ["fail", "report", "pull"]:
            self.fail = True
            status = "fail"
        else:
            status = "pass"

        if not meta_changes_any:
            oneliner = "All dynamic files are in sync with meta content."
            self.logger.success(oneliner)
        else:
            oneliner = "Some dynamic files were out of sync with meta content."
            if action in ["pull", "commit", "amend"]:
                oneliner += " These were resynchronized and applied to "
                if action == "pull":
                    link = html.a(href=pull_data['url'], content=pull_data['number'])
                    oneliner += f"branch '{pr_branch}' and a pull request ({link}) was created."
                else:
                    link = html.a(href=str(self.gh_link.commit(self._hash_latest)), content=latest_hash[:7])
                    oneliner += "the current branch " + (
                        f"in a new commit (hash: {link})" if action == "commit"
                        else f"by amending the latest commit (new hash: {link})"
                    )
        self.add_summary(name=name, status=status, oneliner=oneliner)
        return

    def action_hooks(self):
        name = "Workflow Hooks"
        self.logger.h1(name)
        if self.event_type == EventType.DISPATCH:
            action = self._hooks
            self.logger.input(f"Read action from workflow dispatch input: {action}")
        else:
            action = self.metadata["workflow"]["init"]["hooks_check_action"][self.event_type.value]
            self.logger.input(
                f"Read action from 'meta.workflow.init.hooks_check_action.{self.event_type.value}': {action}"
            )
        if action == "none":
            self.add_summary(
                name=name,
                status="skip",
                oneliner="Hooks are disabled for this event type❗",
            )
            self.logger.skip("Hooks are disabled for this event type; skip❗")
            return
        if not self.metadata["workflow"].get("pre_commit"):
            oneliner = "Hooks are enabled but no pre-commit config set in 'meta.workflow.pre_commit'❗"
            self.fail = True
            self.add_summary(
                name=name,
                status="fail",
                oneliner=oneliner,
            )
            self.logger.error(oneliner, raise_error=False)
            return
        if self.event_name == "pull_request" and action != "fail" and not self.pull_is_internal:
            self.logger.attention(
                "Hook fixes cannot be applied as pull request is from a forked repository; "
                f"switching action from '{action}' to 'fail'."
            )
            action = "fail"
        if action == "pull":
            pr_branch = self.switch_to_ci_branch("hooks")
        if self.meta_changes.get(FileCategory.CONFIG, {}).get("pre-commit-config"):
            pre_commit_temp = True
            pre_commit_config_path = ".__temporary_pre_commit_config__.yaml"
            for result in self.meta_results:
                if result[0].id == "pre-commit-config":
                    with open(pre_commit_config_path, "w") as f:
                        f.write(result[1].after)
                    self.logger.success(
                        "Write temporary pre-commit config file.",
                        "The pre-commit config had been changed in this event, and thus "
                        "the current config file was not valid anymore."
                    )
                    break
            else:
                self.logger.error(
                    "Could not find pre-commit-config in meta results.",
                    "This is an internal error that should not happen; please report it on GitHub."
                )
        else:
            pre_commit_temp = False
            pre_commit_config_path = self.meta.output_paths.pre_commit_config.rel_path
        hooks_output = hooks.run(
            apply=action not in ["fail", "report"],
            ref_range=(self.hash_before, self.hash_after),
            path_config=pre_commit_config_path,
            logger=self.logger,
        )
        passed = hooks_output["passed"]
        modified = hooks_output["modified"]
        if pre_commit_temp:
            Path(pre_commit_config_path).unlink()
            self.logger.success("Remove temporary pre-commit config file.")

        # Push/amend/pull if changes are made and action is not 'fail' or 'report'
        if action not in ["fail", "report"] and modified:
            if action == "amend":
                self.git.commit(stage="all", amend=True)
                latest_hash = self.git.push(force_with_lease=True)
            else:
                commit_msg = CommitMsg(
                    typ=self.metadata["commit"]["secondary_action"]["hook_fix"]["type"],
                    title="Apply automatic fixes made by workflow hooks",
                )
                self.git.commit(message=str(commit_msg), stage="all")
                latest_hash = self.git.push()
            if action == "pull":
                pull_data = self.api.pull_create(
                    head=self.git.current_branch_name(),
                    base=self.ref_name,
                    title=commit_msg.summary,
                    body=commit_msg.body,
                )
                self.switch_to_original_branch()
            else:
                self._hash_latest = latest_hash

        if not passed or (action == "pull" and modified):
            self.fail = True
            status = "fail"
        else:
            status = "pass"

        if action == "pull" and modified:
            link = html.a(href=pull_data['url'], content=pull_data['number'])
            target = f"branch '{pr_branch}' and a pull request ({link}) was created"
        if action in ["commit", "amend"] and modified:
            link = html.a(href=str(self.gh_link.commit(self._hash_latest)), content=latest_hash[:7])
            target = "the current branch " + (
                f"in a new commit (hash: {link})" if action == "commit"
                else f"by amending the latest commit (new hash: {link})"
            )

        if passed:
            oneliner = "All hooks passed without making any modifications." if not modified else (
                "All hooks passed in the second run. "
                f"The modifications made during the first run were applied to {target}."
            )
        elif action in ["fail", "report"]:
            mode = "some failures were auto-fixable" if modified else "failures were not auto-fixable"
            oneliner = f"Some hooks failed ({mode})."
        elif modified:
            oneliner = (
                "Some hooks failed even after the second run. "
                f"The modifications made during the first run were still applied to {target}."
            )
        else:
            oneliner = "Some hooks failed (failures were not auto-fixable)."
        self.add_summary(
            name=name,
            status=status,
            oneliner=oneliner,
            details=hooks_output["summary"]
        )
        return

    def action_repo_labels_sync(self, init: bool = False):
        name = "Repository Labels Synchronizer"
        self.logger.h1(name)
        current_labels = self.api.labels
        if init:
            for label in current_labels:
                self.api.label_delete(label["name"])
            for label in self.metadata["label"]["list"]:
                self.api.label_create(**label)
            return

        return

    def action_repo_settings_sync(self):
        data = self.metadata["repo"]["config"] | {
            "has_issues": True,
            "allow_squash_merge": True,
            "squash_merge_commit_title": "PR_TITLE",
            "squash_merge_commit_message": "PR_BODY",
        }
        topics = data.pop("topics")
        self.api_admin.update_settings(settings=data)
        self.api_admin.replace_topics(topics=topics)
        return

    def action_website_announcement_check(self):
        name = "Website Announcement Expiry Check"
        path_announcement_file = Path(self.metadata["path"]["file"]["website_announcement"])
        if not path_announcement_file.exists():
            self.add_summary(
                name=name,
                status="skip",
                oneliner="Announcement file does not exist❗",
                details=html.ul(
                    [
                        f"❎ No changes were made.",
                        f"🚫 The announcement file was not found at '{path_announcement_file}'"
                    ]
                )
            )
            return
        with open(path_announcement_file) as f:
            current_announcement = f.read()
        (
            commit_date_relative,
            commit_date_absolute,
            commit_date_epoch,
            commit_details
        ) = (
            self.git.log(
                number=1,
                simplify_by_decoration=False,
                pretty=pretty,
                date=date,
                paths=str(path_announcement_file),
            ) for pretty, date in (
                ("format:%cd", "relative"),
                ("format:%cd", None),
                ("format:%cd", "unix"),
                (None, None),
            )
        )
        if not current_announcement:
            last_commit_details_html = html.details(
                content=md.code_block(commit_details),
                summary="📝 Removal Commit Details",
            )
            self.add_summary(
                name=name,
                status="skip",
                oneliner="📭 No announcement to check.",
                details=html.ul(
                    [
                        f"❎ No changes were made."
                        f"📭 The announcement file at '{path_announcement_file}' is empty.\n",
                        f"📅 The last announcement was removed {commit_date_relative} on {commit_date_absolute}.\n",
                        last_commit_details_html,
                    ]
                )
            )
            return

        current_date_epoch = int(
            _util.shell.run_command(["date", "-u", "+%s"], logger=self.logger)
        )
        elapsed_seconds = current_date_epoch - int(commit_date_epoch)
        elapsed_days = elapsed_seconds / (24 * 60 * 60)
        retention_days = self.metadata["web"]["announcement_retention_days"]
        retention_seconds = retention_days * 24 * 60 * 60
        remaining_seconds = retention_seconds - elapsed_seconds
        remaining_days = retention_days - elapsed_days

        if remaining_seconds > 0:
            current_announcement_html = html.details(
                content=md.code_block(current_announcement, "html"),
                summary="📣 Current Announcement",
            )
            last_commit_details_html = html.details(
                content=md.code_block(commit_details),
                summary="📝 Current Announcement Commit Details",
            )
            self.add_summary(
                name=name,
                status="skip",
                oneliner=f"📬 Announcement is still valid for another {remaining_days:.2f} days.",
                details=html.ul(
                    [
                        "❎ No changes were made.",
                        "📬 Announcement is still valid.",
                        f"⏳️ Elapsed Time: {elapsed_days:.2f} days ({elapsed_seconds} seconds)",
                        f"⏳️ Retention Period: {retention_days} days ({retention_seconds} seconds)",
                        f"⏳️ Remaining Time: {remaining_days:.2f} days ({remaining_seconds} seconds)",
                        current_announcement_html,
                        last_commit_details_html,
                    ]
                )
            )
            return

        with open(path_announcement_file, "w") as f:
            f.write("")
        commit_title = "Remove expired announcement"
        commit_body = (
            f"The following announcement made {commit_date_relative} on {commit_date_absolute} "
            f"was expired after {elapsed_days:.2f} days and thus automatically removed:\n\n"
            f"{current_announcement}"
        )
        commit_hash, commit_link = self.commit_website_announcement(
            commit_title=commit_title,
            commit_body=commit_body,
            change_title=commit_title,
            change_body=commit_body,
        )
        removed_announcement_html = html.details(
            content=md.code_block(current_announcement, "html"),
            summary="📣 Removed Announcement",
        )
        last_commit_details_html = html.details(
            content=md.code_block(commit_details),
            summary="📝 Removed Announcement Commit Details",
        )
        self.add_summary(
            name=name,
            status="pass",
            oneliner="🗑 Announcement was expired and thus removed.",
            details=html.ul(
                [
                    f"✅ The announcement was removed (commit {html.a(commit_link, commit_hash)}).",
                    f"⌛ The announcement had expired {abs(remaining_days):.2f} days ({abs(remaining_seconds)} seconds) ago.",
                    f"⏳️ Elapsed Time: {elapsed_days:.2f} days ({elapsed_seconds} seconds)",
                    f"⏳️ Retention Period: {retention_days} days ({retention_seconds} seconds)",
                    removed_announcement_html,
                    last_commit_details_html,
                ]
            )
        )
        return

    def action_website_announcement_update(self):
        name = "Website Announcement Manual Update"
        self.logger.h1(name)
        if not self.ref_is_main:
            self.add_summary(
                name=name,
                status="skip",
                oneliner="Announcement can only be updated from the main branch❗",
            )
            self.logger.warning("Announcement can only be updated from the main branch; skip❗")
            return
        announcement = self._website_announcement
        self.logger.input(f"Read announcement from workflow dispatch input: '{announcement}'")
        if not announcement:
            self.add_summary(
                name=name,
                status="skip",
                oneliner="No announcement was provided.",
            )
            self.logger.skip("No announcement was provided.")
            return
        old_announcement = self.read_website_announcement().strip()
        old_announcement_details = self.git.log(
            number=1,
            simplify_by_decoration=False,
            pretty=None,
            date=None,
            paths=self.metadata["path"]["file"]["website_announcement"],
        )
        old_md = md.code_block(old_announcement_details)

        if announcement == "null":
            announcement = ""

        if announcement.strip() == old_announcement.strip():
            details_list = ["❎ No changes were made."]
            if not announcement:
                oneliner = "No announcement to remove❗"
                details_list.extend(
                    [
                        f"🚫 The 'null' string was passed to delete the current announcement, "
                        f"but the announcement file is already empty.",
                        html.details(content=old_md, summary="📝 Last Removal Commit Details")
                    ]
                )
            else:
                oneliner = "The provided announcement was identical to the existing announcement❗"
                details_list.extend(
                    [
                        "🚫 The provided announcement was the same as the existing one.",
                        html.details(content=old_md, summary="📝 Current Announcement Commit Details")
                    ]
                )
            self.add_summary(
                name=name,
                status="skip",
                oneliner=oneliner,
                details=html.ul(details_list)
            )
            return
        self.write_website_announcement(announcement)
        new_html = html.details(
            content=md.code_block(announcement, "html"),
            summary="📣 New Announcement",
        )
        details_list = []
        if not announcement:
            oneliner = "Announcement was manually removed 🗑"
            details_list.extend(
                [
                    f"✅ The announcement was manually removed.",
                    html.details(content=old_md, summary="📝 Removed Announcement Details")
                ]
            )
            commit_title = "Manually remove announcement"
            commit_body = f"Removed announcement:\n\n{old_announcement}"
        elif not old_announcement:
            oneliner = "A new announcement was manually added 📣"
            details_list.extend([f"✅ A new announcement was manually added.", new_html])
            commit_title = "Manually add new announcement"
            commit_body = announcement
        else:
            oneliner = "Announcement was manually updated 📝"
            details_list.extend(
                [
                    f"✅ The announcement was manually updated.",
                    new_html,
                    html.details(content=old_md, summary="📝 Old Announcement Details")
                ]
            )
            commit_title = "Manually update announcement"
            commit_body = f"New announcement:\n\n{announcement}\n\nRemoved announcement:\n\n{old_announcement}"

        commit_hash, commit_url = self.commit_website_announcement(
            commit_title=commit_title,
            commit_body=commit_body,
            change_title=commit_title,
            change_body=commit_body,
        )
        details_list.append(f"✅ Changes were applied (commit {html.a(commit_url, commit_hash)}).")
        self.add_summary(
            name=name,
            status="pass",
            oneliner=oneliner,
            details=html.ul(details_list)
        )
        return

    def write_website_announcement(self, announcement: str):
        if announcement:
            announcement = f"{announcement.strip()}\n"
        with open(self.metadata["path"]["file"]["website_announcement"], "w") as f:
            f.write(announcement)
        return

    def read_website_announcement(self) -> str:
        with open(self.metadata["path"]["file"]["website_announcement"]) as f:
            return f.read()

    def commit_website_announcement(
        self,
        commit_title: str,
        commit_body: str,
        change_title: str,
        change_body: str,
    ):
        changelog_id = self.metadata["commit"]["primary"]["website"]["announcement"].get("changelog_id")
        if changelog_id:
            changelog_manager = ChangelogManager(
                changelog_metadata=self.metadata["changelog"],
                ver_dist=f"{self.last_ver}+{self.dist_ver}",
                commit_type=self.metadata["commit"]["primary"]["website"]["type"],
                commit_title=commit_title,
                parent_commit_hash=self.hash_after,
                parent_commit_url=str(self.gh_link.commit(self.hash_after))
            )
            changelog_manager.add_change(
                changelog_id=changelog_id,
                section_id=self.metadata["commit"]["primary"]["website"]["announcement"]["changelog_section_id"],
                change_title=change_title,
                change_details=change_body,
            )
            changelog_manager.write_all_changelogs()
        commit = CommitMsg(
            typ=self.metadata["commit"]["primary"]["website"]["type"],
            title=commit_title,
            body=commit_body,
            scope=self.metadata["commit"]["primary"]["website"]["announcement"]["scope"]
        )
        commit_hash = self.git.commit(message=str(commit), stage='all')
        commit_link = str(self.gh_link.commit(commit_hash))
        self._hash_latest = commit_hash
        return commit_hash, commit_link

    def get_commits(self):
        primary_action = {}
        primary_action_types = []
        for primary_action_id, primary_action_commit in self.metadata["commit"]["primary_action"].items():
            conv_commit_type = primary_action_commit["type"]
            primary_action_types.append(conv_commit_type)
            primary_action[conv_commit_type] = PrimaryCommitAction[primary_action_id.upper()]
        secondary_action = {}
        secondary_action_types = []
        for secondary_action_id, secondary_action_commit in self.metadata["commit"]["secondary_action"].items():
            conv_commit_type = secondary_action_commit["type"]
            secondary_action_types.append(conv_commit_type)
            secondary_action[conv_commit_type] = SecondaryCommitAction[secondary_action_id.upper()]
        primary_custom_types = []
        for primary_custom_commit in self.metadata["commit"]["primary_custom"].values():
            conv_commit_type = primary_custom_commit["type"]
            primary_custom_types.append(conv_commit_type)
        all_conv_commit_types = (
            primary_action_types
            + secondary_action_types
            + primary_custom_types
            + list(self.metadata["commit"]["secondary_custom"].keys())
        )
        parser = CommitParser(types=all_conv_commit_types)
        commits = self.git.get_commits(f"{self.hash_before}..{self.hash_after}")
        parsed_commits = []
        for commit in commits:
            conv_msg = parser.parse(msg=commit["msg"])
            if not conv_msg:
                parsed_commits.append(Commit(**commit))
            elif conv_msg.type in primary_action_types:
                parsed_commits.append(
                    Commit(**commit, typ=CommitGroup.PRIMARY_ACTION, action=primary_action[conv_msg.type])
                )
            elif conv_msg.type in secondary_action_types:
                parsed_commits.append(
                    Commit(**commit, typ=CommitGroup.SECONDARY_ACTION, action=secondary_action[conv_msg.type])
                )
            elif conv_msg.type in primary_custom_types:
                parsed_commits.append(Commit(**commit, typ=CommitGroup.PRIMARY_CUSTOM))
            else:
                parsed_commits.append(Commit(**commit, typ=CommitGroup.SECONDARY_CUSTOM))
        return parsed_commits

    def get_latest_version(self) -> tuple[PEP440SemVer | None, int | None]:
        tags_lists = self.git.get_tags()
        if not tags_lists:
            return None, None
        ver_tag_prefix = self.metadata["tag"]["group"]["version"]["prefix"]
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

    def switch_to_ci_branch(self, typ: Literal['hooks', 'meta']):
        current_branch = self.git.current_branch_name()
        new_branch_prefix = self.metadata["branch"]["group"]["ci_pull"]["prefix"]
        new_branch_name = f"{new_branch_prefix}{current_branch}/{typ}"
        self.git.checkout(branch=new_branch_name, reset=True)
        self.logger.success(f"Switch to CI branch '{new_branch_name}' and reset it to '{current_branch}'.")
        return new_branch_name

    def switch_to_original_branch(self):
        self.git.checkout(branch=self.ref_name)
        return

    def assemble_summary(self) -> str:
        github_context, event_payload = (
            html.details(
                content=md.code_block(
                    YAML(typ=['rt', 'string']).dumps(dict(sorted(data.items())), add_final_eol=True),
                    "yaml"
                ),
                summary=summary,
            ) for data, summary in (
                (self.context, "🎬 GitHub Context"), (self.payload, "📥 Event Payload")
            )
        )
        intro = [f"{Emoji.PLAY}The workflow was triggered by a <code>{self.event_name}</code> event."]
        if self.output["config"]["fail"]:
            intro.append(f"{Emoji.FAIL}The workflow failed.")
        else:
            intro.append(f"{Emoji.PASS}The workflow passed.")
        intro = html.ul(intro)
        summary = html.ElementCollection(
            [
                html.h(1, "Workflow Report"),
                intro,
                html.ul([github_context, event_payload]),
                html.h(2, "🏁 Summary"),
                html.ul(self.summary_oneliners),
                html.ElementCollection(self.summary_sections),
                html.h(2, "🪵 Logs"),
                html.details(self.logger.file_log, "Log"),
            ]
        )
        return str(summary)

    def add_summary(
        self,
        name: str,
        status: Literal['pass', 'fail', 'skip', 'warning'],
        oneliner: str,
        details: str | html.Element | html.ElementCollection | None = None,
    ):
        self.summary_oneliners.append(f"{Emoji[status]} <b>{name}</b>: {oneliner}")
        if details:
            self.summary_sections.append(f"## {name}\n\n{details}\n\n")
        return

    @property
    def fail(self):
        return self.output["config"]["fail"]

    @fail.setter
    def fail(self, value: bool):
        self.output["config"]["fail"] = True
        return

    def enable_job_run(self, job_id: str):
        if job_id not in self.output["config"]["run"]:
            self.logger.error(f"Invalid job ID: {job_id}")
        self.output["config"]["run"][job_id] = True
        return

    @property
    def context(self) -> dict:
        """The 'github' context of the triggering event.

        References
        ----------
        - [GitHub Docs](https://docs.github.com/en/actions/learn-github-actions/contexts#github-context)
        """
        return self._context

    @property
    def payload(self) -> dict:
        """The full webhook payload of the triggering event.

        References
        ----------
        - [GitHub Docs](https://docs.github.com/en/webhooks/webhook-events-and-payloads)
        """
        return self._payload

    @property
    def event_name(self) -> str:
        """The name of the triggering event, e.g. 'push', 'pull_request' etc."""
        return self.context["event_name"]

    @property
    def ref(self) -> str:
        """
        The full ref name of the branch or tag that triggered the event,
        e.g. 'refs/heads/main', 'refs/tags/v1.0' etc.
        """
        return self.context["ref"]

    @property
    def ref_name(self) -> str:
        """The short ref name of the branch or tag that triggered the event, e.g. 'main', 'dev/1' etc."""
        return self.context["ref_name"]

    @property
    def repo_owner(self) -> str:
        """GitHub username of the repository owner."""
        return self.context["repository_owner"]

    @property
    def repo_name(self) -> str:
        """Name of the repository."""
        return self.context["repository"].removeprefix(f"{self.repo_owner}/")

    @property
    def default_branch(self) -> str:
        return self.payload["repository"]["default_branch"]

    @property
    def ref_is_main(self) -> bool:
        return self.ref == f"refs/heads/{self.default_branch}"

    @property
    def hash_before(self) -> str:
        """The SHA hash of the most recent commit on the branch before the event."""
        if self.event_name == "push":
            return self.payload["before"]
        if self.event_name == "pull_request":
            return self.payload["pull_request"]["base"]["sha"]
        return self.git.commit_hash_normal()

    @property
    def hash_after(self) -> str:
        """The SHA hash of the most recent commit on the branch after the event."""
        if self.event_name == "push":
            return self.payload["after"]
        if self.event_name == "pull_request":
            return self.payload["pull_request"]["head"]["sha"]
        return self.git.commit_hash_normal()

    @property
    def hash_latest(self) -> str:
        """The SHA hash of the most recent commit on the branch,
        including commits made during the workflow run.
        """
        if self._hash_latest:
            return self._hash_latest
        return self.hash_after

    @property
    def pull_is_internal(self) -> bool:
        """Whether the pull request is internal, i.e. within the same repository."""
        return self.payload["pull_request"]["head"]["repo"]["full_name"] == self.context["repository"]


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
    logger=None
):
    for arg_name, arg in (("meta_sync", meta_sync), ("hooks", hooks)):
        if arg not in ['report', 'amend', 'commit', 'pull', 'none', '']:
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
        meta_sync=meta_sync or 'none',
        hooks=hooks or 'none',
        website_announcement=website_announcement,
        website_announcement_msg=website_announcement_msg,
        logger=logger,
    ).run()
