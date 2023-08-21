# Standard libraries
from pathlib import Path
from typing import Optional, Sequence, Callable
import json
from functools import partial

# Non-standard libraries
from ruamel.yaml import YAML

from repodynamics.meta.data import _cache, package, project, urls
from repodynamics.meta.manager import MetaManager


class Metadata:
    def __init__(
        self,
        manager: MetaManager,
        repo_fullname: str,
        filepath_cache: Optional[str | Path] = None,
        update_cache: bool = False,
        github_token: Optional[str] = None,
    ):
        self.manager = manager
        self._github_token = github_token
        metadata = self._read(self.manager.path_meta)
        if self.manager.path_extensions:
            alts = [self._read(dirpath_alt) for dirpath_alt in self.manager.path_extensions]
            metadata = self._merge(metadata, alts)
        self._metadata = metadata
        self._metadata["repo"] = repo_fullname
        self._cache = _cache.Cache(
            filepath=filepath_cache,
            expiration_days=self._metadata["config"]["meta"]["api_cache_expiration_days"],
            update=update_cache,
        )
        self.path_out = self.manager.path_meta / ".out"
        return

    def update(self):
        self.fill()
        label_syncer = self.metadata["maintain"].pop("_label_syncer")
        pr_labeler = self.metadata["maintain"].pop("_pr_labeler")
        self.manager.update(
            category="metadata",
            name="labels.yaml",
            path=self.path_out / "labels.yaml",
            new_content=partial(YAML().dump, label_syncer),
        )
        self.manager.update(
            category="metadata",
            name="labels_pr.yaml",
            path=self.path_out / "labels_pr.yaml",
            new_content=partial(YAML().dump, pr_labeler),
        )
        self.manager.update(
            category="metadata",
            name="metadata.json",
            path=self.path_out/"metadata.json",
            new_content=partial(json.dump, self.metadata),
        )
        self.manager.metadata = self.metadata
        return

    @property
    def metadata(self) -> dict:
        return self._metadata

    def fill(self) -> dict:
        project.fill(metadata=self._metadata, cache=self._cache, github_token=self._github_token)
        if self._metadata.get("package"):
            package.fill(metadata=self._metadata, cache=self._cache)
        urls.fill(metadata=self._metadata)
        return self.metadata

    def _read(self, dirpath_meta: str | Path) -> dict:
        """
        Read metadata from the 'meta' directory.

        Parameters
        ----------
        dirpath_meta : str or Path
            Path to the 'meta' directory containing the 'data' subdirectory with metadata files.

        Returns
        -------
        dict
            A dictionary of metadata.
        """
        if not isinstance(dirpath_meta, (str, Path)):
            raise TypeError(
                f"Argument 'dirpath_meta' must be a string or a `pathlib.Path` object, "
                f"but got {type(dirpath_meta)}."
            )
        path = (Path(dirpath_meta) / "data").resolve()
        metadata_files = list(path.glob("*.yaml"))
        if not metadata_files:
            self.manager.logger.attention(f"No metadata files found in '{path}'.")
        path_main = path / "main.yaml"
        if path_main in metadata_files:
            metadata_files.remove(path_main)
            metadata = dict(YAML(typ="safe").load(path_main))
        else:
            metadata = dict()
        for path_file in metadata_files:
            section = path_file.stem
            if section in metadata:
                raise ValueError(
                    f"Metadata section '{section}' already exists in 'main.yaml', "
                    f"but '{section}.yaml' also exists."
                )
            metadata[section] = dict(YAML(typ="safe").load(path_file))
        return metadata

    @staticmethod
    def _merge(metadata: dict, alts: list[dict]) -> dict:
        base = alts.pop(-1)
        alts.insert(0, metadata)
        for alt in reversed(alts):
            base = base | alt
        return base
