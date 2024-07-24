import re as _re

from versionman import PEP440SemVer
from loggerman import logger as _logger

from controlman.nested_dict import NestedDict as _NestedDict
from controlman.protocol import Git as _Git
from controlman import data_man as _data_man
from controlman import exception as _exception
from controlman import version as _version


class RepoDataGenerator:

    def __init__(
        self,
        data: _NestedDict,
        git_manager: _Git,
        data_main: _NestedDict | None = None,
        future_versions: dict[str, str | PEP440SemVer] | None = None,
    ):
        self._data = data
        self._data_main = data_main
        self._git = git_manager
        self._future_versions = future_versions or {}
        return

    def generate(self):
        self._package_releases()
        self._repo_labels()
        return

    def _package_releases(self) -> None:
        curr_branch, other_branches = self._git.get_all_branch_names()
        main_branch = self._data["repo.default_branch"]
        release_prefix, pre_release_prefix = allowed_prefixes = tuple(
            self._data_main[f"branch.{group_name}.name"] for group_name in ["release", "pre"]
        )
        branch_pattern = _re.compile(rf"^({release_prefix}|{pre_release_prefix}|{main_branch})")
        self._git.fetch_remote_branches_by_pattern(branch_pattern=branch_pattern)
        ver_tag_prefix = self._data_main.fill("tag.version.prefix")
        branches = other_branches + [curr_branch]
        release_info: dict = {}
        curr_branch_latest_version = None
        self._git.stash()
        for branch in branches:
            if not (branch.startswith(allowed_prefixes) or branch == main_branch):
                continue
            self._git.checkout(branch)
            if self._future_versions.get(branch):
                ver = PEP440SemVer(str(self._future_versions[branch]))
            else:
                ver, dist = _version.get_latest_version(version_tag_prefix=ver_tag_prefix, git_manager=self._git)
            if not ver:
                _logger.warning(f"Failed to get latest version from branch '{branch}'; skipping branch.")
                continue
            if branch == curr_branch:
                branch_metadata = self._data
                curr_branch_latest_version = ver
            elif branch == main_branch:
                branch_metadata = self._data_main
            else:
                try:
                    branch_metadata = _data_man.from_json_file(repo_path=self._git.repo_path)
                except _exception.ControlManException as e:
                    _logger.warning(f"Failed to read metadata from branch '{branch}'; skipping branch.")
                    _logger.debug("Error Details", e)
                    continue
            if branch == main_branch:
                branch_name = self._data.fill("branch.main.name")
            elif branch.startswith(release_prefix):
                new_prefix = self._data.fill("branch.release.name")
                branch_name = f"{new_prefix}{branch.removeprefix(release_prefix)}"
            else:
                new_prefix = self._data.fill("branch.pre.name")
                branch_name = f"{new_prefix}{branch.removeprefix(pre_release_prefix)}"
            version_info = {"branch": branch_name}
            pkg_info = branch_metadata["pkg"]
            if pkg_info:
                package_managers = [
                    package_man_name for platform_name, package_man_name in (
                        ("pypi", "pip"), ("conda", "conda")
                    ) if platform_name in pkg_info
                ]
                if branch == curr_branch:
                    branch_metadata.fill("pkg.entry")
                version_info |= {
                    "python_version_minors": branch_metadata["pkg.python.version.minors"],
                    "os_names": [os["name"] for os in branch_metadata["pkg.os"].values()],
                    "package_managers": package_managers,
                    "cli_names": [
                        script["name"] for script in branch_metadata.get("pkg.entry.cli", {}).values()
                    ],
                    "gui_names": [
                        script["name"] for script in branch_metadata.get("pkg.entry.gui", {}).values()
                    ],
                    "api_names": [
                        script["name"] for script in branch_metadata.get("pkg.entry.api", {}).values()
                    ]
                }
            release_info[str(ver)] = version_info
        self._git.checkout(curr_branch)
        self._git.stash_pop()
        self._data["version"] = release_info
        out = {"versions": [], "branches": [], "interfaces": ["Python API"]}
        for version, version_info in release_info.items():
            out["versions"].append(version)
            out["branches"].append(version_info["branch"])
            for info_key, info in version_info.items():
                if info_key != "branch":
                    out.setdefault(info_key, []).extend(info)
        for key, val in out.items():
            out[key] = sorted(
                set(val),
                key=lambda x: x if key!="python_versions_minors" else tuple(map(int, x.split(".")))
            )
        for key in ("cli_names", "gui_names", "api_names"):
            if key in out:
                out["interfaces"].append(key.removesuffix("_names").upper())
                out["has_scripts"] = True
        self._data["project"] = out
        if curr_branch_latest_version and self._data["pkg"]:
            self._package_development_status(curr_branch_latest_version)
        return

    def _package_development_status(self, ver: PEP440SemVer) -> dict:
        phase = {
            1: "Planning",
            2: "Pre-Alpha",
            3: "Alpha",
            4: "Beta",
            5: "Production/Stable",
            6: "Mature",
            7: "Inactive",
        }
        if ver.release == (0, 0, 0):
            status_code = 1
        elif ver.dev is not None:
            status_code = 2
        elif ver.pre:
            if ver.pre[0] == "a":
                status_code = 3
            else:
                status_code = 4
        elif ver.major == 0:
            status_code = 4
        else:
            latest_ver = max(PEP440SemVer(ver) for ver in self._data["project"]["versions"])
            if ver.major < latest_ver.major:
                status_code = 6
            else:
                status_code = 5
        self._data["pkg.classifiers"].append(f"Development Status :: {status_code} - {phase[status_code]}")
        return

    @_logger.sectioner("Repository Labels")
    def _repo_labels(self) -> None:
        out = []
        for label_type in ("type", "subtype", "status"):
            group = self._data.get(f"label.{label_type}", {})
            if not group:
                continue
            prefix = group["prefix"]
            color = group["color"]
            for label_id, label in self._data.get(f"label.{label_type}.label", {}).items():
                out.append(
                    {
                        "type": "defined",
                        "group_name": label_type,
                        "id": label_id,
                        "name": f"{prefix}{label['suffix']}",
                        "description": label["description"],
                        "color": color,
                    }
                )
        for group_name, group in self._data.get("label.custom.group", {}).items():
            prefix = group["prefix"]
            color = group["color"]
            for label_id, label in group.get("label", {}).items():
                out.append(
                    {
                        "type": "custom_group",
                        "group_name": group_name,
                        "id": label_id,
                        "name": f"{prefix}{label['suffix']}",
                        "description": label["description"],
                        "color": color,
                    }
                )
        for label_id, label_data in self._data.get("label.single.label", {}).items():
            out.append(
                {
                    "type": "custom_single",
                    "group_name": None,
                    "id": label_id,
                    "name": label_data["name"],
                    "description": label_data["description"],
                    "color": label_data["color"],
                }
            )
        for autogroup_name, release_key in (("version", "versions"), ("branch", "branches")):
            entries = self._data.get(f"project.{release_key}", [])
            label_data = self._data[f"label.{autogroup_name}"]
            for entry in entries:
                out.append(
                    {
                        "type": "auto",
                        "group_name": autogroup_name,
                        "id": entry,
                        "name": f"{label_data['prefix']}{entry}",
                        "description": label_data["description"],
                        "color": label_data["color"],
                    }
                )
        _logger.info("Successfully compiled all labels")
        _logger.debug("Generated data:", code=str(out))
        self._data["label.all"] = out
        return
