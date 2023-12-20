from repodynamics.actions.events._base import NonModifyingEventHandler
from repodynamics.actions.context_manager import ContextManager
from repodynamics.datatype import Branch, TemplateType, WorkflowTriggeringAction, RepoDynamicsBotCommand
from repodynamics.logger import Logger
from repodynamics.actions.context_manager import IssueCommentPayload
from repodynamics.actions import _helpers

class IssueCommentEventHandler(NonModifyingEventHandler):

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
        self._payload: IssueCommentPayload = self._context.payload

        self._commands_pull = {
            RepoDynamicsBotCommand.CREATE_DEV_BRANCH: self._create_dev_branch,
        }
        return

    def run_event(self):
        action = self._payload.action
        is_pull = self._payload.is_pull_comment
        if action is WorkflowTriggeringAction.CREATED:
            self._run_pull_created() if is_pull else self._issue_created()
        elif action is WorkflowTriggeringAction.EDITED:
            self._run_pull_edited() if is_pull else self._run_issue_edited()
        elif action is WorkflowTriggeringAction.DELETED:
            self._run_pull_deleted() if is_pull else self._run_issue_deleted()
        else:
            _helpers.error_unsupported_triggering_action(
                event_name="issue_comment", action=action, logger=self._logger
            )
        return

    def _run_pull_created(self):
        command = self._process_comment()
        if not command:
            return
        command_name, kwargs = command
        command_type = RepoDynamicsBotCommand(command_name)
        if command_type not in self._commands_pull:
            return
        self._commands_pull[command_type](**kwargs)
        return

    def _run_pull_edited(self):
        self._run_pull_created()
        return

    def _run_pull_deleted(self):
        return

    def _issue_created(self):
        command = self._process_comment()
        if not command:
            return
        return

    def _run_issue_edited(self):
        self._issue_created()
        return

    def _run_issue_deleted(self):
        return

    def _create_dev_branch(self, task_nr: int):


    def _process_comment(self):
        body = self._payload.body
        if not body.startswith("@RepoDynamicsBot"):
            return
        command_str = body.removeprefix("@RepoDynamicsBot").strip()
        command_name, kwargs = _helpers.parse_function_call(command_str)
        return command_name, kwargs


