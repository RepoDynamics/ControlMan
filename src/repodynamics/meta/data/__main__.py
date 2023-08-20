
import argparse


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
    try:
        meta = Metadata(
            path_root=args.root,
            path_pathfile=args.pathfile,
            filepath_cache=args.cachefile,
            update_cache=args.update_cache,
            github_token=args.github_token,
        )
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    # print(meta.json())
    meta.json(write_to_file=True, output_filepath=args.output)
    return


if __name__ == "__main__":
    __main__()


path = (
    Path(output_filepath).resolve()
    if output_filepath
    else (self.metadata["path"]["abs"]["data"]["local_output"] / "metadata.json")
)
path.parent.mkdir(parents=True, exist_ok=True)