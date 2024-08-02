from typing import NamedTuple as _NamedTuple
from enum import Enum as _Enum


class DynamicFileType(_Enum):
    METADATA = "Metadata Files"
    LICENSE = "License Files"
    PACKAGE = "Package Files"
    CONFIG = "Configuration Files"
    WEBSITE = "Website Files"
    README = "ReadMe Files"
    HEALTH = "Health Files"
    FORM = "Forms"


class DynamicFile_(_Enum):
    METADATA = (DynamicFileType.METADATA, "Metadata files")
    GITHUB_FUNDING = (DynamicFileType.CONFIG, "GitHub funding options configurations")
    GITHUB_CITATION = (DynamicFileType.HEALTH, "GitHub citation configurations")
    GITHUB_CODEOWNERS = (DynamicFileType.CONFIG, "GitHub codeowners configurations")
    GITHUB_ISSUES_CONFIG = (DynamicFileType.CONFIG, "GitHub Issues template chooser configurations")
    GITHUB_ISSUE_FORM = (DynamicFileType.FORM, "GitHub Issue forms")
    GITHUB_DISCUSSION_FORM = (DynamicFileType.FORM, "GitHub Discussion forms")
    GITHUB_PULL_TEMPLATE = (DynamicFileType.FORM, "GitHub Pull Request templates")
    GITHUB_README = (DynamicFileType.README, "GitHub ReadMe files")
    GITHUB_HEALTH = (DynamicFileType.HEALTH, "GitHub Health files")
    GIT_IGNORE = (DynamicFileType.CONFIG, "Git ignore file")
    GIT_ATTRIBUTES = (DynamicFileType.CONFIG, "Git attributes file")
    WEB_ENV_CONDA = (DynamicFileType.CONFIG, "Website build environment file (conda)")
    WEB_ENV_PIP = (DynamicFileType.CONFIG, "Website build environment file (pip)")
    TOOL_ENV_CONDA = (DynamicFileType.CONFIG, "Tool build environment file (conda)")
    TOOL_ENV_PIP = (DynamicFileType.CONFIG, "Tool build environment file (pip)")
    TOOL_CONFIG = (DynamicFileType.CONFIG, "Tool configuration file")
    PKG_TYPING_MARKER = (DynamicFileType.PACKAGE, "Package typing marker file")
    PKG_ENV_CONDA = (DynamicFileType.PACKAGE, "Package environment file (conda)")
    PKG_ENV_PIP = (DynamicFileType.PACKAGE, "Package environment file (pip)")
    PKG_MANIFEST = (DynamicFileType.PACKAGE, "Package manifest file")
    PKG_PYPROJECT = (DynamicFileType.PACKAGE, "Package pyproject file")
    PKG_SOURCE = (DynamicFileType.PACKAGE, "Package source files")
    PKG_README = (DynamicFileType.README, "Package ReadMe files")
    TEST_TYPING_MARKER = (DynamicFileType.PACKAGE, "Test suite typing marker file")
    TEST_ENV_CONDA = (DynamicFileType.PACKAGE, "Test suite environment file (conda)")
    TEST_ENV_PIP = (DynamicFileType.PACKAGE, "Test suite environment file (pip)")
    TEST_MANIFEST = (DynamicFileType.PACKAGE, "Test suite manifest file")
    TEST_PYPROJECT = (DynamicFileType.PACKAGE, "Test suite pyproject file")
    TEST_SOURCE = (DynamicFileType.PACKAGE, "Test suite source file")
    LICENSE = (DynamicFileType.LICENSE, "License file")


class DynamicDirType(_Enum):
    CONTROL = "Control Center"
    LOCAL = "Local"
    MEDIA = "Media"
    WEB_ROOT = "Website Root"
    WEB_SRC = "Website Source"
    PKG_ROOT = "Package Root"
    PKG_SRC = "Package Source"
    TEST_ROOT = "Test Suite Root"
    TEST_SRC = "Test Suite Source"


class GeneratedFile(_NamedTuple):
    type: DynamicFile_
    subtype: str | None = None
    content: str | None = None
    path: str | None = None
    path_before: str | None = None


class DynamicFileChangeTypeContent(_NamedTuple):
    title: str
    emoji: str


class DynamicFileChangeType(_Enum):
    REMOVED = DynamicFileChangeTypeContent("Removed", "🔴")
    MODIFIED = DynamicFileChangeTypeContent("Modified", "🟣")
    MOVED_MODIFIED = DynamicFileChangeTypeContent("Moved & Modified", "🟠")
    MOVED = DynamicFileChangeTypeContent("Moved", "🟡")
    CREATED = DynamicFileChangeTypeContent("Created", "🟢")
    UNCHANGED = DynamicFileChangeTypeContent("Unchanged", "⚪️")
    DISABLED = DynamicFileChangeTypeContent("Disabled", "⚫")


class DynamicDir(_NamedTuple):
    type: DynamicDirType
    path: str | None = None
    path_before: str | None = None
    change: DynamicFileChangeType | None = None
