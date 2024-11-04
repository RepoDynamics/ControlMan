from __future__ import annotations as _annotations
from typing import TYPE_CHECKING as _TYPE_CHECKING
from pathlib import Path as _Path
from xml.etree import ElementTree as _ElementTree
import copy as _copy

from loggerman import logger
import pyserials as _ps
import pylinks
from pylinks.exception.api import WebAPIError as _WebAPIError
from licenseman.spdx import license_text as _license_text

from controlman.datatype import DynamicFile, DynamicFileType
from controlman.file_gen import unit as _unit
from controlman import const as _const

if _TYPE_CHECKING:
    from typing import Literal


class ConfigFileGenerator:
    def __init__(
        self,
        data: _ps.NestedDict,
        data_before: _ps.NestedDict,
        repo_path: _Path,
    ):
        self._data = data
        self._data_before = data_before
        self._path_repo = repo_path
        return

    def generate(self) -> tuple[list[DynamicFile], dict | str | None, dict | str | None]:
        tools_out, pyproject_pkg, pyproject_test = self.tools()
        return (
            self._generate_license()
            + self.generate_codeowners()
            + self.citation()
            + self.web_requirements()
            + self.web_toc()
            + self.funding()
            + tools_out
            + self.issue_template_chooser()
            + self.gitignore()
            + self.gitattributes()
        ), pyproject_pkg, pyproject_test

    def _is_disabled(self, key: str) -> bool:
        return not (self._data[key] or self._data_before[key])

    def generate_codeowners(self) -> list[DynamicFile]:
        """

        Returns
        -------

        References
        ----------
        https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners#codeowners-syntax
        """
        path_key = "health.code_owners.path"
        if self._is_disabled(path_key):
            return []
        codeowners_files = {
            "type": DynamicFileType.CONFIG,
            "subtype": ("codeowners", "Code Owners"),
            "path": self._data[path_key],
            "path_before": self._data_before[path_key],
        }
        data: dict[int, dict[str, list[str]]] = {}
        pattern_description: dict[str, str] = {}
        for member in self._data["team"].values():
            for glob_def in member.get("ownership", []):
                data.setdefault(glob_def["priority"], {}).setdefault(glob_def["glob"], []).append(
                    member["github"]["id"]
                )
                if glob_def.get("description"):
                    pattern_description[glob_def["glob"]] = glob_def["description"]
            for member_role in member.get("roles", []):
                for glob_def in self._data["role"][member_role].get("ownership", []):
                    data.setdefault(glob_def["priority"], {}).setdefault(glob_def["glob"], []).append(
                        member["github"]["id"]
                    )
                    if glob_def.get("description"):
                        pattern_description[glob_def["glob"]] = glob_def["description"]
        if not data:
            return [DynamicFile(**codeowners_files)]
        # Get the maximum length of patterns to align the columns when writing the file
        max_len = max(
            [len(glob_pattern) for priority_dic in data.values() for glob_pattern in priority_dic.keys()]
        )
        lines = []
        for priority_defs in [defs for priority, defs in sorted(data.items())]:
            for pattern, reviewers_list in sorted(priority_defs.items()):
                comment = pattern_description.get(pattern, "")
                for comment_line in comment.splitlines():
                    lines.append(f"# {comment_line}")
                reviewers = " ".join(
                    [f"@{reviewer_id}" for reviewer_id in sorted(set(reviewers_list))]
                )
                lines.append(f"{pattern: <{max_len}}   {reviewers}{"\n" if comment else ''}")
        return [DynamicFile(content="\n".join(lines), **codeowners_files)]

    def _generate_license(self) -> list[DynamicFile]:
        if self._is_disabled("license"):
            return []
        files = []
        for component_id, component_data in self._data["license.component"].items():
            for part in ("text", "header"):
                if component_data["type"] == "exception" and part == "header":
                    continue
                for output_type in ("plain", "md"):
                    text = component_data.get(f"{part}_{output_type}")
                    xml = component_data.get(f"{part}_xml")
                    path = component_data["path"].get(f"{part}_{output_type}")
                    if not (path and (text or xml)):
                        continue
                    if not text:
                        config_component = component_data.get(f"{part}_config", {}).get(output_type, {})
                        config_default = self._data[f"license.config.{part}.{output_type}"] or {}
                        _ps.update.dict_from_addon(
                            data=config_component,
                            addon=config_default,
                            append_list=True,
                            append_dict=True,
                            raise_duplicates=False,
                            raise_type_mismatch=False,
                        )
                        xml_elem = _ElementTree.fromstring(xml)
                        text = _license_text.SPDXLicenseTextPlain(xml_elem).generate(**config_component)
                    subtype_type = "license" if component_data["type"] == "license" else "license_exception"
                    subtype = f"{subtype_type}_{component_id}_{output_type}_{part}"
                    file = DynamicFile(
                        type=DynamicFileType.CONFIG,
                        subtype=(subtype, subtype_type.replace("_", " ").title()),
                        content=text,
                        path=path,
                        path_before=self._data_before.get(
                            "license.component", {}
                        ).get(component_id, {}).get("path", {}).get(f"{part}_{output_type}")
                    )
                    files.append(file)
        return files

    def web_toc(self) -> list[DynamicFile]:
        if self._is_disabled("web.toc"):
            return []
        toc_file = {
            "type": DynamicFileType.WEB_CONFIG,
            "subtype": ("toc", "Table of Contents"),
            "path": f"{self._data["web.path.source"]}/{self._data["web.toc.path"]}" if self._data["web.toc"] else None,
            "path_before": f"{self._data_before["web.path.source"]}/{self._data_before["web.toc.path"]}" if self._data_before["web.toc"] else None,
        }
        toc = self._data["web.toc"]
        if not toc:
            return [DynamicFile(**toc_file)]
        toc_content = _ps.write.to_yaml_string(data={k: v for k, v in toc.items() if k != "path"}, end_of_file_newline=True)
        return [DynamicFile(content=toc_content, **toc_file)]

    def web_requirements(self) -> list[DynamicFile]:
        if self._is_disabled("web"):
            return []
        conda_env_file = {
            "type": DynamicFileType.WEB_CONFIG,
            "subtype": ("env_conda", "Conda Environment"),
            "path": self._data["web.env.file.conda.path"],
            "path_before": self._data_before["web.env.file.conda.path"],
        }
        pip_env_file = {
            "type": DynamicFileType.WEB_CONFIG,
            "subtype": ("env_pip", "Pip Environment"),
            "path": self._data["web.env.file.pip.path"],
            "path_before": self._data_before["web.env.file.pip.path"],
        }
        if not self._data["web"]:
            return [DynamicFile(**env_file) for env_file in (conda_env_file, pip_env_file)]
        dependencies = []
        for path in ("web.sphinx.dependency", "web.theme.dependency"):
            dependency = self._data.get(path)
            if dependency:
                dependencies.append(dependency)
        for extension in self._data.get("web.extension", {}).values():
            dependency = extension.get("dependency")
            if dependency:
                dependencies.append(dependency)
        for add_dep in self._data.get("web.env.dependency", {}).values():
            dependencies.append(add_dep)
        conda_env, pip_env, pip_full = _unit.create_environment_files(
            dependencies=dependencies,
            env_name=pylinks.string.to_slug(self._data["web.env.file.conda.name"]),
        )
        return [
            DynamicFile(content=conda_env, **conda_env_file),
            DynamicFile(content=pip_env if pip_full else None, **pip_env_file)
        ]

    def funding(self) -> list[DynamicFile]:
        """
        References
        ----------
        https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/displaying-a-sponsor-button-in-your-repository#about-funding-files
        """
        if self._is_disabled("funding"):
            return []
        funding_file = {
            "type": DynamicFileType.CONFIG,
            "subtype": ("funding", "Funding"),
            "path": _const.FILEPATH_FUNDING_CONFIG,
            "path_before": _const.FILEPATH_FUNDING_CONFIG,
        }
        if not self._data["funding"]:
            return [DynamicFile(**funding_file)]
        output = {}
        for funding_platform, users in self._data["funding"].items():
            if isinstance(users, list):
                output[funding_platform] = _ps.format.to_yaml_array(data=users, inline=True)
            else:
                output[funding_platform] = users
        file_content = _ps.write.to_yaml_string(data=output, end_of_file_newline=True)
        return [DynamicFile(content=file_content, **funding_file)]

    def tools(self) -> tuple[list[DynamicFile], dict | str | None, dict | str | None]:
        # Collect all environment and config data per env/config file
        env_conda = {}
        env_pip = {}
        conf = {}
        for tool_name, tool in self._data.get("tool", {}).items():
            tool_env = tool.get("env")
            if tool_env:
                env_file = tool_env["file"]
                env_conda_entry = env_conda.setdefault(
                    env_file["conda"]["path"], {"name": env_file["conda"]["name"], "deps": [], "tool_names": []}
                )
                if env_conda_entry["name"] != env_file["conda"]["name"]:
                    raise ValueError()
                env_conda_entry["deps"].extend(list(tool_env["dependency"].values()))
                env_conda_entry["tool_names"].append(tool_name)
                env_file_pip = env_file.get("pip")
                if env_file_pip:
                    env_pip_entry = env_pip.setdefault(env_file_pip["path"], {"deps": [], "tool_names": []})
                    env_pip_entry["deps"].extend(list(tool_env["dependency"].values()))
                    env_pip_entry["tool_names"].append(tool_name)
            conf_file = tool.get("config", {}).get("file")
            if conf_file:
                conf_entry = conf.setdefault(conf_file["path"], {"type": conf_file["type"], "contents": [], "tool_names": []})
                if conf_entry["type"] != conf_file["type"]:
                    raise ValueError()
                if conf_file["type"] == "txt":
                    if not isinstance(conf_file["content"], str):
                        raise ValueError()
                elif not isinstance(conf_file["content"], (list, dict)):
                    raise ValueError()
                for content in conf_entry["contents"]:
                    if type(content) is not type(conf_file["content"]):
                        raise ValueError()
                conf_entry["contents"].append(_copy.deepcopy(conf_file["content"]))
                conf_entry["tool_names"].append(tool_name)
        out = []
        # Write conda environment files
        for conda_env_path, conda_env_data in env_conda.items():
            conda_env = _unit.create_environment_files(
                dependencies=conda_env_data["deps"],
                env_name=conda_env_data["name"],
            )[0]
            out.append(
                DynamicFile(
                    type=DynamicFileType.TOOL_ENV_CONDA,
                    subtype=("_".join(conda_env_data["tool_names"]), ", ".join(conda_env_data["tool_names"])),
                    content=conda_env,
                    path=conda_env_path,
                    path_before=conda_env_path
                )
            )
        # Write pip environment files
        for pip_env_path, pip_env_data in env_pip.items():
            _, pip_env, pip_full = _unit.create_environment_files(dependencies=pip_env_data["deps"])
            if not pip_full:
                logger.warning(f"Tool environment file '{pip_env_path}' does not contain all dependencies.")
            out.append(
                DynamicFile(
                    type=DynamicFileType.TOOL_ENV_PIP,
                    subtype=("_".join(pip_env_data["tool_names"]), ", ".join(pip_env_data["tool_names"])),
                    content=pip_env,
                    path=pip_env_path,
                    path_before=pip_env_path
                )
            )
        # Write configuration files
        pyproject_pkg = None
        pyproject_test = None
        untouchable_paths = []
        # These are package and test-suite pyproject.toml files that are being used
        # regardless of whether other tools use it as their configuration file.
        for typ in ("pkg", "test"):
            pkg_root = self._data[f"{typ}.path.root"]
            untouchable_paths.append(str(_Path(pkg_root) / _const.FILENAME_PKG_PYPROJECT) if pkg_root else None)
        for conf_path, conf_data in conf.items():
            if conf_data["type"] == "txt":
                content = "\n\n".join(conf_data["contents"])
                full = content
            else:
                if isinstance(conf_data["contents"][0], list):
                    full = [elem for content in conf_data["contents"] for elem in content]
                else:
                    for dic in conf_data["contents"][1:]:
                        _ps.update.dict_from_addon(
                            data=conf_data["contents"][0],
                            addon=dic,
                            append_list=True,
                            append_dict=True,
                            raise_duplicates=True,
                        )
                    full = conf_data["contents"][0]
                content = _ps.write.to_string(
                    data=full,
                    data_type=conf_data["type"],
                    end_of_file_newline=True,
                    sort_keys=True,
                )
            if "codecov" in conf_data["tool_names"]:
                self.validate_codecov_config(config=content)
            if conf_path not in untouchable_paths:
                out.append(
                    DynamicFile(
                        type=DynamicFileType.TOOL_CONFIG,
                        subtype=("_".join(conf_data["tool_names"]), ", ".join(conf_data["tool_names"])),
                        content=content,
                        path=conf_path,
                        path_before=conf_path
                    )
                )
            elif conf_path == untouchable_paths[0]:
                pyproject_pkg = full
            elif conf_path == untouchable_paths[1]:
                pyproject_test = full
        # Check old data to remove obsoleted files
        env_conda_old = {}
        env_pip_old = {}
        conf_old = {}
        for tool_name, tool in self._data_before.get("tool", {}).items():
            tool_env = tool.get("env")
            if tool_env:
                env_conda_old.setdefault(tool_env["file"]["conda"]["path"], []).append(tool_name)
                env_file_pip = tool_env["file"].get("pip")
                if env_file_pip:
                    env_pip_old.setdefault(env_file_pip["path"], []).append(tool_name)
            conf_file = tool.get("config", {}).get("file")
            if conf_file:
                conf_old.setdefault(conf_file["path"], []).append(tool_name)
        for dic_old, dic_new, typ in (
            (env_conda_old, env_conda, DynamicFileType.TOOL_ENV_CONDA),
            (env_pip_old, env_pip, DynamicFileType.TOOL_ENV_PIP),
            (conf_old, conf, DynamicFileType.TOOL_CONFIG),
        ):
            for path, tool_names in dic_old.items():
                if path not in dic_new and path not in untouchable_paths:
                    out.append(
                        DynamicFile(
                            type=typ,
                            subtype=("_".join(tool_names), ", ".join(tool_names)),
                            path_before=path
                        )
                    )
        return out, pyproject_pkg, pyproject_test

    def issue_template_chooser(self) -> list[DynamicFile]:
        if self._is_disabled("issue"):
            return []
        generate_file = {
            "type": DynamicFileType.CONFIG,
            "subtype": ("issue_chooser", "Issue Template Chooser"),
            "path": _const.FILEPATH_ISSUES_CONFIG,
            "path_before": _const.FILEPATH_ISSUES_CONFIG,
        }
        issues = self._data["issue"]
        if not issues:
            return [DynamicFile(**generate_file)]
        config = {}
        if issues.get("blank_enabled"):
            config["blank_issues_enabled"] = issues["blank_enabled"]
        if issues.get("contact_links"):
            config["contact_links"] = self._data["issue"]["contact_links"]
        file_content = _ps.write.to_yaml_string(data=config, end_of_file_newline=True) if config else ""
        return [DynamicFile(content=file_content, **generate_file)]

    def gitignore(self) -> list[DynamicFile]:
        file_content = "\n".join(self._data.get("repo.gitignore", []))
        generated_file = DynamicFile(
            type=DynamicFileType.CONFIG,
            subtype=("gitignore", "Git Ignore"),
            content=file_content,
            path=_const.FILEPATH_GITIGNORE,
            path_before=_const.FILEPATH_GITIGNORE
        )
        return [generated_file]

    def gitattributes(self) -> list[DynamicFile]:
        if not (self._data["repo.gitattributes"] or self._data_before["repo.gitattributes"]):
            return []
        file_info = {
            "type": DynamicFileType.CONFIG,
            "subtype": ("gitattributes", "Git Attributes"),
            "path": _const.FILEPATH_GIT_ATTRIBUTES,
            "path_before": _const.FILEPATH_GIT_ATTRIBUTES,
        }
        file_content = ""
        attributes = self._data.get("repo.gitattributes", [])
        max_len_pattern = max([len(list(attribute.keys())[0]) for attribute in attributes])
        max_len_attr = max(
            [max(len(attr) for attr in list(attribute.values())[0]) for attribute in attributes]
        )
        for attribute in attributes:
            pattern = list(attribute.keys())[0]
            attrs = list(attribute.values())[0]
            attrs_str = "  ".join(f"{attr: <{max_len_attr}}" for attr in attrs).strip()
            file_content += f"{pattern: <{max_len_pattern}}    {attrs_str}\n"
        return [DynamicFile(content=file_content, **file_info)]

    def citation(self) -> list[DynamicFile]:

        def create_identifier(ident: dict):
            return {
                k: v for k, v in ident if k not in ("relation", "resource_type")
            }

        def create_repository(repo: dict):
            out = {}
            for in_key, out_key in (
                ("build", "repository-artifact"),
                ("source", "repository-code"),
                ("other", "repository"),
            ):
                if in_key in repo:
                    out[out_key] = repo[in_key]
            return out

        def create_person(entity: str | dict):
            if isinstance(entity, str):
                entity = self._data["team"].get(entity)
                if not entity:
                    raise ValueError(f"Person '{entity}' not found in team data.")
            _out = {}
            if entity["name"].get("legal"):
                _out["name"] = entity["name"]["legal"]
                for in_key, out_key in (
                    ("location", "location"),
                    ("date_start", "date-start"),
                    ("date_end", "date-end"),
                ):
                    if entity.get(in_key):
                        _out[out_key] = entity[in_key]
            else:
                name = entity["name"]
                for in_key, out_key in (
                    ("last", "family-names"),
                    ("first", "given-names"),
                    ("particle", "name-particle"),
                    ("suffix", "name-suffix"),
                    ("affiliation", "affiliation")
                ):
                    if name.get(in_key):
                        _out[out_key] = name[in_key]
            for contact_type, contact_key in (("orcid", "url"), ("email", "id")):
                if entity.get(contact_type):
                    _out[contact_type] = entity[contact_type][contact_key]
            for key in (
                "alias",
                "website",
                "tel",
                "fax",
                "address",
                "city",
                "region",
                "country",
                "post-code",
            ):
                if entity.get(key):
                    _out[key] = entity[key]
            return _out

        def create_reference(ref: dict):
            entity_list_keys = [
                "authors", "contacts", "editors", "editors-series", "recipients", "senders", "translators"
            ]
            entity_keys = ["conference", "database-provider", "institution", "location", "publisher"]
            out = {
                k: v for k, v in ref.items() if k not in ["repository", "identifiers"] + entity_list_keys + entity_keys
            }
            for entity_list_key in entity_list_keys:
                if entity_list_key not in ref:
                    continue
                if entity_list_key == "contacts":
                    out_key = "contact"
                else:
                    out_key = entity_list_key
                out[out_key] = [create_person(entity=entity) for entity in ref[entity_list_key]]
            for entity_key in entity_keys:
                if entity_key in ref:
                    out[entity_key] = create_person(entity=ref[entity_key])
            if "repository" in ref:
                out |= create_repository(ref["repository"])
            if "identifiers" in ref:
                out["identifiers"] = [create_identifier(ident) for ident in ref["identifiers"]]
            return out

        if not (self._data.get("citation") or self._data_before.get("citation")):
            return []
        generated_file = {
            "type": DynamicFileType.CONFIG,
            "subtype": ("citation", "Citation"),
            "path": _const.FILEPATH_CITATION_CONFIG,
            "path_before": _const.FILEPATH_CITATION_CONFIG,
        }
        cite = self._data["citation"]
        if not cite:
            return [DynamicFile(**generated_file)]
        filepath = self._path_repo / _const.FILEPATH_CITATION_CONFIG
        cite_old = _ps.read.yaml_from_file(path=filepath) if filepath.is_file() else {}
        out = {
            k: v for k, v in cite.items() if v and k in [
                "message", "title", "license", "url", "type", "keywords", "abstract"
            ]
        }
        for key in ("version", "date-released", "doi", "commit"):
            if cite_old.get(key):
                out[key] = cite_old[key]
        for key in ("license_url",):
            if cite.get(key):
                out[key.replace('_', "-")] = cite[key]
        if cite.get("repository"):
            out |= create_repository(cite["repository"])
        if cite.get("identifiers"):
            out["identifiers"] = [create_identifier(ident) for ident in cite["identifiers"]]
        if cite.get("contacts"):
            out["contact"] = [create_person(entity=entity) for entity in cite["contacts"]]
        out["authors"] = [create_person(entity=entity) for entity in cite["authors"]]
        if cite.get("preferred_citation"):
            out["preferred-citation"] = create_reference(cite["preferred_citation"])
        if cite.get("references"):
            out["references"] = [create_reference(ref) for ref in cite["references"]]
        out["cff-version"] = "1.2.0"
        file_content = _ps.write.to_yaml_string(data=out, end_of_file_newline=True)
        return [DynamicFile(content=file_content, **generated_file)]

    def validate_codecov_config(self, config: str) -> None:
        try:
            # Validate the config file
            # https://docs.codecov.com/docs/codecov-yaml#validate-your-repository-yaml
            pylinks.http.request(
                verb="POST",
                url="https://codecov.io/validate",
                data=config.encode(),
            )
        except _WebAPIError as e:
            logger.error(
                "CodeCov Configuration File Validation",
                "Validation of Codecov configuration file failed.", str(e)
            )
        return
