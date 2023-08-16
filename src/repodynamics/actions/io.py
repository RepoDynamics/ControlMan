from typing import Callable, get_type_hints
import os
import sys
import json
import inspect
import base64

from repodynamics.ansi import SGR
from repodynamics.logger import Logger


def input(module_name: str, function: Callable, logger: "Logger") -> dict:
    """
    Parse inputs from environment variables.
    """
    logger.section("Processing inputs")
    logger.info(f"Reading inputs for {module_name}.{function.__name__}:")
    params = get_type_hints(function)
    logger.debug(f"Action parameters: {params}")
    default_args = _default_args(function)
    logger.debug(f"Default arguments: {default_args}\n")
    args = {}
    if not params:
        logger.success(f"Action requires no inputs.")
        return args
    params.pop("return", None)
    for idx, (param, typ) in enumerate(params.items()):
        logger.debug(f"{idx + 1}. Reading '{param}':")
        param_env_name = f"RD_{module_name.upper()}__{param.upper()}"
        logger.debug(f"   Checking environment variable '{param_env_name}'")
        val = os.environ.get(param_env_name)
        if val is not None:
            logger.debug(f"   Found input: '{val if 'token' not in param else '**REDACTED**'}'.")
        else:
            logger.debug(f"   {param_env_name} was not set.")
            param_env_name = f"RD_{module_name.upper()}_{function.__name__.upper()}__{param.upper()}"
            logger.debug(f"   Checking environment variable '{param_env_name}'")
            val = os.environ.get(param_env_name)
            if val is None:
                logger.debug(f"   {param_env_name} was not set.")
                if param not in default_args:
                    logger.error(f"Missing input: {param_env_name}")
                logger.debug(f"   Using default value: {default_args[param]}")
                continue
            else:
                logger.debug(f"   Found input: '{val if 'token' not in param else '**REDACTED**'}'.")
        if typ is str:
            args[param] = val
        elif typ is bool:
            if isinstance(val, bool):
                args[param] = val
            elif isinstance(val, str):
                if val.lower() not in ("true", "false", ""):
                    logger.error(
                        "Invalid boolean input: "
                        f"'{param_env_name}' has value '{val}' with type '{type(val)}'."
                    )
                args[param] = val.lower() == "true"
            else:
                logger.error(
                    "Invalid boolean input: "
                    f"'{param_env_name}' has value '{val}' with type '{type(val)}'."
                )
        elif typ is dict:
            args[param] = json.loads(val, strict=False)
        elif typ is int:
            try:
                args[param] = int(val)
            except ValueError:
                logger.error(
                    "Invalid integer input: "
                    f"'{param_env_name}' has value '{val}' with type '{type(val)}'."
                )
        else:
            logger.error(
                "Unknown input type: "
                f"'{param_env_name}' has value '{val}' with type '{type(val)}'."
            )
        emoji = "❎" if val is None else "✅"
        extra = f" (default: {default_args[param]})" if val is None else ""
        logger.debug(f"    {emoji} {param.upper()}{extra}")
    return args


def output(kwargs: dict, logger, env: bool = False) -> None:

    def format_output(name, val):
        if isinstance(val, str) and '\n' in val:
            with open("/dev/urandom", "rb") as f:
                random_bytes = f.read(15)
            random_delimeter = base64.b64encode(random_bytes).decode('utf-8')
            return f"{name}<<{random_delimeter}\n{val}\n{random_delimeter}"
        if isinstance(val, (dict, list, tuple, bool, int)):
            val = json.dumps(val)
        else:
            logger.error(f"Invalid output value: {val} with type {type(val)}.")
        return f"{name}={val}"

    logger.section(f"Writing {'environment variables' if env else 'step outputs'}")
    with open(os.environ["GITHUB_ENV" if env else "GITHUB_OUTPUT"], "a") as fh:
        for idx, (name, value) in enumerate(kwargs.items()):
            name = name.replace('_', '-') if not env else name.upper()
            logger.debug(f"  {idx + 1}. Writing '{name}':")
            value_formatted = format_output(name, value)
            print(value_formatted, file=fh)
            logger.debug(f"   {name} = {value_formatted}")
    return


def summary(content: str, logger) -> None:
    logger.section("Write job summary")
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as fh:
        print(content, file=fh)
        logger.debug(content)
    return


def _default_args(func):
    signature = inspect.signature(func)
    return {
        k: v.default for k, v in signature.parameters.items()
        if v.default is not inspect.Parameter.empty
    }
