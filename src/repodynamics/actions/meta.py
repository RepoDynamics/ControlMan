import sys
import json
from pathlib import Path
from typing import Literal

from markitup import html, md

from repodynamics.ansi import SGR


def meta(
    mode: str,
    cache_hit: bool,
    force_update: str,
    github_token: str,
    extensions: dict,
) -> tuple[dict, str]:

    if force_update not in ["all", "core", "none"]:
        print(SGR.format(f"Invalid input for 'force_update': '{force_update}'.", "error"))
        sys.exit(1)
    if mode not in ["read", "sync", "diff"]:
        print(SGR.format(f"Invalid input for 'mode': '{mode}'.", "error"))
        sys.exit(1)

    if force_update != "none" or not cache_hit:
        from repodynamics.metadata import metadata

        dirpath_alts = []
        for typ, data in extensions.items():
            if typ == "main":
                continue
            if data["has_files"]["data"]:
                dirpath_alt = data["path_dl"] / data["path"]
                dirpath_alts.append(dirpath_alt)

        metadata_dict = metadata.fill(
            path_root=".",
            paths_ext=dirpath_alts,
            filepath_cache=".local/metadata_api_cache.yaml",
            update_cache=force_update == "all",
            github_token=github_token,
        )
        with open(".local/metadata.json", "w") as f:
            json.dump(metadata_dict, f)
    else:
        with open(".local/metadata.json") as f:
            metadata_dict = json.load(f)

    with open("meta/.out/metadata.json") as f:
        metadata_in_repo = json.load(f)

    metadata_changed = metadata_dict != metadata_in_repo

    # Set output
    output = {"meta": metadata_dict, "diff": {"metadata": metadata_changed}}

    if mode == "sync" and metadata_changed:
        with open("meta/.out/metadata.json", "w") as f:
            json.dump(metadata_dict, f)
        with open(".local/metadata_api_cache.yaml") as f:
            metadata_cache = f.read()
        with open("meta/.out/metadata_api_cache.yaml", "w") as f:
            f.write(metadata_cache)

    # if mode != "read":
    #     from repodynamics.sync import sync


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
        content=md.code_block(json.dumps(metadata_dict, indent=4), "json"),
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


def files(repo: str = "", ref: str = "", path: str = "meta", alt_num: int = 0, extensions: dict = None):

    def report_files(category: str, dirpath: str, pattern: str):
        filepaths = list((path_meta / dirpath).glob(pattern))
        sympath = f"'{fullpath}/{dirpath}'"
        if not filepaths:
            print(SGR.format(f"No {category} found in {sympath}.", "info"))
            return False
        print(SGR.format(f"Following {category} were downloaded from {sympath}:", "success"))
        for path_file in filepaths:
            print(f"  ✅ {path_file.name}")
        return True

    if alt_num != 0:
        extension = extensions[f"alt{alt_num}"]
        repo = extension["repo"]
        ref = extension["ref"]
        path = extension["path"]

    fullpath = Path(repo) / ref / path
    path_meta = Path("meta") if alt_num == 0 else Path(f".local/meta_extensions/{repo}/{path}")

    has_files = {}
    for category, dirpath, pattern in [
        ("metadata files", "data", "*.yaml"),
        ("health file templates", "template/health_file", "*.md"),
        ("license templates", "template/license", "*.txt"),
        ("issue forms", "template/issue_form", "*.yaml"),
    ]:
        has_files[dirpath] = report_files(category, dirpath, pattern)

    env_vars = {"RD_META_FILES__ALT_NUM": alt_num + 1}

    if alt_num != 0:
        extensions[f"alt{alt_num}"]["has_files"] = has_files
        env_vars["RD_META__EXTENSIONS"] = extensions
        return None, env_vars, None

    outputs = {"has_extensions": "true", "main": {"has_files": has_files}} | {
        f"alt{i+1}": {"repo": "", "hash_pattern": ".local/meta_extensions/*.yaml"} for i in range(3)
    }
    path_extension = path_meta / "extensions.json"
    if not path_extension.exists():
        if not has_files['data']:
            error_msg = (
                f"Neither metadata files nor extensions file found in the current repository at '{fullpath}'. "
                f"The repository must contain a './meta' directory with an 'extensions.json' file "
                "and/or a 'data' subdirectory containing metadata files in '.yaml' format."
            )
            print(SGR.format(error_msg, "error"))
            sys.exit(1)
        msg = f"No extensions definition file found at '{fullpath}/extensions.json'."
        print(SGR.format(msg, "info"))
        outputs["has_extensions"] = "false"
    else:
        print(SGR.format(f"Reading extensions definition file at '{fullpath}/extensions.json':", "info"))
        try:
            with open(path_extension) as f:
                extensions = json.load(f)
        except json.JSONDecodeError as e:
            print(SGR.format(f"There was a problem reading 'extensions.json': {e}", "error"))
            sys.exit(1)
        if not isinstance(extensions, list) or len(extensions) == 0:
            print(SGR.format(f"Invalid 'extensions.json': {extensions}", "error"))
            sys.exit(1)
        if len(extensions) > 3:
            print(SGR.format(f"Too many extensions in 'extensions.json': {extensions}", "error"))
            sys.exit(1)
        idx_emoji = {0: "1️⃣", 1: "2️⃣", 2: "3️⃣"}
        for idx, ext in enumerate(extensions):
            print(SGR.format(f"  Extension {idx_emoji[idx]}:", "success"))
            if not isinstance(ext, dict):
                print(SGR.format(f"Invalid element in 'extensions.json': '{ext}'", "error"))
                sys.exit(1)
            if "repo" not in ext:
                print(SGR.format(f"Missing 'repo' key in element {idx} of 'extensions.json': {ext}.", "error"))
                sys.exit(1)
            for subkey, subval in ext.items():
                if subkey not in ("repo", "ref", "path"):
                    print(SGR.format(f"Invalid key in 'extensions.json': '{subkey}'", "error"))
                    sys.exit(1)
                if not isinstance(subval, str):
                    print(SGR.format(f"Invalid value for '{subkey}' in 'extensions.json': '{subval}'", "error"))
                    sys.exit(1)
                if subkey in ("repo", "path") and subval == "":
                    print(SGR.format(f"Empty value for '{subkey}' in 'extensions.json'.", "error"))
                    sys.exit(1)
                print(f"    ✅ {subkey}: '{subval}'")
            if "ref" not in ext:
                extensions[idx]["ref"] = ""
                print(SGR.format(f"    ❎ ref: '' (default)", "attention"))
            if "path" not in ext:
                extensions[idx]["path"] = "meta"
                print(SGR.format(f"    ❎ path: 'meta' (default)", "attention"))
            outputs[f"alt{idx+1}"] = extensions[idx] | {
                "hash_pattern": f".local/meta_extensions/{extensions[idx]['repo']}/{extensions[idx]['path']}/data/*.yaml",
                "path_dl": f".local/meta_extensions/{extensions[idx]['repo']}"
            }

    env_vars["RD_META__EXTENSIONS"] = outputs
    return outputs, env_vars, None
