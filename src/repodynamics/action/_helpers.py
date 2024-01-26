from typing import Any
import ast

from repodynamics.logger import Logger


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
