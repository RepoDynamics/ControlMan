from typing import Callable, get_type_hints
import os
import sys
import json
import inspect

from repodynamics.ansi import SGR


def input(module_name: str, function: Callable) -> dict:
    """
    Parse inputs from environment variables.
    """
    print(SGR.format(f"Reading inputs for `{module_name}.{function.__name__}`:", style="info"))
    params = get_type_hints(function)
    default_args = _default_args(function)
    args = {}
    if not params:
        print(SGR.format(f"Action requires no inputs.", "success"))
        return args
    params.pop("return", None)
    for param, typ in params.items():
        param_env_name = f"RD_{module_name.upper()}_{function.__name__.upper()}__{param.upper()}"
        val = os.environ.get(param_env_name)
        if val is None:
            if param not in default_args:
                print(SGR.format(f"Missing input: {param_env_name}", "error"))
                sys.exit(1)
        elif typ is str:
            args[param] = val
        elif typ is bool:
            if isinstance(val, bool):
                args[param] = val
            elif isinstance(val, str):
                if val.lower() not in ("true", "false", ""):
                    error_msg = (
                        "Invalid boolean input: "
                        f"'{param_env_name}' has value '{val}' with type '{type(val)}'."
                    )
                    print(SGR.format(error_msg, "error"))
                    sys.exit(1)
                args[param] = val.lower() == "true"
            else:
                error_msg = (
                    "Invalid boolean input: "
                    f"'{param_env_name}' has value '{val}' with type '{type(val)}'."
                )
                print(SGR.format(error_msg, "error"))
                sys.exit(1)
        elif typ is dict:
            args[param] = json.loads(val, strict=False)
        elif type is int:
            try:
                args[param] = int(val)
            except ValueError:
                error_msg = (
                    "Invalid integer input: "
                    f"'{param_env_name}' has value '{val}' with type '{type(val)}'."
                )
                print(SGR.format(error_msg, "error"))
                sys.exit(1)
        else:
            error_msg = (
                "Unknown input type: "
                f"'{param_env_name}' has value '{val}' with type '{type(val)}'."
            )
            print(SGR.format(error_msg, "error"))
            sys.exit(1)
        emoji = "❎" if val is None else "✅"
        extra = f" (default: {default_args[param]})" if val is None else ""
        print(SGR.format(f"  {emoji} {param.upper()}{extra}", style="success"))
    return args


def output(kwargs: dict, env: bool = False) -> None:
    def format_value(val):
        if isinstance(val, str):
            return val
        if isinstance(val, (dict, list, tuple, bool)):
            return json.dumps(val)
        raise ValueError(f"Invalid output value: {val} with type {type(val)}.")
    msg = f"Setting {'environment variables' if env else 'step outputs'}:"
    print(SGR.format(msg, style="info"))
    with open(os.environ["GITHUB_ENV" if env else "GITHUB_OUTPUT"], "a") as fh:
        for name, value in kwargs.items():
            if not env:
                name = name.replace('_', '-')
            value_formatted = format_value(value)
            print(f"{name}={value_formatted}", file=fh)
            print(SGR.format(f"   {name}", style="success"), f"= {value_formatted}")
    return


def summary(content: str) -> None:
    print(SGR.format("Writing job summary ...", style="info"))
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as fh:
        print(content, file=fh)
    return


def _default_args(func):
    signature = inspect.signature(func)
    return {
        k: v.default for k, v in signature.parameters.items()
        if v.default is not inspect.Parameter.empty
    }
