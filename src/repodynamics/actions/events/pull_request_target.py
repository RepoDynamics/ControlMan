class PullRequestTargetEventHandler:
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
