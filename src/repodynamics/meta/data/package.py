import re

import pylinks
import trove_classifiers

from repodynamics.meta import db


class Python:

    def __init__(self, metadata, cache):
        self.metadata = metadata
        self.package = metadata["package"]
        self.cache = cache
        return

    def fill(self):
        self.name()
        self.development_status()
        self.python_versions()
        self.operating_systems()
        for classifier in self.package["trove_classifiers"]:
            if classifier not in trove_classifiers.classifiers:
                raise ValueError(f"Trove classifier '{classifier}' is not supported anymore.")
        return

    def name(self):
        repo_name = self.metadata["repo"]["name"]
        if not re.match(
            r"^([A-Z0-9]|[A-Z0-9][A-Z0-9._-]*[A-Z0-9])$",
            repo_name,
            flags=re.IGNORECASE,
        ):
            raise ValueError(
                "Repository name must only consist of alphanumeric characters, period (.), "
                "underscore (_) and hyphen (-), and can only start and end with an alphanumeric character, "
                f"but got {repo_name}. "
                "See https://packaging.python.org/en/latest/specifications/name-normalization/ for more details."
            )
        self.package["name"] = re.sub(
            r"[._-]+", "-", repo_name.lower()
        )
        return

    def development_status(self):
        phase = {
            1: "Planning",
            2: "Pre-Alpha",
            3: "Alpha",
            4: "Beta",
            5: "Production/Stable",
            6: "Mature",
            7: "Inactive",
        }
        status_code = self.package["development_status"]
        if isinstance(status_code, str):
            status_code = int(status_code)
        if status_code not in range(1, 8):
            raise ValueError("Project development status must be an integer between 1 and 7.")
        self.package["development_status"] = phase[status_code]
        self.package["trove_classifiers"].append(
            f"Development Status :: {status_code} - {phase[status_code]}"
        )
        return

    def license(self):
        license_id = self.metadata["copyright"]["license"]["id"].lower()
        license_data = db.license.get(license_id)
        if not license_data:
            raise ValueError(f"License ID '{license_id}' is not supported.")
        self.package["trove_classifiers"].append(
            f"License :: OSI Approved :: {license_data['trove_classifier']}"
        )
        return

    def python_versions(self):
        min_ver = self.package["python_version_min"]
        ver = tuple(map(int, min_ver.split(".")))
        if ver[0] != 3:
            raise ValueError(f"Minimum Python version must be 3.x, but got {min_ver}.")
        # Get a list of all Python versions that have been released to date.
        current_python_versions = self.released_python_versions()
        vers = [
            ".".join(map(str, v))
            for v in sorted(
                set([tuple(v[:2]) for v in current_python_versions if v[0] == 3 and v[1] >= ver[1]])
            )
        ]
        if len(vers) == 0:
            raise ValueError(f"Minimum Python version is higher than latest release version.")
        self.package["python_versions"] = vers
        self.package["python_versions_cibuild"] = [ver.replace(".", "") for ver in vers]
        # Add trove classifiers
        classifiers = [
            "Programming Language :: Python :: {}".format(postfix)
            for postfix in ["3 :: Only"] + vers
        ]
        self.package["trove_classifiers"].extend(classifiers)
        return

    def operating_systems(self):
        trove_classifiers_postfix = {
            "windows": "Microsoft :: Windows",
            "macos": "MacOS",
            "linux": "POSIX :: Linux",
            "independent": "OS Independent",
        }
        trove_classifier_template = "Operating System :: {}"
        github_os_matrix = []
        build_matrix = []
        for os in self.package["operating_systems"]:
            os_id = os["id"].lower()
            if os_id not in ["linux", "macos", "windows"]:
                raise ValueError(
                    f"Operating system ID '{os_id}' is not supported. "
                    "Supported operating system IDs are 'linux', 'macos', and 'windows'."
                )
            self.package["trove_classifiers"].append(
                trove_classifier_template.format(trove_classifiers_postfix[os_id])
            )
            github_runner = f"{os_id if os_id != 'linux' else 'ubuntu'}-latest"
            github_os_matrix.append(github_runner)
            if os["cibuilds"]:
                for cibuild in os["cibuilds"]:
                    build_matrix.append((github_runner, cibuild))
        self.package["github_runners"] = github_os_matrix
        self.package["build_matrix"] = build_matrix
        is_pure_python = not build_matrix
        self.package["is_pure_python"] = is_pure_python
        if is_pure_python:
            self.package["trove_classifiers"].append(
                trove_classifier_template.format(trove_classifiers_postfix["independent"])
            )
        return

    def released_python_versions(self):
        release_versions = self.cache['python_versions']
        if release_versions:
            return release_versions
        vers = pylinks.api.github.repo(username="python", repo_name="cpython").semantic_versions(
            tag_prefix="v"
        )
        release_versions = sorted(set([v[:2] for v in vers if v[0] >= 3]))
        self.cache["python_versions"] = release_versions
        return release_versions


def fill(metadata, cache):
    language = metadata["package"]["language"].lower()
    match language:
        case "python":
            Python(metadata, cache).fill()
        case _:
            raise ValueError(f"Package language '{language}' is not supported.")
    return
