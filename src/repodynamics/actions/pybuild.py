import json
from pathlib import Path

from markitup import html, md

from repodynamics.logger import Logger


def build(path_dist: str, logger=None) -> tuple[dict, str]:
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
    return output, None, str(log)


def publish(
        platform: str, path_dist: str = "dist", logger=None,
) -> tuple[dict, str]:

    package_name, package_version = _get_package_name_ver(path_dist)

    download_url = {
        "PyPI": "https://pypi.org/project",
        "TestPyPI": "https://test.pypi.org/project",
    }
    upload_url = {
        "PyPI": "https://upload.pypi.org/legacy/",
        "TestPyPI": "https://test.pypi.org/legacy/",
    }
    outputs = {
        "download_url": f"{download_url[platform]}/{package_name}/{package_version}",
        "upload_url": upload_url[platform],
    }

    dists = "\n".join([path.name for path in list(Path(path_dist).glob("*.*"))])
    dist_files = html.details(
        content=md.code_block(dists, "bash"),
        summary="🖥 Distribution Files",
    )
    log_list = html.ul(
        [
            f"📦 Package Name: `{package_name}`",
            f"📦 Package Version: `{package_version}`",
            f"📦 Platform: `{platform}`",
            f"📦 Download URL: `{outputs['download_url']}`",
        ]
    )
    log = html.ElementCollection([log_list, dist_files])
    return outputs, None, str(log)


def _get_package_name_ver(path_dist):
    filename = list(Path(path_dist).glob("*.tar.gz"))[0]
    dist_name = filename.stem.removesuffix(".tar.gz")
    package_name, version = dist_name.rsplit("-", 1)
    return package_name, version
