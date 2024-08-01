from typing import NamedTuple as _NamedTuple
from pathlib import Path as _Path
from enum import Enum as _Enum

import conventional_commits as _conventional_commits
from versionman import PEP440SemVer as _PEP440SemVer


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









class EventType(_Enum):
    PUSH_MAIN = "push_main"
    PUSH_RELEASE = "push_release"
    PUSH_DEV = "push_dev"
    PUSH_CI_PULL = "push_ci_pull"
    PUSH_OTHER = "push_other"
    PULL_MAIN = "pull_main"
    PULL_RELEASE = "pull_release"
    PULL_DEV = "pull_dev"
    PULL_OTHER = "pull_other"
    SCHEDULE = "schedule"
    DISPATCH = "dispatch"


class BranchType(_Enum):
    MAIN = "main"
    RELEASE = "release"
    PRERELEASE = "pre-release"
    DEV = "development"
    AUTOUPDATE = "auto-update"
    OTHER = "other"


class Branch(_NamedTuple):
    type: BranchType
    name: str
    prefix: str | None = None
    suffix: str | int | _PEP440SemVer | tuple[int, str] | tuple[int, str, int] | None = None


class CommitGroup(_Enum):
    PRIMARY_ACTION = "primary_action"
    PRIMARY_CUSTOM = "primary_custom"
    SECONDARY_ACTION = "secondary_action"
    SECONDARY_CUSTOM = "secondary_custom"
    NON_CONV = "non_conventional"


class PrimaryActionCommitType(_Enum):
    RELEASE_MAJOR = "release_major"
    RELEASE_MINOR = "release_minor"
    RELEASE_PATCH = "release_patch"
    RELEASE_POST = "release_post"
    WEBSITE = "website"
    META = "meta"


class SecondaryActionCommitType(_Enum):
    AUTO_UPDATE = "auto-update"
    META_SYNC = "meta_sync"
    REVERT = "revert"
    HOOK_FIX = "hook_fix"


class GroupedCommit:
    def __init__(self, group: CommitGroup):
        self._group = group
        return

    @property
    def group(self) -> CommitGroup:
        return self._group


class PrimaryActionCommit(GroupedCommit):
    def __init__(
        self,
        action: PrimaryActionCommitType,
        conv_type: str,
    ):
        super().__init__(CommitGroup.PRIMARY_ACTION)
        self._action = action
        self._conv_type = conv_type
        return

    @property
    def action(self) -> PrimaryActionCommitType:
        return self._action

    @property
    def conv_type(self) -> str:
        return self._conv_type

    def __repr__(self):
        return f"PrimaryActionCommit(action={self.action}, conv_type={self.conv_type})"


class PrimaryCustomCommit(GroupedCommit):
    def __init__(self, group_id: str, conv_type: str):
        super().__init__(CommitGroup.PRIMARY_CUSTOM)
        self._conv_type = conv_type
        self._id = group_id
        return

    @property
    def id(self) -> str:
        return self._id

    @property
    def conv_type(self) -> str:
        return self._conv_type

    def __repr__(self):
        return f"PrimaryCustomCommit(id={self.id}, conv_type={self.conv_type})"


class SecondaryActionCommit(GroupedCommit):
    def __init__(self, action: SecondaryActionCommitType, conv_type: str):
        super().__init__(CommitGroup.SECONDARY_ACTION)
        self._action = action
        self._conv_type = conv_type
        return

    @property
    def action(self) -> SecondaryActionCommitType:
        return self._action

    @property
    def conv_type(self) -> str:
        return self._conv_type

    def __repr__(self):
        return f"SecondaryActionCommit(action={self.action}, conv_type={self.conv_type})"


class SecondaryCustomCommit(GroupedCommit):
    def __init__(self, conv_type: str, changelog_id: str, changelog_section_id: str):
        super().__init__(CommitGroup.SECONDARY_CUSTOM)
        self._conv_type = conv_type
        self._changelog_id = changelog_id
        self._changelog_section_id = changelog_section_id
        return

    @property
    def conv_type(self) -> str:
        return self._conv_type

    @property
    def changelog_id(self) -> str:
        return self._changelog_id

    @property
    def changelog_section_id(self) -> str:
        return self._changelog_section_id

    def __repr__(self):
        return (
            f"SecondaryCustomCommit("
            f"conv_type={self.conv_type}, changelog_id={self.changelog_id}, "
            f"changelog_section_id={self.changelog_section_id})"
        )


class NonConventionalCommit(GroupedCommit):
    def __init__(self):
        super().__init__(CommitGroup.NON_CONV)
        return

    def __repr__(self):
        return "NonConventionalCommit()"


class Commit(_NamedTuple):
    hash: str
    author: str
    date: str
    files: list[str]
    msg: str | _conventional_commits.message.ConventionalCommitMessage
    group_data: (
        PrimaryActionCommit
        | PrimaryCustomCommit
        | SecondaryActionCommit
        | SecondaryCustomCommit
        | NonConventionalCommit
    )


class Issue(_NamedTuple):
    group_data: PrimaryActionCommit | PrimaryCustomCommit
    type_labels: list[str]
    form: dict


class InitCheckAction(_Enum):
    NONE = "none"
    FAIL = "fail"
    REPORT = "report"
    PULL = "pull"
    COMMIT = "commit"
    AMEND = "amend"


class IssueStatus(_Enum):
    TRIAGE = "triage"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"
    INVALID = "invalid"
    PLANNING = "planning"
    REQUIREMENT_ANALYSIS = "requirement_analysis"
    DESIGN = "design"
    IMPLEMENTATION = "implementation"
    TESTING = "testing"
    DEPLOY_ALPHA = "deploy_alpha"
    DEPLOY_BETA = "deploy_beta"
    DEPLOY_RC = "deploy_rc"
    DEPLOY_FINAL = "deploy_final"


class LabelType(_Enum):
    VERSION = "version"
    BRANCH = "branch"
    TYPE = "primary_type"
    SUBTYPE = "subtype"
    STATUS = "status"
    CUSTOM_GROUP = "custom_group"
    SINGLE = "single"
    UNKNOWN = "unknown"


class Label(_NamedTuple):
    category: LabelType
    name: str
    prefix: str = ""
    type: PrimaryActionCommitType | IssueStatus | str = None

    @property
    def suffix(self) -> str:
        return self.name.removeprefix(self.prefix)


class Emoji:
    """Enum of emojis used in the bot."""

    _db = {
        "PASS": "✅",
        "SKIP": "❎",
        "FAIL": "❌",
        "WARNING": "⚠️",
        "PLAY": "▶️",
    }

    def __init__(self):
        for name, emoji in self._db.items():
            setattr(self, name, emoji)
        return

    def __getitem__(self, item: str):
        return self._db[item.upper()]


Emoji = Emoji()
