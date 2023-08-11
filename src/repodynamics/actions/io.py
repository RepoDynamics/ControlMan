from typing import Callable, get_type_hints
import os
import sys
import json

from repodynamics.ansi import SGR


def input(action: Callable) -> dict:
    """
    Parse inputs from environment variables.
    """
    print(
        SGR.format(
            f"Reading inputs for action '{action.__name__}':",
            style=SGR.style("bold", "b_blue"),
        )
    )
    params = get_type_hints(action)
    args = {}
    if not params:
        print(SGR.format(f"Action requires no inputs.", "success"))
        return args
    params.pop("return", None)
    for param, typ in params.items():
        action_name = action.__name__.upper().replace('_', '-')
        param_name = param.upper()
        param_env_name = f"RD__{action_name}__{param_name}"
        val = os.environ.get(param_env_name)
        if val is None:
            print(SGR.format(f"Missing input: {param_env_name}", "error"))
            sys.exit(1)
        if typ is str:
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
    return args


def output(**kwargs) -> None:
    print(SGR.format("Writing outputs:", style="info"))
    with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
        for name, value in kwargs.items():
            output_name = name.replace('_', '-')
            print(f"{output_name}={value}", file=fh)
            print(SGR.format(f"  {output_name}", style="success"), f"= {value}")
    return


def summary(content: str) -> None:
    print(SGR.format("Writing summary", style="info"))
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as fh:
        print(content, file=fh)
    return
