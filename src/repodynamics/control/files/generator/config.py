import pyserials
from actionman.logger import Logger
import pylinks
from pylinks.exceptions import WebAPIError

from repodynamics.path import PathManager
from repodynamics.datatype import DynamicFile
from repodynamics.control.content import ControlCenterContentManager


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
        self._logger.h2("Generate Files")
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
        self._logger.h3("Generate File: FUNDING.yml")
        info = self._path_manager.funding
        funding = self._ccm["funding"]
        if not funding:
            self._logger.skip("'funding' not set in metadata; skipping.")
            return [(info, "")]
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
        output_str = pyserials.write.to_yaml_string(data=output, end_of_file_newline=True)
        self._logger.success(f"Generated 'FUNDING.yml' file.", output_str)
        return [(info, output_str)]

    def workflow_requirements(self) -> list[tuple[DynamicFile, str]]:
        tools = self._ccm["workflow"]["tool"]
        out = []
        for tool_name, tool_spec in tools.items():
            text = "\n".join(tool_spec["pip_spec"])
            out.append((self._path_manager.workflow_requirements(tool_name), text))
        return out

    def pre_commit_config(self) -> list[tuple[DynamicFile, str]]:
        out = []
        for config_type in ("main", "release", "pre-release", "implementation", "development", "auto-update", "other"):
            info = self._path_manager.pre_commit_config(config_type)
            config = self._ccm["workflow"]["pre_commit"].get(config_type)
            if not config:
                self._logger.skip("'pre_commit' not set in metadata.")
                out.append((info, ""))
            else:
                text = pyserials.write.to_yaml_string(data=config, end_of_file_newline=True)
                out.append((info, text))
        return out

    def read_the_docs(self) -> list[tuple[DynamicFile, str]]:
        info = self._path_manager.read_the_docs_config
        config = self._ccm["web"].get("readthedocs")
        if not config:
            self._logger.skip("'readthedocs' not set in metadata.")
            return [(info, "")]
        text = pyserials.write.to_yaml_string(
            data={
                key: val for key, val in config.items()
                if key not in ["name", "platform", "versioning_scheme", "language"]
            },
            end_of_file_newline=True
        )
        return [(info, text)]

    def codecov_config(self) -> list[tuple[DynamicFile, str]]:
        info = self._path_manager.codecov_config
        config = self._ccm["workflow"].get("codecov")
        if not config:
            self._logger.skip("'codecov' not set in metadata.")
            return [(info, "")]
        text = pyserials.write.to_yaml_string(data=config, end_of_file_newline=True)
        try:
            # Validate the config file
            # https://docs.codecov.com/docs/codecov-yaml#validate-your-repository-yaml
            pylinks.request(
                verb="POST",
                url="https://codecov.io/validate",
                data=text.encode(),
            )
        except WebAPIError as e:
            self._logger.error("Validation of Codecov configuration file failed.", str(e))
        return [(info, text)]

    def issue_template_chooser(self) -> list[tuple[DynamicFile, str]]:
        info = self._path_manager.issue_template_chooser_config
        file = {"blank_issues_enabled": self._ccm["issue"]["blank_enabled"]}
        if self._ccm["issue"].get("contact_links"):
            file["contact_links"] = self._ccm["issue"]["contact_links"]
        text = pyserials.write.to_yaml_string(data=file, end_of_file_newline=True)
        return [(info, text)]

    def gitignore(self) -> list[tuple[DynamicFile, str]]:
        info = self._path_manager.gitignore
        local_dir = self._ccm["path"]["dir"]["local"]["root"]
        text = "\n".join(
            self._ccm["repo"].get("gitignore", [])
            + [
                f"{local_dir}/**",
                f"!{local_dir}/**/",
                f"!{local_dir}/**/README.md",
            ]
        )
        return [(info, text)]

    def gitattributes(self) -> list[tuple[DynamicFile, str]]:
        info = self._path_manager.gitattributes
        text = ""
        attributes = self._ccm["repo"].get("gitattributes", [])
        max_len_pattern = max([len(list(attribute.keys())[0]) for attribute in attributes])
        max_len_attr = max(
            [max(len(attr) for attr in list(attribute.values())[0]) for attribute in attributes]
        )
        for attribute in attributes:
            pattern = list(attribute.keys())[0]
            attrs = list(attribute.values())[0]
            attrs_str = "  ".join(f"{attr: <{max_len_attr}}" for attr in attrs).strip()
            text += f"{pattern: <{max_len_pattern}}    {attrs_str}\n"
        return [(info, text)]
