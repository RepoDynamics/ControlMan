# Standard libraries
from pathlib import Path
from typing import Optional, Sequence

# Non-standard libraries
from ruamel.yaml import YAML

from repodynamics.metadata import _cache, project, package, urls


class Metadata:
    def __init__(
        self,
        path_root: str | Path = ".",
        paths_ext: Optional[Sequence[str | Path]] = None,
        filepath_cache: Optional[str | Path] = None,
        update_cache: bool = False,
        github_token: Optional[str] = None,
    ):
        self.github_token = github_token
        metadata = self._read(Path(path_root) / "meta")
        if paths_ext:
            alts = [self._read(dirpath_alt) for dirpath_alt in paths_ext]
            metadata = self._merge(metadata, alts)
        self.metadata = metadata
        self.cache = _cache.Cache(
            filepath=filepath_cache,
            expiration_days=self.metadata["config"]["meta"]["api_cache_expiration_days"],
            update=update_cache,
        )
        return

    def fill(self):
        project.fill(metadata=self.metadata, cache=self.cache, github_token=self.github_token)
        if self.metadata.get("package"):
            package.fill(metadata=self.metadata, cache=self.cache)
        urls.fill(metadata=self.metadata)
        return

    @staticmethod
    def _read(dirpath_meta: str | Path) -> dict:
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
            raise ValueError(f"No metadata files found in '{path}'.")
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
    def _merge(metadata: dict, alts: Sequence[dict]) -> dict:
        base = alts.pop(-1)
        alts.insert(0, metadata)
        for alt in reversed(alts):
            base = base | alt
        return base


def fill(
    path_root: str | Path = ".",
    paths_ext: Optional[Sequence[str | Path]] = None,
    filepath_cache: Optional[str | Path] = None,
    update_cache: bool = False,
    github_token: Optional[str] = None,
) -> dict:
    meta = Metadata(
        path_root=path_root,
        paths_ext=paths_ext,
        filepath_cache=filepath_cache,
        update_cache=update_cache,
        github_token=github_token,
    )
    meta.fill()
    return meta.metadata
