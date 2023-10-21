from typing import NamedTuple
from pathlib import Path
from enum import Enum


class EventType(Enum):
    PUSH_MAIN = "push_main"
    PUSH_RELEASE = "push_release"
    PUSH_DEV = "push_dev"
    PUSH_OTHER = "push_other"
    PULL_MAIN = "pull_main"
    PULL_RELEASE = "pull_release"
    PULL_DEV = "pull_dev"
    PULL_OTHER = "pull_other"
    SCHEDULE = "schedule"
    DISPATCH = "dispatch"


class CommitGroup(Enum):
    PRIMARY_ACTION = 0
    PRIMARY_CUSTOM = 1
    SECONDARY_ACTION = 2
    SECONDARY_CUSTOM = 3
    NON_CONV = 4


class PrimaryActionCommit(Enum):
    PACKAGE_MAJOR = "package_major"
    PACKAGE_MINOR = "package_minor"
    PACKAGE_PATCH = "package_patch"
    PACKAGE_POST = "package_post"
    WEBSITE = "website"
    META = "meta"


class SecondaryCommitAction(Enum):
    META_SYNC = 0
    REVERT = 1
    HOOK_FIX = 2


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
    filename: str
    rel_path: str
    path: Path
    alt_paths: list[Path] | None = None
    is_dir: bool = False


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
            self.scope = []
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
            raise TypeError(
                f"Argument 'footer' must be a dict, but got {type(footer)}: {footer}"
            )
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


class Commit(NamedTuple):
    hash: str
    author: str
    date: str
    files: list[str]
    msg: str
    typ: CommitGroup = CommitGroup.NON_CONV
    conv_msg: CommitMsg | None = None
    action: PrimaryActionCommit | SecondaryCommitAction | None = None


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

