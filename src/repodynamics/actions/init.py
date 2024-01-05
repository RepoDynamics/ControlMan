import github_contexts
from github_contexts.github.enums import EventType

from repodynamics.actions.events.issue_comment import IssueCommentEventHandler
from repodynamics.actions.events.issues import IssuesEventHandler
from repodynamics.actions.events.pull_request import PullRequestEventHandler
from repodynamics.actions.events.pull_request_target import PullRequestTargetEventHandler
from repodynamics.actions.events.push import PushEventHandler
from repodynamics.actions.events.schedule import ScheduleEventHandler
from repodynamics.actions.events.workflow_dispatch import WorkflowDispatchEventHandler
from repodynamics.datatype import TemplateType
from repodynamics.logger import Logger


def init(
    template: str,
    context: dict,
    path_root_base: str,
    path_root_head: str,
    admin_token: str = "",
    package_build: bool = False,
    package_lint: bool = False,
    package_test: bool = False,
    website_build: bool = False,
    meta_sync: str = "none",
    hooks: str = "none",
    website_announcement: str = "",
    website_announcement_msg: str = "",
    logger=None,
):
    logger = logger or Logger("console")
    logger.h1("Initialize RepoDynamics Init Action")
    try:
        template_type = TemplateType(template)
    except ValueError:
        supported_templates = ", ".join([f"'{enum.value}'" for enum in TemplateType])
        logger.error(
            "Invalid input: template",
            f"Expected one of {supported_templates}; got '{template}' instead.",
        )
        return
    context_manager = github_contexts.context_github(context=context)
    args = {
        "template_type": template_type,
        "context_manager": context_manager,
        "path_root_base": path_root_base,
        "path_root_head": path_root_head,
        "admin_token": admin_token,
        "logger": logger
    }
    event = context_manager.event_name
    if event is EventType.ISSUES:
        event_manager = IssuesEventHandler(**args)
    elif event is EventType.ISSUE_COMMENT:
        event_manager = IssueCommentEventHandler(**args)
    elif event is EventType.PULL_REQUEST:
        event_manager = PullRequestEventHandler(**args)
    elif event is EventType.PULL_REQUEST_TARGET:
        event_manager = PullRequestTargetEventHandler(**args)
    elif event is EventType.PUSH:
        event_manager = PushEventHandler(**args)
    elif event is EventType.SCHEDULE:
        event_manager = ScheduleEventHandler(**args)
    elif event is EventType.WORKFLOW_DISPATCH:
        event_manager = WorkflowDispatchEventHandler(
            package_build=package_build,
            package_lint=package_lint,
            package_test=package_test,
            website_build=website_build,
            meta_sync=meta_sync,
            hooks=hooks,
            website_announcement=website_announcement,
            website_announcement_msg=website_announcement_msg,
            **args,
        )
    else:
        logger.error(f"Event '{event}' is not supported.")
    return event_manager.run()
