# Non-standard libraries
import ruamel.yaml
from repodynamics.logger import Logger


class ConfigFileGenerator:
    def __init__(self, metadata: dict, logger: Logger = None):
        self._logger = logger or Logger()
        self._meta = metadata
        self._logger.h2("Generate Files")
        return

    def generate(self) -> list[dict]:
        label_syncer, pr_labeler = self._labels()
        updates = [
            dict(category="config", name="funding", content=self._funding()),
            dict(category="config", name="labels", content=label_syncer),
            dict(category="config", name="labels_pr", content=pr_labeler),
        ]
        return updates

    def _labels(self) -> tuple[str, str]:
        self._logger.h3("Process metadata: labels")
        # repo labels: https://github.com/marketplace/actions/label-syncer
        repo_labels = []
        pr_labels = []
        labels = self._meta.get('labels', [])
        for label in labels:
            repo_labels.append({attr: label[attr] for attr in ["name", "description", "color"]})
            if label.get("pulls"):
                pr_labels.append({"label": label["name"], **label["pulls"]})
        label_syncer = ruamel.yaml.YAML(typ=['rt', 'string']).dumps(
            repo_labels, add_final_eol=True
        ) if repo_labels else ""
        pr_labeler = ruamel.yaml.YAML(typ=['rt', 'string']).dumps(
            {"version": "v1", "labels": pr_labels}, add_final_eol=True
        ) if pr_labels else ""
        return label_syncer, pr_labeler

    def _funding(self) -> str:
        """
        References
        ----------
        https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/displaying-a-sponsor-button-in-your-repository#about-funding-files
        """
        self._logger.h3("Generate File: FUNDING.yml")
        funding = self._meta.get("funding")
        if not funding:
            self._logger.skip("'funding' not set in metadata; skipping.")
            return ""
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
        output_str = ruamel.yaml.YAML(typ=['rt', 'string']).dumps(output, add_final_eol=True)
        self._logger.success(f"Generated 'FUNDING.yml' file.", output_str)
        return output_str
