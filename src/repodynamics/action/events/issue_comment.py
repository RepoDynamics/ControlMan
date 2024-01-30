"""Event handler for comments on issues and pull requests."""


from github_contexts import GitHubContext
from github_contexts.github.payloads.issue_comment import IssueCommentPayload
from github_contexts.github.enums import ActionType
from actionman.logger import Logger

from repodynamics.action.events._base import EventHandler
from repodynamics.datatype import TemplateType, RepoDynamicsBotCommand, BranchType
from repodynamics.action import _helpers


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
        path_repo_base: str,
        path_repo_head: str,
        logger: Logger,
    ):
        super().__init__(
            template_type=template_type,
            context_manager=context_manager,
            admin_token=admin_token,
            path_repo_base=path_repo_base,
            path_repo_head=path_repo_head,
            logger=logger
        )
        self._payload: IssueCommentPayload = self._context.event
        self._comment = self._payload.comment
        self._issue = self._payload.issue

        self._command_runner = {
            "pull": {
                RepoDynamicsBotCommand.CREATE_DEV_BRANCH: self._create_dev_branch,
            },
            "issue": {}
        }
        return

    def run_event(self):
        action = self._payload.action
        self._logger.info(title="Action", message=action.value)
        is_pull = self._payload.is_on_pull
        self._logger.info(title="On pull request", message=str(is_pull))
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
        self._process_comment()
        return

    def _run_edited_pull(self):
        self._process_comment()
        return

    def _run_deleted_pull(self):
        self._logger.notice("No action for deleted pull request comments.")
        return

    def _run_created_issue(self):
        self._process_comment()
        return

    def _run_edited_issue(self):
        self._process_comment()
        return

    def _run_deleted_issue(self):
        self._logger.notice("No action for deleted issue comments.")
        return

    def _create_dev_branch(self, kwargs: dict):
        self._logger.section("Create Development Branch", group=True)
        if "task" not in kwargs:
            self._logger.error("Argument 'task' is missing.")
            self._logger.section_end()
            return
        if not isinstance(kwargs["task"], int):
            self._logger.error("Argument 'task' is not an integer.")
            self._logger.section_end()
            return
        task_nr = kwargs["task"]
        pull_data = self._gh_api.pull(self._issue.number)
        head_branch = self.resolve_branch(branch_name=pull_data["head"]["ref"])
        if head_branch.type is not BranchType.IMPLEMENT:
            self._logger.error(title="Invalid branch type", message=head_branch.type.value)
            return
        dev_branch_name = self.create_branch_name_development(
            issue_nr=head_branch.suffix[0],
            base_branch_name=head_branch.suffix[1],
            task_nr=task_nr,
        )
        _, branch_names = self._git_base.get_all_branch_names()
        if dev_branch_name in branch_names:
            self._logger.error(title="Development branch already exists", message=dev_branch_name)
            return
        tasklist = self._extract_tasklist(body=self._issue.body)
        if len(tasklist) < task_nr:
            self._logger.error(
                title="Invalid task number",
                message=f"No task {task_nr} in tasklist; it has only {len(tasklist)} entries."
            )
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
        self._logger.info(title="Created and pushed development branch", message=dev_branch_name)
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
        self._logger.info(title="Created draft pull request", message=pull_data["html_url"])
        self._logger.section_end()
        return

    def _process_comment(self):
        self._logger.section("Process Comment", group=True)
        body = self._comment.body
        if not body.startswith("@RepoDynamicsBot"):
            self._logger.info("Comment is not a command as it does not start with '@RepoDynamicsBot'.")
            return
        command_str = body.removeprefix("@RepoDynamicsBot").strip()
        try:
            command_name, kwargs = _helpers.parse_function_call(command_str)
        except Exception as e:
            self._logger.error("Failed to parse command.", str(e))
            return
        try:
            command_type = RepoDynamicsBotCommand(command_name)
        except ValueError:
            self._logger.error(title="Invalid command name", message=command_name)
            return
        is_pull = self._payload.is_on_pull
        command_runner_map = self._command_runner["pull" if is_pull else "issue"]
        if command_type not in command_runner_map:
            event_name = "pull request" if is_pull else "issue"
            self._logger.error(
                title=f"Unsupported command for {event_name} comments",
                message=f"Command {command_type.value} is not supported for {event_name} comments."
            )
            return
        self._logger.info(title="Command", message=command_type.value)
        self._logger.debug(message="Arguments:", code=str(kwargs))
        self._logger.section_end()
        command_runner_map[command_type](kwargs)
        return
