from typing import Literal

from repodynamics.meta.manager import MetaManager


class HealthFileSync:

    def __init__(self, sync_manager: "MetaManager"):
        self._manager = sync_manager
        self._meta = self._manager.metadata
        self._root = self._manager.path_root
        self._file = {
            "CODE_OF_CONDUCT": {"filename": "CODE_OF_CONDUCT.md"},
            "CODEOWNERS": {"filename": "CODEOWNERS"},
            "CONTRIBUTING": {"filename": "CONTRIBUTING.md"},
            "GOVERNANCE": {"filename": "GOVERNANCE.md"},
            "SECURITY": {"filename": "SECURITY.md"},
            "SUPPORT": {"filename": "SUPPORT.md"},
        }
        return

    def update(self):
        for name in self._file:
            allowed_paths = self.allowed_paths(name)
            target_path = self.target_path(name)
            if not target_path:
                target_path = allowed_paths.pop(0)
                new_content = ""
            elif target_path not in allowed_paths:
                self._logger.error(
                    f"The path '{target_path.relative_to(self._root)}' set in 'config.yaml' metadata file "
                    f"is not an allowed path for {name} file. "
                    "Allowed paths for health files are the root ('.'), docs, and .github directories."
                )
            else:
                new_content = self.text(name)
                allowed_paths.remove(target_path)
            self._manager.update(
                category="health_file",
                name=name,
                path=target_path,
                new_content=new_content,
                alt_paths=allowed_paths,
            )
        return

    def allowed_paths(self, name: str):
        # Health files are only allowed in the root, docs, and .github directories
        return [
            self._root / allowed_path_rel / f"{self._file[name]['filename']}"
            for allowed_path_rel in ['.', 'docs', '.github']
        ]

    def target_path(self, name: str):
        rel_path = self._meta["config"]["health_file_path"].get(name.casefold())
        return self._root / rel_path / self._file[name]["filename"] if rel_path else None

    def text(self, name: str) -> str:
        return self.generate_codeowners() if name == "CODEOWNERS" else self._manager.template("health_file", name)

    def generate_codeowners(self) -> str:
        """

        Returns
        -------

        References
        ----------
        https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners#codeowners-syntax
        """
        if not self._meta.get("maintain"):
            raise ValueError("Metadata is missing the 'maintain' section.")
        if not self._meta["maintain"].get("pulls"):
            raise ValueError("Metadata is missing the 'maintain.pulls' section.")
        if not isinstance(self._meta["maintain"]["pulls"], list):
            raise ValueError("Metadata 'maintain.pulls' section must be a list.")
        max_len = 0
        for entry in self._meta["maintain"]["pulls"]:
            if not isinstance(entry, dict):
                raise ValueError("Metadata 'maintain.pulls' section must be a list of dicts.")
            if not entry.get("pattern"):
                raise ValueError("Metadata 'maintain.pulls' section must contain 'pattern' key.")
            if not isinstance(entry["pattern"], str):
                raise ValueError("Metadata 'maintain.pulls' section 'pattern' key must be a string.")
            if not entry.get("reviewers"):
                raise ValueError("Metadata 'maintain.pulls' section must contain 'reviewers' key.")
            if not isinstance(entry["reviewers"], list):
                raise ValueError("Metadata 'maintain.pulls' section 'reviewers' key must be a list.")
            if not all([isinstance(reviewer, str) for reviewer in entry["reviewers"]]):
                raise ValueError(
                    "Metadata 'maintain.pulls' section 'reviewers' key must be a list of strings."
                )
            # Get the maximum length of patterns to align the columns when writing the file
            max_len = max(max_len, len(entry["pattern"]))
        text = ""
        for entry in self._meta["maintain"]["pulls"]:
            reviewers = " ".join([f"@{reviewer.removeprefix('@')}" for reviewer in entry["reviewers"]])
            text += f'{entry["pattern"]: <{max_len}}   {reviewers}\n'
        return text
