# Standard libraries
from pathlib import Path
from typing import Optional, Sequence, Callable
import json
from functools import partial

# Non-standard libraries
from ruamel.yaml import YAML
import jsonschema
import traceback


from repodynamics.meta.data import _cache, package, project
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
        self.logger = manager.logger
        self._github_token = github_token
        self.logger.section("Read metadata from main repository")
        metadata = self._read(self.manager.path_meta)
        alts = []
        if self.manager.path_extensions:
            for dirpath_alt in self.manager.path_extensions:
                self.logger.section(f"Read metadata from extension repository")
                alts.append(self._read(dirpath_alt))
        metadata = self._merge(metadata, alts)
        self._metadata = metadata
        self._metadata["repo"] = repo_fullname
        self._cache = _cache.Cache(
            filepath=filepath_cache,
            expiration_days=self._metadata.get("api_cache_expiration_days") or 10,
            update=update_cache,
            logger=self.logger,
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
        project.fill(
            metadata=self._metadata, cache=self._cache, github_token=self._github_token, logger=self.logger
        )
        if self._metadata.get("package"):
            package.Python(metadata=self._metadata, cache=self._cache, logger=self.logger).fill()
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
            self.manager.logger.error(
                f"Argument 'dirpath_meta' must be a string or a `pathlib.Path` object, "
                f"but got '{dirpath_meta}' with type '{type(dirpath_meta)}'."
            )
        path = (Path(dirpath_meta) / "data").resolve()
        metadata_files = list(path.glob("*.yaml"))
        metadata = dict()
        if not metadata_files:
            self.manager.logger.attention(f"No metadata files found in '{path}'.")
            return metadata
        for path_file in metadata_files:
            self.logger.info(f"Read '{path_file.name}':")
            section = dict(YAML(typ="safe").load(path_file))
            self.logger.debug(json.dumps(section, indent=3))
            for new_key in section:
                if new_key in metadata:
                    self.logger.error(
                        f"Found a duplicate of metadata key '{new_key}' in '{path_file.name}'."
                    )
            metadata |= section
        return metadata

    def _merge(self, metadata: dict, alts: list[dict]) -> dict:
        self.logger.section("Merge metadata from main and extension repositories")
        if alts:
            base = alts.pop(-1)
            alts.insert(0, metadata)
            for alt in reversed(alts):
                base = base | alt
        else:
            base = metadata
        try:
            jsonschema.validate(instance=base, schema=self.manager.schema)
        except jsonschema.exceptions.ValidationError as e:
            self.logger.debug(traceback.format_exc())
            self.logger.error(f"Invalid metadata schema: {e.message}.")
        return base
