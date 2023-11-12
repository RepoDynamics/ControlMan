from repodynamics.logger import Logger
from repodynamics.actions.context_manager import ContextManager

from repodynamics.actions.events.issue_comment import IssueCommentEventHandler
from repodynamics.actions.events.issues import IssuesEventHandler
from repodynamics.actions.events.pull_request import PullRequestEventHandler
from repodynamics.actions.events.pull_request_target import PullRequestTargetEventHandler
from repodynamics.actions.events.push import PushEventHandler
from repodynamics.actions.events.schedule import ScheduleEventHandler
from repodynamics.actions.events.workflow_dispatch import WorkflowDispatchEventHandler


# class Init:
#
#     def __init__(
#         self,
#         context: dict,
#         admin_token: str,
#         logger: Logger | None = None,
#     ):
#         self.state: StateManager | None = None
#         self.metadata_branch: dict = {}
#         self.metadata_branch_before: dict = {}
#         self.changed_files: dict[RepoFileType, list[str]] = {}
#         return
#
#     def categorize_labels(self, label_names: list[str]):
#         label_dict = {
#             label_data["name"]: label_key
#             for label_key, label_data in self.metadata_main["label"]["compiled"].items()
#         }
#         out = {}
#         for label in label_names:
#             out[label] = label_dict[label]
#         return out


def init(
    context: dict,
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
    context_manager = ContextManager(github_context=context)
    args = {"context_manager": context_manager, "admin_token": admin_token, "logger": logger}
    event_name = context_manager.github.event_name
    if event_name == "issues":
        event_manager = IssuesEventHandler(**args)
    elif event_name == "issue_comment":
        event_manager = IssueCommentEventHandler(**args)
    elif event_name == "pull_request":
        event_manager = PullRequestEventHandler(**args)
    elif event_name == "pull_request_target":
        event_manager = PullRequestTargetEventHandler(**args)
    elif event_name == "push":
        event_manager = PushEventHandler(**args)
    elif event_name == "schedule":
        event_manager = ScheduleEventHandler(**args)
    elif event_name == "workflow_dispatch":
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
        logger.error(f"Event '{event_name}' is not supported.")
    return event_manager.run()
