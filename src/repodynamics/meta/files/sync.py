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
        self.logger = self._manager.logger
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
        self.logger.section("Update file: LICENSE")
        license_id = self._meta.get("license_id")
        if license_id:
            self.logger.debug(f"license_id: {license_id}")
            new_content = self._manager.template(
                category="license", name=license_id.lower().removesuffix("+")
            )
        else:
            self.logger.attention("No license_id found in metadata.")
            new_content = None
        self._manager.update(
            category="license",
            name="LICENSE",
            path=self._root / "LICENSE",
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
        self.logger.section("Update file: FUNDING.yml")
        path = self._root / ".github" / "FUNDING.yml"
        funding = self._meta.get("funding")
        if not funding:
            self._manager.update(
                category="config",
                name="FUNDING",
                path=path,
            )
            return
        yaml_output = dict()
        for funding_platform, users in funding.items():
            if funding_platform in ["github", "custom"]:
                if isinstance(users, list):
                    flow_list = ruamel.yaml.comments.CommentedSeq()
                    flow_list.fa.set_flow_style()
                    flow_list.extend(users)
                    yaml_output[funding_platform] = flow_list
                elif isinstance(users, str):
                    yaml_output[funding_platform] = users
                else:
                    self._manager.logger.error(
                        f"Users of the '{funding_platform}' funding platform must be either "
                        f"a string or a list of strings, but got {users}."
                    )
            else:
                if not isinstance(users, str):
                    self._manager.logger.error(
                        f"User of the '{funding_platform}' funding platform must be a single string, "
                        f"but got {users}."
                    )
                yaml_output[funding_platform] = users
        self._manager.update(
            category="config",
            name="FUNDING",
            path=path,
            new_content=partial(ruamel.yaml.YAML().dump, yaml_output)
        )
        return

    def update_health_files(self):
        HealthFileSync(sync_manager=self._manager).update()
        return

    def update_package(self):
        package.PackageFileSync(sync_manager=self._manager).update()
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
