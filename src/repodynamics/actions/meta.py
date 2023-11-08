import pylinks
from pylinks.api.github import Repo
from markitup import html

from repodynamics.actions.context import ContextManager
from repodynamics.actions.state_manager import StateManager
from repodynamics.meta.meta import Meta
from repodynamics.logger import Logger
from repodynamics.datatype import InitCheckAction
from repodynamics.git import Git


class MetaAction:
    
    def __init__(
        self, 
        context_manager: ContextManager,
        gh_link: pylinks.site.github.Repo,
        gh_api: Repo,
        git: Git,
        logger: Logger | None = None
    ):
        self._context = context_manager
        self._gh_link = gh_link
        self._gh_api = gh_api
        self._git = git
        self._logger = logger or Logger()
        return

    def __call__(self, action: InitCheckAction, meta: Meta, state: StateManager):
        name = "Meta Sync"
        self._logger.h1(name)
        self._logger.input(f"Action: {action.value}")

        action = metadata_raw["workflow"]["init"]["meta_check_action"][self.event_type.value]
        self._logger.input(
            f"Read action from 'meta.workflow.init.meta_check_action.{self.event_type.value}': {action}"
        )

        if action == "none":
            state.add_summary(
                name=name,
                status="skip",
                oneliner="Meta synchronization is disabled for this event type❗",
            )
            self._logger.skip("Meta synchronization is disabled for this event type; skip❗")
            return

        if self.event_name == "pull_request" and action != "fail" and not self.pull_is_internal:
            self._logger.attention(
                "Meta synchronization cannot be performed as pull request is from a forked repository; "
                f"switching action from '{action}' to 'fail'."
            )
            action = "fail"

        if action == "pull":
            pr_branch = state.switch_to_ci_branch("meta")

        self.metadata, self.metadata_ci = meta.read_metadata_full()
        self.meta_results, self.meta_changes, meta_summary = meta.compare_files()
        meta_changes_any = any(any(change.values()) for change in self.meta_changes.values())

        # Push/amend/pull if changes are made and action is not 'fail' or 'report'
        if action not in ["fail", "report"] and meta_changes_any:
            meta.apply_changes()
            if action == "amend":
                state.commit(stage="all", amend=True, push=True)
            else:
                commit_msg = CommitMsg(
                    typ=self.metadata["commit"]["secondary_action"]["meta_sync"]["type"],
                    title="Sync dynamic files with meta content",
                )
                state.commit(message=str(commit_msg), stage="all", push=True, set_upstream=action == "pull")
            if action == "pull":
                pull_data = self._gh_api.pull_create(
                    head=self._git.current_branch_name(),
                    base=self._context.ref_name,
                    title=commit_msg.summary,
                    body=commit_msg.body,
                )
                state.switch_to_original_branch()

        if not meta_changes_any:
            oneliner = "All dynamic files are in sync with meta content."
            self._logger.success(oneliner)
        else:
            oneliner = "Some dynamic files were out of sync with meta content."
            if action in ["pull", "commit", "amend"]:
                oneliner += " These were resynchronized and applied to "
                if action == "pull":
                    link = html.a(href=pull_data["url"], content=pull_data["number"])
                    oneliner += f"branch '{pr_branch}' and a pull request ({link}) was created."
                else:
                    link = html.a(
                        href=str(self._gh_link.commit(state.hash_latest)),
                        content=state.hash_latest[:7]
                    )
                    oneliner += "the current branch " + (
                        f"in a new commit (hash: {link})"
                        if action == "commit"
                        else f"by amending the latest commit (new hash: {link})"
                    )
        state.add_summary(
            name=name,
            status="fail" if meta_changes_any and action in ["fail", "report", "pull"] else "pass",
            oneliner=oneliner,
            details=meta_summary
        )
        return
