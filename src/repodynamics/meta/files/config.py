from pathlib import Path

# Non-standard libraries
import ruamel.yaml
from ruamel.yaml import YAML
import pylinks
from pylinks.http import WebAPIError
from repodynamics.logger import Logger
from repodynamics.path import PathFinder
from repodynamics.datatype import DynamicFile
from repodynamics.meta.manager import MetaManager


class ConfigFileGenerator:
    def __init__(self, metadata: MetaManager, output_path: PathFinder, logger: Logger = None):
        self._logger = logger or Logger()
        self._meta = metadata
        self._out_db = output_path
        self._logger.h2("Generate Files")
        return

    def generate(self) -> list[tuple[DynamicFile, str]]:
        # label_syncer, pr_labeler = self._labels()
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

    # def _labels(self) -> tuple[str, str]:
    #     self._logger.h3("Process metadata: labels")
    #     # repo labels: https://github.com/marketplace/actions/label-syncer
    #     repo_labels = []
    #     pr_labels = []
    #     labels = self._meta.get('labels', [])
    #     for label in labels:
    #         repo_labels.append({attr: label[attr] for attr in ["name", "description", "color"]})
    #         if label.get("pulls"):
    #             pr_labels.append({"label": label["name"], **label["pulls"]})
    #     label_syncer = ruamel.yaml.YAML(typ=['rt', 'string']).dumps(
    #         repo_labels, add_final_eol=True
    #     ) if repo_labels else ""
    #     pr_labeler = ruamel.yaml.YAML(typ=['rt', 'string']).dumps(
    #         {"version": "v1", "labels": pr_labels}, add_final_eol=True
    #     ) if pr_labels else ""
    #     return label_syncer, pr_labeler

    # def repo_labels(self) -> list[tuple[OutputFile, str]]:
    #     self._logger.h3("Process metadata: labels")
    #     # repo labels: https://github.com/marketplace/actions/label-syncer
    #     info = self._out_db.labels_repo
    #     out = []
    #     prefixes = []
    #     for group_name, group in self._meta["label"]["group"].items():
    #         prefix = group["prefix"]
    #         if prefix in prefixes:
    #             self._logger.error(f"Duplicate prefix '{prefix}' in label group '{group_name}'.")
    #         prefixes.append(prefix)
    #         suffixes = []
    #         for label in group['labels'].values():
    #             suffix = label['suffix']
    #             if suffix in suffixes:
    #                 self._logger.error(f"Duplicate suffix '{suffix}' in label group '{group_name}'.")
    #             suffixes.append(suffix)
    #             out.append(
    #                 {
    #                     "name": f"{prefix}{suffix}",
    #                     "description": label["description"],
    #                     "color": group["color"]
    #                 }
    #             )
    #     text = ruamel.yaml.YAML(typ=['rt', 'string']).dumps(out, add_final_eol=True) if out else ""
    #     return [(info, text)]

    def funding(self) -> list[tuple[DynamicFile, str]]:
        """
        References
        ----------
        https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/displaying-a-sponsor-button-in-your-repository#about-funding-files
        """
        self._logger.h3("Generate File: FUNDING.yml")
        info = self._out_db.funding
        funding = self._meta["funding"]
        if not funding:
            self._logger.skip("'funding' not set in metadata; skipping.")
            return [(info, "")]
        output = {}
        for funding_platform, users in funding.items():
            if funding_platform in ["github", "custom"]:
                if isinstance(users, list):
                    flow_list = ruamel.yaml.comments.CommentedSeq()
                    flow_list.fa.set_flow_style()
                    flow_list.extend(users)
                    output[funding_platform] = flow_list
                elif isinstance(users, str):
                    output[funding_platform] = users
                # Other cases are not possible because of the schema
            else:
                output[funding_platform] = users
        output_str = YAML(typ=["rt", "string"]).dumps(output, add_final_eol=True)
        self._logger.success(f"Generated 'FUNDING.yml' file.", output_str)
        return [(info, output_str)]

    def workflow_requirements(self) -> list[tuple[DynamicFile, str]]:
        tools = self._meta["workflow"]["tool"]
        out = []
        for tool_name, tool_spec in tools.items():
            text = "\n".join(tool_spec["pip_spec"])
            out.append((self._out_db.workflow_requirements(tool_name), text))
        return out

    def pre_commit_config(self) -> list[tuple[DynamicFile, str]]:
        out = []
        for config_type in ("main", "release", "dev", "other"):
            info = self._out_db.pre_commit_config(config_type)
            config = self._meta["workflow"]["pre_commit"].get(config_type)
            if not config:
                self._logger.skip("'pre_commit' not set in metadata.")
                out.append((info, ""))
            else:
                text = YAML(typ=["rt", "string"]).dumps(config, add_final_eol=True)
                out.append((info, text))
        return out

    def read_the_docs(self) -> list[tuple[DynamicFile, str]]:
        info = self._out_db.read_the_docs_config
        config = self._meta["web"].get("readthedocs")
        if not config:
            self._logger.skip("'readthedocs' not set in metadata.")
            return [(info, "")]
        text = YAML(typ=["rt", "string"]).dumps(
            {key: val for key, val in config.items() if key != "name"}, add_final_eol=True
        )
        return [(info, text)]

    def codecov_config(self) -> list[tuple[DynamicFile, str]]:
        info = self._out_db.codecov_config
        config = self._meta["workflow"].get("codecov")
        if not config:
            self._logger.skip("'codecov' not set in metadata.")
            return [(info, "")]
        text = YAML(typ=["rt", "string"]).dumps(config, add_final_eol=True)
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
        info = self._out_db.issue_template_chooser_config
        file = {"blank_issues_enabled": self._meta["issue"]["blank_enabled"]}
        if self._meta["issue"].get("contact_links"):
            file["contact_links"] = self._meta["issue"]["contact_links"]
        text = YAML(typ=["rt", "string"]).dumps(file, add_final_eol=True)
        return [(info, text)]

    def gitignore(self) -> list[tuple[DynamicFile, str]]:
        info = self._out_db.gitignore
        local_dir = self._meta["path"]["dir"]["local"]["root"]
        text = "\n".join(
            self._meta["repo"].get("gitignore", [])
            + [
                f"{local_dir}/**",
                f"!{local_dir}/**/",
                f"!{local_dir}/**/README.md",
            ]
        )
        return [(info, text)]

    def gitattributes(self) -> list[tuple[DynamicFile, str]]:
        info = self._out_db.gitattributes
        text = ""
        attributes = self._meta["repo"].get("gitattributes", [])
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
