import argparse
import importlib
import sys
import traceback

from repodynamics.actions import io
from repodynamics.logger import Logger
from repodynamics.actions._db import action_color


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", type=str, nargs="+", help="Name of the action to run.")
    action = parser.parse_args().action
    logger = Logger("github")
    if len(action) > 2:
        logger.error(f"Expected 2 arguments, but got {action}")
    if len(action) == 1:
        action.append(action[0])
    action = [arg.replace("-", "_") for arg in action]
    module_name, function_name = action
    action_module = importlib.import_module(f"repodynamics.actions.{module_name}")
    action = getattr(action_module, function_name)
    inputs = io.input(module_name=module_name, function=action, logger=logger)
    try:
        outputs, env_vars, summary = action(logger=logger, **inputs)
    except Exception as e:
        sys.stdout.flush()  # Flush stdout buffer before printing the exception
        logger.error(f"An unexpected error occurred: {e}", traceback.format_exc())
    logger.h1("Write Outputs & Summary")
    if outputs:
        io.output(outputs, logger=logger)
    if env_vars:
        io.output(env_vars, env=True, logger=logger)
    if summary:
        io.summary(content=summary, logger=logger)
    return


if __name__ == "__main__":
    main()
