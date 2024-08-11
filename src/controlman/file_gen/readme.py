from pathlib import Path as _Path

import docsman as _dm
from readme_renderer.markdown import render as _render
import pyserials as _ps

from controlman.datatype import DynamicFile as _GeneratedFile, DynamicFileType


def generate(data: _ps.NestedDict, data_before: _ps.NestedDict, root_path: _Path) -> list[_GeneratedFile]:

    generated_files = []
    default_footer_themed = _generate_footer(
        footer_data=data["theme.footer"],
        default_badge=data["theme.badge"],
        themed=True,
        root_path=root_path,
    )
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
                default_footer=default_footer_themed,
                default_badge=data["theme.badge"],
                root_path=root_path,
                themed=True,
            )
            generated_files.append(file)

    default_footer_light = _generate_footer(
        footer_data=data["theme.footer"],
        default_badge=data["theme.badge"],
        themed=False,
        root_path=root_path,
    )
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
                default_footer=default_footer_light,
                default_badge=data["theme.badge"],
                root_path=root_path,
                themed=False,
            )
            generated_files.append(file)
    return generated_files


def _generate_file(
    filetype: DynamicFileType,
    subtype: tuple[str, str],
    path_before: str,
    file_data: dict,
    default_footer: str,
    default_badge: dict | None,
    themed: bool,
    root_path: _Path
) -> _GeneratedFile:
    file_info = {
        "type": filetype,
        "subtype": subtype,
        "path": file_data["path"],
        "path_before": path_before,
        "content": "",
    }
    content = file_data["content"]
    if not content:
        return _GeneratedFile(**file_info)
    content = _dm.write.ReadmeFileWriter(
        default_badge=default_badge,
        themed=themed,
        root_path=root_path
    ).generate(elements=content)
    footer = file_data.get("footer")
    if footer != "":
        footer = default_footer if footer is None else _generate_footer(
            footer_data=footer,
            default_badge=default_badge,
            themed=themed,
            root_path=root_path
        )
    file_info["content"] = f"{content}\n{footer}".strip()
    return _GeneratedFile(**file_info)


def _generate_footer(
    footer_data: list | None,
    default_badge: dict | None,
    themed: bool,
    root_path: _Path
):
    if not footer_data:
        return ""
    return _dm.write.ReadmeFileWriter(
        default_badge=default_badge,
        themed=themed,
        root_path=root_path
    ).generate(elements=footer_data)


def render_pypi_readme(markdown_str: str):
    # https://github.com/pypa/readme_renderer/blob/main/readme_renderer/markdown.py
    html_str = _render(markdown_str)
    if not html_str:
        raise ValueError("Renderer encountered an error.")
    return html_str