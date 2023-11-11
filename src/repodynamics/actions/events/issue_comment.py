from repodynamics.actions.events._base import NonModifyingEventHandler


class IssueCommentEventHandler(NonModifyingEventHandler):
    def run(self):
        is_pull = self._context.payload.get("pull_request")
        if is_pull:
            if action == WorkflowTriggeringAction.CREATED:
                self.event_comment_pull_created()
            elif action == WorkflowTriggeringAction.EDITED:
                self.event_comment_pull_edited()
            elif action == WorkflowTriggeringAction.DELETED:
                self.event_comment_pull_deleted()
            else:
                self.logger.error(action_err_msg, action_err_details)
        else:
            if action == WorkflowTriggeringAction.CREATED:
                self.event_comment_issue_created()
            elif action == WorkflowTriggeringAction.EDITED:
                self.event_comment_issue_edited()
            elif action == WorkflowTriggeringAction.DELETED:
                self.event_comment_issue_deleted()
            else:
                self.logger.error(action_err_msg, action_err_details)

    def event_comment_pull_created(self):
        return

    def event_comment_pull_edited(self):
        return

    def event_comment_pull_deleted(self):
        return

    def event_comment_issue_created(self):
        action_err_details = (
            "The workflow was triggered by a comment on "
            + (
                "a pull request ('issue_comment' event with 'pull_request' payload)"
                if is_pull
                else "an issue ('issue_comment' event without 'pull_request' payload)"
            )
            + f", {action_err_details_sub}"
        )
        return

    def event_comment_issue_edited(self):
        return

    def event_comment_issue_deleted(self):
        return
