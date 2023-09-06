import argparse

from repodynamics.logger import Logger


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("type", type=str, help="Style to apply to the text.")
    parser.add_argument("message", type=str, help="Text to print.")
    parser.add_argument("details", nargs="?", type=str, help="Color to apply to the text.")
    args = parser.parse_args()
    logger = Logger("github")
    if args.type in [f"h{i}" for i in range(1, 5)]:
        logger._h(int(args.type[1]), args.message)
    else:
        logger.log(args.type, args.message, args.details)


if __name__ == "__main__":
    main()
