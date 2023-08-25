import re

import pylinks
import trove_classifiers

from repodynamics.meta import db
from repodynamics.logger import Logger


class Python:

    def __init__(self, metadata, cache, logger: Logger = None):
        self.metadata = metadata
        self.package = metadata["package"]
        self.cache = cache
        self.logger = logger or Logger("console")
        return

    def fill(self):
        self.name()
        self.platform_urls()
        self.development_status()
        self.license()
        self.python_versions()
        self.operating_systems()
        for classifier in self.package["trove_classifiers"]:
            if classifier not in trove_classifiers.classifiers:
                self.logger.error(f"Trove classifier '{classifier}' is not supported.")
        return

    def name(self):
        self.logger.section("Process metadata: package.name")
        name = self.metadata["name"]
        self.package["name"] = re.sub(r"[ ._-]+", "-", name.lower())
        self.logger.success(f"package.name: {self.package['name']}")
        return

    def platform_urls(self):
        url = self.metadata.setdefault("url", {})
        package_name = self.metadata["package"]["name"]
        url["conda"] = f"https://anaconda.org/conda-forge/{package_name}/"
        url["pypi"] = f"https://pypi.org/project/{package_name}/"
        return

    def development_status(self):
        self.logger.section("Process metadata: package.development_status")
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
        self.package["development_status"] = phase[status_code]
        trove_classifier = f"Development Status :: {status_code} - {phase[status_code]}"
        self.package["trove_classifiers"].append(trove_classifier)
        self.logger.success(f"Development status: {phase[status_code]}")
        self.logger.success(f"Set trove classifier: {trove_classifier}")
        return

    def license(self):
        self.logger.section("Process metadata: license_id (trove classifier)")
        license_id = self.metadata.get("license_id")
        if not license_id:
            self.logger.attention("No license ID provided; skipping.")
            return
        license_data = db.license[license_id]
        self.package["trove_classifiers"].append(
            f"License :: OSI Approved :: {license_data['trove_classifier']}"
        )
        self.logger.success(f"Set trove classifier: {license_data['trove_classifier']}")
        return

    def python_versions(self):
        self.logger.section("Process metadata: package.python_version_min")
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
            self.logger.error(
                f"python_version_min '{min_ver}' is higher than "
                f"latest release version '{'.'.join(current_python_versions[-1])}'."
            )
        self.package["python_versions"] = vers
        self.logger.success(f"Set package.python_versions: {vers}")
        # Add trove classifiers
        classifiers = [
            "Programming Language :: Python :: {}".format(postfix)
            for postfix in ["3 :: Only"] + vers
        ]
        self.package["trove_classifiers"].extend(classifiers)
        self.logger.success(f"Set trove classifiers: {classifiers}")
        return

    def operating_systems(self):
        self.logger.section("Process metadata: package.operating_systems")
        trove_classifiers_postfix = {
            "windows": "Microsoft :: Windows",
            "macos": "MacOS",
            "linux": "POSIX :: Linux",
            "independent": "OS Independent",
        }
        trove_classifier_template = "Operating System :: {}"
        if not self.package.get("operating_systems"):
            self.logger.attention("No operating systems provided.")
            self.package["os_independent"] = True
            self.package["pure_python"] = True
            self.package["github_runners"] = ["ubuntu-latest", "macos-latest", "windows-latest"]
            self.package["trove_classifiers"].append(
                trove_classifier_template.format(trove_classifiers_postfix["independent"])
            )
            return

        self.package["os_independent"] = False
        self.package["github_runners"] = []
        cibw_platforms = []
        for os_name, specs in self.package["operating_systems"].items():
            self.package["trove_classifiers"].append(
                trove_classifier_template.format(trove_classifiers_postfix[os_name])
            )
            default_runner = f"{os_name if os_name != 'linux' else 'ubuntu'}-latest"
            if not specs:
                self.logger.attention(f"No specifications provided for operating system '{os_name}'.")
                self.package["github_runners"].append(default_runner)
                continue
            runner = default_runner if not specs.get("runner") else specs["runner"]
            self.package["github_runners"].append(runner)
            if specs.get("cibw_build"):
                for cibw_platform in specs["cibw_build"]:
                    cibw_platforms.append({"runner": runner, "cibw_platform": cibw_platform})

        if cibw_platforms:
            self.package["pure_python"] = False
            self.package["cibw_matrix_platform"] = cibw_platforms
            self.package["cibw_matrix_python"] = [
                f"cp{ver.replace('.', '')}" for ver in self.package["python_versions"]
            ]
        else:
            self.package["pure_python"] = True
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
