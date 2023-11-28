from pathlib import Path
import json
from typing import Literal, NamedTuple
import datetime
from enum import Enum
import shutil

from markitup import html, md
import pylinks

from repodynamics import meta
from repodynamics.logger import Logger
from repodynamics.git import Git
from repodynamics.meta.manager import MetaManager
from repodynamics import hook, _util
from repodynamics.commit import CommitParser
from repodynamics.version import PEP440SemVer
from repodynamics.actions._changelog import ChangelogManager
from repodynamics.actions.repo_config import RepoConfigAction
from repodynamics.actions.context_manager import ContextManager
from repodynamics.meta.meta import Meta
from repodynamics.path import RelativePath

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
    InitCheckAction,
    WorkflowDispatchInput,
)


class EventHandler:
    def __init__(self, context_manager: ContextManager, admin_token: str, logger: Logger | None = None):
        self._context = context_manager
        self._metadata_main: MetaManager | None = meta.read_from_json_file(
            path_root="repo_self", logger=logger
        )
        self._logger = logger or Logger()

        repo_user = self._context.github.repo_owner
        repo_name = self._context.github.repo_name
        self._gh_api_admin = pylinks.api.github(token=admin_token).user(repo_user).repo(repo_name)
        self._gh_api = pylinks.api.github(token=self._context.github.token).user(repo_user).repo(repo_name)
        self._gh_link = pylinks.site.github.user(repo_user).repo(repo_name)
        self._git_base: Git = Git(
            path_repo="repo_self",
            user=(self._context.payload.sender_username, self._context.payload.sender_email),
            logger=self._logger,
        )
        if self._context.github.event_name == "pull_request" and not self._context.payload.internal:
            self._git_head: Git = Git(
                path_repo="repo_fork",
                user=(self._context.payload.sender_username, self._context.payload.sender_email),
                logger=self._logger,
            )
        else:
            self._git_head = self._git_base
        self._meta: Meta | None = None
        self._metadata_branch: MetaManager | None = None
        self._branch: Branch | None = None
        self._event_type: EventType | None = None
        self._summary_oneliners: list[str] = []
        self._summary_sections: list[str | html.ElementCollection | html.Element] = []
        self._amended: bool = False
        self._tag: str = ""
        self._version: str = ""
        self._failed = False
        self._hash_latest: str = ""
        self._job_run_flag: dict[str, bool] = {
            job_id: False
            for job_id in [
                "package_build",
                "package_test_local",
                "package_lint",
                "website_build",
                "website_deploy",
                "website_rtd_preview",
                "package_publish_testpypi",
                "package_publish_pypi",
                "package_test_testpypi",
                "package_test_pypi",
                "github_release",
            ]
        }
        self._release_info: dict = {
            "name": "",
            "body": "",
            "prerelease": False,
            "make_latest": "legacy",
            "discussion_category_name": "",
        }
        return

    def run(self):
        self.run_event()
        return self._finalize()

    def run_event(self) -> None:
        ...

    def _finalize(self):
        self._logger.h1("Finalization")
        summary = self.assemble_summary()
        output = self.output
        return output, None, summary

    def _action_meta(self, action: InitCheckAction | None = None):
        name = "Meta Sync"
        self._logger.h1(name)
        if not action:
            action = InitCheckAction(
                self._metadata_main["workflow"]["init"]["meta_check_action"][self._event_type.value]
            )
        self._logger.input(f"Action: {action.value}")
        if action == InitCheckAction.NONE:
            self.add_summary(
                name=name,
                status="skip",
                oneliner="Meta synchronization is disabled for this event type❗",
            )
            self._logger.skip("Meta synchronization is disabled for this event type; skip❗")
            return
        if action == InitCheckAction.PULL:
            pr_branch = self.switch_to_ci_branch("meta")
        self._metadata_branch = self._meta.read_metadata_full()
        meta_results, meta_changes, meta_summary = self._meta.compare_files()
        meta_changes_any = any(any(change.values()) for change in meta_changes.values())
        # Push/amend/pull if changes are made and action is not 'fail' or 'report'
        if action not in [InitCheckAction.FAIL, InitCheckAction.REPORT] and meta_changes_any:
            self._meta.apply_changes()
            if action == InitCheckAction.AMEND:
                self.commit(stage="all", amend=True, push=True)
            else:
                commit_msg = CommitMsg(
                    typ=self._metadata_main["commit"]["secondary_action"]["meta_sync"]["type"],
                    title="Sync dynamic files with meta content",
                )
                self.commit(
                    message=str(commit_msg),
                    stage="all",
                    push=True,
                    set_upstream=action == InitCheckAction.PULL,
                )
            if action == InitCheckAction.PULL:
                pull_data = self._gh_api.pull_create(
                    head=pr_branch,
                    base=self._context.target_branch_name,
                    title=commit_msg.summary,
                    body=commit_msg.body,
                )
                self.switch_to_original_branch()
        if not meta_changes_any:
            oneliner = "All dynamic files are in sync with meta content."
            self._logger.success(oneliner)
        else:
            oneliner = "Some dynamic files were out of sync with meta content."
            if action in [InitCheckAction.PULL, InitCheckAction.COMMIT, InitCheckAction.AMEND]:
                oneliner += " These were resynchronized and applied to "
                if action == InitCheckAction.PULL:
                    link = html.a(href=pull_data["url"], content=pull_data["number"])
                    oneliner += f"branch '{pr_branch}' and a pull request ({link}) was created."
                else:
                    link = html.a(
                        href=str(self._gh_link.commit(self.hash_latest)), content=self.hash_latest[:7]
                    )
                    oneliner += "the current branch " + (
                        f"in a new commit (hash: {link})"
                        if action == InitCheckAction.COMMIT
                        else f"by amending the latest commit (new hash: {link})"
                    )
        self.add_summary(
            name=name,
            status="fail"
            if meta_changes_any
            and action in [InitCheckAction.FAIL, InitCheckAction.REPORT, InitCheckAction.PULL]
            else "pass",
            oneliner=oneliner,
            details=meta_summary,
        )
        return

    def _action_hooks(self, action: InitCheckAction | None = None):
        name = "Workflow Hooks"
        self._logger.h1(name)
        if not action:
            action = InitCheckAction(
                self._metadata_main["workflow"]["init"]["hooks_check_action"][self._event_type.value]
            )
        self._logger.input(f"Action: {action.value}")
        if action == InitCheckAction.NONE:
            self.add_summary(
                name=name,
                status="skip",
                oneliner="Hooks are disabled for this event type❗",
            )
            self._logger.skip("Hooks are disabled for this event type; skip❗")
            return
        config = self._metadata_main["workflow"]["pre_commit"].get(self._branch.type.value)
        if not config:
            oneliner = "Hooks are enabled but no pre-commit config set in 'meta.workflow.pre_commit'❗"
            self.add_summary(
                name=name,
                status="fail",
                oneliner=oneliner,
            )
            self._logger.error(oneliner, raise_error=False)
            return
        # if self.meta_changes.get(DynamicFileType.CONFIG, {}).get("pre-commit-config"):
        #     for result in self.meta_results:
        #         if result[0].id == "pre-commit-config":
        #             config = result[1].after
        #             self._logger.success(
        #                 "Load pre-commit config from metadata.",
        #                 "The pre-commit config had been changed in this event, and thus "
        #                 "the current config file was not valid anymore.",
        #             )
        #             break
        #     else:
        #         self._logger.error(
        #             "Could not find pre-commit-config in meta results.",
        #             "This is an internal error that should not happen; please report it on GitHub.",
        #         )
        # else:
        #     config = self.meta.paths.pre_commit_config.path
        if action == InitCheckAction.PULL:
            pr_branch = self.switch_to_ci_branch("hooks")
        input_action = (
            action
            if action in [InitCheckAction.REPORT, InitCheckAction.AMEND, InitCheckAction.COMMIT]
            else (InitCheckAction.REPORT if action == InitCheckAction.FAIL else InitCheckAction.COMMIT)
        )
        commit_msg = (
            CommitMsg(
                typ=self._metadata_main["commit"]["secondary_action"]["hook_fix"]["type"],
                title="Apply automatic fixes made by workflow hooks",
            )
            if action in [InitCheckAction.COMMIT, InitCheckAction.PULL]
            else ""
        )
        hooks_output = hook.run(
            ref_range=(self._context.hash_before, self.hash_latest),
            action=input_action.value,
            commit_message=str(commit_msg),
            path_root=self._meta.paths.root,
            config=config,
            git=self._git_head,
            logger=self._logger,
        )
        passed = hooks_output["passed"]
        modified = hooks_output["modified"]
        # Push/amend/pull if changes are made and action is not 'fail' or 'report'
        if action not in [InitCheckAction.FAIL, InitCheckAction.REPORT] and modified:
            self.push(amend=action == InitCheckAction.AMEND, set_upstream=action == InitCheckAction.PULL)
            if action == InitCheckAction.PULL:
                pull_data = self._gh_api.pull_create(
                    head=pr_branch,
                    base=self._context.target_branch_name,
                    title=commit_msg.summary,
                    body=commit_msg.body,
                )
                self.switch_to_original_branch()
        if action == InitCheckAction.PULL and modified:
            link = html.a(href=pull_data["url"], content=pull_data["number"])
            target = f"branch '{pr_branch}' and a pull request ({link}) was created"
        if action in [InitCheckAction.COMMIT, InitCheckAction.AMEND] and modified:
            link = html.a(href=str(self._gh_link.commit(self.hash_latest)), content=self.hash_latest[:7])
            target = "the current branch " + (
                f"in a new commit (hash: {link})"
                if action == InitCheckAction.COMMIT
                else f"by amending the latest commit (new hash: {link})"
            )
        if passed:
            oneliner = (
                "All hooks passed without making any modifications."
                if not modified
                else (
                    "All hooks passed in the second run. "
                    f"The modifications made during the first run were applied to {target}."
                )
            )
        elif action in [InitCheckAction.FAIL, InitCheckAction.REPORT]:
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
            status="fail" if not passed or (action == InitCheckAction.PULL and modified) else "pass",
            oneliner=oneliner,
            details=hooks_output["summary"],
        )
        return

    def commit(
        self,
        message: str = "",
        stage: Literal["all", "staged", "unstaged"] = "all",
        amend: bool = False,
        push: bool = False,
        set_upstream: bool = False,
    ):
        commit_hash = self._git_head.commit(message=message, stage=stage, amend=amend)
        if amend:
            self._amended = True
        if push:
            commit_hash = self.push(set_upstream=set_upstream)
        return commit_hash

    def push(self, amend: bool = False, set_upstream: bool = False):
        new_hash = self._git_head.push(
            target="origin", set_upstream=set_upstream, force_with_lease=self._amended or amend
        )
        self._amended = False
        if new_hash and self._git_head.current_branch_name() == self._context.github.ref_name:
            self._hash_latest = new_hash
        return new_hash

    def _tag_version(self, ver: str | PEP440SemVer, msg: str = ""):
        tag_prefix = self._metadata_main["tag"]["group"]["version"]["prefix"]
        tag = f"{tag_prefix}{ver}"
        if not msg:
            msg = f"Release version {ver}"
        self._git_head.create_tag(tag=tag, message=msg)
        self._tag = tag
        self._version = str(ver)
        return

    def switch_to_ci_branch(self, typ: Literal["hooks", "meta"]):
        current_branch = self._git_head.current_branch_name()
        new_branch_prefix = self._metadata_main.branch__group["ci_pull"]["prefix"]
        new_branch_name = f"{new_branch_prefix}{current_branch}/{typ}"
        self._git_head.stash()
        self._git_head.checkout(branch=new_branch_name, reset=True)
        self._logger.success(f"Switch to CI branch '{new_branch_name}' and reset it to '{current_branch}'.")
        return new_branch_name

    def switch_to_original_branch(self):
        self._git_head.checkout(branch=self._context.github.ref_name)
        self._git_head.stash_pop()
        return

    @property
    def hash_latest(self) -> str:
        """The SHA hash of the most recent commit on the branch,
        including commits made during the workflow run.
        """
        return self._hash_latest if self._hash_latest else self._context.hash_after

    def add_summary(
        self,
        name: str,
        status: Literal["pass", "fail", "skip", "warning"],
        oneliner: str,
        details: str | html.Element | html.ElementCollection | None = None,
    ):
        if status == "fail":
            self._failed = True
        self._summary_oneliners.append(f"{Emoji[status]}&nbsp;<b>{name}</b>: {oneliner}")
        if details:
            self._summary_sections.append(f"<h2>{name}</h2>\n\n{details}\n\n")
        return

    def _set_job_run(
        self,
        package_build: bool | None = None,
        package_lint: bool | None = None,
        package_test_local: bool | None = None,
        website_build: bool | None = None,
        website_deploy: bool | None = None,
        website_rtd_preview: bool | None = None,
        package_publish_testpypi: bool | None = None,
        package_publish_pypi: bool | None = None,
        package_test_testpypi: bool | None = None,
        package_test_pypi: bool | None = None,
        github_release: bool | None = None,
    ) -> None:
        data = locals()
        data.pop("self")
        for key, val in data.items():
            if val is not None:
                self._job_run_flag[key] = val
        return

    def _set_release(
        self,
        name: str | None = None,
        body: str | None = None,
        prerelease: bool | None = None,
        make_latest: Literal["legacy", "latest", "none"] | None = None,
        discussion_category_name: str | None = None,
    ):
        data = locals()
        data.pop("self")
        for key, val in data.items():
            if val is not None:
                self._release_info[key] = val
        return

    def _get_latest_version(
        self,
        branch: str | None = None,
        dev_only: bool = False,
        from_fork: bool = False,
    ) -> tuple[PEP440SemVer | None, int | None]:
        git = self._git_head if from_fork else self._git_base
        ver_tag_prefix = self._metadata_main["tag"]["group"]["version"]["prefix"]
        if branch:
            git.stash()
            curr_branch = git.current_branch_name()
            git.checkout(branch=branch)
        latest_version = git.get_latest_version(tag_prefix=ver_tag_prefix, dev_only=dev_only)
        distance = git.get_distance(
            ref_start=f"refs/tags/{ver_tag_prefix}{latest_version.input}"
        ) if latest_version else None
        if branch:
            git.checkout(branch=curr_branch)
            git.stash_pop()
        if not latest_version and not dev_only:
            self._logger.error(f"No matching version tags found with prefix '{ver_tag_prefix}'.")
        return latest_version, distance

    @staticmethod
    def _get_next_version(version: PEP440SemVer, action: PrimaryActionCommitType):
        if action == PrimaryActionCommitType.RELEASE_MAJOR:
            if version.major == 0:
                return version.next_minor
            return version.next_major
        if action == PrimaryActionCommitType.RELEASE_MINOR:
            return version.next_minor
        if action == PrimaryActionCommitType.RELEASE_PATCH:
            return version.next_patch
        if action == PrimaryActionCommitType.RELEASE_POST:
            return version.next_post
        return version

    @property
    def output(self) -> dict:
        metadata = self._metadata_branch or self._metadata_main
        package = metadata.package
        package_name = package.get("name", "")
        if self._failed:
            # Just to be safe, disable publish/deploy/release jobs if fail is True
            self._set_job_run(
                website_deploy=False,
                package_publish_testpypi=False,
                package_publish_pypi=False,
                github_release=False,
            )
        for job_id, dependent_job_id in (
            ("package_publish_testpypi", "package_test_testpypi"),
            ("package_publish_pypi", "package_test_pypi"),
            ("website_deploy", "website_build"),
        ):
            if self._job_run_flag[job_id]:
                self._job_run_flag[dependent_job_id] = True
        if self._job_run_flag["package_publish_testpypi"] or self._job_run_flag["package_publish_pypi"]:
            self._job_run_flag["package_build"] = True
        out = {
            "config": {
                "fail": self._failed,
                "checkout": {
                    "ref": self.hash_latest,
                    "ref_before": self._context.hash_before,
                    "repository": self._context.target_repo_fullname,
                },
                "run": self._job_run_flag,
                "package": {
                    "version": self._version,
                    "upload_url_testpypi": "https://test.pypi.org/legacy/",
                    "upload_url_pypi": "https://upload.pypi.org/legacy/",
                    "download_url_testpypi": f"https://test.pypi.org/project/{package_name}/{self._version}",
                    "download_url_pypi": f"https://pypi.org/project/{package_name}/{self._version}",
                },
                "release": self._release_info | {"tag_name": self._tag},
            },
            "metadata_ci": {
                "path": metadata["path"],
                "web": {
                    "readthedocs": {"name": metadata["web"].get("readthedocs", {}).get("name")},
                },
                "url": {"website": {"base": metadata["url"]["website"]["base"]}},
                "package": {
                    "name": package_name,
                    "github_runners": package.get("github_runners", []),
                    "python_versions": package.get("python_versions", []),
                    "python_version_max": package.get("python_version_max", ""),
                    "pure_python": package.get("pure_python", True),
                    "cibw_matrix_platform": package.get("cibw_matrix_platform", []),
                    "cibw_matrix_python": package.get("cibw_matrix_python", []),
                },
            },
        }
        return out

    def assemble_summary(self) -> str:
        github_context, event_payload = (
            html.details(content=md.code_block(str(data), lang="yaml"), summary=summary)
            for data, summary in (
                (self._context.github, "🎬 GitHub Context"),
                (self._context.payload, "📥 Event Payload"),
            )
        )
        intro = [
            f"{Emoji.PLAY} The workflow was triggered by a <code>{self._context.github.event_name}</code> event."
        ]
        if self._failed:
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
                html.ul(self._summary_oneliners),
            ]
        )
        logs = html.ElementCollection(
            [
                html.h(2, "🪵 Logs"),
                html.details(self._logger.file_log, "Log"),
            ]
        )
        summaries = html.ElementCollection(self._summary_sections)
        path = Path("./repodynamics")
        path.mkdir(exist_ok=True)
        with open(path / "log.html", "w") as f:
            f.write(str(logs))
        with open(path / "report.html", "w") as f:
            f.write(str(summaries))
        return str(summary)

    def resolve_branch(self, branch_name: str | None = None) -> Branch:
        if not branch_name:
            branch_name = self._context.github.ref_name
        if branch_name == self._context.payload.repository_default_branch:
            return Branch(name=branch_name, type=BranchType.DEFAULT)
        return self._metadata_main.get_branch_info_from_name(branch_name=branch_name)


class NonModifyingEventHandler(EventHandler):
    def __init__(self, context_manager: ContextManager, admin_token: str = "", logger: Logger | None = None):
        super().__init__(context_manager=context_manager, admin_token=admin_token, logger=logger)
        return


class ModifyingEventHandler(EventHandler):
    def __init__(self, context_manager: ContextManager, admin_token: str, logger: Logger | None = None):
        super().__init__(context_manager=context_manager, admin_token=admin_token, logger=logger)
        return

    def _action_file_change_detector(self) -> dict[RepoFileType, list[str]]:
        name = "File Change Detector"
        self._logger.h1(name)
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
        changes = self._git_head.changed_files(
            ref_start=self._context.hash_before, ref_end=self._context.hash_after
        )
        self._logger.success("Detected changed files", json.dumps(changes, indent=3))
        fixed_paths = [outfile.rel_path for outfile in self._meta.paths.fixed_files]
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
                if path in fixed_paths:
                    typ = RepoFileType.DYNAMIC
                elif path == ".github/_README.md" or path.endswith("/README.md"):
                    typ = RepoFileType.README
                elif path.startswith(self._meta.paths.dir_source_rel):
                    typ = RepoFileType.PACKAGE
                elif path.startswith(self._meta.paths.dir_website_rel):
                    typ = RepoFileType.WEBSITE
                elif path.startswith(self._meta.paths.dir_tests_rel):
                    typ = RepoFileType.TEST
                elif path.startswith(RelativePath.dir_github_workflows):
                    typ = RepoFileType.WORKFLOW
                elif (
                    path.startswith(RelativePath.dir_github_discussion_template)
                    or path.startswith(RelativePath.dir_github_issue_template)
                    or path.startswith(RelativePath.dir_github_pull_request_template)
                    or path.startswith(RelativePath.dir_github_workflow_requirements)
                ):
                    typ = RepoFileType.DYNAMIC
                elif path == RelativePath.file_path_meta:
                    typ = RepoFileType.SUPERMETA
                elif path == f"{self._meta.paths.dir_meta_rel}paths.yaml":
                    typ = RepoFileType.SUPERMETA
                elif path.startswith(self._meta.paths.dir_meta_rel):
                    typ = RepoFileType.META
                else:
                    typ = RepoFileType.OTHER
                summary_detail[typ].append(f"{change_type_map[change_type].value.emoji} {path}")
                change_group[typ].append(path)
        summary_details = []
        changed_groups_str = ""
        for file_type, summaries in summary_detail.items():
            if summaries:
                summary_details.append(html.h(3, file_type.value.title))
                summary_details.append(html.ul(summaries))
                changed_groups_str += f", {file_type.value}"
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
            status="warning"
            if summary_detail[RepoFileType.SUPERMETA]
            else ("pass" if changed_groups_str else "skip"),
            oneliner=oneliner,
            details=html.ElementCollection(summary_details),
        )
        return change_group

    def _get_commits(self) -> list[Commit]:
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
        commits = self._git_head.get_commits(f"{self._context.hash_before}..{self._context.hash_after}")
        self._logger.success("Read commits from git history", json.dumps(commits, indent=4))
        parser = CommitParser(
            types=self._metadata_main.get_all_conventional_commit_types(), logger=self._logger
        )
        parsed_commits = []
        for commit in commits:
            conv_msg = parser.parse(msg=commit["msg"])
            if not conv_msg:
                parsed_commits.append(Commit(**commit, group_data=NonConventionalCommit()))
            else:
                group = self._metadata_main.get_commit_type_from_conventional_type(conv_type=conv_msg.type)
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
