from typing import Callable, get_type_hints
import os
import json
import inspect
import base64

from repodynamics.logger import Logger


def input(module_name: str, function: Callable, logger: Logger) -> dict:
    """
    Parse inputs from environment variables.
    """

    def _default_args(func):
        signature = inspect.signature(func)
        return {
            k: v.default for k, v in signature.parameters.items() if v.default is not inspect.Parameter.empty
        }

    logger.h2("Read Inputs")
    params = get_type_hints(function)
    default_args = _default_args(function)
    args = {}
    if not params:
        logger.skip("Action requires no inputs")
        return args
    params.pop("return", None)
    for idx, (param, typ) in enumerate(params.items()):
        logs = []
        title = f"Read '{param}' ({typ.__name__})"
        param_env_name = f"RD_{module_name.upper()}__{param.upper()}"
        logs.append(f"- ℹ️ Checking environment variable '{param_env_name}'")
        val = os.environ.get(param_env_name)
        if val is not None:
            logs.append(f"- ✅ Found input: '{val if 'token' not in param else '**REDACTED**'}'")
        else:
            logs.append(f"- ❎ {param_env_name} was not set")
            param_env_name = f"RD_{module_name.upper()}_{function.__name__.upper()}__{param.upper()}"
            logs.append(f"- ℹ️ Checking environment variable '{param_env_name}'")
            val = os.environ.get(param_env_name)
            if val is None:
                logs.append(f"- ❎ {param_env_name} was not set")
                if param not in default_args:
                    logs.append(f"- ⛔ ERROR: Input {param} is not set and has no default value")
                    logger.error(title, logs)
                logs.append(f"- ❎ Using default value '{default_args[param]}'")
                logger.skip(title, logs)
                continue
            else:
                logs.append(f"- ✅ Found input: '{val if 'token' not in param else '**REDACTED**'}'")
        if typ is str:
            args[param] = val
        elif typ is bool:
            potential_error_msg = (
                "- ⛔ ERROR: Invalid boolean input: "
                f"'{param_env_name}' has value '{val}' with type '{type(val)}'"
            )
            if isinstance(val, bool):
                args[param] = val
            elif isinstance(val, str):
                if val.lower() not in ("true", "false", ""):
                    logs.append(potential_error_msg)
                    logger.error(title, logs)
                args[param] = val.lower() == "true"
            else:
                logs.append(potential_error_msg)
                logger.error(title, logs)
        elif typ is dict:
            args[param] = json.loads(val, strict=False) if val else {}
        elif typ is int:
            try:
                args[param] = int(val)
            except ValueError:
                logs.append(
                    "- ⛔ ERROR: Invalid integer input: "
                    f"'{param_env_name}' has value '{val}' with type '{type(val)}'"
                )
        else:
            logger.error(
                "- ⛔ ERROR: Unknown input type: "
                f"'{param_env_name}' has value '{val}' with type '{type(val)}'"
            )
    return args


def output(kwargs: dict, logger, env: bool = False) -> None:
    def format_output(name, val):
        if isinstance(val, str):
            if "\n" in val:
                with open("/dev/urandom", "rb") as f:
                    random_bytes = f.read(15)
                random_delimeter = base64.b64encode(random_bytes).decode("utf-8")
                return f"{name}<<{random_delimeter}\n{val}\n{random_delimeter}"
        elif isinstance(val, (dict, list, tuple, bool, int)):
            val = json.dumps(val)
        else:
            logs.append(f"- ⛔ ERROR: Invalid output value: {val} with type {type(val)}")
            logger.error(title, logs)
        return f"{name}={val}"

    logger.h2(f"Write {'Environment Variables' if env else 'Step Outputs'}")
    with open(os.environ["GITHUB_ENV" if env else "GITHUB_OUTPUT"], "a") as fh:
        for idx, (name, value) in enumerate(kwargs.items()):
            logs = []
            name = name.replace("_", "-") if not env else name.upper()
            title = f"Write '{name}' ({type(value).__name__})"
            value_formatted = format_output(name, value)
            print(value_formatted, file=fh)
            logs.append(f"- ✅ Wrote output: '{value_formatted}'")
            logger.success(title, logs)
    return


def summary(content: str, logger) -> None:
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as fh:
        print(content, file=fh)
    logger.success("Write Job Summary", content)
    return
