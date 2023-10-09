"""Package File Generator

"""


# Standard libraries
import datetime
from pathlib import Path
from typing import Literal
import re

# Non-standard libraries
import tomlkit
import tomlkit.items

from repodynamics.logger import Logger
from repodynamics.meta.reader import MetaReader
from repodynamics import _util


class PackageFileGenerator:
    def __init__(self, metadata: dict, reader: MetaReader, logger: Logger = None):
        self._reader = reader
        self._logger = logger or self._reader.logger
        self._meta = metadata
        self._root = self._reader.path.root
        return

    def generate(self):
        updates = [
            dict(category="package", name=name, content=content)
            for name, content in [
                ("pyproject", self.pyproject()),
                ("dir", self._package_dir()),
                ("docstring", self.init_docstring()),
                ("requirements", self._requirements()),
            ]
        ]
        return updates

    def _package_dir(self):
        self._logger.h4("Update path: package")
        path_src = self._reader.path.dir_source
        package_name = self._meta["package"]["name"]
        path_package = path_src / package_name
        if path_package.exists():
            self._logger.skip(f"Package path exists", f"{path_package}")
            return path_package, path_package
        self._logger.info(
            f"Package path '{path_package}' does not exist; looking for package directory."
        )
        package_dirs = [
            subdir
            for subdir in [
                content for content in path_src.iterdir() if content.is_dir()
            ]
            if "__init__.py"
            in [
                sub_content.name
                for sub_content in subdir.iterdir()
                if sub_content.is_file()
            ]
        ]
        count_dirs = len(package_dirs)
        if count_dirs == 0:
            self._logger.success(
                f"No package directory found in '{path_src}'; creating one."
            )
            return None, path_package
        elif count_dirs == 1:
            self._logger.success(
                f"Rename package directory to '{package_name}'",
                f"Old Path: '{package_dirs[0]}'\nNew Path: '{path_package}'",
            )
            return package_dirs[0], path_package
        else:
            self._logger.error(
                f"More than one package directory found in '{path_src}'",
                "\n".join([str(package_dir) for package_dir in package_dirs]),
            )
        return

    def init_docstring(self) -> str:
        self._logger.h3("Generate File Content: __init__.py")
        content = self._meta["package"]["init"].format(**self._meta).strip()
        return content

    def pyproject(self):
        pyproject = _util.dict.fill_template(self._reader.package_config, metadata=self._meta)
        project = pyproject.setdefault("project", {})
        for key, val in self.pyproject_project().items():
            if key not in project:
                project[key] = val
        return tomlkit.dumps(pyproject)

    def pyproject_project(self) -> dict:
        data_type = {
            "name": ("str", self._meta["package"]["name"]),
            "dynamic": ("array", ["version"]),
            "description": ("str", self._meta["tagline"]),
            "readme": ("str", f"{self._meta['path']['source']}/readme_pypi.md"),
            "requires-python": ("str", f">= {self._meta['package']['python_version_min']}"),
            "license": ("inline_table", {"file": "LICENSE"}),
            "authors": ("array_of_inline_tables", self.pyproject_project_authors),
            "maintainers": ("array_of_inline_tables", self.pyproject_project_maintainers),
            "keywords": ("array", self._meta["keywords"]),
            "classifiers": ("array", self._meta["package"]["trove_classifiers"]),
            "urls": ("table", self.pyproject_project_urls),
            "scripts": ("table", self.pyproject_project_scripts),
            "gui-scripts": ("table", self.pyproject_project_gui_scripts),
            "entry-points": ("table_of_tables", self.pyproject_project_entry_points),
            "dependencies": ("array", self.pyproject_project_dependencies),
            "optional-dependencies": ("table_of_arrays", self.pyproject_project_optional_dependencies),
        }
        project = {}
        for key, (dtype, val) in data_type.items():
            if val:
                project[key] = _util.toml.format_object(obj=val, toml_type=dtype)
        return project

    @property
    def pyproject_project_urls(self):
        # For list of URL keys, see:
        # https://github.com/pypi/warehouse/blob/e69029dc1b23eb2436a940038b927e772238a7bf/warehouse/templates/packaging/detail.html#L20-L62
        return {
            "Homepage": self._meta["url"]["website"]["base"],
            "Download": self._meta["url"]["github"]["releases"]["home"],
            "News": self._meta["url"]["website"]["news"],
            "Documentation": self._meta["url"]["website"]["base"],
            "Bug Tracker": self._meta["url"]["github"]["issues"]["home"],
            "Sponsor": self._meta["url"]["website"]["sponsor"],
            "Source": self._meta["url"]["github"]["home"],
        }

    @property
    def pyproject_project_authors(self):
        return self._get_authors_maintainers(role="authors")

    @property
    def pyproject_project_maintainers(self):
        return self._get_authors_maintainers(role="maintainers")

    @property
    def pyproject_project_dependencies(self):
        if not self._meta["package"].get("dependencies"):
            return
        return [dep["pip_spec"] for dep in self._meta["package"]["dependencies"]]

    @property
    def pyproject_project_optional_dependencies(self):
        return (
            {
                dep_group["name"]: [dep["pip_spec"] for dep in dep_group["packages"]]
                for dep_group in self._meta["package"]["optional_dependencies"]
            }
            if self._meta["package"].get("optional_dependencies")
            else None
        )

    @property
    def pyproject_project_scripts(self):
        return self._scripts(gui=False)

    @property
    def pyproject_project_gui_scripts(self):
        return self._scripts(gui=True)

    @property
    def pyproject_project_entry_points(self):
        return (
            {
                entry_group["group_name"]: {
                    entry_point["name"]: entry_point["ref"]
                    for entry_point in entry_group["entry_points"]
                }
                for entry_group in self._meta["package"]["entry_points"]
            }
            if self._meta["package"].get("entry_points")
            else None
        )

    def _requirements(self) -> str:
        self._logger.h3("Generate File Content: requirements.txt")
        requirements = ""
        if self._meta["package"].get("dependencies"):
            for dep in self._meta["package"]["dependencies"]:
                requirements += f"{dep['pip_spec']}\n"
        if self._meta["package"].get("optional_dependencies"):
            for dep_group in self._meta["package"]["optional_dependencies"]:
                for dep in dep_group["packages"]:
                    requirements += f"{dep['pip_spec']}\n"
        return requirements

    def _get_authors_maintainers(self, role: Literal["authors", "maintainers"]):
        """
        Update the project authors in the pyproject.toml file.

        References
        ----------
        https://packaging.python.org/en/latest/specifications/declaring-project-metadata/#authors-maintainers
        """
        people = []
        for person in self._meta[role]:
            if not person["name"]:
                self._logger.warning(
                    f'One of {role} with username \'{person["username"]}\' '
                    f"has no name set in their GitHub account. They will be dropped from the list of {role}."
                )
                continue
            user = {"name": person["name"]}
            email = person.get("email")
            if email:
                user["email"] = email
            people.append(user)
        return people

    def _scripts(self, gui: bool):
        cat = "gui_scripts" if gui else "scripts"
        return (
            {script["name"]: script["ref"] for script in self._meta["package"][cat]}
            if self._meta["package"].get(cat)
            else None
        )
