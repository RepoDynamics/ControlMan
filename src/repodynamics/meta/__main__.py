import argparse

from repodynamics import meta


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=str, help="Path to the root directory.", required=False)
    parser.add_argument(
        "--pathfile", type=str, help="Path to the paths metadata file.", required=False
    )
    parser.add_argument(
        "--cachefile", type=str, help="Path for the cache metadata file.", required=False
    )
    parser.add_argument(
        "--output", type=str, help="Path for the output metadata file.", required=False
    )
    parser.add_argument(
        "--update_cache",
        action=argparse.BooleanOptionalAction,
        help="Force update cache metadata file.",
        required=False,
    )
    parser.add_argument(
        "--github_token",
        type=str,
        help="GitHub Token to access the GitHub GraphQL API; without this, discussion categories cant be retrieved.",
        required=False,
    )
    args = parser.parse_args()
    return


if __name__ == "__main__":
    main()