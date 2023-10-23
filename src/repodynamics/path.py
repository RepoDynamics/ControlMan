from typing import Literal
from pathlib import Path

from repodynamics import _util
from repodynamics.logger import Logger
from repodynamics.datatype import DynamicFile, DynamicFileType


class InputPath:
    def __init__(self, super_paths: dict, path_root: str | Path = ".", logger: Logger | None = None):
        self._logger = logger or Logger()
        self._path_root = Path(path_root).resolve()
        self._paths = super_paths
        for path, name in ((self.dir_meta, "meta"), (self.dir_github, "github")):
            if not path.is_dir():
                self._logger.error(f"Input {name} directory '{path}' not found.")
        if self.dir_local.is_file():
            self._logger.error(f"Input local directory '{self.dir_local}' is a file.")
        if not self.dir_local.exists():
            self._logger.info(f"Creating input local directory '{self.dir_local}'.")
            self.dir_local_log_repodynamics_action.mkdir(parents=True, exist_ok=True)
        return

    @property
    def paths(self) -> dict:
        return self._paths

    @property
    def root(self):
        return self._path_root

    @property
    def dir_github(self):
        return self._path_root / ".github"

    @property
    def dir_source(self):
        return self._path_root / self._paths["dir"]["source"]

    @property
    def dir_tests(self):
        return self._path_root / self._paths["dir"]["tests"]

    @property
    def dir_meta(self):
        return self._path_root / self._paths["dir"]["meta"]

    @property
    def dir_website(self):
        return self._path_root / self._paths["dir"]["website"]

    @property
    def dir_local(self):
        return self._path_root / self._paths["dir"]["local"]

    @property
    def dir_local_log(self):
        return self.dir_local / "log"

    @property
    def dir_local_log_repodynamics_action(self):
        return self.dir_local_log / "repodynamics"

    @property
    def dir_local_meta(self):
        return self.dir_local / "meta"

    @property
    def dir_local_meta_extensions(self):
        return self.dir_local_meta / "extensions"

    @property
    def dir_meta_package_config_build(self):
        return self.dir_meta / "package" / "config_build"

    @property
    def dir_meta_package_config_tools(self):
        return self.dir_meta / "package" / "config_tools"

    @property
    def local_config(self) -> Path:
        return self.dir_local / "config.yaml"

    @property
    def local_api_cache(self):
        return self.dir_local_meta / "api_cache.yaml"

    @property
    def meta_core_extensions(self):
        return self.dir_meta / "core" / "extensions.yaml"


class OutputPath:

    def __init__(self, super_paths: dict, path_root: str | Path, logger: Logger | None = None):
        self._path_root = Path(path_root).resolve()
        self._logger = logger or Logger()
        self._paths = super_paths
        return

    @property
    def root(self):
        return self._path_root

    @property
    def fixed_files(self) -> list[DynamicFile]:
        files = [
            self.metadata,
            self.metadata_ci,
            self.license,
            self.readme_main,
            self.readme_pypi,
            self.funding,
            self.pre_commit_config,
            self.read_the_docs_config,
            self.issue_template_chooser_config,
            self.package_pyproject,
            self.test_package_pyproject,
            self.package_requirements,
            self.package_manifest,
            self.codecov_config,
            self.gitignore,
            self.gitattributes,
            self.pull_request_template("default"),
            self.website_announcement,
        ]
        for health_file_name in ['code_of_conduct', 'codeowners', 'contributing', 'governance', 'security', 'support']:
            for target_path in ['.', 'docs', '.github']:
                files.append(self.health_file(health_file_name, target_path))
        return files

    @property
    def fixed_dirs(self):
        return [
            self.dir_issue_forms,
            self.dir_pull_request_templates,
            self.dir_discussion_forms,
        ]

    @property
    def all_files(self) -> list[Path]:
        files = [file.path for file in self.fixed_files]
        files.extend(list((self._path_root / ".github/workflow_requirements").glob("*.txt")))
        files.extend(list((self._path_root / ".github/ISSUE_TEMPLATE").glob("*.yaml")))
        files.extend(list((self._path_root / ".github/PULL_REQUEST_TEMPLATE").glob("*.md")))
        files.remove(self._path_root / ".github/PULL_REQUEST_TEMPLATE/README.md")
        files.extend(list((self._path_root / ".github/DISCUSSION_TEMPLATE").glob("*.yaml")))
        return files

    @property
    def metadata(self) -> DynamicFile:
        filename = ".metadata.json"
        rel_path = f".github/{filename}"
        path = self._path_root / rel_path
        return DynamicFile("metadata", DynamicFileType.METADATA, filename, rel_path, path)

    @property
    def metadata_ci(self) -> DynamicFile:
        filename = ".metadata_ci.json"
        rel_path = f".github/{filename}"
        path = self._path_root / rel_path
        return DynamicFile("metadata-ci", DynamicFileType.METADATA, filename, rel_path, path)

    @property
    def license(self) -> DynamicFile:
        filename = "LICENSE"
        rel_path = filename
        path = self._path_root / rel_path
        return DynamicFile("license", DynamicFileType.LICENSE, filename, rel_path, path)

    @property
    def readme_main(self) -> DynamicFile:
        filename = "README.md"
        rel_path = filename
        path = self._path_root / rel_path
        return DynamicFile("readme-main", DynamicFileType.README, filename, rel_path, path)

    @property
    def readme_pypi(self) -> DynamicFile:
        filename = "readme_pypi.md"
        rel_path = f'{self._paths["dir"]["source"]}/{filename}'
        path = self._path_root / rel_path
        return DynamicFile("readme-pypi", DynamicFileType.README, filename, rel_path, path)

    @property
    def funding(self) -> DynamicFile:
        filename = "FUNDING.yml"
        rel_path = f'.github/{filename}'
        path = self._path_root / rel_path
        return DynamicFile("funding", DynamicFileType.CONFIG, filename, rel_path, path)

    @property
    def pre_commit_config(self) -> DynamicFile:
        filename = ".pre-commit-config.yaml"
        rel_path = f'.github/{filename}'
        path = self._path_root / rel_path
        return DynamicFile("pre-commit-config", DynamicFileType.CONFIG, filename, rel_path, path)

    @property
    def read_the_docs_config(self) -> DynamicFile:
        filename = ".readthedocs.yaml"
        rel_path = f'.github/{filename}'
        path = self._path_root / rel_path
        return DynamicFile("read-the-docs-config", DynamicFileType.CONFIG, filename, rel_path, path)

    @property
    def issue_template_chooser_config(self) -> DynamicFile:
        filename = "config.yml"
        rel_path = f'.github/ISSUE_TEMPLATE/{filename}'
        path = self._path_root / rel_path
        return DynamicFile("issue-template-chooser-config", DynamicFileType.CONFIG, filename, rel_path, path)

    @property
    def package_pyproject(self) -> DynamicFile:
        filename = "pyproject.toml"
        rel_path = filename
        path = self._path_root / rel_path
        return DynamicFile("package-pyproject", DynamicFileType.PACKAGE, filename, rel_path, path)

    @property
    def test_package_pyproject(self) -> DynamicFile:
        filename = "pyproject.toml"
        rel_path = f'{self._paths["dir"]["tests"]}/{filename}'
        path = self._path_root / rel_path
        return DynamicFile("test-package-pyproject", DynamicFileType.PACKAGE, filename, rel_path, path)

    @property
    def package_requirements(self) -> DynamicFile:
        filename = "requirements.txt"
        rel_path = filename
        path = self._path_root / rel_path
        return DynamicFile("package-requirements", DynamicFileType.PACKAGE, filename, rel_path, path)

    @property
    def package_manifest(self) -> DynamicFile:
        filename = "MANIFEST.in"
        rel_path = filename
        path = self._path_root / rel_path
        return DynamicFile("package-manifest", DynamicFileType.PACKAGE, filename, rel_path, path)

    @property
    def codecov_config(self) -> DynamicFile:
        filename = ".codecov.yml"
        rel_path = f'.github/{filename}'
        path = self._path_root / rel_path
        return DynamicFile("codecov-config", DynamicFileType.CONFIG, filename, rel_path, path)

    @property
    def gitignore(self) -> DynamicFile:
        filename = ".gitignore"
        rel_path = filename
        path = self._path_root / rel_path
        return DynamicFile("gitignore", DynamicFileType.CONFIG, filename, rel_path, path)

    @property
    def gitattributes(self) -> DynamicFile:
        filename = ".gitattributes"
        rel_path = filename
        path = self._path_root / rel_path
        return DynamicFile("gitattributes", DynamicFileType.CONFIG, filename, rel_path, path)

    @property
    def website_announcement(self) -> DynamicFile:
        filename = "announcement.html"
        rel_path = f"{self._paths['dir']['website']}/{filename}"
        path = self._path_root / rel_path
        return DynamicFile("website-announcement", DynamicFileType.WEBSITE, filename, rel_path, path)

    def workflow_requirements(self, name: str) -> DynamicFile:
        filename = f"{name}.txt"
        rel_path = f'.github/workflow_requirements/{filename}'
        path = self._path_root / rel_path
        return DynamicFile(f"workflow-requirement-{name}", DynamicFileType.CONFIG, filename, rel_path, path)

    def health_file(
        self,
        name: Literal['code_of_conduct', 'codeowners', 'contributing', 'governance', 'security', 'support'],
        target_path: Literal['.', 'docs', '.github'] = "."
    ) -> DynamicFile:
        # Health files are only allowed in the root, docs, and .github directories
        allowed_paths = [".", "docs", ".github"]
        if target_path not in allowed_paths:
            self._logger.error(f"Path '{target_path}' not allowed for health files.")
        if name not in ['code_of_conduct', 'codeowners', 'contributing', 'governance', 'security', 'support']:
            self._logger.error(f"Health file '{name}' not recognized.")
        filename = name.upper() + (".md" if name != "codeowners" else "")
        rel_path = ("" if target_path == "." else f"{target_path}/") + filename
        path = self._path_root / rel_path
        allowed_paths.remove(target_path)
        alt_paths = [self._path_root / dir_ / filename for dir_ in allowed_paths]
        return DynamicFile(f"health-file-{name}", DynamicFileType.HEALTH, filename, rel_path, path, alt_paths)

    def issue_form(self, name: str, priority: int) -> DynamicFile:
        filename = f"{priority:02}_{name}.yaml"
        rel_path = f'.github/ISSUE_TEMPLATE/{filename}'
        path = self._path_root / rel_path
        return DynamicFile(f"issue-form-{name}", DynamicFileType.FORM, filename, rel_path, path)

    def issue_form_outdated(self, path: Path) -> DynamicFile:
        filename = path.name
        rel_path = str(path.relative_to(self._path_root))
        return DynamicFile(f"issue-form-outdated-{filename}", DynamicFileType.FORM, filename, rel_path, path)

    def pull_request_template(self, name: str | Literal['default']) -> DynamicFile:
        filename = "PULL_REQUEST_TEMPLATE.md" if name == "default" else f"{name}.md"
        rel_path = f'.github/{filename}' if name == "default" else f'.github/PULL_REQUEST_TEMPLATE/{filename}'
        path = self._path_root / rel_path
        return DynamicFile(f"pull-request-template-{name}", DynamicFileType.FORM, filename, rel_path, path)

    def pull_request_template_outdated(self, path: Path) -> DynamicFile:
        filename = path.name
        rel_path = str(path.relative_to(self._path_root))
        return DynamicFile(f"pull-request-template-outdated-{filename}", DynamicFileType.FORM, filename, rel_path, path)

    def discussion_form(self, name: str) -> DynamicFile:
        filename = f"{name}.yaml"
        rel_path = f'.github/DISCUSSION_TEMPLATE/{filename}'
        path = self._path_root / rel_path
        return DynamicFile(f"discussion-form-{name}", DynamicFileType.FORM, filename, rel_path, path)

    def discussion_form_outdated(self, path: Path) -> DynamicFile:
        filename = path.name
        rel_path = str(path.relative_to(self._path_root))
        return DynamicFile(f"discussion-form-outdated-{filename}", DynamicFileType.FORM, filename, rel_path, path)

    def package_dir(self, package_name: str, old_path: Path | None, new_path: Path) -> DynamicFile:
        filename = package_name
        rel_path = str(new_path.relative_to(self._path_root))
        alt_paths = [old_path] if old_path else None
        return DynamicFile(
            "package-dir", DynamicFileType.PACKAGE, filename, rel_path, new_path, alt_paths=alt_paths, is_dir=True
        )

    def python_file(self, path: Path):
        filename = path.name
        rel_path = str(path.relative_to(self._path_root))
        return DynamicFile(rel_path, DynamicFileType.PACKAGE, filename, rel_path, path)

    def package_tests_dir(self, package_name: str, old_path: Path | None, new_path: Path) -> DynamicFile:
        filename = f"{package_name}_tests"
        rel_path = str(new_path.relative_to(self._path_root))
        alt_paths = [old_path] if old_path else None
        return DynamicFile(
            "test-package-dir", DynamicFileType.PACKAGE, filename, rel_path, new_path, alt_paths=alt_paths, is_dir=True
        )

    def package_init(self, package_name: str) -> DynamicFile:
        filename = "__init__.py"
        rel_path = f'{self._paths["dir"]["source"]}/{package_name}/{filename}'
        path = self._path_root / rel_path
        return DynamicFile("package-init", DynamicFileType.PACKAGE, filename, rel_path, path)

    def package_typing_marker(self, package_name: str) -> DynamicFile:
        filename = "py.typed"
        rel_path = f'{self._paths["dir"]["source"]}/{package_name}/{filename}'
        path = self._path_root / rel_path
        return DynamicFile("package-typing-marker", DynamicFileType.PACKAGE, filename, rel_path, path)

    @property
    def dir_issue_forms(self):
        return self._path_root / ".github/ISSUE_TEMPLATE/"

    @property
    def dir_pull_request_templates(self):
        return self._path_root / ".github/PULL_REQUEST_TEMPLATE/"

    @property
    def dir_discussion_forms(self):
        return self._path_root / ".github/DISCUSSION_TEMPLATE/"
