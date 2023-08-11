import json
from pathlib import Path

from markitup import html, md


def changed_files(categories: dict, total: dict) -> tuple[dict, str]:
    """
    Parse outputs from `actions/changed-files` action.

    This is used in the `repo_changed_files.yaml` workflow.
    It parses the outputs from the `actions/changed-files` action and
    creates a new output variable `json` that contains all the data,
    and writes a job summary.
    """
    # Parse and clean outputs
    sep_groups = dict()
    for item_name, val in categories.items():
        group_name, attr = item_name.split("_", 1)
        group = sep_groups.setdefault(group_name, dict())
        group[attr] = val
    group_summary_list = []
    for group_name, group_attrs in sep_groups.items():
        sep_groups[group_name] = dict(sorted(group_attrs.items()))
        group_summary_list.append(
            f"{'✅' if group_attrs['any_modified'] == 'true' else '❌'}  {group_name}"
        )
    total = dict(sorted(total.items()))
    all_groups = {"all": total} | sep_groups
    file_list = "\n".join(sorted(total["all_changed_and_modified_files"].split()))
    # Write job summary
    changed_files = html.details(
        content=md.code_block(file_list, "bash"),
        summary="🖥 Changed Files",
    )
    details = html.details(
        content=md.code_block(json.dumps(all_groups, indent=4), "json"),
        summary="🖥 Details",
    )
    log = html.ElementCollection(
        [html.h(4, "Modified Categories"), html.ul(group_summary_list), changed_files, details]
    )
    return {"json": json.dumps(all_groups)}, str(log)


def package_build_sdist() -> tuple[dict, str]:
    filename = list((Path.cwd() / "dist").glob("*.tar.gz"))[0]
    dist_name = filename.stem.removesuffix(".tar.gz")
    package_name, version = dist_name.rsplit("-", 1)
    output = {"package-name": package_name, "package-version": version}
    log = html.ul(
        [
            f"📦 Package Name: `{package_name}`",
            f"📦 Package Version: `{version}`",
            f"📦 Filename: `{filename.name}`",
        ]
    )
    return output, str(log)


def package_publish_pypi(
        package_name: str, package_version: str, platform_name: str, dist_path: str = "dist"
) -> tuple[dict, str]:
    download_url = {
        "PyPI": "https://pypi.org/project",
        "TestPyPI": "https://test.pypi.org/project",
    }
    upload_url = {
        "PyPI": "https://upload.pypi.org/legacy/",
        "TestPyPI": "https://test.pypi.org/legacy/",
    }
    outputs = {
        "download_url": f"{download_url[platform_name]}/{package_name}/{package_version}",
        "upload_url": upload_url[platform_name],
    }

    dists = "\n".join([path.name for path in list(Path(dist_path).glob("*.*"))])
    dist_files = html.details(
        content=md.code_block(dists, "bash"),
        summary="🖥 Distribution Files",
    )
    log_list = html.ul(
        [
            f"📦 Package Name: `{package_name}`",
            f"📦 Package Version: `{package_version}`",
            f"📦 Platform: `{platform_name}`",
            f"📦 Download URL: `{outputs['download_url']}`",
        ]
    )
    log = html.ElementCollection([log_list, dist_files])
    return outputs, str(log)
