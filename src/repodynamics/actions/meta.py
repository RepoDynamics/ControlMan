import sys
import json
from pathlib import Path
from typing import Literal

from markitup import html, md

from repodynamics.logger import Logger


def meta(
    repo_fullname: str,
    github_token: str,
    commit: bool,
    extensions: dict,
    summary_path: str = None,
    logger: Logger = None,
) -> tuple[None, None, None]:
    from repodynamics import meta
    dirpath_alts = [
        Path(data["path_dl"]) / data["path"] for typ, data in extensions.items()
        if typ.startswith("alt") and data.get("has_files")
    ]
    output, summary = meta.update(
        repo_fullname=repo_fullname,
        path_root=".",
        path_extensions=dirpath_alts,
        commit=commit,
        github_token=github_token,
        logger=logger
    )
    if summary_path:
        summary_path = Path(summary_path)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        with open(summary_path, "w") as f:
            f.write(summary)
        return output, None, None
    return output, None, summary


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
    path_meta = Path("meta") if alt_num == 0 else Path(f".local/repodynamics/meta/extensions/{repo}/{path}")
    logger.section("Process extension files")

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
                "path_dl": f".local/repodynamics/meta/extensions/{extensions[idx]['repo']}"
            }
    env_vars["RD_META__EXTENSIONS"] = outputs
    return outputs, env_vars, None


