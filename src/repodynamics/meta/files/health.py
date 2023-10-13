from pathlib import Path


from repodynamics.meta.reader import MetaReader
from repodynamics.logger import Logger
from repodynamics.meta.writer import OutputFile, OutputPaths


class HealthFileGenerator:
    def __init__(self, metadata: dict, path_root: str | Path = ".", logger: Logger = None):
        self._path_root = Path(path_root).resolve()
        self._logger = logger or Logger()
        self._meta = metadata
        self._out_db = OutputPaths(path_root=self._path_root, logger=self._logger)
        self._logger.h2("Generate Files")
        return

    def generate(self) -> list[tuple[OutputFile, str]]:
        updates = []
        for health_file_id, data in self._meta["health_file"].items():
            info = self._out_db.health_file(health_file_id, target_path=data["path"])
            text = self._generate_codeowners() if health_file_id == "codeowners" else data["text"]
            updates.append((info, text))
        return updates

    def _generate_codeowners(self) -> str:
        """

        Returns
        -------

        References
        ----------
        https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners#codeowners-syntax
        """
        codeowners = self._meta.get("maintainer", {}).get("pull", {}).get("reviewer", {}).get("by_path")
        if not codeowners:
            return ""
        # Get the maximum length of patterns to align the columns when writing the file
        max_len = max([len(list(codeowner_dic.keys())[0]) for codeowner_dic in codeowners])
        text = ""
        for entry in codeowners:
            pattern = list(entry.keys())[0]
            reviewers_list = entry[pattern]
            reviewers = " ".join([f"@{reviewer.removeprefix('@')}" for reviewer in reviewers_list])
            text += f'{pattern: <{max_len}}   {reviewers}\n'
        return text
