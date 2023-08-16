# Standard libraries
from pathlib import Path
from typing import Literal, Optional, Sequence

# Non-standard libraries
import ruamel.yaml

from repodynamics.files.manager import FileSyncManager
from repodynamics.files.health_files import HealthFileSync
from repodynamics.files import package


class FileSync:
    def __init__(self, manager: FileSyncManager):
        self._manager = manager
        self._root = self._manager.path_root
        self._meta = self._manager.metadata
        return

    def update(self):
        self.update_license()
        self.update_funding()
        self.update_health_files()
        self.update_package()
        self.update_issue_templates()
        self.update_discussion_templates()
        return

    def update_license(self):
        license = self._meta["copyright"]["license"]
        path = self._root / "LICENSE"
        license_exists = path.exists()
        if license_exists:
            with open(path) as f:
                text_old = f.read()
        else:
            text_old = ""

        if not license:
            path.unlink(missing_ok=True)
            self._manager.add_summary(
                category="license", name="LICENSE", status="removed" if license_exists else "disabled"
            )
            return

        license_id = license['id'].lower().removesuffix("+")
        text_new = self._manager.template(category="license", name=license_id)

        if not license_exists:
            # File is being created
            status = "created"
        elif text_old == text_new:
            # File exists and is unchanged
            status = "unchanged"
        else:
            # File is being modified
            status = "modified"
        self._manager.add_summary(
            category="license",
            name="LICENSE",
            status=status,
            before=text_old,
            after=text_new,
        )
        if status != "unchanged":
            # Write the new content to the file
            with open(self._root / "LICENSE", "w") as f:
                f.write(text_new)
        return

    def update_funding(self):
        """

        Returns
        -------

        References
        ----------
        https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/displaying-a-sponsor-button-in-your-repository#about-funding-files
        """
        funding = self._meta["funding"]
        path = self._root / ".github" / "FUNDING.yml"
        file_exists = path.exists()

        if file_exists:
            with open(path) as f:
                text_old = f.read()
        else:
            text_old = ""

        if not funding:
            path.unlink(missing_ok=True)
            self._manager.add_summary(
                category="funding", name="FUNDING", status="removed" if file_exists else "disabled"
            )
            return

        if not isinstance(funding, dict):
            raise ValueError(
                f"Funding must be a dictionary, but got {funding}."
            )

        funding = dict()
        for funding_platform, users in funding.items():
            if funding_platform not in [
                "community_bridge",
                "github",
                "issuehunt",
                "ko_fi",
                "liberapay",
                "open_collective",
                "otechie",
                "patreon",
                "tidelift",
                "custom",
            ]:
                raise ValueError(f"Funding platform '{funding_platform}' is not recognized.")
            if funding_platform in ["github", "custom"]:
                if isinstance(users, list):
                    if len(users) > 4:
                        raise ValueError("The maximum number of allowed users is 4.")
                    flow_list = ruamel.yaml.comments.CommentedSeq()
                    flow_list.fa.set_flow_style()
                    flow_list.extend(users)
                    funding[funding_platform] = flow_list
                elif isinstance(users, str):
                    funding[funding_platform] = users
                else:
                    raise ValueError(
                        f"Users of the '{funding_platform}' funding platform must be either "
                        f"a string or a list of strings, but got {users}."
                    )
            else:
                if not isinstance(users, str):
                    raise ValueError(
                        f"User of the '{funding_platform}' funding platform must be a single string, "
                        f"but got {users}."
                    )
                funding[funding_platform] = users

        with open(path, "w") as f:
            ruamel.yaml.YAML().dump(funding, f)

        with open(path) as f:
            text_new = f.read()

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
            category="funding",
            name="FUNDING",
            status=status,
            before=text_old,
            after=text_new,
        )
        return

    def update_health_files(self):
        HealthFileSync(sync_manager=self._manager).update()
        return

    def update_package(self):
        package.sync(self._manager)
        return

    def update_issue_templates(self):
        pass

    def update_discussion_templates(self):
        return

    def _get_absolute_paths(self):
        def recursive(dic, new_dic):
            for key, val in dic.items():
                if isinstance(val, str):
                    new_dic[key] = str(self.path_root / val)
                else:
                    new_dic[key] = recursive(val, dict())
            return new_dic

        return recursive(self.metadata["path"], dict())


def sync(
    path_root: str | Path = ".",
    paths_ext: Optional[Sequence[str | Path]] = None,
    metadata: Optional[dict] = None,
    logger: Optional[Literal["github"]] = None
):
    manager = FileSyncManager(
        path_root=path_root,
        paths_ext=paths_ext,
        metadata=metadata,
        logger=logger
    )
    syncer = FileSync(manager=manager)
    syncer.update()
    return
