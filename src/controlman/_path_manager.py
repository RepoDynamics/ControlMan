from typing import Literal as _Literal
from pathlib import Path as _Path

from loggerman import logger as _logger

from controlman.datatype import DynamicFile as _DynamicFile, DynamicFileType as _DynamicFileType
from controlman import path as _path, _util


class PathManager:

    @_logger.sectioner("Initialize Path Manager")
    def __init__(self, repo_path: str | _Path):
        self._path_root = _Path(repo_path).resolve()
        pathfile = self._path_root / _path.FILE_PATH_META
        rel_path_meta = pathfile.read_text().strip().removesuffix("./") if pathfile.is_file() else ".control"
        paths = _util.file.read_datafile(
            path_repo=self._path_root,
            path_data=f"{rel_path_meta}/path.yaml",
            relpath_schema="path",
            log_section_title="Read Path Declaration File"
        )
        self._paths = self._check_paths(paths=paths, rel_path_meta=rel_path_meta)
        return

    @_logger.sectioner("Check Paths")
    def _check_paths(self, paths, rel_path_meta):
        paths["dir"]["control"] = rel_path_meta
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
                        _logger.critical(f"Input local directory '{fullpath}' is a file")
                    if not fullpath.exists():
                        _logger.info(f"Create input local directory '{fullpath}'.")
                        fullpath.mkdir(parents=True, exist_ok=True)
        for path, name in ((self.dir_meta, "control center"), (self.dir_github, "github")):
            if not path.is_dir():
                _logger.critical(f"Input {name} directory '{path}' not found")
        return paths

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
        return f'{self._paths["dir"]["control"]}/'

    @property
    def dir_meta(self):
        return self._path_root / self.dir_meta_rel

    @property
    def dir_docs(self) -> _Path:
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
    def fixed_files(self) -> list[_DynamicFile]:
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
        for pre_commit_config_type in [
            "main", "release", "pre-release", "implementation", "development", "auto-update", "other"
        ]:
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
    def all_files(self) -> list[_Path]:
        files = [file.path for file in self.fixed_files if file.id != "metadata"]
        files.extend(list((self._path_root / ".github/workflow_requirements").glob("*.txt")))
        files.extend(list((self._path_root / ".github/ISSUE_TEMPLATE").glob("*.yaml")))
        files.extend(list((self._path_root / ".github/PULL_REQUEST_TEMPLATE").glob("*.md")))
        files.remove(self._path_root / ".github/PULL_REQUEST_TEMPLATE/README.md")
        files.extend(list((self._path_root / ".github/DISCUSSION_TEMPLATE").glob("*.yaml")))
        return files

    @property
    def file_path_meta(self) -> _Path:
        return self.root / _path.FILE_PATH_META

    @property
    def file_local_config(self) -> _Path:
        return self.dir_local / "config.yaml"

    @property
    def file_local_api_cache(self):
        return self.dir_local_cache_repodynamics / "api_cache.yaml"

    @property
    def file_meta_core_extensions(self):
        return self.dir_meta / "core" / "extensions.yaml"

    @property
    def metadata(self) -> _DynamicFile:
        rel_path = _path.FILE_METADATA
        path = self._path_root / rel_path
        return _DynamicFile("metadata", _DynamicFileType.METADATA, rel_path, path)

    @property
    def license(self) -> _DynamicFile:
        rel_path = _path.FILE_LICENSE
        path = self._path_root / rel_path
        return _DynamicFile("license", _DynamicFileType.LICENSE, rel_path, path)

    @property
    def readme_main(self) -> _DynamicFile:
        rel_path = _path.FILE_README_MAIN
        path = self._path_root / rel_path
        return _DynamicFile("readme-main", _DynamicFileType.README, rel_path, path)

    @property
    def readme_pypi(self) -> _DynamicFile:
        filename = "README_pypi.md"
        rel_path = f'{self._paths["dir"]["source"]}/{filename}'
        path = self._path_root / rel_path
        return _DynamicFile("readme-pypi", _DynamicFileType.README, rel_path, path)

    def readme_dir(self, dir_path: str):
        filename = "README.md" if dir_path not in ["docs", ".github"] else "_README.md"
        rel_path = f"{dir_path}/{filename}"
        path = self._path_root / rel_path
        return _DynamicFile(f"readme-dir-{dir_path}", _DynamicFileType.README, rel_path, path)

    @property
    def funding(self) -> _DynamicFile:
        rel_path = _path.FILE_FUNDING
        path = self._path_root / rel_path
        return _DynamicFile("funding", _DynamicFileType.CONFIG, rel_path, path)

    def pre_commit_config(
        self,
        branch_type: _Literal[
            "main", "release", "pre-release", "implementation", "development", "auto-update", "other"
        ]
    ) -> _DynamicFile:
        rel_path = getattr(_path, f"file_pre_commit_config_{branch_type.replace('-', '_')}".upper())
        path = self._path_root / rel_path
        return _DynamicFile(f"pre-commit-config-{branch_type}", _DynamicFileType.CONFIG, rel_path, path)

    @property
    def read_the_docs_config(self) -> _DynamicFile:
        rel_path = _path.FILE_READTHEDOCS_CONFIG
        path = self._path_root / rel_path
        return _DynamicFile("read-the-docs-config", _DynamicFileType.CONFIG, rel_path, path)

    @property
    def issue_template_chooser_config(self) -> _DynamicFile:
        rel_path = _path.FILE_ISSUE_TEMPLATE_CHOOSER_CONFIG
        path = self._path_root / rel_path
        return _DynamicFile("issue-template-chooser-config", _DynamicFileType.CONFIG, rel_path, path)

    @property
    def package_pyproject(self) -> _DynamicFile:
        rel_path = _path.FILE_PYTHON_PYPROJECT
        path = self._path_root / rel_path
        return _DynamicFile("package-pyproject", _DynamicFileType.PACKAGE, rel_path, path)

    @property
    def test_package_pyproject(self) -> _DynamicFile:
        filename = "pyproject.toml"
        rel_path = f'{self._paths["dir"]["tests"]}/{filename}'
        path = self._path_root / rel_path
        return _DynamicFile("test-package-pyproject", _DynamicFileType.PACKAGE, rel_path, path)

    @property
    def package_requirements(self) -> _DynamicFile:
        rel_path = _path.FILE_PYTHON_REQUIREMENTS
        path = self._path_root / rel_path
        return _DynamicFile("package-requirements", _DynamicFileType.PACKAGE, rel_path, path)

    @property
    def package_manifest(self) -> _DynamicFile:
        rel_path = _path.FILE_PYTHON_MANIFEST
        path = self._path_root / rel_path
        return _DynamicFile("package-manifest", _DynamicFileType.PACKAGE, rel_path, path)

    @property
    def codecov_config(self) -> _DynamicFile:
        rel_path = _path.FILE_CODECOV_CONFIG
        path = self._path_root / rel_path
        return _DynamicFile("codecov-config", _DynamicFileType.CONFIG, rel_path, path)

    @property
    def gitignore(self) -> _DynamicFile:
        rel_path = _path.FILE_GITIGNORE
        path = self._path_root / rel_path
        return _DynamicFile("gitignore", _DynamicFileType.CONFIG, rel_path, path)

    @property
    def gitattributes(self) -> _DynamicFile:
        rel_path = _path.FILE_GITATTRIBUTES
        path = self._path_root / rel_path
        return _DynamicFile("gitattributes", _DynamicFileType.CONFIG, rel_path, path)

    @property
    def website_announcement(self) -> _DynamicFile:
        filename = "announcement.html"
        rel_path = f"{self._paths['dir']['website']}/{filename}"
        path = self._path_root / rel_path
        return _DynamicFile("website-announcement", _DynamicFileType.WEBSITE, rel_path, path)

    def workflow_requirements(self, name: str) -> _DynamicFile:
        filename = f"{name}.txt"
        rel_path = f".github/workflow_requirements/{filename}"
        path = self._path_root / rel_path
        return _DynamicFile(f"workflow-requirement-{name}", _DynamicFileType.CONFIG, rel_path, path)

    def health_file(
        self,
        name: _Literal["code_of_conduct", "codeowners", "contributing", "governance", "security", "support"],
        target_path: _Literal[".", "docs", ".github"] = ".",
    ) -> _DynamicFile:
        # Health files are only allowed in the root, docs, and .github directories
        allowed_paths = [".", "docs", ".github"]
        if target_path not in allowed_paths:
            _logger.critical(f"Path '{target_path}' not allowed for health files.")
        if name not in ["code_of_conduct", "codeowners", "contributing", "governance", "security", "support"]:
            _logger.critical(f"Health file '{name}' not recognized.")
        filename = name.upper() + (".md" if name != "codeowners" else "")
        rel_path = ("" if target_path == "." else f"{target_path}/") + filename
        path = self._path_root / rel_path
        allowed_paths.remove(target_path)
        alt_paths = [self._path_root / dir_ / filename for dir_ in allowed_paths]
        return _DynamicFile(f"health-file-{name}", _DynamicFileType.HEALTH, rel_path, path, alt_paths)

    def issue_form(self, name: str, priority: int) -> _DynamicFile:
        filename = f"{priority:02}_{name}.yaml"
        rel_path = f".github/ISSUE_TEMPLATE/{filename}"
        path = self._path_root / rel_path
        return _DynamicFile(f"issue-form-{name}", _DynamicFileType.FORM, rel_path, path)

    def issue_form_outdated(self, path: _Path) -> _DynamicFile:
        filename = path.name
        rel_path = str(path.relative_to(self._path_root))
        return _DynamicFile(f"issue-form-outdated-{filename}", _DynamicFileType.FORM, rel_path, path)

    def pull_request_template(self, name: str | _Literal["default"]) -> _DynamicFile:
        filename = "PULL_REQUEST_TEMPLATE.md" if name == "default" else f"{name}.md"
        rel_path = f".github/{filename}" if name == "default" else f".github/PULL_REQUEST_TEMPLATE/{filename}"
        path = self._path_root / rel_path
        return _DynamicFile(f"pull-request-template-{name}", _DynamicFileType.FORM, rel_path, path)

    def pull_request_template_outdated(self, path: _Path) -> _DynamicFile:
        filename = path.name
        rel_path = str(path.relative_to(self._path_root))
        return _DynamicFile(f"pull-request-template-outdated-{filename}", _DynamicFileType.FORM, rel_path, path)

    def discussion_form(self, name: str) -> _DynamicFile:
        filename = f"{name}.yaml"
        rel_path = f".github/DISCUSSION_TEMPLATE/{filename}"
        path = self._path_root / rel_path
        return _DynamicFile(f"discussion-form-{name}", _DynamicFileType.FORM, rel_path, path)

    def discussion_form_outdated(self, path: _Path) -> _DynamicFile:
        filename = path.name
        rel_path = str(path.relative_to(self._path_root))
        return _DynamicFile(f"discussion-form-outdated-{filename}", _DynamicFileType.FORM, rel_path, path)

    def package_dir(self, old_path: _Path | None, new_path: _Path) -> _DynamicFile:
        rel_path = str(new_path.relative_to(self._path_root))
        alt_paths = [old_path] if old_path else None
        return _DynamicFile(
            "package-dir",
            _DynamicFileType.PACKAGE,
            rel_path,
            new_path,
            alt_paths=alt_paths,
            is_dir=True,
        )

    def python_file(self, path: _Path):
        rel_path = str(path.relative_to(self._path_root))
        return _DynamicFile(rel_path, _DynamicFileType.PACKAGE, rel_path, path)

    def package_tests_dir(self, old_path: _Path | None, new_path: _Path) -> _DynamicFile:
        rel_path = str(new_path.relative_to(self._path_root))
        alt_paths = [old_path] if old_path else None
        return _DynamicFile(
            "test-package-dir",
            _DynamicFileType.PACKAGE,
            rel_path,
            new_path,
            alt_paths=alt_paths,
            is_dir=True,
        )

    def package_init(self, package_name: str) -> _DynamicFile:
        filename = "__init__.py"
        rel_path = f'{self._paths["dir"]["source"]}/{package_name}/{filename}'
        path = self._path_root / rel_path
        return _DynamicFile("package-init", _DynamicFileType.PACKAGE, rel_path, path)

    def package_typing_marker(self, package_name: str) -> _DynamicFile:
        filename = "py.typed"
        rel_path = f'{self._paths["dir"]["source"]}/{package_name}/{filename}'
        path = self._path_root / rel_path
        return _DynamicFile("package-typing-marker", _DynamicFileType.PACKAGE, rel_path, path)
