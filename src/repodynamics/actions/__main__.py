import argparse
import importlib
import sys
import traceback


from repodynamics.actions import io
from repodynamics.ansi import SGR
from repodynamics.logger import Logger
from repodynamics.actions._db import action_color

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", type=str, nargs='+', help="Name of the action to run.")
    action = parser.parse_args().action
    if len(action) > 2:
        print(SGR.format(f"Expected 2 arguments, but got {action}", "error"))
        sys.exit(1)
    if len(action) == 1:
        action.append(action[0])
    action = [arg.replace('-', '_') for arg in action]
    module_name, function_name = action
    print(SGR.format(f"Executing repodynamics.actions.{module_name}.{function_name}", "info"))
    try:
        action_module = importlib.import_module(f"repodynamics.actions.{module_name}")
        action = getattr(action_module, function_name)
        logger = Logger("github", color=action_color[module_name])
        inputs = io.input(module_name=module_name, function=action, logger=logger)
        outputs, env_vars, summary = action(logger=logger, **inputs)
        if outputs:
            io.output(outputs, logger=logger)
        if env_vars:
            io.output(env_vars, env=True, logger=logger)
        if summary:
            io.summary(content=summary, logger=logger)
    except Exception as e:
        print(SGR.format(f"An unexpected error occurred: {e}", "error"))
        print(traceback.format_exc())
    return


if __name__ == "__main__":
    main()
