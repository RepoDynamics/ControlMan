import argparse
import importlib
import sys
import traceback

import actionman

from repodynamics.logger import Logger
from repodynamics.actions.init import init

action_color = {
    "context": (255, 199, 6),
    "meta": (200, 120, 255),
    "announce": (106, 245, 120),
    "hooks": (252, 189, 0),
    "init": (79, 255, 15),
}


def main():
    # parser = argparse.ArgumentParser()
    # parser.add_argument("action", type=str, nargs="+", help="Name of the action to run.")
    # action = parser.parse_args().action
    logger = Logger("github")
    # if len(action) > 2:
    #     logger.error(f"Expected 2 arguments, but got {action}")
    # if len(action) == 1:
    #     action.append(action[0])
    # action = [arg.replace("-", "_") for arg in action]
    # module_name, function_name = action
    # logger.success("Determine Action", [f"- Module: {module_name}", f"- Function: {function_name}"])
    # action_module = importlib.import_module(f"repodynamics.actions.{module_name}")
    # action = getattr(action_module, function_name)
    inputs = actionman.io.read_function_args_from_environment_variables(
        function=init,
        name_prefix="RD_INIT__",
        hide_args=["admin_token"],
        ignore_params=["logger"],
        logger=logger
    )
    try:
        outputs, env_vars, summary = init(**inputs, logger=logger)
    except Exception as e:
        sys.stdout.flush()  # Flush stdout buffer before printing the exception
        logger.error(f"An unexpected error occurred: {e}", traceback.format_exc())
    logger.h1("Write Outputs & Summary")
    if outputs:
        actionman.io.write_github_outputs(outputs, logger=logger)
    if env_vars:
        actionman.io.write_github_outputs(env_vars, to_env=True, logger=logger)
    if summary:
        actionman.io.write_github_summary(content=summary, logger=logger)
    return


if __name__ == "__main__":
    main()
