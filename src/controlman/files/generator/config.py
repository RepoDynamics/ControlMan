import pyserials
from actionman.logger import Logger
import pylinks
from pylinks.exceptions import WebAPIError

from controlman._path import PathManager
from controlman.datatype import DynamicFile
from controlman.control.content import ControlCenterContentManager


def generate(
    content_manager: ControlCenterContentManager,
    path_manager: PathManager,
    logger: Logger,
) -> list[tuple[DynamicFile, str]]:
    return ConfigFileGenerator(
        content_manager=content_manager,
        path_manager=path_manager,
        logger=logger,
    ).generate()


class ConfigFileGenerator:
    def __init__(
        self,
        content_manager: ControlCenterContentManager,
        path_manager: PathManager,
        logger: Logger
    ):
        self._ccm = content_manager
        self._path_manager = path_manager
        self._logger = logger
        return

    def generate(self) -> list[tuple[DynamicFile, str]]:
        return (
            self.funding()
            + self.workflow_requirements()
            + self.pre_commit_config()
            + self.read_the_docs()
            + self.codecov_config()
            + self.issue_template_chooser()
            + self.gitignore()
            + self.gitattributes()
        )

    def funding(self) -> list[tuple[DynamicFile, str]]:
        """
        References
        ----------
        https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/displaying-a-sponsor-button-in-your-repository#about-funding-files
        """
        self._logger.section("GitHub Funding Configuration File")
        file_info = self._path_manager.funding
        funding = self._ccm["funding"]
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
        self._logger.info(message="File info:", code=str(file_info))
        self._logger.debug(message="File content:", code=file_content)
        self._logger.section_end()
        return [(file_info, file_content)]

    def workflow_requirements(self) -> list[tuple[DynamicFile, str]]:
        self._logger.section("Workflow Requirements Files")
        tools = self._ccm["workflow"]["tool"]
        out = []
        for tool_name, tool_spec in tools.items():
            self._logger.section(f"Tool: {tool_name}")
            file_info = self._path_manager.workflow_requirements(tool_name)
            file_content = "\n".join(tool_spec["pip_spec"])
            out.append((file_info, file_content))
            self._logger.info(message="File info:", code=str(file_info))
            self._logger.debug(message="File content:", code=file_content)
            self._logger.section_end()
        self._logger.section_end()
        return out

    def pre_commit_config(self) -> list[tuple[DynamicFile, str]]:
        self._logger.section("Pre-Commit Configuration Files")
        out = []
        for config_type in ("main", "release", "pre-release", "implementation", "development", "auto-update", "other"):
            self._logger.section(f"Branch Type '{config_type}'")
            file_info = self._path_manager.pre_commit_config(config_type)
            config = self._ccm["workflow"]["pre_commit"].get(config_type)
            if not config:
                file_content = ""
            else:
                file_content = pyserials.write.to_yaml_string(data=config, end_of_file_newline=True)
            out.append((file_info, file_content))
            self._logger.info(message="File info:", code=str(file_info))
            self._logger.debug(message="File content:", code=file_content)
            self._logger.section_end()
        self._logger.section_end()
        return out

    def read_the_docs(self) -> list[tuple[DynamicFile, str]]:
        self._logger.section("ReadTheDocs Configuration File")
        file_info = self._path_manager.read_the_docs_config
        config = self._ccm["web"].get("readthedocs")
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
        self._logger.info(message="File info:", code=str(file_info))
        self._logger.debug(message="File content:", code=file_content)
        self._logger.section_end()
        return [(file_info, file_content)]

    def codecov_config(self) -> list[tuple[DynamicFile, str]]:
        self._logger.section("Codecov Configuration File")
        file_info = self._path_manager.codecov_config
        config = self._ccm["workflow"].get("codecov")
        if not config:
            file_content = ""
        else:
            file_content = pyserials.write.to_yaml_string(data=config, end_of_file_newline=True)
            try:
                # Validate the config file
                # https://docs.codecov.com/docs/codecov-yaml#validate-your-repository-yaml
                pylinks.request(
                    verb="POST",
                    url="https://codecov.io/validate",
                    data=file_content.encode(),
                )
            except WebAPIError as e:
                self._logger.error("Validation of Codecov configuration file failed.", str(e))
        self._logger.info(message="File info:", code=str(file_info))
        self._logger.debug(message="File content:", code=file_content)
        self._logger.section_end()
        return [(file_info, file_content)]

    def issue_template_chooser(self) -> list[tuple[DynamicFile, str]]:
        self._logger.section("Issue Template Chooser Configuration File")
        file_info = self._path_manager.issue_template_chooser_config
        file = {"blank_issues_enabled": self._ccm["issue"]["blank_enabled"]}
        if self._ccm["issue"].get("contact_links"):
            file["contact_links"] = self._ccm["issue"]["contact_links"]
        file_content = pyserials.write.to_yaml_string(data=file, end_of_file_newline=True)
        self._logger.info(message="File info:", code=str(file_info))
        self._logger.debug(message="File content:", code=file_content)
        self._logger.section_end()
        return [(file_info, file_content)]

    def gitignore(self) -> list[tuple[DynamicFile, str]]:
        self._logger.section("Gitignore File")
        file_info = self._path_manager.gitignore
        local_dir = self._ccm["path"]["dir"]["local"]["root"]
        file_content = "\n".join(
            self._ccm["repo"].get("gitignore", [])
            + [
                f"{local_dir}/**",
                f"!{local_dir}/**/",
                f"!{local_dir}/**/README.md",
            ]
        )
        self._logger.info(message="File info:", code=str(file_info))
        self._logger.debug(message="File content:", code=file_content)
        self._logger.section_end()
        return [(file_info, file_content)]

    def gitattributes(self) -> list[tuple[DynamicFile, str]]:
        self._logger.section("Gitattributes File")
        file_info = self._path_manager.gitattributes
        file_content = ""
        attributes = self._ccm["repo"].get("gitattributes", [])
        max_len_pattern = max([len(list(attribute.keys())[0]) for attribute in attributes])
        max_len_attr = max(
            [max(len(attr) for attr in list(attribute.values())[0]) for attribute in attributes]
        )
        for attribute in attributes:
            pattern = list(attribute.keys())[0]
            attrs = list(attribute.values())[0]
            attrs_str = "  ".join(f"{attr: <{max_len_attr}}" for attr in attrs).strip()
            file_content += f"{pattern: <{max_len_pattern}}    {attrs_str}\n"
        self._logger.info(message="File info:", code=str(file_info))
        self._logger.debug(message="File content:", code=file_content)
        self._logger.section_end()
        return [(file_info, file_content)]
