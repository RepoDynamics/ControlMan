from typing import NamedTuple
from pathlib import Path
from enum import Enum
from repodynamics.version import PEP440SemVer


class EventType(Enum):
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


class BranchType(Enum):
    DEFAULT = "main"
    RELEASE = "release"
    PRE_RELEASE = "pre_release"
    DEV = "dev"
    CI_PULL = "ci_pull"
    OTHER = "other"


class Branch(NamedTuple):
    type: BranchType
    name: str
    prefix: str | None = None
    suffix: str | int | PEP440SemVer | tuple[int, str] | None = None


class RepoFileType(Enum):
    SUPERMETA = "SuperMeta Content"
    WORKFLOW = "Workflows"
    META = "Meta Content"
    DYNAMIC = "Dynamic Content"
    PACKAGE = "Package Files"
    TEST = "Test-Suite Files"
    WEBSITE = "Website Files"
    README = "README Files"
    OTHER = "Other Files"


class DynamicFileType(Enum):
    METADATA = "Metadata Files"
    LICENSE = "License Files"
    PACKAGE = "Package Files"
    CONFIG = "Configuration Files"
    WEBSITE = "Website Files"
    README = "ReadMe Files"
    HEALTH = "Health Files"
    FORM = "Forms"


class DynamicFile(NamedTuple):
    id: str
    category: DynamicFileType
    rel_path: str
    path: Path
    alt_paths: list[Path] | None = None
    is_dir: bool = False

    @property
    def filename(self) -> str:
        return self.path.name


class _FileStatus(NamedTuple):
    title: str
    emoji: str


class FileChangeType(Enum):
    REMOVED = _FileStatus("Removed", "🔴")
    MODIFIED = _FileStatus("Modified", "🟣")
    BROKEN = _FileStatus("Broken", "🟠")
    CREATED = _FileStatus("Created", "🟢")
    UNMERGED = _FileStatus("Unmerged", "⚪️")
    UNKNOWN = _FileStatus("Unknown", "⚫")


class DynamicFileChangeTypeContent(NamedTuple):
    title: str
    emoji: str


class DynamicFileChangeType(Enum):
    REMOVED = DynamicFileChangeTypeContent("Removed", "🔴")
    MODIFIED = DynamicFileChangeTypeContent("Modified", "🟣")
    MOVED_MODIFIED = DynamicFileChangeTypeContent("Moved & Modified", "🟠")
    MOVED_REMOVED = DynamicFileChangeTypeContent("Moved & Removed", "🟠")
    MOVED = DynamicFileChangeTypeContent("Moved", "🟡")
    CREATED = DynamicFileChangeTypeContent("Created", "🟢")
    UNCHANGED = DynamicFileChangeTypeContent("Unchanged", "⚪️")
    DISABLED = DynamicFileChangeTypeContent("Disabled", "⚫")


class Diff(NamedTuple):
    status: DynamicFileChangeType
    after: str
    before: str = ""
    path_before: Path | None = None


class CommitMsg:
    def __init__(
        self,
        typ: str,
        title: str,
        body: str | None = None,
        scope: str | tuple[str] | list[str] | None = None,
        footer: dict[str, str | list[str]] | None = None,
    ):
        for arg, arg_name in ((typ, "typ"), (title, "title")):
            if not isinstance(arg, str):
                raise TypeError(f"Argument '{arg_name}' must be a string, but got {type(arg)}: {arg}")
            if "\n" in arg:
                raise ValueError(f'Argument `{arg_name}` must not contain a newline, but got: """{arg}"""')
            if ":" in arg:
                raise ValueError(f'Argument `{arg_name}` must not contain a colon, but got: """{arg}"""')
        self.type = typ
        self.title = title
        if isinstance(body, str):
            self.body = body.strip()
        elif body is None:
            self.body = ""
        else:
            raise TypeError(f"Argument 'body' must be a string or None, but got {type(body)}: {body}")
        if scope is None:
            scope = []
        if isinstance(scope, (list, tuple)):
            self.scope = [str(s) for s in scope]
        elif isinstance(scope, str):
            self.scope = [scope]
        else:
            raise TypeError(
                f"Argument 'scope' must be a string or list/tuple of strings, but got {type(scope)}: {scope}"
            )
        if footer is None:
            self.footer = {}
        elif isinstance(footer, dict):
            self.footer = footer
        else:
            raise TypeError(f"Argument 'footer' must be a dict, but got {type(footer)}: {footer}")
        return

    @property
    def summary(self):
        scope = f"({', '.join(self.scope)})" if self.scope else ""
        return f"{self.type}{scope}: {self.title}"

    def __str__(self):
        commit = self.summary
        if self.body:
            commit += f"\n\n{self.body}"
        if self.footer:
            commit += "\n\n-----------\n\n"
            for key, values in self.footer.items():
                if isinstance(values, str):
                    values = [values]
                for value in values:
                    commit += f"{key}: {value}\n"
        return commit.strip() + "\n"


class CommitGroup(Enum):
    PRIMARY_ACTION = "primary_action"
    PRIMARY_CUSTOM = "primary_custom"
    SECONDARY_ACTION = "secondary_action"
    SECONDARY_CUSTOM = "secondary_custom"
    NON_CONV = "non_conventional"


class PrimaryActionCommitType(Enum):
    RELEASE_MAJOR = "release_major"
    RELEASE_MINOR = "release_minor"
    RELEASE_PATCH = "release_patch"
    RELEASE_POST = "release_post"
    WEBSITE = "website"
    META = "meta"


class SecondaryActionCommitType(Enum):
    META_SYNC = "meta_sync"
    REVERT = "revert"
    HOOK_FIX = "hook_fix"


class GroupedCommit:
    def __init__(self, group: CommitGroup):
        self._group = group
        return

    @property
    def group(self):
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


class Commit(NamedTuple):
    hash: str
    author: str
    date: str
    files: list[str]
    msg: str | CommitMsg
    group_data: (
        PrimaryActionCommit
        | PrimaryCustomCommit
        | SecondaryActionCommit
        | SecondaryCustomCommit
        | NonConventionalCommit
    )


class Issue(NamedTuple):
    group_data: PrimaryActionCommit | PrimaryCustomCommit
    type_labels: list[str]
    form: dict


class WorkflowTriggeringAction(Enum):
    """
    Triggering actions of events that can trigger a workflow.
    Each action is only valid for certain events. For example:

    created: issue_comment
    edited: issue_comment
    deleted: issue_comment
    opened: issues, pull_request
    labeled: issues, pull_request
    reopened: issues, pull_request
    synchronize: pull_request
    closed: issues, pull_request
    ready_for_review: pull_request
    """

    CREATED = "created"
    EDITED = "edited"
    DELETED = "deleted"
    OPENED = "opened"
    CLOSED = "closed"
    LABELED = "labeled"
    REOPENED = "reopened"
    SYNCHRONIZE = "synchronize"
    READY_FOR_REVIEW = "ready_for_review"


class InitCheckAction(Enum):
    NONE = "none"
    FAIL = "fail"
    REPORT = "report"
    PULL = "pull"
    COMMIT = "commit"
    AMEND = "amend"


class WorkflowDispatchInput(NamedTuple):
    meta: InitCheckAction
    hooks: InitCheckAction
    package_build: bool
    package_lint: bool
    package_test: bool
    website_build: bool
    website_announcement: str
    website_announcement_msg: str


class IssueStatus(Enum):
    TRIAGE = "triage"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"
    INVALID = "invalid"
    QUEUED = "queued"
    DISCUSS = "discuss"
    NEED_VOLUNTEER = "need_volunteer"
    IN_DEV = "in_dev"
    IN_REVIEW = "in_review"
    ALPHA = "alpha"
    BETA = "beta"
    RC = "rc"
    FINAL = "final"


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
