# Standard libraries
import datetime
from pathlib import Path
from typing import Literal
import re

# Non-standard libraries
import tomlkit
import tomlkit.items


class PyProjectTOML:

    def __init__(self, metadata: dict, path_root: str | Path, path_meta: str | Path):
        self._meta = metadata
        self._path_root = Path(path_root).resolve()
        self._path_meta = Path(path_meta).resolve()
        self._path_pyproject = Path(path_root) / "pyproject.toml"
        if not self._path_pyproject.exists():
            raise FileNotFoundError(f"File {self._path_pyproject} does not exist.")
        if not self._path_pyproject.is_file():
            raise ValueError(f"Path {self._path_pyproject} is not a file.")
        if self._path_pyproject.name != "pyproject.toml":
            raise ValueError(f"File {self._path_pyproject} is not a 'pyproject.toml' file.")
        with open(self._path_pyproject) as f:
            self._file: tomlkit.TOMLDocument = tomlkit.load(f)
            self._file_raw: str = f.read()

        return

    def update(self):
        self.update_header_comment()
        self.update_project_table()
        # self.update_project_urls()
        # self.update_project_maintainers()
        # self.update_project_authors()
        self.update_versioningit_onbuild()
        with open(self._path_pyproject, "w") as f:
            f.write(tomlkit.dumps(self._file))

    def update_header_comment(self):
        lines = [
            f"{self._meta['project']['name']} pyproject.toml File.",
            (
                "Automatically generated on "
                f"{datetime.datetime.utcnow().strftime('%Y.%m.%d at %H:%M:%S UTC')} "
                f"by PyPackIT {pypackit.__version__}"
            ),
            "This file contains build system requirements and information,",
            " which are used by pip to build the package.",
            " For more information, see https://pypackit.readthedocs.io",
        ]
        for line_idx, line in enumerate(lines):
            self._file.body[line_idx][1].trivia.comment = f"# {line}"
        return

    def update_project_table(self):
        data_type = {
            "name": ("str", self._meta["package"]["name"]),
            "description": ("str", self._meta["project"]["tagline"]),
            "readme": ("str", self._meta["path"]["pypi_readme"]),
            "requires-python": ("str", f">= {self._meta['package']['python_version_min']}"),
            "license": ("inline_table", {"file": "LICENSE"}),
            # "authors": ("array_of_inline_tables", ),
            # "maintainers": ("array_of_inline_tables", ),
            "keywords": ("array", self._meta["project"]["keywords"]),
            "classifiers": ("array", self._meta["project"]["trove_classifiers"]),
            "urls": (
                "table",
                {
                    "Homepage": self._meta['url']['website']['home'],
                    "Download": self._meta['url']['github']['releases']['home'],
                    "News": self._meta['url']['website']['news'],
                    "Documentation": self._meta['url']['website']['home'],
                    "Bug Tracker": self._meta['url']['github']['issues']['home'],
                    # "Sponsor": "",
                    "Source": self._meta['url']['github']['home'],
                },
            ),
            # "scripts": "table",
            # "gui-scripts": "table",
            # "entry-points": "table_of_tables",
            "dependencies": (
                "array",
                (
                    [dep["pip_spec"] for dep in self._meta["package"]["dependencies"]]
                    if self._meta["package"]["dependencies"]
                    else None
                ),
            ),
            "optional-dependencies": (
                "table_of_arrays",
                (
                    {
                        group_name: [dep["pip_spec"] for dep in deps]
                        for group_name, deps in self._meta["package"][
                            "optional_dependencies"
                        ].items()
                    }
                    if self._meta["package"]["optional_dependencies"]
                    else None
                ),
            ),
        }
        for key, (dtype, val) in data_type.items():
            if not val:
                continue
            if dtype == "str":
                toml_val = val
            elif dtype == "array":
                toml_val = tomlkit.array(val).multiline(True)
            elif dtype == "table":
                toml_val = val
            elif dtype == "inline_table":
                toml_val = tomlkit.inline_table()
                toml_val.update(val)
            elif dtype == "array_of_inline_tables":
                toml_val = tomlkit.array().multiline(True)
                for table in val:
                    toml_val.append(tomlkit.inline_table().update(table))
            elif dtype == "table_of_arrays":
                toml_val = {
                    tab_key: tomlkit.array(arr).multiline(True) for tab_key, arr in val.items()
                }
            elif dtype == "table_of_tables":
                toml_val = tomlkit.table(is_super_table=True).update(val)
            else:
                raise ValueError(f"Unknown data type {dtype} for key {key}.")
            self._file["project"][key] = toml_val
        return

    def _update_project_authors_maintainers(self, role: Literal["authors", "maintainers"]):
        people = tomlkit.array().multiline(True)
        for person in self._meta["project"][role]:
            person_dict = dict(name=person["name"])
            if person.get("email"):
                person_dict["email"] = person["email"]
            people.append(tomlkit.inline_table().update(person_dict))
        self._file["project"][role] = people

    def update_project_authors(self):
        """
        Update the project authors in the pyproject.toml file.

        References
        ----------
        https://packaging.python.org/en/latest/specifications/declaring-project-metadata/#authors-maintainers
        """
        return self._update_project_authors_maintainers(role="authors")

    def update_project_maintainers(self):
        """
        Update the project maintainers in the pyproject.toml file.

        References
        ----------
        https://packaging.python.org/en/latest/specifications/declaring-project-metadata/#authors-maintainers
        """
        return self._update_project_authors_maintainers(role="maintainers")

    def update_project_urls(self):
        """
        Update the project urls in the pyproject.toml file.

        References
        ----------
        https://packaging.python.org/en/latest/specifications/declaring-project-metadata/#urls
        """
        urls = tomlkit.inline_table()
        for url_key, url_val in self._meta["url"].items():
            urls[url_key] = url_val
        self._file["project"]["urls"] = urls
        return

    def update_versioningit_onbuild(self):
        tab = self._file["tool"]["versioningit"]["onbuild"]
        tab["source-file"] = f"src/{self._meta['package']['name']}/__init__.py"
        tab["build-file"] = f"{self._meta['package']['name']}/__init__.py"
        return

    def update_package_init_docstring(self):
            filename = self.metadata["project"]["license"]['id'].lower().rstrip("+")
            with open(
                    Path(self.metadata["path"]["abs"]["meta"]["template"]["license"])
                    / f"{filename}_notice.txt"
            ) as f:
                text = f.read()
            copyright_notice = text.format(metadata=self.metadata)
            docstring = f"""{self.metadata['project']['name']}

    {self.metadata['project']['tagline']}

    {self.metadata['project']['description']}

    {copyright_notice}"""
            path_src = self._path_root / "src"
            path_package = path_src / self.metadata["package"]["name"]
            if not path_package.exists():
                package_dirs = [
                    sub
                    for sub in [sub for sub in path_src.iterdir() if sub.is_dir()]
                    if "__init__.py" in [subsub.name for subsub in sub.iterdir()]
                ]
                if len(package_dirs) > 1:
                    raise ValueError(f"More than one package directory found in '{path_src}'.")
                package_dirs[0].rename(path_package)
            path_init = path_package / "__init__.py"
            with open(path_init) as f:
                text = f.read()
            docstring_pattern = r"(\"\"\")(.*?)(\"\"\")"
            match = re.search(docstring_pattern, text, re.DOTALL)
            if match:
                # Replace the existing docstring with the new one
                new_text = re.sub(docstring_pattern, rf"\1{docstring}\3", text, flags=re.DOTALL)
            else:
                # If no docstring found, add the new docstring at the beginning of the file
                new_text = f'"""\n{docstring}\n"""\n{text}'
            # Write the modified content back to the file
            with open(path_init, "w") as file:
                file.write(new_text)
            return

