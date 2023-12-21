from repodynamics.actions.events._base import EventHandler
from repodynamics.actions.context_manager import ContextManager


class ScheduleEventHandler(EventHandler):

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
        self._payload: IssuesPayload = self._context.event
        return

    def run(self):
        cron = self.context.payload["schedule"]
        if cron == self.metadata_main.workflow__init__schedule__sync:
            self.event_schedule_sync()
        elif cron == self.metadata_main.workflow__init__schedule__test:
            self.event_schedule_test()
        else:
            self.logger.error(
                f"Unknown cron expression for scheduled workflow: {cron}",
                f"Valid cron expressions defined in 'workflow.init.schedule' metadata are:\n"
                f"{self.metadata_main.workflow__init__schedule}",
            )

    def event_schedule_sync(self):
        self.event_type = EventType.SCHEDULE
        self.action_website_announcement_check()
        self.action_meta()
        return

    def event_schedule_test(self):
        self.event_type = EventType.SCHEDULE
        return
