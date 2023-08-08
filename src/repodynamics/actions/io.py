from typing import Callable, Optional, get_type_hints
import os
import sys
import json


def input(action: Callable) -> dict:
    """
    Parse inputs from environment variables.
    """
    params = get_type_hints(action)
    args = {}
    if not params:
        return args
    params.pop("return", None)
    for param, typ in params.items():
        action_name = action.__name__.upper().replace('_', '-')
        param_name = param.upper().replace('_', '-')
        param_env_name = f"RD__{action_name}__{param_name}"
        val = os.environ.get(param_env_name)
        if val is None:
            print(f"ERROR: Missing input: {param_env_name}")
            sys.exit(1)
        if typ is str:
            args[param] = val
        elif typ is bool:
            if isinstance(val, bool):
                args[param] = val
            elif isinstance(val, str):
                if val.lower() not in ("true", "false", ""):
                    print(
                        "ERROR! Invalid boolean input: "
                        f"'{param_env_name}' has value '{val}' with type {type(val)}."
                    )
                    sys.exit(1)
                args[param] = val.lower() == "true"
            else:
                print(
                    "ERROR! Invalid boolean input: "
                    f"'{param_env_name}' has value '{val}' with type {type(val)}."
                )
                sys.exit(1)
        elif typ is dict:
            args[param] = json.loads(val, strict=False)
        else:
            print(f"ERROR: Unknown input type: {typ}")
            sys.exit(1)
    return args


def output(**kwargs) -> Optional[dict]:
    with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
        for name, value in kwargs.items():
            print(f"{name.replace('_', '-')}={value}", file=fh)
    return


def summary(content: str) -> None:
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as fh:
        print(content, file=fh)
    return
