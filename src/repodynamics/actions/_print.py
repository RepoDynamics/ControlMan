import argparse

from repodynamics.ansi import SGR


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("text", type=str, help="Text to print.")
    parser.add_argument("style", type=str, help="Style to apply to the text.")
    parser.add_argument("action", nargs="?", type=str, help="Color to apply to the text.")
    args = parser.parse_args()
    print(SGR.format(args.text, args.style, args.action))


if __name__ == "__main__":
    main()
