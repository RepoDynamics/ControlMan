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
from repodynamics.meta.writer import OutputFile, OutputPaths


class PackageFileGenerator:
    def __init__(
        self,
        metadata: dict,
        package_config: tomlkit.TOMLDocument,
        path_root: str | Path = ".",
        logger: Logger = None
    ):
        self._logger = logger or Logger()
        self._meta = metadata
        self._pyproject = package_config
        self._path_root = Path(path_root).resolve()
        self._out_db = OutputPaths(path_root=self._path_root, logger=self._logger)
        return

    def generate(self):
        return self.requirements() + self.init_docstring() + self.pyproject()

    def requirements(self) -> list[tuple[OutputFile, str]]:
        self._logger.h3("Generate File Content: requirements.txt")
        info = self._out_db.package_requirements
        text = ""
        if self._meta["package"].get("core_dependencies"):
            for dep in self._meta["package"]["dependencies"]:
                text += f"{dep['pip_spec']}\n"
        if self._meta["package"].get("optional_dependencies"):
            for dep_group in self._meta["package"]["optional_dependencies"]:
                for dep in dep_group["packages"]:
                    text += f"{dep['pip_spec']}\n"
        return [(info, text)]

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

    def init_docstring(self) -> list[tuple[OutputFile, str]]:
        self._logger.h3("Generate File Content: __init__.py")
        info = self._out_db.package_init
        text = self._meta["package"].get("docs", {}).get("main_init", "").strip()
        return [(info, text)]

    def pyproject(self) -> list[tuple[OutputFile, str]]:
        info = self._out_db.package_pyproject
        pyproject = _util.dict.fill_template(self._pyproject, metadata=self._meta)
        project = pyproject.setdefault("project", {})
        for key, val in self.pyproject_project().items():
            if key not in project:
                project[key] = val
        return [(info, tomlkit.dumps(pyproject))]

    def pyproject_project(self) -> dict:
        data_type = {
            "name": ("str", self._meta["package"]["name"]),
            "dynamic": ("array", ["version"]),
            "description": ("str", self._meta.get("tagline")),
            "readme": ("str", self._out_db.readme_pypi.rel_path),
            "requires-python": ("str", f">= {self._meta['package']['python_version_min']}"),
            "license": (
                "inline_table",
                {"file": self._out_db.license.rel_path} if self._meta.get("license") else None
            ),
            "authors": ("array_of_inline_tables", self.pyproject_project_authors),
            "maintainers": ("array_of_inline_tables", self.pyproject_project_maintainers),
            "keywords": ("array", self._meta.get("keywords")),
            "classifiers": ("array", self._meta["package"].get("trove_classifiers")),
            "urls": ("table", self._meta["package"].get("urls")),
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
    def pyproject_project_authors(self):
        return self._get_authors_maintainers(role="authors")

    @property
    def pyproject_project_maintainers(self):
        return self._get_authors_maintainers(role="maintainers")

    @property
    def pyproject_project_dependencies(self):
        if not self._meta["package"].get("core_dependencies"):
            return
        return [dep["pip_spec"] for dep in self._meta["package"]["core_dependencies"]]

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

    def _get_authors_maintainers(self, role: Literal["authors", "maintainers"]):
        """
        Update the project authors in the pyproject.toml file.

        References
        ----------
        https://packaging.python.org/en/latest/specifications/declaring-project-metadata/#authors-maintainers
        """
        people = []
        target_people = (
            self._meta.get("maintainer", {}).get("list", []) if role == "maintainers"
            else self._meta.get("authors", [])
        )
        for person in target_people:
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
