from typing import Literal

from repodynamics.files.manager import FileSyncManager


class HealthFileSync:

    def __init__(self, sync_manager: "FileSyncManager"):
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
            self.update_file(name)
        return

    def update_file(
            self,
            name: Literal[
                "CODE_OF_CONDUCT", "CODEOWNERS", "CONTRIBUTING", "GOVERNANCE", "SECURITY", "SUPPORT"
            ]
    ):
        allowed_paths = self.allowed_paths(name)
        target_path = self.target_path(name)

        if not target_path:
            # Health file is disabled; delete it if it exists
            removed = False
            for path in allowed_paths:
                if path.exists():
                    with open(path) as f:
                        text_old = f.read()
                    path.unlink()
                    removed = True
            self._manager.add_summary(
                category="health_file",
                name=name,
                status="removed" if removed else "disabled",
                before=text_old if removed else "",
            )
            return

        if target_path not in allowed_paths:
            raise ValueError(
                f"The path '{target_path.relative_to(self._root)}' set in 'config.yaml' metadata file "
                f"is not an allowed path for {name} file. "
                "Allowed paths for health files are the root ('.'), docs, and .github directories."
            )

        # Get the current content of the file if it exists
        text_old = ""
        file_exists = False
        if target_path.exists():
            with open(target_path) as f:
                text_old = f.read()
            file_exists = True

        # Make sure no duplicates exist in other allowed paths
        allowed_paths.remove(target_path)
        for allowed_path in allowed_paths:
            if allowed_path.exists():
                self._manager.log(f"Removing duplicate health file at '{allowed_path.relative_to(self._root)}'.")
                allowed_path.unlink()

        # Generate the new content from template
        text_new = self.text(name)

        if not file_exists:
            # File is being created
            status = "created"
        elif text_old == text_new:
            # File exists and is unchanged
            status = "unchanged"
        else:
            # File is being modified
            status = "modified"

        self._manager.add_summary(
            category="health_file",
            name=name,
            status=status,
            before=text_old,
            after=text_new,
        )

        if status != "unchanged":
            # Write the new content to the file
            with open(target_path, "w") as f:
                f.write(text_new)

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
