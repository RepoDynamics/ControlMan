# Standard libraries
from pathlib import Path
from typing import Literal, Optional, Sequence
from functools import partial

# Non-standard libraries
import ruamel.yaml

from repodynamics.meta.manager import MetaManager
from repodynamics.meta.files.health_files import HealthFileSync
from repodynamics.meta.files import package


class FileSync:
    def __init__(self, manager: MetaManager):
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
        path = self._root / "LICENSE"
        license = self._meta["copyright"]["license"]
        new_content = self._manager.template(
            category="license", name=license['id'].lower().removesuffix("+")
        ) if license else None
        self._manager.update(
            category="license",
            name="LICENSE",
            path=path,
            new_content=new_content
        )
        return

    def update_funding(self):
        """

        Returns
        -------

        References
        ----------
        https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/displaying-a-sponsor-button-in-your-repository#about-funding-files
        """
        path = self._root / ".github" / "FUNDING.yml"
        funding = self._meta["funding"]
        if not funding:
            self._manager.update(
                category="config",
                name="FUNDING",
                path=path,
            )
            return
        if not isinstance(funding, dict):
            logger.error(f"Funding must be a dictionary, but got {funding}.")
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
                logger.error(f"Funding platform '{funding_platform}' is not recognized.")
            if funding_platform in ["github", "custom"]:
                if isinstance(users, list):
                    if len(users) > 4:
                        logger.error("The maximum number of allowed users is 4.")
                    flow_list = ruamel.yaml.comments.CommentedSeq()
                    flow_list.fa.set_flow_style()
                    flow_list.extend(users)
                    funding[funding_platform] = flow_list
                elif isinstance(users, str):
                    funding[funding_platform] = users
                else:
                    self._logger.error(
                        f"Users of the '{funding_platform}' funding platform must be either "
                        f"a string or a list of strings, but got {users}."
                    )
            else:
                if not isinstance(users, str):
                    self._logger.error(
                        f"User of the '{funding_platform}' funding platform must be a single string, "
                        f"but got {users}."
                    )
                funding[funding_platform] = users
        self._manager.update(
            category="config",
            name="FUNDING",
            path=path,
            new_content=partial(ruamel.yaml.YAML().dump, funding)
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
    manager = MetaManager(
        path_root=path_root,
        paths_ext=paths_ext,
        metadata=metadata,
        logger=logger
    )
    syncer = FileSync(manager=manager)
    syncer.update()
    return
