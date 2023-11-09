import shutil

from repodynamics.meta import read_from_json_file
from repodynamics.actions.context_manager import ContextManager
from repodynamics.actions.init import ModifyingEventHandler
from repodynamics.logger import Logger
from repodynamics.datatype import WorkflowTriggeringAction, EventType, BranchType, Branch, InitCheckAction
from repodynamics.meta.meta import Meta
from repodynamics import _util
from repodynamics.actions import _helpers


class PushEventHandler(ModifyingEventHandler):

    def __init__(
        self,
        context_manager: ContextManager,
        admin_token: str,
        logger: Logger | None = None,
    ):
        super().__init__(context_manager=context_manager, admin_token=admin_token, logger=logger)
        return

    def run(self):
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
            _helpers.error_unsupported_triggering_action(
                event_name="push", action=action, logger=self._logger
            )
        return

    def _run_branch_created(self):
        if self._context.ref_is_main:
            if not self._git_self.get_tags():
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
        meta = Meta(
            path_root="repo_self",
            github_token=self._context.github.token,
            logger=self._logger
        )
        metadata = read_from_json_file(path_root="repo_self", logger=self._logger)
        shutil.rmtree(meta.input_path.dir_source)
        shutil.rmtree(meta.input_path.dir_tests)
        shutil.rmtree(meta.input_path.dir_local)
        for item in meta.input_path.dir_meta.iterdir():
            if item.is_dir():
                if item.name not in ("__examples__", "__new__"):
                    shutil.rmtree(item)
            else:
                item.unlink()
        path_meta_new = meta.input_path.dir_meta / "__new__"
        for item in path_meta_new.iterdir():
            item.rename(meta.input_path.dir_meta / item.name)
        path_meta_new.rmdir()
        (meta.input_path.dir_github / ".repodynamics_meta_path.txt").unlink(missing_ok=True)
        for path_dynamic_file in meta.paths.all_files:
            path_dynamic_file.unlink(missing_ok=True)
        for changelog_data in metadata.changelog.values():
            path_changelog_file = meta.paths.root / changelog_data["path"]
            path_changelog_file.unlink(missing_ok=True)
        with open(meta.paths.dir_website / "announcement.html", "w") as f:
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

    def _run_branch_edited(self):
        if self._context.ref_is_main:
            return self._run_branch_edited_main()
        self._metadata_main = read_from_json_file(path_root="repo_self", logger=self._logger)
        branch = self._metadata_main.get_branch_info_from_name(branch_name=self._context.github.ref_name)
        if branch.type == BranchType.RELEASE:
            return self._run_branch_edited_release()
        elif branch.type == BranchType.DEV:
            return self._run_branch_edited_dev()
        elif branch.type == BranchType.CI_PULL:
            return self._run_branch_edited_ci_pull()
        else:
            return self._run_branch_edited_other()

    def _run_branch_edited_main(self):
        if not self._git_self.get_tags():
            # The repository is in the initialization phase
            head_commit_msg = self._context.payload.head_commit_message
            if head_commit_msg == "init":
                # User is signaling the end of initialization phase
                return self._run_first_release()
            # User is still setting up the repository (still in initialization phase)
            return self._run_init_phase()
        self._metadata_before = read_from_json_file(
            path_root="repo_self",
            commit_hash=self._context.hash_before,
            git=self._git_self,
            logger=self._logger
        )
        if not self._metadata_before:
            return self._run_existing_repository_initialized()
        return self._run_branch_modified_main()

    def _run_init_phase(self):
        self._meta = Meta(
            path_root="repo_self",
            github_token=self._context.github.token,
            logger=self._logger
        )
        self._metadata_main = self._meta.read_metadata_full()
        self._action_meta(action=InitCheckAction.AMEND)

        repo_config = RepoConfigAction(
            workflow_api=self.gh_api,
            admin_api=self.gh_api_admin,
            metadata=metadata_new,
            metadata_before=self.metadata_main,
            logger=self.logger,
        )
        repo_config.update_repo_settings()
        repo_config.update_pages_settings()
        repo_config.replace_repo_labels()

        self.state = StateManager(
            metadata_main=self.metadata_main,
            metadata_branch=self.metadata_main,
            context_manager=self.context,
            git=self.git,
            logger=self.logger,
        )
        self._action_meta(action=InitCheckAction.AMEND, meta=self.meta_main, state=self.state)

        repo_config.update_branch_names()
        return

    def _run_first_release(self):
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
        self.state_manager.tag_version(ver="0.0.0", msg="First release")

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

    def _run_branch_edited_default(self):
        self.metadata_branch = self.meta_main.read_metadata_full()
        if not self.tags_on_main:
            # The repository has just been created from the template
            head_commit_msg = self.context.push_commit_head_message
            if head_commit_msg == "init":
                # User is signaling the end of initialization phase
                return self._run_first_release()
            # User is still setting up the repository (still in initialization phase)
            return self._run_init_phase()
        metadata_before = self.git.file_at_hash(
            commit_hash=self.context.hash_before,
            path=self.meta_main.paths.metadata.rel_path
        )
        if not metadata_before:
            return self._run_existing_repository_initialized()
        self.metadata_branch_before = meta.read_from_json_string(
            content=metadata_before,
            logger=self.logger
        )
        self._run_branch_modified_main()
        return

    def _run_existing_repository_initialized(self):
        return


    def _run_branch_modified_main(self):
        self.metadata_branch_before = self.git.file_at_hash(
            commit_hash=self.hash_before, path=self.meta_main.paths.metadata.rel_path
        )
        self.action_repo_labels_sync()

        self.action_file_change_detector()
        for job_id in ("package_build", "package_test_local", "package_lint", "website_build"):
            self.set_job_run(job_id)

        self.action_meta(action=action = metadata_raw["workflow"]["init"]["meta_check_action"][self.event_type.value])
        self._action_hooks()
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
            parent_commit_url=self._gh_link.commit(self.hash_before),
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

    def _run_branch_edited_release(self):
        self.event_type = EventType.PUSH_RELEASE
        action_hooks = self.metadata["workflow"]["init"]["hooks_check_action"][self.event_type.value]
        return

    def _run_branch_edited_dev(self):
        self.event_type = EventType.PUSH_DEV
        self.action_meta()
        self._action_hooks()
        return

    def _run_branch_edited_other(self):
        self.event_type = EventType.PUSH_OTHER
        self.action_meta()
        self._action_hooks()
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
            _helpers.error_unsupported_triggering_action(
                event_name="push", action=action, logger=self._logger
            )

    def _run_tag_created(self):
        return

    def _run_tag_deleted(self):
        return

    def _run_tag_edited(self):
        return