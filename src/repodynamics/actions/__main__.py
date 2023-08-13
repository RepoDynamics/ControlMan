import argparse
import importlib
import sys

from repodynamics.actions import io
from repodynamics.ansi import SGR


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
        inputs = io.input(module_name=module_name, function=action)
        outputs, env_vars, summary = action(**inputs)
        if outputs:
            io.output(outputs)
        if env_vars:
            io.output(env_vars, env=True)
        if summary:
            io.summary(content=summary)
    except Exception as e:
        print(SGR.format("An unexpected error occurred:", "error"))
        raise e
    return


if __name__ == "__main__":
    main()
