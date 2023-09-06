from pathlib import Path


from repodynamics.meta.reader import MetaReader
from repodynamics.logger import Logger


class HealthFileGenerator:
    def __init__(self, metadata: dict, reader: MetaReader, logger: Logger = None):
        if not isinstance(reader, MetaReader):
            raise TypeError(f"reader must be of type MetaReader, not {type(reader)}")
        self._reader = reader
        self._logger = logger or reader.logger
        self._meta = metadata
        self._health_file = {
            "code_of_conduct": "CODE_OF_CONDUCT.md",
            "codeowners": "CODEOWNERS",
            "contributing": "CONTRIBUTING.md",
            "governance": "GOVERNANCE.md",
            "security": "SECURITY.md",
            "support": "SUPPORT.md",
        }
        self._logger.h2("Generate Files")
        return

    def generate(self) -> list[dict]:
        updates = []
        for health_file in self._health_file:
            update = {"category": "health_file", "name": health_file, "content": "", "target_path": "."}
            target_path = self._meta.get("health_file", {}).get(health_file)
            if not target_path:
                self._logger.skip(f"'{health_file}' not set in metadata; skipping.")
                updates.append(update)
                continue
            update['target_path'] = target_path
            update['content'] = self._health_file_content(health_file)
        return updates

    def _health_file_content(self, name: str) -> str:
        if name == "codeowners":
            return self._generate_codeowners()
        return self._reader.template("health_file", self._health_file[name]).format(**self._meta)

    def _generate_codeowners(self) -> str:
        """

        Returns
        -------

        References
        ----------
        https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners#codeowners-syntax
        """
        # Get the maximum length of patterns to align the columns when writing the file
        if not self._meta.get("pulls"):
            return ""
        max_len = max([len(entry["pattern"]) for entry in self._meta["pulls"]])
        text = ""
        for entry in self._meta["pulls"]:
            reviewers = " ".join([f"@{reviewer.removeprefix('@')}" for reviewer in entry["reviewers"]])
            text += f'{entry["pattern"]: <{max_len}}   {reviewers}\n'
        return text
