import sys
import traceback

import github_contexts
from github_contexts.github.enums import EventType
import actionman

from repodynamics.actions.events.issue_comment import IssueCommentEventHandler
from repodynamics.actions.events.issues import IssuesEventHandler
from repodynamics.actions.events.pull_request import PullRequestEventHandler
from repodynamics.actions.events.pull_request_target import PullRequestTargetEventHandler
from repodynamics.actions.events.push import PushEventHandler
from repodynamics.actions.events.schedule import ScheduleEventHandler
from repodynamics.actions.events.workflow_dispatch import WorkflowDispatchEventHandler
from repodynamics.datatype import TemplateType


EVENT_HANDLER = {
        EventType.ISSUES: IssuesEventHandler,
        EventType.ISSUE_COMMENT: IssueCommentEventHandler,
        EventType.PULL_REQUEST: PullRequestEventHandler,
        EventType.PULL_REQUEST_TARGET: PullRequestTargetEventHandler,
        EventType.PUSH: PushEventHandler,
        EventType.SCHEDULE: ScheduleEventHandler,
        EventType.WORKFLOW_DISPATCH: WorkflowDispatchEventHandler,
    }


def action():
    logger = actionman.log.logger(output_html_filepath="log.html")
    logger.section("Action")
    inputs = actionman.io.read_environment_variables(
        ("TEMPLATE_TYPE", str, False, True),
        ("GITHUB_CONTEXT", dict, False, True),
        ("PATH_REPO_BASE", str, False, True),
        ("PATH_REPO_HEAD", str, False, True),
        ("ADMIN_TOKEN", str, True, False),
        name_prefix="RD_PROMAN__",
        logger=logger
    )
    logger.section("Initialization")
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
        sys.stdout.flush()  # Flush stdout buffer before printing the exception
        logger.error(f"An unexpected error occurred: {e}", traceback.format_exc())
    logger.section("Outputs & Summary")
    if outputs:
        actionman.io.write_github_outputs(outputs, logger=logger)
    if env_vars:
        actionman.io.write_github_outputs(env_vars, to_env=True, logger=logger)
    if summary:
        actionman.io.write_github_summary(content=summary, logger=logger)
    return


def get_template_type(input_template_type: str, logger: actionman.log.Logger) -> TemplateType:
    try:
        template_type = TemplateType(input_template_type)
        status = actionman.log.LogStatus.PASS
        summary = f"Input template type was successfully recognized as '{template_type.value}'."
    except ValueError:
        status = actionman.log.LogStatus.FAIL
        summary = f"Input template type was not recognized."
    logger.entry(
        status=actionman.log.LogStatus.PASS,
        title="Verify input template type",
        summary=summary,
        details=[f"Input: {input_template_type}"],
    )
    if status is actionman.log.LogStatus.FAIL:
        supported_templates = ", ".join([f"'{enum.value}'" for enum in TemplateType])
        logger.error(
            summary=f"Failed to recognize input template type '{input_template_type}'.",
            details=f"Expected one of: {supported_templates}."
        )
    return template_type


def get_event_handler(event: EventType, logger: actionman.log.Logger):
    handler = EVENT_HANDLER.get(event)
    if handler:
        status = actionman.log.LogStatus.PASS
        summary = f"Event '{event.value}' was successfully recognized."
    else:
        status = actionman.log.LogStatus.FAIL
        summary = f"Event '{event.value}' is not supported."
    logger.entry(
        status=status,
        title="Verify workflow triggering event",
        summary=summary,
    )
    if status is actionman.log.LogStatus.FAIL:
        supported_events = ", ".join([f"'{enum.value}'" for enum in EVENT_HANDLER.keys()])
        logger.error(
            summary=f"Unsupported workflow triggering event '{event.value}'.",
            details=f"Expected one of: {supported_events}."
        )
    return handler


if __name__ == "__main__":
    action()
