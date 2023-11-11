from repodynamics.datatype import WorkflowTriggeringAction
from repodynamics.logger import Logger


def error_unsupported_triggering_action(
    event_name: str, action: WorkflowTriggeringAction | str, logger: Logger
):
    action_name = action.value if isinstance(action, WorkflowTriggeringAction) else action
    action_err_msg = f"Unsupported triggering action for '{event_name}' event."
    action_err_details_sub = f"but the triggering action '{action_name}' is not supported."
    action_err_details = (
        f"The workflow was triggered by an event of type '{event_name}', {action_err_details_sub}"
    )
    logger.error(action_err_msg, action_err_details)
    return
