from typing import Literal, Optional, Sequence, Callable
from pathlib import Path

from repodynamics.logger import Logger
from repodynamics.meta.manager import MetaManager
from repodynamics.meta.data.metadata import Metadata
from repodynamics.meta.files.sync import FileSync


def update(
    repo_fullname: str,
    path_root: str | Path = ".",
    path_extensions: Optional[Sequence[str | Path]] = None,
    filepath_cache: Optional[str | Path] = None,
    update_cache: bool = False,
    github_token: Optional[str] = None,
    logger: Logger = None
):
    manager = MetaManager(
        path_root=path_root,
        paths_ext=path_extensions,
        logger=logger
    )
    metadata = Metadata(
        manager=manager,
        repo_fullname=repo_fullname,
        filepath_cache=filepath_cache,
        update_cache=update_cache,
        github_token=github_token
    )
    metadata.update()
    file_sync = FileSync(manager=manager)
    file_sync.update()
    return manager._summary
