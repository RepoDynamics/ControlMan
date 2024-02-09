from loggerman import logger

from controlman._path_manager import PathManager
from controlman.datatype import DynamicFile
from controlman import ControlCenterContentManager


def generate(
    content_manager: ControlCenterContentManager,
    path_manager: PathManager,
) -> list[tuple[DynamicFile, str]]:
    return _HealthFileGenerator(
        content_manager=content_manager,
        path_manager=path_manager,
    ).generate()


class _HealthFileGenerator:
    def __init__(
        self,
        content_manager: ControlCenterContentManager,
        path_manager: PathManager,
    ):
        self._ccm = content_manager
        self._pathman = path_manager
        return

    @logger.sectioner("Generate Health Files")
    def generate(self) -> list[tuple[DynamicFile, str]]:
        updates = []
        for health_file_id, data in self._ccm["health_file"].items():
            logger.section(health_file_id.replace("_", " ").title())
            file_info = self._pathman.health_file(health_file_id, target_path=data["path"])
            file_content = self._codeowners() if health_file_id == "codeowners" else data["text"]
            updates.append((file_info, file_content))
            logger.info(code_title="File info", code=str(file_info))
            logger.debug(code_title="File content", code=file_content)
            logger.section_end()
        return updates

    def _codeowners(self) -> str:
        """

        Returns
        -------

        References
        ----------
        https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners#codeowners-syntax
        """
        codeowners = self._ccm["maintainer"].get("pull", {}).get("reviewer", {}).get("by_path")
        if not codeowners:
            return ""
        # Get the maximum length of patterns to align the columns when writing the file
        max_len = max([len(list(codeowner_dic.keys())[0]) for codeowner_dic in codeowners])
        text = ""
        for entry in codeowners:
            pattern = list(entry.keys())[0]
            reviewers_list = entry[pattern]
            reviewers = " ".join([f"@{reviewer.removeprefix('@')}" for reviewer in reviewers_list])
            text += f"{pattern: <{max_len}}   {reviewers}\n"
        return text
