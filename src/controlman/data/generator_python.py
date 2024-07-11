# Standard libraries
from typing import Literal as _Literal
import datetime as _datetime
from pathlib import Path as _Path
import re as _re
import copy as _copy

# Non-standard libraries
import pylinks
import trove_classifiers as _trove_classifiers
import pyserials
from loggerman import logger as _logger
import pyshellman

from controlman import _util, exception as _exception
from versionman import PEP440SemVer
from controlman._path_manager import PathManager
from controlman import ControlCenterContentManager
from controlman.data.cache import APICacheManager
from controlman.protocol import Git as _Git
from controlman.data.generator_custom import ControlCenterCustomContentGenerator


class PythonContentGenerator:

    def __init__(
        self,
        data: dict,
        path_manager: PathManager,
        git_manager: _Git,
        cache: APICacheManager,
        ccm_before: ControlCenterContentManager | dict,
        future_versions: dict[str, str | PEP440SemVer],
        github_api: pylinks.api.GitHub,
    ):
        self._data = data
        self._git = git_manager
        self._ccm_before = ccm_before
        self._pathman = path_manager
        self._future_versions = future_versions
        self._cache = cache
        self._github_api = github_api
        self._pkg: dict | None = None
        return

    def generate(self, typ: _Literal["package", "test"]) -> dict:
        pkg = self._data[typ]
        self._pkg = pkg
        if typ == "package":
            self._package_name()
        else:
            self._package_testsuite_name()
            testsuite_name, testsuite_import_name = self._package_testsuite_name()
            pkg["testsuite_name"] = testsuite_name
            pkg["testsuite_import_name"] = testsuite_import_name

        trove_classifiers = pkg.setdefault("classifiers", [])
        if self._data["license"].get("trove_classifier"):
            trove_classifiers.append(self._data["license"]["trove_classifier"])
        if self._data["package"].get("typed"):
            trove_classifiers.append("Typing :: Typed")

        # package_urls = self._package_platform_urls()
        # self._data["url"] |= {"pypi": package_urls["pypi"], "conda": package_urls["conda"]}

        # dev_info = self._package_development_status()
        # package |= {
        #     "development_phase": dev_info["dev_phase"],
        #     "major_ready": dev_info["major_ready"],
        # }
        # trove_classifiers.append(dev_info["trove_classifier"])

        python_ver_info = self._package_python_versions()
        pkg["python_version_max"] = python_ver_info["python_version_max"]
        pkg["python_versions"] = python_ver_info["python_versions"]
        pkg["python_versions_py3x"] = python_ver_info["python_versions_py3x"]
        pkg["python_versions_int"] = python_ver_info["python_versions_int"]
        trove_classifiers.extend(python_ver_info["trove_classifiers"])

        os_info = self._package_operating_systems()
        trove_classifiers.extend(os_info["trove_classifiers"])
        pkg |= {
            "os_titles": os_info["os_titles"],
            "os_independent": os_info["os_independent"],
            "pure_python": os_info["pure_python"],
            "github_runners": os_info["github_runners"],
            "cibw_matrix_platform": os_info["cibw_matrix_platform"],
            "cibw_matrix_python": os_info["cibw_matrix_python"],
        }

        release_info = self._package_releases()
        pkg["releases"] = {
            "per_branch": release_info["per_branch"],
            "branch_names": release_info["branch_names"],
            "os_titles": release_info["os_titles"],
            "python_versions": release_info["python_versions"],
            "package_versions": release_info["package_versions"],
            "package_managers": release_info["package_managers"],
            "cli_scripts": release_info["cli_scripts"],
            "gui_scripts": release_info["gui_scripts"],
            "has_scripts": release_info["has_scripts"],
            "interfaces": release_info["interfaces"],
        }

        for classifier in trove_classifiers:
            if classifier not in _trove_classifiers.classifiers:
                _logger.error(f"Trove classifier '{classifier}' is not supported.")
        pkg["trove_classifiers"] = sorted(trove_classifiers)
        return self._data

    @_logger.sectioner("Package Name")
    def _package_name(self) -> None:
        name = self._data["name"]
        if not self._pkg.get("name"):
            package_name = _re.sub(r"[ ._-]+", "-", name)
            self._pkg["name"] = package_name
            _logger.info(f"No package name specified", f"setting from project name: {package_name}.")
        if not self._pkg.get("import_name"):
            import_name = self._pkg["name"].replace("-", "_").lower()
            self._pkg["import_name"] = import_name
            _logger.info(f"No package import name specified", f"setting from package name: {import_name}.")
        # _logger.info(title=f"Package name", msg=package_name)
        # _logger.info(title="Package import name", msg=import_name)
        return

    @_logger.sectioner("Package Test-Suite Name")
    def _package_testsuite_name(self) -> tuple[str, str]:
        testsuite_name = pyserials.update.templated_data_from_source(
            templated_data=self._data["package"]["pyproject_tests"]["project"]["name"],
            source_data=self._data
        )
        import_name = testsuite_name.replace("-", "_").lower()
        _logger.info(title="Test-suite name", msg=testsuite_name)
        return testsuite_name, import_name

    # @_logger.sectioner("Package Platform URLs")
    # def _package_platform_urls(self) -> dict:
    #     package_name = self._data["package"]["name"]
    #     url = {
    #         "conda": f"https://anaconda.org/conda-forge/{package_name}/",
    #         "pypi": f"https://pypi.org/project/{package_name}/",
    #     }
    #     _logger.info(title="PyPI", msg=url["pypi"])
    #     _logger.info(title="Conda Forge", msg=url["conda"])
    #     return url

    def _package_development_status(self) -> dict:
        # TODO: add to data
        _logger.section("Package Development Status")
        phase = {
            1: "Planning",
            2: "Pre-Alpha",
            3: "Alpha",
            4: "Beta",
            5: "Production/Stable",
            6: "Mature",
            7: "Inactive",
        }
        status_code = self._data["package"]["development_status"]
        output = {
            "major_ready": status_code in [5, 6],
            "dev_phase": phase[status_code],
            "trove_classifier": f"Development Status :: {status_code} - {phase[status_code]}",
        }
        _logger.info(f"Development info: {output}")
        _logger.section_end()
        return output

    @_logger.sectioner("Package Python Versions")
    def _package_python_versions(self) -> dict:
        min_ver_str = self._data["package"]["python_version_min"]
        min_ver = list(map(int, min_ver_str.split(".")))
        if len(min_ver) < 3:
            min_ver.extend([0] * (3 - len(min_ver)))
        if min_ver < [3, 10, 0]:
            _logger.critical(
                f"Minimum Python version cannot be less than 3.10.0, but got {min_ver_str}."
            )
        min_ver = tuple(min_ver)
        # Get a list of all Python versions that have been released to date.
        current_python_versions = self._get_released_python3_versions()
        compatible_versions_full = [v for v in current_python_versions if v >= min_ver]
        if len(compatible_versions_full) == 0:
            _logger.error(
                f"python_version_min '{min_ver_str}' is higher than "
                f"latest release version '{'.'.join(current_python_versions[-1])}'."
            )
        compatible_minor_versions = sorted(set([v[:2] for v in compatible_versions_full]))
        vers = [".".join(map(str, v)) for v in compatible_minor_versions]
        py3x_format = [f"py{''.join(map(str, v))}" for v in compatible_minor_versions]
        output = {
            "python_version_max": vers[-1],
            "python_versions": vers,
            "python_versions_py3x": py3x_format,
            "python_versions_int": compatible_minor_versions,
            "trove_classifiers": [
                "Programming Language :: Python :: {}".format(postfix) for postfix in ["3 :: Only"] + vers
            ],
        }
        _logger.info(title="Supported versions", msg=str(output["python_versions"]))
        _logger.debug("Generated data:", code=str(output))
        return output

    @_logger.sectioner("Package Operating Systems")
    def _package_operating_systems(self):
        trove_classifiers_postfix = {
            "windows": "Microsoft :: Windows",
            "macos": "MacOS",
            "linux": "POSIX :: Linux",
            "independent": "OS Independent",
        }
        trove_classifier_template = "Operating System :: {}"
        output = {
            "os_titles": [],
            "os_independent": True,
            "pure_python": True,
            "github_runners": [],
            "trove_classifiers": [],
            "cibw_matrix_platform": [],
            "cibw_matrix_python": [],
        }
        os_title = {
            "linux": "Linux",
            "macos": "macOS",
            "windows": "Windows",
        }
        if not self._data["package"].get("operating_systems"):
            _logger.info("No operating systems provided; package is platform independent.")
            output["trove_classifiers"].append(
                trove_classifier_template.format(trove_classifiers_postfix["independent"])
            )
            output["github_runners"].extend(["ubuntu-latest", "macos-latest", "windows-latest"])
            output["os_titles"].extend(list(os_title.values()))
            _logger.section_end()
            return output
        output["os_independent"] = False
        for os_name, specs in self._data["package"]["operating_systems"].items():
            output["os_titles"].append(os_title[os_name])
            output["trove_classifiers"].append(
                trove_classifier_template.format(trove_classifiers_postfix[os_name])
            )
            default_runner = f"{os_name if os_name != 'linux' else 'ubuntu'}-latest"
            if not specs:
                _logger.info(f"No specifications provided for operating system '{os_name}'.")
                output["github_runners"].append(default_runner)
                continue
            runner = default_runner if not specs.get("runner") else specs["runner"]
            output["github_runners"].append(runner)
            if specs.get("cibw_build"):
                for cibw_platform in specs["cibw_build"]:
                    output["cibw_matrix_platform"].append({"runner": runner, "cibw_platform": cibw_platform})
        if output["cibw_matrix_platform"]:
            output["pure_python"] = False
            output["cibw_matrix_python"].extend(
                [f"cp{ver.replace('.', '')}" for ver in self._data["package"]["python_versions"]]
            )
        _logger.debug("Generated data:", code=str(output))
        return output

    @_logger.sectioner("Package Releases")
    def _package_releases(self) -> dict[str, list[str | dict[str, str | list[str] | PEP440SemVer]]]:
        source = self._ccm_before if self._ccm_before else self._data
        release_prefix, pre_release_prefix = allowed_prefixes = tuple(
            source["branch"][group_name]["prefix"] for group_name in ["release", "pre-release"]
        )
        main_branch_name = source["branch"]["main"]["name"]
        branch_pattern = _re.compile(rf"^({release_prefix}|{pre_release_prefix}|{main_branch_name})")
        releases: list[dict] = []
        self._git.fetch_remote_branches_by_pattern(branch_pattern=branch_pattern)
        curr_branch, other_branches = self._git.get_all_branch_names()
        ver_tag_prefix = source["tag"]["group"]["version"]["prefix"]
        branches = other_branches + [curr_branch]
        self._git.stash()
        for branch in branches:
            if not (branch.startswith(allowed_prefixes) or branch == main_branch_name):
                continue
            self._git.checkout(branch)
            if self._future_versions.get(branch):
                ver = PEP440SemVer(str(self._future_versions[branch]))
            else:
                ver = self._git.get_latest_version(tag_prefix=ver_tag_prefix)
            if not ver:
                _logger.warning(f"Failed to get latest version from branch '{branch}'; skipping branch.")
                continue
            if branch == curr_branch:
                branch_metadata = self._data
            else:
                try:
                    branch_metadata = _util.file.read_datafile(
                        path_repo=self._pathman.root,
                        path_data=self._pathman.metadata.rel_path,
                        schema="metadata",
                    )
                except _exception.content.ControlManContentException as e:
                    _logger.warning(f"Failed to read metadata from branch '{branch}'; skipping branch.")
                    _logger.debug("Error Details", e)
                    continue
            if not branch_metadata:
                _logger.warning(f"Failed to read metadata from branch '{branch}'; skipping branch.")
                continue
            if not branch_metadata.get("package", {}).get("python_versions"):
                _logger.warning(f"No Python versions specified for branch '{branch}'; skipping branch.")
                continue
            if not branch_metadata.get("package", {}).get("os_titles"):
                _logger.warning(f"No operating systems specified for branch '{branch}'; skipping branch.")
                continue
            if branch == main_branch_name:
                branch_name = self._data["branch"]["main"]["name"]
            elif branch.startswith(release_prefix):
                new_prefix = self._data["branch"]["release"]["prefix"]
                branch_name = f"{new_prefix}{branch.removeprefix(release_prefix)}"
            else:
                new_prefix = self._data["branch"]["pre-release"]["prefix"]
                branch_name = f"{new_prefix}{branch.removeprefix(pre_release_prefix)}"
            release_info = {
                "branch": branch_name,
                "version": str(ver),
                "python_versions": branch_metadata["package"]["python_versions"],
                "os_titles": branch_metadata["package"]["os_titles"],
                "package_managers": ["pip"] + (["conda"] if branch_metadata["package"].get("conda") else []),
                "cli_scripts": [
                    script["name"] for script in branch_metadata["package"].get("cli_scripts", [])
                ],
                "gui_scripts": [
                    script["name"] for script in branch_metadata["package"].get("gui_scripts", [])
                ],
            }
            releases.append(release_info)
        self._git.checkout(curr_branch)
        self._git.stash_pop()
        releases.sort(key=lambda i: i["version"], reverse=True)
        all_branch_names = []
        all_python_versions = []
        all_os_titles = []
        all_package_versions = []
        all_package_managers = []
        all_cli_scripts = []
        all_gui_scripts = []
        for release in releases:
            all_branch_names.append(release["branch"])
            all_os_titles.extend(release["os_titles"])
            all_python_versions.extend(release["python_versions"])
            all_package_versions.append(str(release["version"]))
            all_package_managers.extend(release["package_managers"])
            all_cli_scripts.extend(release["cli_scripts"])
            all_gui_scripts.extend(release["gui_scripts"])
        all_os_titles = sorted(set(all_os_titles))
        all_python_versions = sorted(set(all_python_versions), key=lambda ver: tuple(map(int, ver.split("."))))
        all_package_managers = sorted(set(all_package_managers))
        all_cli_scripts = sorted(set(all_cli_scripts))
        all_gui_scripts = sorted(set(all_gui_scripts))
        out = {
            "per_branch": releases,
            "branch_names": all_branch_names,
            "os_titles": all_os_titles,
            "python_versions": all_python_versions,
            "package_versions": all_package_versions,
            "package_managers": all_package_managers,
            "cli_scripts": all_cli_scripts,
            "gui_scripts": all_gui_scripts,
            "has_scripts": bool(all_cli_scripts or all_gui_scripts),
            "interfaces": ["Python API"],
        }
        if all_cli_scripts:
            out["interfaces"].append("CLI")
        if all_gui_scripts:
            out["interfaces"].append("GUI")
        _logger.debug(f"Generated data:", code=str(out))
        return out

    @_logger.sectioner("Get Current Python Versions")
    def _get_released_python3_versions(self) -> list[tuple[int, int, int]]:
        release_versions = self._cache.get("python_versions")
        if release_versions:
            return [tuple(ver) for ver in release_versions]
        _logger.info("Get Python versions from GitHub API")
        vers = self._github_api.user("python").repo("cpython").semantic_versions(tag_prefix="v")
        release_versions = sorted(set([v for v in vers if v[0] >= 3]))
        self._cache.set("python_versions", release_versions)
        return release_versions
