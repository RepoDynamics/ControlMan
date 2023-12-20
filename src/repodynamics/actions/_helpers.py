from typing import Any
import ast

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


def parse_function_call(code: str) -> tuple[str, dict[str, Any]]:
    """
    Parse a Python function call from a string.

    Parameters
    ----------
    code : str
        The code to parse.

    Returns
    -------
    tuple[str, dict[str, Any]]
        A tuple containing the function name and a dictionary of keyword arguments.
    """

    class CallVisitor(ast.NodeVisitor):

        def visit_Call(self, node):
            self.func_name = getattr(node.func, 'id', None)  # Function name
            self.args = {arg.arg: self._arg_value(arg.value) for arg in node.keywords}  # Keyword arguments

        def _arg_value(self, node):
            if isinstance(node, ast.Constant):
                return node.value
            elif isinstance(node, (ast.List, ast.Tuple, ast.Dict)):
                return ast.literal_eval(node)
            return "Complex value"  # Placeholder for complex expressions

    tree = ast.parse(code)
    visitor = CallVisitor()
    visitor.visit(tree)

    return visitor.func_name, visitor.args
