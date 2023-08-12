import sys
import json
from pathlib import Path

from markitup import html, md

from repodynamics.ansi import SGR


def meta(
    cache_hit: bool,
    force_update: str,
    github_token: str,
    filepath_full: str,
    filepath_cache: str,
    dirpath_main: str,
    dirpath_alt1: str,
    dirpath_alt2: str,
    dirpath_alt3: str,
) -> tuple[dict, str]:

    if force_update not in ["all", "core", "none"]:
        print(SGR.format(f"Invalid input for 'force_update': '{force_update}'.", "error"))
        sys.exit(1)

    if force_update != "none" or not cache_hit:
        from repodynamics.metadata import metadata

        dirpath_alts = []
        for dirpath_alt in [dirpath_alt1, dirpath_alt2, dirpath_alt3]:
            path = Path(dirpath_alt) / "data"
            if list(path.glob("*.yaml")):
                dirpath_alts.append(dirpath_alt)

        metadata_dict = metadata.fill(
            dirpath_main=dirpath_main,
            dirpath_alts=dirpath_alts,
            filepath_cache=filepath_cache,
            update_cache=force_update == "all",
            github_token=github_token,
        )
        with open(filepath_full, "w") as f:
            json.dump(metadata_dict, f)
    else:
        with open(filepath_full) as f:
            metadata_dict = json.load(f)
    metadata_str = json.dumps(metadata_dict)
    metadata_str_pretty = json.dumps(metadata_dict, indent=4)

    # Set output
    output = {"json": metadata_str}

    # Generate summary
    force_update_emoji = "✅" if force_update == "all" else ("❌" if force_update == "none" else "☑️")
    cache_hit_emoji = "✅" if cache_hit else "❌"
    if not cache_hit or force_update == "all":
        result = "Updated all metadata"
    elif force_update == "core":
        result = "Updated core metadata but loaded API metadata from cache"
    else:
        result = "Loaded all metadata from cache"

    metadata_details = html.details(
        content=md.code_block(metadata_str_pretty, "json"),
        summary=" 🖥  Metadata",
        content_indent=""
    )
    results_list = html.ElementCollection(
        [
            html.li(f"{force_update_emoji}  Force update (input: {force_update})", content_indent=""),
            html.li(f"{cache_hit_emoji}  Cache hit", content_indent=""),
            html.li(f"➡️  {result}", content_indent=""),
        ],
    )
    log = f"<h2>Repository Metadata</h2>{metadata_details}{results_list}"
    return output, log


def files(repository: str, ref: str, path: str, path_dl: str, is_main: bool = False):
    fullpath = Path(repository) / ref / path / "data"
    meta_path = Path(path_dl) / path / "data"
    metadata_paths = list(meta_path.glob("*.yaml"))
    if not metadata_paths:
        print(SGR.format(f"No metadata files found in '{fullpath}'.", "attention"))
    else:
        print(SGR.format(f"Following metadata files were downloaded from {fullpath}:", "success"))
        for path_file in metadata_paths:
            print(SGR.format(f"  {path_file.name}", "success"))
    if not is_main:
        return
    path_extension = Path(path_dl) / path / "extensions.json"
    if not path_extension.exists():
        if not metadata_paths:
            error_msg = (
                f"Neither metadata files nor extensions file found in the current repository at '{fullpath}'. "
                f"The repository must contain a 'data' subdirectory in the provided path '{path}', "
                "with metadata files stored in '.yaml' files, and/or an 'extensions.json' file "
                f"in the '{path}' directory."
            )
            print(SGR.format(error_msg, "error"))
            sys.exit(1)
        msg = f"No 'extensions.json' file found in '{path}'; the next step will be skipped."
        print(SGR.format(msg, "attention"))
        extensions = {"alt_1": {"repo": ""}, "alt_2": {"repo": ""}, "alt_3": {"repo": ""}}
    else:
        print(SGR.format(f"  extensions.json", "success"))
        print(SGR.format(f"Reading 'extensions.json':", "info"))
        try:
            with open(path_extension) as f:
                extensions = json.load(f)
        except json.JSONDecodeError as e:
            print(SGR.format(f"There was a problem reading 'extensions.json': {e}", "error"))
            sys.exit(1)
        if not isinstance(extensions, dict) or len(extensions) == 0:
            print(SGR.format(f"Invalid 'extensions.json': {extensions}", "error"))
            sys.exit(1)
        for key, val in extensions.items():
            if key not in ("alt_1", "alt_2", "alt_3"):
                print(SGR.format(f"Invalid root key in 'extensions.json': '{key}'", "error"))
                sys.exit(1)
            if not isinstance(val, dict):
                print(SGR.format(f"Invalid value for '{key}' in 'extensions.json': '{val}'", "error"))
                sys.exit(1)
            print(SGR.format(f"  {key}:", "success"))
            if "repo" not in val:
                print(SGR.format(f"Missing key in 'extensions.json': '{key}.repo'", "error"))
                sys.exit(1)
            for subkey, subval in val.items():
                if subkey not in ("repo", "ref", "path"):
                    print(SGR.format(f"Invalid key in 'extensions.json': '{key}.{subkey}'", "error"))
                    sys.exit(1)
                if not isinstance(subval, str):
                    print(SGR.format(f"Invalid value for '{key}.{subkey}' in 'extensions.json': '{subval}'", "error"))
                    sys.exit(1)
                if subkey in ("repo", "path") and subval == "":
                    print(SGR.format(f"Empty value for '{key}.{subkey}' in 'extensions.json'.", "error"))
                    sys.exit(1)
                print(SGR.format(f"    {subkey}: {subval}", "success"))
            if "path" not in val:
                extensions[key]["path"] = "meta"
                print(SGR.format(f"    path: meta (set to default)", "attention"))

    print(SGR.format(f"4. Checkout Extension Repositories", "heading", "meta"))
    if not path_extension.exists():
        print(SGR.format(f"No 'extensions.json' was found; skipping.", "success"))
    return {"ext": json.dumps(extensions)}, None
