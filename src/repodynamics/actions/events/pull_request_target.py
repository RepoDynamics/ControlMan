class PullRequestTargetEventHandler:

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
        self._payload: IssuesPayload = self._context.payload
        return

    def run(self):
        if action == WorkflowTriggeringAction.OPENED:
            self.event_pull_target_opened()
        elif action == WorkflowTriggeringAction.REOPENED:
            self.event_pull_target_reopened()
        elif action == WorkflowTriggeringAction.SYNCHRONIZE:
            self.event_pull_target_synchronize()
        else:
            self.logger.error(action_err_msg, action_err_details)

    def event_pull_target_opened(self):
        return

    def event_pull_target_reopened(self):
        return

    def event_pull_target_synchronize(self):
        return

    def event_pull_request_target(self):
        self.set_job_run("website_rtd_preview")
        return
