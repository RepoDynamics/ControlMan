import sys
import json
from pathlib import Path
from typing import Literal

from markitup import html, md

from repodynamics.logger import Logger


def meta(
    github_token: str,
    extensions: dict,
    logger: Logger = None,
) -> tuple[None, dict, None]:
    from repodynamics import meta
    dirpath_alts = [
        Path(data["path_dl"]) / data["path"] for typ, data in extensions.items()
        if typ.startswith("alt") and data.get("has_files")
    ]
    summary = meta.update(
        path_root=".",
        path_extensions=dirpath_alts,
        github_token=github_token,
        logger=logger
    )
    return None, {"RD_META__SUMMARY": summary}, None


def files(
    repo: str = "",
    ref: str = "",
    path: str = "meta",
    alt_num: int = 0,
    extensions: dict = None,
    logger: Logger = None
):

    def report_files(category: str, dirpath: str, pattern: str):
        filepaths = list((path_meta / dirpath).glob(pattern))
        sympath = f"'{fullpath}/{dirpath}'"
        if not filepaths:
            logger.info(f"No {category} found in {sympath}.")
            return False
        logger.info(f"Following {category} were downloaded from {sympath}:")
        for path_file in filepaths:
            logger.debug(f"  ✅ {path_file.name}")
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
        ("discussion forms", "template/discussion_form", "*.yaml"),
        ("media files", "media", "**/*"),
    ]:
        has_files[dirpath] = report_files(category, dirpath, pattern)

    env_vars = {"RD_META_FILES__ALT_NUM": alt_num + 1}

    if alt_num != 0:
        extensions[f"alt{alt_num}"]["has_files"] = has_files
        env_vars["RD_META__EXTENSIONS"] = extensions
        return None, env_vars, None

    outputs = {"main": {"has_files": has_files}} | {f"alt{i+1}": {"repo": ""} for i in range(3)}
    path_extension = path_meta / "extensions.json"
    if not path_extension.exists():
        if not has_files['data']:
            logger.error(
                f"Neither metadata files nor extensions file found in the current repository at '{fullpath}'. "
                f"The repository must contain a './meta' directory with an 'extensions.json' file "
                "and/or a 'data' subdirectory containing metadata files in '.yaml' format."
            )
        logger.info(f"No extensions definition file found at '{fullpath}/extensions.json'.")
    else:
        logger.info(f"Reading extensions definition file at '{fullpath}/extensions.json':")
        try:
            with open(path_extension) as f:
                extensions = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"There was a problem reading 'extensions.json': {e}")
        if not isinstance(extensions, list) or len(extensions) == 0:
            logger.error(f"Invalid 'extensions.json': {extensions}")
        if len(extensions) > 3:
            logger.error(f"Too many extensions in 'extensions.json': {extensions}")
        idx_emoji = {0: "1️⃣", 1: "2️⃣", 2: "3️⃣"}
        for idx, ext in enumerate(extensions):
            logger.success(f"  Extension {idx_emoji[idx]}:")
            if not isinstance(ext, dict):
                logger.error(f"Invalid element in 'extensions.json': '{ext}'")
            if "repo" not in ext:
                logger.error(f"Missing 'repo' key in element {idx} of 'extensions.json': {ext}.")
            for subkey, subval in ext.items():
                if subkey not in ("repo", "ref", "path"):
                    logger.error(f"Invalid key in 'extensions.json': '{subkey}'")
                if not isinstance(subval, str):
                    logger.error(f"Invalid value for '{subkey}' in 'extensions.json': '{subval}'")
                if subkey in ("repo", "path") and subval == "":
                    logger.error(f"Empty value for '{subkey}' in 'extensions.json'.")
                logger.debug(f"    ✅ {subkey}: '{subval}'")
            if "ref" not in ext:
                extensions[idx]["ref"] = ""
                logger.attention(f"    ❎ ref: '' (default)", "attention")
            if "path" not in ext:
                extensions[idx]["path"] = "meta"
                logger.attention(f"    ❎ path: 'meta' (default)")
            outputs[f"alt{idx+1}"] = extensions[idx] | {
                "path_dl": f".local/meta_extensions/{extensions[idx]['repo']}"
            }
    env_vars["RD_META__EXTENSIONS"] = outputs
    return outputs, env_vars, None


def finalize(
    detect: bool,
    sync: str,
    push_changes: bool,
    push_sha: str,
    pull_number: str,
    pull_url: str,
    pull_head_sha: str,
    changes_categories: dict,
    changes_all: dict,
    summary: dict = None,
    logger: Logger = None,
) -> tuple[dict, str]:
    """
    Parse outputs from `actions/changed-files` action.

    This is used in the `repo_changed_files.yaml` workflow.
    It parses the outputs from the `actions/changed-files` action and
    creates a new output variable `json` that contains all the data,
    and writes a job summary.
    """
    if detect:
        all_groups, job_summary = _changed_files(changes_categories, changes_all)
    else:
        job_summary = html.ElementCollection()

    job_summary.append(html.h(2, "Metadata"))

    with open("meta/.out/metadata.json") as f:
        metadata_dict = json.load(f)

    job_summary.append(
        html.details(
            content=md.code_block(json.dumps(metadata_dict, indent=4), "json"),
            summary=" 🖥  Metadata",
            content_indent=""
        )
    )

    return None, None, str(job_summary)


    # Generate summary
    # force_update_emoji = "✅" if force_update == "all" else ("❌" if force_update == "none" else "☑️")
    # cache_hit_emoji = "✅" if cache_hit else "❌"
    # if not cache_hit or force_update == "all":
    #     result = "Updated all metadata"
    # elif force_update == "core":
    #     result = "Updated core metadata but loaded API metadata from cache"
    # else:
    #     result = "Loaded all metadata from cache"

    # results_list = html.ElementCollection(
    #     [
    #         html.li(f"{force_update_emoji}  Force update (input: {force_update})", content_indent=""),
    #         html.li(f"{cache_hit_emoji}  Cache hit", content_indent=""),
    #         html.li(f"➡️  {result}", content_indent=""),
    #     ],
    # )
    # log = f"<h2>Repository Metadata</h2>{metadata_details}{results_list}"

    # return {"json": json.dumps(all_groups)}, str(log)


def _changed_files(changes_categories: dict, changes_all: dict):
    summary = html.ElementCollection(
        [
            html.h(2, "Changed Files"),
        ]
    )

    # Parse and clean outputs
    sep_groups = dict()
    for item_name, val in changes_categories.items():
        group_name, attr = item_name.split("_", 1)
        group = sep_groups.setdefault(group_name, dict())
        group[attr] = val
    for group_name, group_attrs in sep_groups.items():
        sep_groups[group_name] = dict(sorted(group_attrs.items()))
        if group_attrs["any_modified"] == "true":
            summary.append(
                html.details(
                    content=md.code_block(json.dumps(sep_groups[group_name], indent=4), "json"),
                    summary=group_name,
                )
            )
        # group_summary_list.append(
        #     f"{'✅' if group_attrs['any_modified'] == 'true' else '❌'}  {group_name}"
        # )
    changes_all = dict(sorted(changes_all.items()))
    all_groups = {"all": changes_all} | sep_groups
    file_list = "\n".join(sorted(changes_all["all_changed_and_modified_files"].split()))
    # Write job summary
    summary.append(
        html.details(
            content=md.code_block(file_list, "bash"),
            summary="🖥 Changed Files",
        )
    )
    # details = html.details(
    #     content=md.code_block(json.dumps(all_groups, indent=4), "json"),
    #     summary="🖥 Details",
    # )
    # log = html.ElementCollection(
    #     [html.h(4, "Modified Categories"), html.ul(group_summary_list), changed_files, details]
    # )
    return all_groups, summary
