from pathlib import Path as _Path
import os as _os
import copy as _copy

import docsman as _dm
from readme_renderer.markdown import render as _render
import pyserials as _ps

from controlman.datatype import DynamicFile as _GeneratedFile, DynamicFileType


def generate(data: _ps.NestedDict, data_before: _ps.NestedDict, repo_path: _Path) -> list[_GeneratedFile]:

    generated_files = []
    current_dir = _Path.cwd()
    _os.chdir(repo_path)
    try:
        for readme_key, readme_type in (
            ("readme", DynamicFileType.README),
            ("health", DynamicFileType.HEALTH)
        ):
            for readme_id, readme_file_data in data.get(readme_key, {}).items():
                file = _generate_file(
                    filetype=readme_type,
                    subtype=(readme_id, readme_id),
                    path_before=data_before[f"{readme_key}.{readme_id}.path"],
                    file_data=readme_file_data,
                    default_footer=data["theme.footer"],
                    default_badge=data["theme.badge"],
                    themed=True,
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
                    default_footer=data["theme.footer"],
                    default_badge=data["theme.badge"],
                    themed=False,
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
    default_footer: str | list | None,
    default_badge: dict | None,
    themed: bool,
) -> _GeneratedFile:
    file_info = {
        "type": filetype,
        "subtype": subtype,
        "path": file_data["path"],
        "path_before": path_before,
    }
    content = file_data["content"]
    if not content:
        contents = []
    elif isinstance(content, str):
        contents = [content]
    else:
        contents = content
    footer = file_data.get("footer")
    if footer is None:
        if isinstance(default_footer, str):
            contents.append(default_footer)
        elif isinstance(default_footer, list):
            contents.extend(default_footer)
    elif footer != "":
        if isinstance(footer, str):
            contents.append(footer)
        elif isinstance(footer, list):
            contents.extend(footer)
    if not contents:
        return _GeneratedFile(**file_info)
    doc = _dm.generate(
        content=_copy.deepcopy(contents),
        themed=themed,
    )
    file_info["content"] = doc.syntax_md()
    return _GeneratedFile(**file_info)


def render_pypi_readme(markdown_str: str):
    # https://github.com/pypa/readme_renderer/blob/main/readme_renderer/markdown.py
    html_str = _render(markdown_str)
    if not html_str:
        raise ValueError("Renderer encountered an error.")
    return html_str