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
from repodynamics.path import OutputPath
from repodynamics.datatype import DynamicFile


class PackageFileGenerator:
    def __init__(
        self,
        metadata: dict,
        package_config: tomlkit.TOMLDocument,
        test_package_config: tomlkit.TOMLDocument,
        output_path: OutputPath,
        logger: Logger = None
    ):
        self._logger = logger or Logger()
        self._meta = metadata
        self._pyproject = package_config
        self._pyproject_test = test_package_config
        self._out_db = output_path

        self._package_dir_output = []
        return

    def generate(self):
        self._package_dir_output = self._package_dir()
        return (
            self.requirements()
            + self.init_docstring()
            + self.pyproject()
            + self.pyproject_tests()
            + self._package_dir_output
            + self._package_dir(tests=True)
            + self.typing_marker()
            + self.manifest()
        )

    def typing_marker(self) -> list[tuple[DynamicFile, str]]:
        info = self._out_db.package_typing_marker(package_name=self._meta["package"]["name"])
        text = (
            "# PEP 561 marker file. See https://peps.python.org/pep-0561/\n"
            if self._meta["package"].get("typed") else ""
        )
        return [(info, text)]

    def requirements(self) -> list[tuple[DynamicFile, str]]:
        self._logger.h3("Generate File Content: requirements.txt")
        info = self._out_db.package_requirements
        text = ""
        if self._meta["package"].get("core_dependencies"):
            for dep in self._meta["package"]["core_dependencies"]:
                text += f"{dep['pip_spec']}\n"
        if self._meta["package"].get("optional_dependencies"):
            for dep_group in self._meta["package"]["optional_dependencies"]:
                for dep in dep_group["packages"]:
                    text += f"{dep['pip_spec']}\n"
        return [(info, text)]

    def _package_dir(self, tests: bool = False) -> list[tuple[DynamicFile, str]]:
        self._logger.h4("Update path: package")
        package_name = self._meta["package"]["name"]
        name = package_name if not tests else f"{package_name}_tests"
        sub_path = self._meta["path"]["dir"]["source"] if not tests else f'{self._meta["path"]["dir"]["tests"]}/src'
        path = self._out_db.root / sub_path / name
        func = self._out_db.package_tests_dir if tests else self._out_db.package_dir
        if path.exists():
            self._logger.skip(f"Package path exists", f"{path}")
            out = [(func(name, path, path), "")]
            return out
        self._logger.info(
            f"Package path '{path}' does not exist; looking for package directory."
        )
        package_dirs = [
            subdir
            for subdir in [
                content for content in path.parent.iterdir() if content.is_dir()
            ]
            if "__init__.py"
            in [
                sub_content.name
                for sub_content in subdir.iterdir()
                if sub_content.is_file()
            ]
        ] if path.parent.is_dir() else []
        count_dirs = len(package_dirs)
        if count_dirs > 1:
            self._logger.error(
                f"More than one package directory found in '{path}'",
                "\n".join([str(package_dir) for package_dir in package_dirs]),
            )
        if count_dirs == 1:
            self._logger.success(
                f"Rename package directory to '{name}'",
                f"Old Path: '{package_dirs[0]}'\nNew Path: '{path}'",
            )
            out = [(func(package_name, old_path=package_dirs[0], new_path=path), "")]
            package_old_name = package_dirs[0].name
            for filepath in self._out_db.root.glob("**/*.py") if not tests else path.glob("**/*.py"):
                new_content = self.rename_imports(
                    module_content=path.read_text(),
                    old_name=package_old_name,
                    new_name=name
                )
                out.append((self._out_db.python_file(filepath), new_content))
            return out
        self._logger.success(
            f"No package directory found in '{path}'; creating one."
        )
        out = [(func(name, old_path=None, new_path=path), "")]
        for testsuite_filename in ["__init__.txt", "__main__.txt", "general_tests.txt"]:
            filepath = _util.file.datafile(f"template/testsuite/{testsuite_filename}")
            text = _util.dict.fill_template(filepath.read_text(), metadata=self._meta)
            out.append((self._out_db.python_file((path / testsuite_filename).with_suffix(".py")), text))
        return out

    def init_docstring(self) -> list[tuple[DynamicFile, str]]:
        self._logger.h3("Generate File Content: __init__.py")
        docs_config = self._meta["package"].get("docs", {})
        if "main_init" not in docs_config:
            self._logger.skip("No docstring set in package.docs.main_init; skipping.")
            return []
        docstring_text = docs_config["main_init"].strip()
        docstring = f'"""\n{docstring_text}\n"""\n'

        package_dir_info = self._package_dir_output[0][0]
        current_dir_path = package_dir_info.alt_paths[0] if package_dir_info.alt_paths else package_dir_info.path
        filepath = current_dir_path / "__init__.py"
        if filepath.is_file():
            with open(filepath, "r") as f:
                file_content = f.read().strip()
        else:
            file_content = """__version_details__ = {"version": "0.0.0"}
__version__ = __version_details__["version"]"""
        pattern = re.compile(r'^((?:[\t ]*#.*\n|[\t ]*\n)*)("""(?:.|\n)*?"""(?:\n|$))', re.MULTILINE)
        match = pattern.match(file_content)
        if not match:
            # If no docstring found, add the new docstring at the beginning of the file
            text = f"{docstring}\n\n{file_content}".strip() + "\n"
        else:
            # Replace the existing docstring with the new one
            text = re.sub(pattern, rf'\1{docstring}', file_content)
        info = self._out_db.package_init(self._meta["package"]["name"])
        return [(info, text)]

    def manifest(self) -> list[tuple[DynamicFile, str]]:
        info = self._out_db.package_manifest
        text = "\n".join(self._meta["package"].get("manifest", []))
        return [(info, text)]

    def pyproject(self) -> list[tuple[DynamicFile, str]]:
        info = self._out_db.package_pyproject
        pyproject = _util.dict.fill_template(self._pyproject, metadata=self._meta)
        project = pyproject.setdefault("project", {})
        for key, val in self.pyproject_project().items():
            if key not in project:
                project[key] = val
        return [(info, tomlkit.dumps(pyproject))]

    def pyproject_tests(self) -> list[tuple[DynamicFile, str]]:
        info = self._out_db.test_package_pyproject
        pyproject = _util.dict.fill_template(self._pyproject_test, metadata=self._meta)
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

    def rename_imports(self, module_content: str, old_name: str, new_name: str) -> str:
        """
        Rename the old import name to the new import name in the provided module content.

        Parameters:
        - module_content: str - The content of the Python module as a string.
        - old_name: str - The old name of the import to be renamed.
        - new_name: str - The new name that will replace the old name.

        Returns:
        - The updated module content as a string with the old names replaced by the new names.
        """
        # Regular expression patterns to match the old name in import statements
        patterns = [
            rf'^\s*from\s+{re.escape(old_name)}(?:.[a-zA-Z0-9_]+)*\s+import',
            rf'^\s*import\s+{re.escape(old_name)}(?:.[a-zA-Z0-9_]+)*'
        ]
        updated_module_content = module_content
        for pattern in patterns:
            # Compile the pattern into a regular expression object
            regex = re.compile(pattern, flags=re.MULTILINE)
            # Replace the old name with the new name wherever it matches
            updated_module_content = regex.sub(
                lambda match: match.group(0).replace(old_name, new_name, 1),
                updated_module_content
            )
        return updated_module_content
