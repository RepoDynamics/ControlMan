import json
from pathlib import Path

from markitup import html, md



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
