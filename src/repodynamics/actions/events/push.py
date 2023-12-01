import shutil

from pylinks.http import WebAPIError

from repodynamics.meta import read_from_json_file
from repodynamics.actions.context_manager import ContextManager
from repodynamics.actions.events._base import ModifyingEventHandler
from repodynamics.logger import Logger
from repodynamics.datatype import (
    WorkflowTriggeringAction,
    EventType,
    BranchType,
    Branch,
    InitCheckAction,
    CommitMsg,
    RepoFileType,
    CommitGroup,
    PrimaryActionCommitType,
)
from repodynamics.meta.meta import Meta
from repodynamics import _util
from repodynamics.actions import _helpers
from repodynamics.path import RelativePath
from repodynamics.version import PEP440SemVer


class PushEventHandler(ModifyingEventHandler):
    def __init__(
        self,
        context_manager: ContextManager,
        admin_token: str,
        logger: Logger | None = None,
    ):
        super().__init__(context_manager=context_manager, admin_token=admin_token, logger=logger)
        self._branch: Branch | None = None
        return

    def run_event(self):
        ref_type = self._context.github.ref_type
        if ref_type == "branch":
            self._run_branch()
        elif ref_type == "tag":
            self._run_tag()
        else:
            self._logger.error(
                f"Unsupported reference type for 'push' event.",
                "The workflow was triggered by a 'push' event, "
                f"but the reference type '{ref_type}' is not supported.",
            )
        return

    def _run_branch(self):
        action = self._context.payload.action
        if action == WorkflowTriggeringAction.CREATED:
            self._run_branch_created()
        elif action == WorkflowTriggeringAction.EDITED:
            self._run_branch_edited()
        elif action == WorkflowTriggeringAction.DELETED:
            self._run_branch_deleted()
        else:
            _helpers.error_unsupported_triggering_action(event_name="push", action=action, logger=self._logger)
        return

    def _run_branch_created(self):
        if self._context.ref_is_main:
            if not self._git_base.get_tags():
                self._run_repository_created()
            else:
                self._logger.skip(
                    "Creation of default branch detected while a version tag is present; skipping.",
                    "This is likely a result of a repository transfer, or renaming of the default branch.",
                )
        else:
            self._logger.skip(
                "Creation of non-default branch detected; skipping.",
            )
        return

    def _run_repository_created(self):
        self._logger.info("Detected event: repository creation")
        meta = Meta(path_root="repo_self", github_token=self._context.github.token, logger=self._logger)
        metadata = read_from_json_file(path_root="repo_self", logger=self._logger)
        shutil.rmtree(meta.paths.dir_meta)
        shutil.rmtree(meta.paths.dir_source)
        shutil.rmtree(meta.paths.dir_tests)
        shutil.rmtree(meta.paths.dir_local)
        shutil.rmtree(meta.paths.dir_website)
        (meta.paths.dir_docs / "__website_new__").rename(meta.paths.dir_website)
        (meta.paths.root / "__meta_new__").rename(meta.paths.dir_meta)
        meta.paths.file_path_meta.unlink(missing_ok=True)
        for path_dynamic_file in meta.paths.all_files:
            path_dynamic_file.unlink(missing_ok=True)
        for changelog_data in metadata.changelog.values():
            path_changelog_file = meta.paths.root / changelog_data["path"]
            path_changelog_file.unlink(missing_ok=True)
        self.commit(
            message="Initialize repository from RepoDynamics PyPackIT template", push=True
        )
        self.add_summary(
            name="Init",
            status="pass",
            oneliner="Repository created from RepoDynamics PyPackIT template.",
        )
        return

    def _run_branch_edited(self):
        if self._context.ref_is_main:
            self._event_type = EventType.PUSH_MAIN
            self._branch = Branch(type=BranchType.DEFAULT, name=self._context.github.ref_name)
            return self._run_branch_edited_main()
        self._branch = self._metadata_main.get_branch_info_from_name(branch_name=self._context.github.ref_name)
        self._git_head.fetch_remote_branches_by_name(branch_names=self._context.github.ref_name)
        self._git_head.checkout(self._context.github.ref_name)
        self._meta = Meta(
            path_root="repo_self",
            github_token=self._context.github.token,
            hash_before=self._context.hash_before,
            logger=self._logger,
        )
        if self._branch.type == BranchType.RELEASE:
            self._event_type = EventType.PUSH_RELEASE
            return self._run_branch_edited_release()
        if self._branch.type == BranchType.DEV:
            self._event_type = EventType.PUSH_DEV
            return self._run_branch_edited_dev()
        if self._branch.type == BranchType.CI_PULL:
            self._event_type = EventType.PUSH_CI_PULL
            return self._run_branch_edited_ci_pull()
        self._event_type = EventType.PUSH_OTHER
        return self._run_branch_edited_other()

    def _run_branch_edited_main(self):
        if not self._git_base.get_tags():
            # The repository is in the initialization phase
            head_commit_msg = self._context.payload.head_commit_message
            if head_commit_msg == "init":
                # User is signaling the end of initialization phase
                return self._run_first_release()
            # User is still setting up the repository (still in initialization phase)
            return self._run_init_phase()
        self._metadata_main_before = read_from_json_file(
            path_root="repo_self",
            commit_hash=self._context.hash_before,
            git=self._git_base,
            logger=self._logger,
        )
        if not self._metadata_main_before:
            return self._run_existing_repository_initialized()
        return self._run_branch_edited_main_normal()

    def _run_init_phase(self):
        self._metadata_main_before = read_from_json_file(
            path_root="repo_self",
            commit_hash=self._context.hash_before,
            git=self._git_base,
            logger=self._logger,
        )
        self._meta = Meta(
            path_root="repo_self",
            github_token=self._context.github.token,
            future_versions={self._branch.name: "0.0.0"},
            logger=self._logger,
        )
        self._metadata_main = self._metadata_branch = self._meta.read_metadata_full()
        self._config_repo()
        self._config_repo_pages()
        self._config_repo_labels_reset()
        self._action_meta(action=InitCheckAction.COMMIT)
        if self._metadata_main["workflow"].get("pre_commit"):
            self._action_hooks(action=InitCheckAction.COMMIT)
        self._config_repo_branch_names()
        self._set_job_run(
            package_lint=True,
            package_test_local=True,
            website_build=True,
            website_deploy=True,
        )
        return

    def _run_first_release(self):
        self._run_init_phase()
        # commit_msg = CommitMsg(
        #     typ="init",
        #     title="Initialize package and website",
        #     body="This is an initial release of the website, and the yet empty package on PyPI and TestPyPI.",
        # )
        # self.commit(
        #     message=str(commit_msg),
        #     amend=True,
        #     push=True,
        # )

        # Squash all commits into a single commit
        # Ref: https://blog.avneesh.tech/how-to-delete-all-commit-history-in-github
        #      https://stackoverflow.com/questions/55325930/git-how-to-squash-all-commits-on-master-branch
        self._git_head.checkout("temp", orphan=True)
        self.commit(message="init: Create repository from RepoDynamics PyPackIT template")
        self._git_head.branch_delete(self._context.github.ref_name, force=True)
        self._git_head.branch_rename(self._context.github.ref_name, force=True)
        self._hash_latest = self._git_head.push(
            target="origin", ref=self._context.github.ref_name, force_with_lease=True
        )
        self._tag_version(ver="0.0.0", msg="Initial release")
        self._set_job_run(
            package_publish_testpypi=True,
            package_publish_pypi=True,
        )
        return

    def _run_existing_repository_initialized(self):
        return

    def _run_branch_edited_main_normal(self):
        self.action_repo_labels_sync()

        self.action_file_change_detector()
        for job_id in ("package_build", "package_test_local", "package_lint", "website_build"):
            self.set_job_run(job_id)

        self.action_meta(action=metadata_raw["workflow"]["init"]["meta_check_action"][self.event_type.value])
        self._action_hooks()
        self.last_ver_main, self.dist_ver_main = self._get_latest_version()
        commits = self._get_commits()
        if len(commits) != 1:
            self._logger.error(
                f"Push event on main branch should only contain a single commit, but found {len(commits)}.",
                raise_error=False,
            )
            self.fail = True
            return
        commit = commits[0]
        if commit.group_data.group not in [CommitGroup.PRIMARY_ACTION, CommitGroup.PRIMARY_CUSTOM]:
            self._logger.error(
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
            next_ver = self._get_next_version(self.last_ver_main, commit.group_data.action)
            ver_dist = str(next_ver)

        changelog_manager = ChangelogManager(
            changelog_metadata=self.metadata_main["changelog"],
            ver_dist=ver_dist,
            commit_type=commit.group_data.conv_type,
            commit_title=commit.msg.title,
            parent_commit_hash=self.hash_before,
            parent_commit_url=self._gh_link.commit(self.hash_before),
        )
        changelog_manager.add_from_commit_body(commit.msg.body)
        changelog_manager.write_all_changelogs()
        self.commit(amend=True, push=True)

        if next_ver:
            self._tag_version(ver=next_ver)
            for job_id in ("package_publish_testpypi", "package_publish_pypi", "github_release"):
                self.set_job_run(job_id)
            self._release_info["body"] = changelog_manager.get_entry("package_public")[0]
            self._release_info["name"] = f"{self.metadata_main['name']} {next_ver}"

        if commit.group_data.group == CommitGroup.PRIMARY_ACTION:
            self.set_job_run("website_deploy")
        return

    def _run_branch_edited_release(self):
        self.event_type = EventType.PUSH_RELEASE
        action_hooks = self.metadata["workflow"]["init"]["hooks_check_action"][self.event_type.value]
        return

    def _run_branch_edited_dev(self):
        changed_file_groups = self._action_file_change_detector()
        for file_type in (RepoFileType.SUPERMETA, RepoFileType.META, RepoFileType.DYNAMIC):
            if changed_file_groups[file_type]:
                self._action_meta()
                break
        else:
            self._metadata_branch = read_from_json_file(path_root="repo_self", logger=self._logger)
        self._action_hooks()
        commits = self._get_commits()
        head_commit = commits[0]
        if head_commit.group_data.group != CommitGroup.NON_CONV:
            footers = head_commit.msg.footer
            ready_for_review = footers.get("ready_for_review", ["false"])
            if len(ready_for_review) != 1:
                self._logger.error(
                    f"Found {len(ready_for_review)} 'ready_for_review' footers, but expected 1.",
                    raise_error=False,
                )
                self._failed = True
                return
            if ready_for_review[0] == "true":
                if self._metadata_main["repo"]["full_name"] == self._context.github.repo_fullname:
                    # workflow is running from own repository
                    matching_pulls = self._gh_api.pull_list(
                        state="open",
                        head=f"{self._context.github.repo_owner}:{self._context.github.ref_name}",
                        base=self._branch.suffix[1],
                    )
                    if not matching_pulls:
                        self._gh_api.pull_create(
                            title=head_commit.msg.title,
                            body=head_commit.msg.body,
                            head=self._context.github.ref_name,
                            base=self._branch.suffix[1],
                        )
                    elif len(matching_pulls) != 1:
                        self._logger.error(
                            f"Found {len(matching_pulls)} matching pull requests, but expected 0 or 1.",
                            raise_error=False,
                        )
                        self._failed = True
                        return
                    else:
                        self._gh_api.pull_update(
                            number=matching_pulls[0]["number"],
                            draft=False,
                        )
                    return
        if changed_file_groups[RepoFileType.WEBSITE]:
            self._set_job_run(website_build=True)
        if changed_file_groups[RepoFileType.TEST]:
            self._set_job_run(package_test_local=True)
        if changed_file_groups[RepoFileType.PACKAGE]:
            self._set_job_run(
                package_build=True,
                package_lint=True,
                package_test_local=True,
                website_build=True,
                package_publish_testpypi=True,
            )
        elif any(
            filepath in changed_file_groups[RepoFileType.DYNAMIC]
            for filepath in (
                RelativePath.file_python_pyproject,
                RelativePath.file_python_manifest,
            )
        ):
            self._set_job_run(
                package_build=True,
                package_lint=True,
                package_test_local=True,
                package_publish_testpypi=True,
            )
        if self._job_run_flag["package_publish_testpypi"]:
            issue_labels = [
                label["name"] for label in self._gh_api.issue_labels(number=self._branch.suffix[0])
            ]
            final_commit_type = self._metadata_main.get_issue_data_from_labels(issue_labels).group_data
            if final_commit_type.group == CommitGroup.PRIMARY_CUSTOM or final_commit_type.action in (
                PrimaryActionCommitType.WEBSITE,
                PrimaryActionCommitType.META,
            ):
                self._set_job_run(package_publish_testpypi=False)
                return
            self._git_head.fetch_remote_branches_by_name(branch_names=self._branch.suffix[1])
            ver_last_target, _ = self._get_latest_version(branch=self._branch.suffix[1])
            ver_last_dev, _ = self._get_latest_version(dev_only=True)
            if ver_last_target.pre:
                next_ver = ver_last_target.next_post
                if not ver_last_dev or (
                    ver_last_dev.release != next_ver.release or ver_last_dev.pre != next_ver.pre
                ):
                    dev = 0
                else:
                    dev = (ver_last_dev.dev or -1) + 1
                next_ver_str = f"{next_ver}.dev{dev}"
            else:
                next_ver = self._get_next_version(ver_last_target, final_commit_type.action)
                next_ver_str = str(next_ver)
                if final_commit_type.action != PrimaryActionCommitType.RELEASE_POST:
                    next_ver_str += f".a{self._branch.suffix[0]}"
                if not ver_last_dev:
                    dev = 0
                elif final_commit_type.action == PrimaryActionCommitType.RELEASE_POST:
                    if ver_last_dev.post is not None and ver_last_dev.post == next_ver.post:
                        dev = ver_last_dev.dev + 1
                    else:
                        dev = 0
                elif ver_last_dev.pre is not None and ver_last_dev.pre == ("a", self._branch.suffix[0]):
                    dev = ver_last_dev.dev + 1
                else:
                    dev = 0
                next_ver_str += f".dev{dev}"
            self._tag_version(
                ver=PEP440SemVer(next_ver_str),
                msg=f"Developmental release (issue: #{self._branch.suffix[0]}, target: {self._branch.suffix[1]})",
            )
        return

    def _run_branch_edited_other(self):
        changed_file_groups = self._action_file_change_detector()
        for file_type in (RepoFileType.SUPERMETA, RepoFileType.META, RepoFileType.DYNAMIC):
            if changed_file_groups[file_type]:
                self._action_meta()
                break
        else:
            self._metadata_branch = read_from_json_file(path_root="repo_self", logger=self._logger)
        self._action_hooks()
        if changed_file_groups[RepoFileType.WEBSITE]:
            self._set_job_run(website_build=True)
        if changed_file_groups[RepoFileType.TEST]:
            self._set_job_run(package_test_local=True)
        if changed_file_groups[RepoFileType.PACKAGE]:
            self._set_job_run(
                package_build=True,
                package_lint=True,
                package_test_local=True,
                website_build=True,
            )
        elif any(
            filepath in changed_file_groups[RepoFileType.DYNAMIC]
            for filepath in (
                RelativePath.file_python_pyproject,
                RelativePath.file_python_manifest,
            )
        ):
            self._set_job_run(
                package_build=True,
                package_lint=True,
                package_test_local=True,
            )
        return

    def _run_branch_deleted(self):
        return

    def _run_tag(self):
        action = self._context.payload.action
        if action == WorkflowTriggeringAction.CREATED:
            self._run_tag_created()
        elif action == WorkflowTriggeringAction.DELETED:
            self._run_tag_deleted()
        elif action == WorkflowTriggeringAction.EDITED:
            self._run_tag_edited()
        else:
            _helpers.error_unsupported_triggering_action(event_name="push", action=action, logger=self._logger)

    def _run_tag_created(self):
        return

    def _run_tag_deleted(self):
        return

    def _run_tag_edited(self):
        return

    def _config_repo(self):
        data = self._metadata_main.repo__config | {
            "has_issues": True,
            "allow_squash_merge": True,
            "squash_merge_commit_title": "PR_TITLE",
            "squash_merge_commit_message": "PR_BODY",
        }
        topics = data.pop("topics")
        self._gh_api_admin.repo_update(**data)
        self._gh_api_admin.repo_topics_replace(topics=topics)
        if not self._gh_api_admin.actions_permissions_workflow_default()["can_approve_pull_request_reviews"]:
            self._gh_api_admin.actions_permissions_workflow_default_set(can_approve_pull_requests=True)
        return

    def _config_repo_pages(self) -> None:
        """Activate GitHub Pages (source: workflow) if not activated, update custom domain."""
        if not self._gh_api.info["has_pages"]:
            self._gh_api_admin.pages_create(build_type="workflow")
        cname = self._metadata_main.web__base_url
        try:
            self._gh_api_admin.pages_update(
                cname=cname.removeprefix("https://").removeprefix("http://") if cname else "",
                build_type="workflow",
            )
        except WebAPIError as e:
            self._logger.warning(f"Failed to update custom domain for GitHub Pages", str(e))
        if cname:
            try:
                self._gh_api_admin.pages_update(https_enforced=cname.startswith("https://"))
            except WebAPIError as e:
                self._logger.warning(f"Failed to update HTTPS enforcement for GitHub Pages", str(e))
        return

    def _config_repo_labels_reset(self):
        for label in self._gh_api.labels:
            self._gh_api.label_delete(label["name"])
        for label_name, label_data in self._metadata_main.label__compiled.items():
            self._gh_api.label_create(
                name=label_name, description=label_data["description"], color=label_data["color"]
            )
        return

    def _config_repo_branch_names(self) -> dict:
        if not self._metadata_main_before:
            self._logger.error("Cannot update branch names as no previous metadata is available.")
        before = self._metadata_main_before.branch
        after = self._metadata_main.branch
        old_to_new_map = {}
        if before["default"]["name"] != after["default"]["name"]:
            self._gh_api_admin.branch_rename(
                old_name=before["default"]["name"], new_name=after["default"]["name"]
            )
            old_to_new_map[before["default"]["name"]] = after["default"]["name"]
        branches = self._gh_api_admin.branches
        branch_names = [branch["name"] for branch in branches]
        for group_name in ("release", "dev", "ci_pull"):
            prefix_before = before["group"][group_name]["prefix"]
            prefix_after = after["group"][group_name]["prefix"]
            if prefix_before != prefix_after:
                for branch_name in branch_names:
                    if branch_name.startswith(prefix_before):
                        new_name = f"{prefix_after}{branch_name.removeprefix(prefix_before)}"
                        self._gh_api_admin.branch_rename(old_name=branch_name, new_name=new_name)
                        old_to_new_map[branch_name] = new_name
        return old_to_new_map
