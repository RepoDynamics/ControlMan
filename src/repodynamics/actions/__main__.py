import argparse
import importlib
import sys

from repodynamics.actions import io
from repodynamics.ansi import SGR


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", type=str, help="Name of the action to run.")
    action = parser.parse_args().action
    action_name = action.replace('-', '_')
    try:
        action_module = importlib.import_module(f"repodynamics.actions.{action_name}")
        action = getattr(action_module, action_name)
        inputs = io.input(action=action)
        outputs, summary = action(**inputs)
        if outputs:
            io.output(**outputs)
        if summary:
            io.summary(content=summary)
    except Exception as e:
        print(SGR.format("An unexpected error occurred:", "error"))
        print(e)
        sys.exit(1)
    return


if __name__ == "__main__":
    main()
