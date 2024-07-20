import datetime
from pathlib import Path as _Path

from loggerman import logger
import pyserials
import pylinks
from pylinks.exceptions import WebAPIError
import markitup as _miu

from controlman._path_manager import PathManager
from controlman.datatype import DynamicFile, DynamicFileType
from controlman.nested_dict import NestedDict as _NestedDict
from controlman.file_gen import unit as _unit


class ConfigFileGenerator:
    def __init__(
        self,
        data: _NestedDict,
        path_manager: PathManager,
    ):
        self._data = data
        self._path_manager = path_manager
        return

    def generate(self) -> list[tuple[DynamicFile, str]]:
        return (
            self.web_requirements()
            + self.funding()
            + self.workflow_requirements()
            + self.pre_commit_config()
            + self.read_the_docs()
            + self.codecov_config()
            + self.issue_template_chooser()
            + self.gitignore()
            + self.gitattributes()
        )

    def web_requirements(self):
        if not self._data["web"]:
            return []
        dependencies = []
        for path in ("web.sphinx.dependency", "web.theme.dependency"):
            dependency = self._data.get(path)
            if dependency:
                dependencies.append(dependency)
        for path in ("web.extensions", "web.packages"):
            for item in self._data.get(path, []):
                dependency = item["dependency"]
                if dependency:
                    dependencies.append(dependency)
        if not dependencies:
            return []
        conda_env, pip_env, pip_full = _unit.create_environment_files(
            dependencies=dependencies,
            env_name=f"{_miu.txt.slug(self._data['name'])}-website",
        )
        rel_path_base = _Path(self._data["dir.path.web"])
        conda_env_file_info = DynamicFile(
            id="website_conda_env",
            category=DynamicFileType.CONFIG,
            rel_path=rel_path_base/"environment.yaml"
        )
        output = [()]
        return

    @logger.sectioner("Generate GitHub Funding Configuration File")
    def funding(self) -> list[tuple[DynamicFile, str]]:
        """
        References
        ----------
        https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/displaying-a-sponsor-button-in-your-repository#about-funding-files
        """
        file_info = self._path_manager.funding
        funding = self._data["funding"]
        if not funding:
            file_content = ""
        else:
            output = {}
            for funding_platform, users in funding.items():
                if funding_platform in ["github", "custom"]:
                    if isinstance(users, list):
                        output[funding_platform] = pyserials.format.to_yaml_array(data=users, inline=True)
                    elif isinstance(users, str):
                        output[funding_platform] = users
                    # Other cases are not possible because of the schema
                else:
                    output[funding_platform] = users
            file_content = pyserials.write.to_yaml_string(data=output, end_of_file_newline=True)
        logger.info(code_title="File info", code=file_info)
        logger.debug(code_title="File content", code=file_content)
        return [(file_info, file_content)]

    @logger.sectioner("Generate Workflow Requirements Files")
    def workflow_requirements(self) -> list[tuple[DynamicFile, str]]:
        tools = self._data["workflow"]["tool"]
        out = []
        for tool_name, tool_spec in tools.items():
            logger.section(f"Tool: {tool_name}")
            file_info = self._path_manager.workflow_requirements(tool_name)
            file_content = "\n".join(tool_spec["pip_spec"])
            out.append((file_info, file_content))
            logger.info(code_title="File info", code=str(file_info))
            logger.debug(code_title="File content", code=file_content)
            logger.section_end()
        return out

    @logger.sectioner("Generate Pre-Commit Configuration Files")
    def pre_commit_config(self) -> list[tuple[DynamicFile, str]]:
        file_info = self._path_manager.pre_commit_config
        config = self._data["workflow"].get("pre_commit")
        if not config:
            file_content = ""
        else:
            file_content = pyserials.write.to_yaml_string(data=config, end_of_file_newline=True)
        logger.info(code_title="File info", code=str(file_info))
        logger.debug(code_title="File content", code=file_content)
        return [(file_info, file_content)]

    @logger.sectioner("Generate ReadTheDocs Configuration File")
    def read_the_docs(self) -> list[tuple[DynamicFile, str]]:
        file_info = self._path_manager.read_the_docs_config
        config = self._data["web"].get("readthedocs")
        if not config:
            file_content = ""
        else:
            file_content = pyserials.write.to_yaml_string(
                data={
                    key: val for key, val in config.items()
                    if key not in ["name", "platform", "versioning_scheme", "language"]
                },
                end_of_file_newline=True
            )
        logger.info(code_title="File info", code=str(file_info))
        logger.debug(code_title="File content", code=file_content)
        return [(file_info, file_content)]

    @logger.sectioner("Generate Codecov Configuration File")
    def codecov_config(self) -> list[tuple[DynamicFile, str]]:
        file_info = self._path_manager.codecov_config
        config = self._data["workflow"].get("codecov")
        if not config:
            file_content = ""
        else:
            file_content = pyserials.write.to_yaml_string(data=config, end_of_file_newline=True)
            try:
                # Validate the config file
                # https://docs.codecov.com/docs/codecov-yaml#validate-your-repository-yaml
                pylinks.http.request(
                    verb="POST",
                    url="https://codecov.io/validate",
                    data=file_content.encode(),
                )
            except WebAPIError as e:
                logger.error("Validation of Codecov configuration file failed.", str(e))
        logger.info(code_title="File info", code=str(file_info))
        logger.debug(code_title="File content", code=file_content)
        return [(file_info, file_content)]

    @logger.sectioner("Generate Issue Template Chooser Configuration File")
    def issue_template_chooser(self) -> list[tuple[DynamicFile, str]]:
        file_info = self._path_manager.issue_template_chooser_config
        file = {"blank_issues_enabled": self._data["issue"]["blank_enabled"]}
        if self._data["issue"].get("contact_links"):
            file["contact_links"] = self._data["issue"]["contact_links"]
        file_content = pyserials.write.to_yaml_string(data=file, end_of_file_newline=True)
        logger.info(code_title="File info", code=str(file_info))
        logger.debug(code_title="File content", code=file_content)
        return [(file_info, file_content)]

    @logger.sectioner("Generate Gitignore File")
    def gitignore(self) -> list[tuple[DynamicFile, str]]:
        file_info = self._path_manager.gitignore
        local_dir = self._data["path"]["dir"]["local"]["root"]
        file_content = "\n".join(
            self._data["repo"].get("gitignore", [])
            + [
                f"{local_dir}/**",
                f"!{local_dir}/**/",
                f"!{local_dir}/**/README.md",
            ]
        )
        logger.info(code_title="File info", code=str(file_info))
        logger.debug(code_title="File content", code=file_content)
        return [(file_info, file_content)]

    @logger.sectioner("Generate Gitattributes File")
    def gitattributes(self) -> list[tuple[DynamicFile, str]]:
        file_info = self._path_manager.gitattributes
        file_content = ""
        attributes = self._data["repo"].get("gitattributes", [])
        max_len_pattern = max([len(list(attribute.keys())[0]) for attribute in attributes])
        max_len_attr = max(
            [max(len(attr) for attr in list(attribute.values())[0]) for attribute in attributes]
        )
        for attribute in attributes:
            pattern = list(attribute.keys())[0]
            attrs = list(attribute.values())[0]
            attrs_str = "  ".join(f"{attr: <{max_len_attr}}" for attr in attrs).strip()
            file_content += f"{pattern: <{max_len_pattern}}    {attrs_str}\n"
        logger.info(code_title="File info", code=str(file_info))
        logger.debug(code_title="File content", code=file_content)
        return [(file_info, file_content)]

    def citation(self) -> dict | None:

        def create_person(person_id):
            person = self._data["people"][person_id]
            pout = {}
            if person["name"].get("legal"):
                pout["name"] = person["name"]["legal"]
                for in_key, out_key in (
                    ("location", "location"),
                    ("date_start", "date-start"),
                    ("date_end", "date-end"),
                ):
                    if person.get(in_key):
                        pout[out_key] = person[in_key]
            else:
                name = person["name"]
                for in_key, out_key in (
                    ("last", "family-names"),
                    ("first", "given-names"),
                    ("particle", "name-particle"),
                    ("suffix", "name-suffix"),
                    ("affiliation", "affiliation")
                ):
                    if name.get(in_key):
                        pout[out_key] = name[in_key]
            for contact_type, contact_key in (("orcid", "url"), ("email", "user")):
                if person.get(contact_type):
                    pout[contact_type] = person[contact_type][contact_key]
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
                if person.get(key):
                    pout[key] = person[key]
            return pout

        def create_reference(ref: dict):
            out = {}
            for key in (
                "abbreviation",
                "abstract",
            ):
                if ref.get(key):
                    out[key] = ref[key]
            out["authors"] = [
                create_person(person_id=author_map["id"]) for author_map in ref["authors"]
            ]
            return out

        def get_commit() -> str:
            return

        if not self._data.get("citation"):
            return
        cite = self._data["citation"]
        cite_old = pyserials.read.yaml_from_file(
            path=self._path_manager.citation.path
        ) if self._path_manager.citation.path.is_file() else {}
        out = {
            "message": cite["message"],
            "title": cite["title"],
            "version": cite_old.get("version", ""),
            "date-released": cite_old.get("date-released", ""),
            "doi": cite_old.get("doi", ""),
            "commit": get_commit(),
        }
        for key in ("license", "license_url", "url"):
            if cite.get(key):
                out[key.replace('_', "-")] = cite[key]
        if cite.get("repository"):
            for in_key, out_key in (
                ("build", "repository-artifact"),
                ("source", "repository-code"),
                ("other", "repository"),
            ):
                if cite["repository"].get(in_key):
                    out[out_key] = cite["repository"][in_key]
        for key in ["identifiers", "type", "keywords", "abstract"]:
            if cite.get(key):
                out[key] = cite[key]
        if cite.get("contacts"):
            out["contact"] = [
                create_person(person_id=contact_id) for contact_id in cite["contacts"]
            ]
        out["authors"] = [
            create_person(person_id=author_map["id"]) for author_map in cite["authors"]
        ]
        if cite.get("preferred_citation"):
            out["preferred-citation"] = create_reference(cite["preferred_citation"])
        if cite.get("references"):
            out["references"] = [create_reference(ref) for ref in cite["references"]]
        out["cff-version"] = "1.2.0"
        return out

    def prepare_citation_for_release(
        self,
        doi: str,
        version: str,
    ):
        cit_cur = pyserials.read.yaml_from_file(
            path=self._path_manager.citation.path
        ) if self._path_manager.citation.path.is_file() else self.citation()
        cit_cur["version"] = version
        cit_cur["doi"] = doi
        cit_cur["date-released"] = datetime.datetime.now().strftime('%Y-%m-%d')
        cit_cur.pop("commit", None)
