import json
from pathlib import Path as _Path

from actionman.logger import Logger as _Logger

from controlman.content.manager import ControlCenterContent, ControlCenterContentManager

from controlman import _file_io as _file_io
from controlman.control.data import validator as _validator
from controlman._git import Git as _Git
from controlman._path import RelativePath as _RelativePath


def from_json_file(
    path_repo: str | _Path,
    logger: _Logger,
    log_section_title: str = "Read Control Center Settings",
) -> ControlCenterContentManager | None:
    logger.section(log_section_title, group=True)
    path_json = _Path(path_repo).resolve() / _RelativePath.file_metadata
    data = _file_io.read_datafile(path_data=path_json)  # TODO: add logging and error handling
    if not data:
        logger.section_end()
        return
    meta_manager = ControlCenterContentManager(data=data)
    _validator.validate(content_manager=meta_manager, logger=logger)
    logger.section_end()
    return meta_manager


def from_json_file_at_commit(
    commit_hash: str,
    git: _Git,
    logger: _Logger,
) -> ControlCenterContentManager:
    content = git.file_at_hash(
        commit_hash=commit_hash,
        path=_RelativePath.file_metadata,
        raise_missing=True,
    )
    return from_json_string(content=content, logger=logger) if content else None


def from_json_string(content: str, logger: _Logger | None = None) -> ControlCenterContentManager:
    logger = logger or _Logger()
    metadata = json.loads(content)
    meta_manager = ControlCenterContentManager(data=metadata)
    _validator.validate(content_manager=meta_manager, logger=logger)
    return meta_manager
