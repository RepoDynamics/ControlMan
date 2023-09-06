import sys
import json
from pathlib import Path
from typing import Literal

from markitup import html, md

from repodynamics.logger import Logger


def meta(
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


