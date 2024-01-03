"""Event handler for comments on issues and pull requests."""


from github_contexts import GitHubContext
from github_contexts.github.payloads.issue_comment import IssueCommentPayload
from github_contexts.github.enums import ActionType

from repodynamics.actions.events._base import EventHandler
from repodynamics.datatype import Branch, TemplateType, RepoDynamicsBotCommand, BranchType
from repodynamics.logger import Logger
from repodynamics.actions import _helpers


class IssueCommentEventHandler(EventHandler):
    """Event handler for the `issue_comment` event type.

    This event is triggered when a comment on an issue or pull request
    is created, edited, or deleted.
    """

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
        self._payload: IssueCommentPayload = self._context.event
        self._comment = self._payload.comment
        self._issue = self._payload.issue

        self._command_runner_pull = {
            RepoDynamicsBotCommand.CREATE_DEV_BRANCH: self._create_dev_branch,
        }
        self._command_runner_issue = {}
        return

    def run_event(self):
        action = self._payload.action
        is_pull = self._payload.is_on_pull
        if action is ActionType.CREATED:
            self._run_created_pull() if is_pull else self._run_created_issue()
        elif action is ActionType.EDITED:
            self._run_edited_pull() if is_pull else self._run_edited_issue()
        elif action is ActionType.DELETED:
            self._run_deleted_pull() if is_pull else self._run_deleted_issue()
        else:
            self.error_unsupported_triggering_action()
        return

    def _run_created_pull(self):
        command = self._process_comment()
        if not command:
            return
        command_type, kwargs = command
        if command_type not in self._command_runner_pull:
            return
        self._command_runner_pull[command_type](kwargs)
        return

    def _run_edited_pull(self):
        self._run_created_pull()
        return

    def _run_deleted_pull(self):
        return

    def _run_created_issue(self):
        command = self._process_comment()
        if not command:
            return
        command_type, kwargs = command
        if command_type not in self._command_runner_issue:
            return
        self._command_runner_issue[command_type](kwargs)
        return

    def _run_edited_issue(self):
        self._run_created_issue()
        return

    def _run_deleted_issue(self):
        return

    def _create_dev_branch(self, kwargs: dict):
        if "task" not in kwargs or not isinstance(kwargs["task"], int):
            self._logger.error("Invalid task number.")
            return
        task_nr = kwargs["task"]
        pull_data = self._gh_api.pull(self._issue.number)
        head_branch = self.resolve_branch(branch_name=pull_data["head"]["ref"])
        if head_branch.type is not BranchType.IMPLEMENT:
            self._logger.error("Invalid branch type.")
            return
        dev_branch_name = self.create_branch_name_development(
            issue_nr=head_branch.suffix[0],
            base_branch_name=head_branch.suffix[1],
            task_nr=task_nr,
        )
        _, branch_names = self._git_base.get_all_branch_names()
        if dev_branch_name in branch_names:
            self._logger.error("Branch already exists.")
            return
        tasklist = self._extract_tasklist(body=self._issue.body)
        if len(tasklist) < task_nr:
            self._logger.error("Invalid task number.")
            return
        self._git_base.fetch_remote_branches_by_name(branch_names=head_branch.name)
        self._git_base.checkout(branch=head_branch.name)
        self._git_base.checkout(branch=dev_branch_name, create=True)
        self._git_base.commit(
            message=(
                f"init: Create development branch '{dev_branch_name}' "
                f"from implementation branch '{head_branch.name}' for task {task_nr}"
            ),
            allow_empty=True,
        )
        self._git_base.push(target="origin", set_upstream=True)
        task = tasklist[task_nr - 1]
        sub_tasklist_str = self._write_tasklist(entries=[task])
        pull_body = (
            f"This pull request implements task {task_nr} of the "
            f"pull request #{self._issue.number}:\n\n"
            f"{self._MARKER_TASKLIST_START}\n{sub_tasklist_str}\n{self._MARKER_TASKLIST_END}"
        )
        pull_data = self._gh_api.pull_create(
            head=dev_branch_name,
            base=head_branch.name,
            title=task["summary"],
            body=pull_body,
            maintainer_can_modify=True,
            draft=True,
        )
        self._gh_api.issue_labels_set(number=pull_data["number"], labels=self._issue.label_names)
        return

    def _process_comment(self):
        body = self._comment.body
        if not body.startswith("@RepoDynamicsBot"):
            return
        command_str = body.removeprefix("@RepoDynamicsBot").strip()
        command_name, kwargs = _helpers.parse_function_call(command_str)
        command_type = RepoDynamicsBotCommand(command_name)
        return command_type, kwargs


