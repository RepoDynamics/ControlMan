from pathlib import Path as _Path
import os as _os

import pyserials as _ps
import mdit as _mdit

from controlman.datatype import DynamicFile as _GeneratedFile, DynamicFileType


def generate(data: _ps.NestedDict, data_before: _ps.NestedDict, repo_path: _Path) -> list[_GeneratedFile]:

    generated_files = []
    current_dir = _Path.cwd()
    _os.chdir(repo_path)
    try:
        footer = data["theme.footer"]
        if isinstance(footer, str):
            footer_themed = footer_simple = footer
        elif isinstance(footer, list):
            footer_doc = _mdit.generate(footer)
            footer_themed = footer_doc.source("github")
            footer_simple = footer_doc.source("pypi")
        else:
            footer_themed = footer_simple = ""
        for readme_key, readme_type in (
            ("readme", DynamicFileType.README),
            ("health", DynamicFileType.HEALTH)
        ):
            for readme_id, readme_file_data in data.get(readme_key, {}).items():
                if readme_id == "code_owners":
                    continue
                file = _generate_file(
                    filetype=readme_type,
                    subtype=(readme_id, readme_id),
                    path_before=data_before[f"{readme_key}.{readme_id}.path"],
                    file_data=readme_file_data,
                    default_footer=footer_themed,
                    target="github",
                )
                generated_files.append(file)
        for readme_key in ("pkg", "test"):
            for path, subtype in (
                ("readme", ("readme_pypi", "PyPI README")),
                ("conda.readme", ("readme_conda", "Conda README"))
            ):
                readme_data = data[f"{readme_key}.{path}"]
                if not readme_data:
                    continue
                file = _generate_file(
                    filetype=DynamicFileType[f"{readme_key.upper()}_CONFIG"],
                    subtype=subtype,
                    path_before=data_before[f"{readme_key}.{path}.path"],
                    file_data=readme_data,
                    default_footer=footer_simple,
                    target="pypi",
                )
                generated_files.append(file)
    finally:
        _os.chdir(current_dir)
    return generated_files


def _generate_file(
    filetype: DynamicFileType,
    subtype: tuple[str, str],
    path_before: str,
    file_data: dict,
    default_footer: str,
    target: str,
) -> _GeneratedFile:
    file_info = {
        "type": filetype,
        "subtype": subtype,
        "path": file_data["path"],
        "path_before": path_before,
    }
    content = file_data["content"]
    if isinstance(content, str):
        content_str = content
    else:
        content_str = _mdit.generate(content).source(target, heading_number_explicit=False)
    footer = file_data.get("footer")
    if footer is None:
        footer = default_footer
    file_info["content"] = f"{f"{content_str}\n\n{footer}".strip()}\n"
    return _GeneratedFile(**file_info)
