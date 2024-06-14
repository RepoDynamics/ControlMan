"""ControlMan

The control center manager for RepoDynamics template repositories.
"""


from pathlib import Path as _Path

from loggerman import logger as _logger
import pyserials as _pyserials
from versionman import PEP440SemVer as _PEP440SemVer

from controlman import exception, datatype, content, path, protocol, _util
from controlman.content_manager import ControlCenterContentManager
from controlman.center_manager import ControlCenterManager
from controlman.files.generator.forms import pre_process_existence

from controlman.data import validator as _validator


def initialize_manager(
    git_manager: protocol.Git,
    github_token: str | None = None,
    content_manager: ControlCenterContentManager | dict | None = None,
    future_versions: dict[str, str | _PEP440SemVer] | None = None,
    log_section_title: str = "Initialize Control Center Manager",
) -> ControlCenterManager:
    if log_section_title:
        _logger.section(log_section_title, group=True)
    manager = ControlCenterManager(
        git_manager=git_manager,
        github_token=github_token,
        content_manager=content_manager,
        future_versions=future_versions,
    )
    if log_section_title:
        _logger.section_end()
    return manager


def read_from_json_file(
    path_repo: str | _Path,
    log_section_title: str = "Read Control Center Contents From JSON File",
) -> ControlCenterContentManager | None:
    if log_section_title:
        _logger.section(log_section_title, group=True)
    data_dict = _util.file.read_datafile(
        path_repo=path_repo, path_data=path.FILE_METADATA, relpath_schema="metadata"
    )
    if not data_dict:
        if log_section_title:
            _logger.section_end()
        return
    meta_manager = ControlCenterContentManager(data=data_dict)
    _validator.validate(content_manager=meta_manager)
    if log_section_title:
        _logger.section_end()
    return meta_manager


def read_from_json_file_at_commit(
    commit_hash: str,
    git_manager: protocol.Git,
    log_section_title: str = "Read Control Center Contents From JSON File at Commit",
) -> ControlCenterContentManager | None:
    if log_section_title:
        _logger.section(log_section_title, group=True)
    data_str = git_manager.file_at_hash(
        commit_hash=commit_hash,
        path=path.FILE_METADATA,
    )
    output = read_from_json_string(data=data_str, log_section_title="") if data_str else None
    return output


def read_from_json_string(
    data: str,
    log_section_title: str = "Read Control Center Contents From JSON String",
) -> ControlCenterContentManager:
    if log_section_title:
        _logger.section(log_section_title, group=True)
    metadata = _pyserials.read.json_from_string(data=data)
    meta_manager = ControlCenterContentManager(data=metadata)
    _validator.validate(content_manager=meta_manager)
    if log_section_title:
        _logger.section_end()
    return meta_manager
