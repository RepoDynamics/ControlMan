import github_contexts
from github_contexts.github.enums import EventType
import actionman

from repodynamics.action.events.issue_comment import IssueCommentEventHandler
from repodynamics.action.events.issues import IssuesEventHandler
from repodynamics.action.events.pull_request import PullRequestEventHandler
from repodynamics.action.events.pull_request_target import PullRequestTargetEventHandler
from repodynamics.action.events.push import PushEventHandler
from repodynamics.action.events.schedule import ScheduleEventHandler
from repodynamics.action.events.workflow_dispatch import WorkflowDispatchEventHandler
from repodynamics.datatype import TemplateType


def action():
    logger = actionman.logger.create(output_html_filepath="log.html")
    logger.section("Action")
    logger.section("Initialize")
    inputs = actionman.io.read_environment_variables(
        ("TEMPLATE_TYPE", str, True, False),
        ("GITHUB_CONTEXT", dict, True, False),
        ("PATH_REPO_BASE", str, True, False),
        ("PATH_REPO_HEAD", str, True, False),
        ("ADMIN_TOKEN", str, False, True),
        name_prefix="RD_PROMAN__",
        logger=logger,
        log_section_name="Read Inputs"
    )
    template_type = get_template_type(input_template_type=inputs.pop("TEMPLATE_TYPE"), logger=logger)
    context_manager = github_contexts.context_github(context=inputs.pop("GITHUB_CONTEXT"))
    event_handler_class = get_event_handler(event=context_manager.event_name, logger=logger)
    event_handler = event_handler_class(
        template_type=template_type,
        context_manager=context_manager,
        admin_token=inputs["ADMIN_TOKEN"] or "",
        path_root_base=inputs["PATH_REPO_BASE"],
        path_root_head=inputs["PATH_REPO_HEAD"],
        logger=logger
    )
    try:
        outputs, env_vars, summary = event_handler.run()
    except Exception as e:
        logger.critical(title=f"An unexpected error occurred", message=str(e))
        raise e  # This will never be reached, but is required to satisfy the type checker and IDE
    logger.section("Outputs & Summary")
    if outputs:
        actionman.io.write_github_outputs(outputs, logger=logger)
    if env_vars:
        actionman.io.write_github_outputs(env_vars, to_env=True, logger=logger)
    if summary:
        actionman.io.write_github_summary(content=summary, logger=logger)
    return


def get_template_type(input_template_type: str, logger: actionman.logger.Logger) -> TemplateType:
    """Parse and verify the input template type."""
    logger.section("Verify Template Type", group=True)
    try:
        template_type = TemplateType(input_template_type)
    except ValueError:
        supported_templates = ", ".join([f"'{enum.value}'" for enum in TemplateType])
        logger.critical(
            title="Template type verification failed",
            message=f"Expected one of {supported_templates}, but got '{input_template_type}'.",
        )
        raise ValueError()  # This will never be reached, but is required to satisfy the type checker and IDE
    logger.info(title="Template type", message=template_type.value)
    logger.section_end()
    return template_type


def get_event_handler(event: EventType, logger: actionman.logger.Logger):
    logger.section("Verify Triggering Event", group=True)
    event_to_handler = {
        EventType.ISSUES: IssuesEventHandler,
        EventType.ISSUE_COMMENT: IssueCommentEventHandler,
        EventType.PULL_REQUEST: PullRequestEventHandler,
        EventType.PULL_REQUEST_TARGET: PullRequestTargetEventHandler,
        EventType.PUSH: PushEventHandler,
        EventType.SCHEDULE: ScheduleEventHandler,
        EventType.WORKFLOW_DISPATCH: WorkflowDispatchEventHandler,
    }
    handler = event_to_handler.get(event)
    if handler:
        logger.info(title="Event handler", message=handler.__name__)
        logger.section_end()
        return handler
    supported_events = ", ".join([f"'{enum.value}'" for enum in event_to_handler.keys()])
    logger.critical(
        title="Unsupported workflow triggering event",
        message=f"Expected one of {supported_events}, but got '{event.value}'.",
    )
    raise ValueError()  # This will never be reached, but is required to satisfy the type checker and IDE


if __name__ == "__main__":
    action()
