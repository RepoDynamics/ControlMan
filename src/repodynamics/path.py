from typing import Literal
from pathlib import Path

from repodynamics import _util
from repodynamics.logger import Logger
from repodynamics.datatype import DynamicFile, DynamicFileType


class RelativePath:
    file_metadata = ".github/.metadata.json"
    file_license = "LICENSE"
    file_readme_main = "README.md"
    file_funding = ".github/FUNDING.yml"
    file_pre_commit_config_main = ".github/.pre-commit-config-main.yaml"
    file_pre_commit_config_release = ".github/.pre-commit-config-release.yaml"
    file_pre_commit_config_dev = ".github/.pre-commit-config-dev.yaml"
    file_pre_commit_config_other = ".github/.pre-commit-config-other.yaml"
    file_readthedocs_config = ".github/.readthedocs.yaml"
    file_issue_template_chooser_config = ".github/ISSUE_TEMPLATE/config.yml"
    file_python_pyproject = "pyproject.toml"
    file_python_requirements = "requirements.txt"
    file_python_manifest = "MANIFEST.in"
    file_codecov_config = ".github/.codecov.yml"
    file_gitignore = ".gitignore"
    file_gitattributes = ".gitattributes"
    file_path_meta = ".github/.control_center_path.txt"
    dir_github = ".github/"
    dir_github_workflows = ".github/workflows/"
    dir_github_workflow_requirements = ".github/workflow_requirements/"
    dir_github_issue_template = ".github/ISSUE_TEMPLATE/"
    dir_github_pull_request_template = ".github/PULL_REQUEST_TEMPLATE/"
    dir_github_discussion_template = ".github/DISCUSSION_TEMPLATE/"


class PathFinder:
    def __init__(self, path_root: str | Path, logger: Logger | None = None):
        self._path_root = Path(path_root).resolve()
        self._logger = logger or Logger()
        pathfile = self._path_root / RelativePath.file_path_meta
        rel_path_meta = pathfile.read_text().strip().removesuffix("./") if pathfile.is_file() else ".meta"
        paths = _util.dict.read(
            path=self._path_root / rel_path_meta / "path.yaml",
            schema=_util.file.datafile("schema/path.yaml"),
            raise_empty=False,
            logger=self._logger,
        )
        paths["dir"]["meta"] = rel_path_meta
        dir_local_root = paths["dir"]["local"]["root"]
        for local_dir in ("cache", "report"):
            dict_local_dir = paths["dir"]["local"][local_dir]
            dict_local_dir["root"] = f'{dir_local_root}/{dict_local_dir["root"]}'
            for key, sub_dir in dict_local_dir.items():
                if key != "root":
                    full_rel_path = f'{dict_local_dir["root"]}/{sub_dir}'
                    dict_local_dir[key] = full_rel_path
                    fullpath = self._path_root / full_rel_path
                    if fullpath.is_file():
                        self._logger.error(f"Input local directory '{fullpath}' is a file")
                    if not fullpath.exists():
                        self._logger.info(f"Creating input local directory '{fullpath}'.")
                        fullpath.mkdir(parents=True, exist_ok=True)
        self._paths = paths
        for path, name in ((self.dir_meta, "meta"), (self.dir_github, "github")):
            if not path.is_dir():
                self._logger.error(f"Input {name} directory '{path}' not found")
        return

    @property
    def paths_dict(self) -> dict:
        return self._paths

    @property
    def root(self):
        return self._path_root

    @property
    def dir_github(self):
        return self._path_root / ".github"

    @property
    def dir_source_rel(self) -> str:
        return f'{self._paths["dir"]["source"]}/'

    @property
    def dir_source(self):
        return self._path_root / self.dir_source_rel

    @property
    def dir_tests_rel(self) -> str:
        return f'{self._paths["dir"]["tests"]}/'

    @property
    def dir_tests(self):
        return self._path_root / self.dir_tests_rel

    @property
    def dir_meta_rel(self) -> str:
        return f'{self._paths["dir"]["meta"]}/'

    @property
    def dir_meta(self):
        return self._path_root / self.dir_meta_rel

    @property
    def dir_docs(self) -> Path:
        return self._path_root / "docs"

    @property
    def dir_website_rel(self) -> str:
        return f'{self._paths["dir"]["website"]}/'

    @property
    def dir_website(self):
        return self._path_root / self.dir_website_rel

    @property
    def dir_local(self):
        return self._path_root / self._paths["dir"]["local"]["root"]

    @property
    def dir_local_cache(self):
        return self._path_root / self._paths["dir"]["local"]["cache"]["root"]

    @property
    def dir_local_report(self):
        return self._path_root / self._paths["dir"]["local"]["report"]["root"]

    @property
    def dir_local_report_repodynamics(self):
        return self._path_root / self._paths["dir"]["local"]["report"]["repodynamics"]

    @property
    def dir_local_cache_repodynamics(self):
        return self._path_root / self._paths["dir"]["local"]["cache"]["repodynamics"]

    @property
    def dir_local_meta_extensions(self):
        return self.dir_local_cache_repodynamics / "extensions"

    @property
    def dir_meta_package_config_build(self):
        return self.dir_meta / "package" / "config_build"

    @property
    def dir_meta_package_config_tools(self):
        return self.dir_meta / "package" / "config_tools"

    @property
    def dir_issue_forms(self):
        return self._path_root / ".github/ISSUE_TEMPLATE/"

    @property
    def dir_pull_request_templates(self):
        return self._path_root / ".github/PULL_REQUEST_TEMPLATE/"

    @property
    def dir_discussion_forms(self):
        return self._path_root / ".github/DISCUSSION_TEMPLATE/"

    @property
    def fixed_files(self) -> list[DynamicFile]:
        files = [
            self.metadata,
            self.license,
            self.readme_main,
            self.readme_pypi,
            self.funding,
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
        for health_file_name in [
            "code_of_conduct",
            "codeowners",
            "contributing",
            "governance",
            "security",
            "support",
        ]:
            for target_path in [".", "docs", ".github"]:
                files.append(self.health_file(health_file_name, target_path))
        for pre_commit_config_type in ["main", "release", "dev", "other"]:
            files.append(self.pre_commit_config(pre_commit_config_type))
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
        files = [file.path for file in self.fixed_files if file.id != "metadata"]
        files.extend(list((self._path_root / ".github/workflow_requirements").glob("*.txt")))
        files.extend(list((self._path_root / ".github/ISSUE_TEMPLATE").glob("*.yaml")))
        files.extend(list((self._path_root / ".github/PULL_REQUEST_TEMPLATE").glob("*.md")))
        files.remove(self._path_root / ".github/PULL_REQUEST_TEMPLATE/README.md")
        files.extend(list((self._path_root / ".github/DISCUSSION_TEMPLATE").glob("*.yaml")))
        return files

    @property
    def file_path_meta(self) -> Path:
        return self.root / RelativePath.file_path_meta

    @property
    def file_local_config(self) -> Path:
        return self.dir_local / "config.yaml"

    @property
    def file_local_api_cache(self):
        return self.dir_local_cache_repodynamics / "api_cache.yaml"

    @property
    def file_meta_core_extensions(self):
        return self.dir_meta / "core" / "extensions.yaml"

    @property
    def metadata(self) -> DynamicFile:
        rel_path = RelativePath.file_metadata
        path = self._path_root / rel_path
        return DynamicFile("metadata", DynamicFileType.METADATA, rel_path, path)

    @property
    def license(self) -> DynamicFile:
        rel_path = RelativePath.file_license
        path = self._path_root / rel_path
        return DynamicFile("license", DynamicFileType.LICENSE, rel_path, path)

    @property
    def readme_main(self) -> DynamicFile:
        rel_path = RelativePath.file_readme_main
        path = self._path_root / rel_path
        return DynamicFile("readme-main", DynamicFileType.README, rel_path, path)

    @property
    def readme_pypi(self) -> DynamicFile:
        filename = "readme_pypi.md"
        rel_path = f'{self._paths["dir"]["source"]}/{filename}'
        path = self._path_root / rel_path
        return DynamicFile("readme-pypi", DynamicFileType.README, rel_path, path)

    def readme_dir(self, dir_path: str):
        filename = "README.md" if dir_path not in ["docs", ".github"] else "_README.md"
        rel_path = f"{dir_path}/{filename}"
        path = self._path_root / rel_path
        return DynamicFile(f"readme-dir-{dir_path}", DynamicFileType.README, rel_path, path)

    @property
    def funding(self) -> DynamicFile:
        rel_path = RelativePath.file_funding
        path = self._path_root / rel_path
        return DynamicFile("funding", DynamicFileType.CONFIG, rel_path, path)

    def pre_commit_config(self, branch_type: Literal["main", "release", "dev", "other"]) -> DynamicFile:
        rel_path = getattr(RelativePath, f"file_pre_commit_config_{branch_type}")
        path = self._path_root / rel_path
        return DynamicFile(f"pre-commit-config-{branch_type}", DynamicFileType.CONFIG, rel_path, path)

    @property
    def read_the_docs_config(self) -> DynamicFile:
        rel_path = RelativePath.file_readthedocs_config
        path = self._path_root / rel_path
        return DynamicFile("read-the-docs-config", DynamicFileType.CONFIG, rel_path, path)

    @property
    def issue_template_chooser_config(self) -> DynamicFile:
        rel_path = RelativePath.file_issue_template_chooser_config
        path = self._path_root / rel_path
        return DynamicFile("issue-template-chooser-config", DynamicFileType.CONFIG, rel_path, path)

    @property
    def package_pyproject(self) -> DynamicFile:
        rel_path = RelativePath.file_python_pyproject
        path = self._path_root / rel_path
        return DynamicFile("package-pyproject", DynamicFileType.PACKAGE, rel_path, path)

    @property
    def test_package_pyproject(self) -> DynamicFile:
        filename = "pyproject.toml"
        rel_path = f'{self._paths["dir"]["tests"]}/{filename}'
        path = self._path_root / rel_path
        return DynamicFile("test-package-pyproject", DynamicFileType.PACKAGE, rel_path, path)

    @property
    def package_requirements(self) -> DynamicFile:
        rel_path = RelativePath.file_python_requirements
        path = self._path_root / rel_path
        return DynamicFile("package-requirements", DynamicFileType.PACKAGE, rel_path, path)

    @property
    def package_manifest(self) -> DynamicFile:
        rel_path = RelativePath.file_python_manifest
        path = self._path_root / rel_path
        return DynamicFile("package-manifest", DynamicFileType.PACKAGE, rel_path, path)

    @property
    def codecov_config(self) -> DynamicFile:
        rel_path = RelativePath.file_codecov_config
        path = self._path_root / rel_path
        return DynamicFile("codecov-config", DynamicFileType.CONFIG, rel_path, path)

    @property
    def gitignore(self) -> DynamicFile:
        rel_path = RelativePath.file_gitignore
        path = self._path_root / rel_path
        return DynamicFile("gitignore", DynamicFileType.CONFIG, rel_path, path)

    @property
    def gitattributes(self) -> DynamicFile:
        rel_path = RelativePath.file_gitattributes
        path = self._path_root / rel_path
        return DynamicFile("gitattributes", DynamicFileType.CONFIG, rel_path, path)

    @property
    def website_announcement(self) -> DynamicFile:
        filename = "announcement.html"
        rel_path = f"{self._paths['dir']['website']}/{filename}"
        path = self._path_root / rel_path
        return DynamicFile("website-announcement", DynamicFileType.WEBSITE, rel_path, path)

    def workflow_requirements(self, name: str) -> DynamicFile:
        filename = f"{name}.txt"
        rel_path = f".github/workflow_requirements/{filename}"
        path = self._path_root / rel_path
        return DynamicFile(f"workflow-requirement-{name}", DynamicFileType.CONFIG, rel_path, path)

    def health_file(
        self,
        name: Literal["code_of_conduct", "codeowners", "contributing", "governance", "security", "support"],
        target_path: Literal[".", "docs", ".github"] = ".",
    ) -> DynamicFile:
        # Health files are only allowed in the root, docs, and .github directories
        allowed_paths = [".", "docs", ".github"]
        if target_path not in allowed_paths:
            self._logger.error(f"Path '{target_path}' not allowed for health files.")
        if name not in ["code_of_conduct", "codeowners", "contributing", "governance", "security", "support"]:
            self._logger.error(f"Health file '{name}' not recognized.")
        filename = name.upper() + (".md" if name != "codeowners" else "")
        rel_path = ("" if target_path == "." else f"{target_path}/") + filename
        path = self._path_root / rel_path
        allowed_paths.remove(target_path)
        alt_paths = [self._path_root / dir_ / filename for dir_ in allowed_paths]
        return DynamicFile(f"health-file-{name}", DynamicFileType.HEALTH, rel_path, path, alt_paths)

    def issue_form(self, name: str, priority: int) -> DynamicFile:
        filename = f"{priority:02}_{name}.yaml"
        rel_path = f".github/ISSUE_TEMPLATE/{filename}"
        path = self._path_root / rel_path
        return DynamicFile(f"issue-form-{name}", DynamicFileType.FORM, rel_path, path)

    def issue_form_outdated(self, path: Path) -> DynamicFile:
        filename = path.name
        rel_path = str(path.relative_to(self._path_root))
        return DynamicFile(f"issue-form-outdated-{filename}", DynamicFileType.FORM, rel_path, path)

    def pull_request_template(self, name: str | Literal["default"]) -> DynamicFile:
        filename = "PULL_REQUEST_TEMPLATE.md" if name == "default" else f"{name}.md"
        rel_path = f".github/{filename}" if name == "default" else f".github/PULL_REQUEST_TEMPLATE/{filename}"
        path = self._path_root / rel_path
        return DynamicFile(f"pull-request-template-{name}", DynamicFileType.FORM, rel_path, path)

    def pull_request_template_outdated(self, path: Path) -> DynamicFile:
        filename = path.name
        rel_path = str(path.relative_to(self._path_root))
        return DynamicFile(f"pull-request-template-outdated-{filename}", DynamicFileType.FORM, rel_path, path)

    def discussion_form(self, name: str) -> DynamicFile:
        filename = f"{name}.yaml"
        rel_path = f".github/DISCUSSION_TEMPLATE/{filename}"
        path = self._path_root / rel_path
        return DynamicFile(f"discussion-form-{name}", DynamicFileType.FORM, rel_path, path)

    def discussion_form_outdated(self, path: Path) -> DynamicFile:
        filename = path.name
        rel_path = str(path.relative_to(self._path_root))
        return DynamicFile(f"discussion-form-outdated-{filename}", DynamicFileType.FORM, rel_path, path)

    def package_dir(self, old_path: Path | None, new_path: Path) -> DynamicFile:
        rel_path = str(new_path.relative_to(self._path_root))
        alt_paths = [old_path] if old_path else None
        return DynamicFile(
            "package-dir",
            DynamicFileType.PACKAGE,
            rel_path,
            new_path,
            alt_paths=alt_paths,
            is_dir=True,
        )

    def python_file(self, path: Path):
        filename = path.name
        rel_path = str(path.relative_to(self._path_root))
        return DynamicFile(rel_path, DynamicFileType.PACKAGE, rel_path, path)

    def package_tests_dir(self, old_path: Path | None, new_path: Path) -> DynamicFile:
        rel_path = str(new_path.relative_to(self._path_root))
        alt_paths = [old_path] if old_path else None
        return DynamicFile(
            "test-package-dir",
            DynamicFileType.PACKAGE,
            rel_path,
            new_path,
            alt_paths=alt_paths,
            is_dir=True,
        )

    def package_init(self, package_name: str) -> DynamicFile:
        filename = "__init__.py"
        rel_path = f'{self._paths["dir"]["source"]}/{package_name}/{filename}'
        path = self._path_root / rel_path
        return DynamicFile("package-init", DynamicFileType.PACKAGE, rel_path, path)

    def package_typing_marker(self, package_name: str) -> DynamicFile:
        filename = "py.typed"
        rel_path = f'{self._paths["dir"]["source"]}/{package_name}/{filename}'
        path = self._path_root / rel_path
        return DynamicFile("package-typing-marker", DynamicFileType.PACKAGE, rel_path, path)
