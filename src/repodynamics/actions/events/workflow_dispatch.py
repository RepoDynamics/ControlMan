from github_contexts import GitHubContext

from repodynamics.datatype import WorkflowDispatchInput
from repodynamics.actions.events._base import EventHandler
from repodynamics.datatype import InitCheckAction, TemplateType
from repodynamics.logger import Logger


class WorkflowDispatchEventHandler(EventHandler):

    def __init__(
        self,
        template_type: TemplateType,
        context_manager: GitHubContext,
        admin_token: str,
        package_build: bool,
        package_lint: bool,
        package_test: bool,
        website_build: bool,
        meta_sync: str,
        hooks: str,
        website_announcement: str,
        website_announcement_msg: str,
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
        for arg_name, arg in (("meta_sync", meta_sync), ("hooks", hooks)):
            if arg not in ["report", "amend", "commit", "pull", "none", ""]:
                raise ValueError(
                    f"Invalid input argument for '{arg_name}': "
                    f"Expected one of 'report', 'amend', 'commit', 'pull', or 'none', but got '{arg}'."
                )
        self._input_package_build = package_build
        self._input_package_lint = package_lint
        self._input_package_test = package_test
        self._input_website_build = website_build
        self._input_meta_sync = InitCheckAction(meta_sync or "none")
        self._input_hooks = InitCheckAction(hooks or "none")
        self._input_website_announcement = website_announcement
        self._input_website_announcement_msg = website_announcement_msg
        return

    def event_workflow_dispatch(self):
        if self.context.ref_is_main:
            self.state
        self.action_website_announcement_update()
        self._action_meta(action=self._dispatch_inputs.meta)
        self._action_hooks()
        return
