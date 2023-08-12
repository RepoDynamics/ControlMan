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
        else:
            error_msg = (
                "Unknown input type: "
                f"'{param_env_name}' has value '{val}' with type '{type(val)}'."
            )
            print(SGR.format(error_msg, "error"))
            sys.exit(1)
        print(SGR.format(f"  {param.upper()}: {'☑️' if val is None else '✅'}", style="success"))
    return args


def output(**kwargs) -> None:
    print(SGR.format("Writing outputs:", style="info"))
    with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
        for name, value in kwargs.items():
            output_name = name.replace('_', '-')
            print(f"{output_name}={value}", file=fh)
            print(SGR.format(f"   {output_name}", style="success"), f"= {value}")
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
