# Standard libraries
import re as _re

# Non-standard libraries
from packaging import specifiers as _specifiers

from gittidy import Git as _Git
import pylinks
from loggerman import logger as _logger
import pyserials as _ps

from controlman import exception as _exception
from controlman.cache_manager import CacheManager


class PythonDataGenerator:

    def __init__(
        self,
        data: _ps.NestedDict,
        git_manager: _Git,
        cache: CacheManager,
        github_api: pylinks.api.GitHub,
    ):
        self._data = data
        self._git = git_manager
        self._cache = cache
        self._github_api = github_api
        return

    def generate(self):
        self._package_python_versions()
        return

    def _package_python_versions(self) -> None:

        def get_python_releases():
            release_versions = self._cache.get("python", "releases")
            if release_versions:
                return release_versions
            release_versions = self._github_api.user("python").repo("cpython").semantic_versions(tag_prefix="v")
            live_versions = []
            for version in release_versions:
                version_tuple = tuple(map(int, version.split(".")))
                if version_tuple[0] < 2:
                    continue
                if version_tuple[0] == 2 and version_tuple[1] < 3:
                    continue
                live_versions.append(version)
            live_versions = sorted(live_versions, key=lambda x: tuple(map(int, x.split("."))))
            self._cache.set("python", "releases", live_versions)
            return live_versions

        version_spec_key = "pkg.python.version.spec"
        spec_str = self._data.fill(version_spec_key)
        if not spec_str:
            _exception.load.ControlManSchemaValidationError(
                source="source",
                before_substitution=True,
                problem="The package has not specified a Python version specifier.",
                json_path=version_spec_key,
                data=self._data(),
            )
        try:
            spec = _specifiers.SpecifierSet(spec_str)
        except _specifiers.InvalidSpecifier as e:
            raise _exception.load.ControlManSchemaValidationError(
                source="source",
                before_substitution=True,
                problem=f"Invalid Python version specifier '{spec_str}'.",
                json_path=version_spec_key,
                data=self._data(),
            ) from None

        current_python_versions = get_python_releases()
        micro_str = []
        micro_int = []
        minor_str = []
        minor_int = []
        for compat_ver_micro_str in spec.filter(current_python_versions):
            micro_str.append(compat_ver_micro_str)
            compat_ver_micro_int = tuple(map(int, compat_ver_micro_str.split(".")))
            micro_int.append(compat_ver_micro_int)
            compat_ver_minor_str = ".".join(map(str, compat_ver_micro_int[:2]))
            if compat_ver_minor_str in minor_str:
                continue
            minor_str.append(compat_ver_minor_str)
            minor_int.append(compat_ver_micro_int[:2])

        if len(micro_str) == 0:
            raise _exception.load.ControlManSchemaValidationError(
                source="source",
                before_substitution=True,
                problem=f"The Python version specifier '{spec_str}' does not match any "
                f"released Python version: '{current_python_versions}'.",
                json_path=version_spec_key,
                data=self._data(),
            )
        output = {
            "micros": sorted(micro_str, key=lambda x: tuple(map(int, x.split(".")))),
            "minors": sorted(minor_str, key=lambda x: tuple(map(int, x.split(".")))),
        }
        self._data["pkg.python.version"].update(output)
        if self._data["test"]:
            self._data["test.python.version.spec"] = spec_str
        return
