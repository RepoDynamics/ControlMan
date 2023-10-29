from __future__ import annotations

from typing import Literal
from packaging.version import Version


class PEP440SemVer:
    def __init__(self, version: str):
        self._version_input = version
        self._version = Version(version)
        if len(self._version.release) != 3:
            raise ValueError(f"Invalid version: {version}")
        if self._version.local:
            raise ValueError(f"Invalid version: {version}")
        return

    @property
    def base(self) -> str:
        """The base version string."""
        return self._version.base_version

    @property
    def epoch(self) -> int:
        """The epoch of the version. If unspecified, this is 0."""
        return self._version.epoch

    @property
    def release(self) -> tuple[int, int, int]:
        """The release segment of the version."""
        return self._version.release

    @property
    def pre(self) -> tuple[Literal["a", "b", "rc"], int] | None:
        """The pre-release segment of the version."""
        return self._version.pre

    @property
    def post(self) -> int | None:
        """The post segment of the version."""
        return self._version.post

    @property
    def dev(self) -> int | None:
        """The dev segment of the version."""
        return self._version.dev

    @property
    def major(self) -> int:
        """The major number of the release segment."""
        return self.release[0]

    @property
    def minor(self) -> int:
        """The minor number of the release segment."""
        return self.release[1]

    @property
    def patch(self) -> int:
        """The patch number of the release segment."""
        return self.release[2]

    @property
    def input(self) -> str:
        """The input string used to create this object."""
        return self._version_input

    @property
    def release_type(self) -> Literal["final", "pre", "post", "dev"]:
        if self.dev is not None:
            return "dev"
        if self.post is not None:
            return "post"
        if self.pre:
            return "pre"
        return "final"

    @property
    def is_final_like(self) -> bool:
        """Whether the version is final or post-final."""
        return not (self.dev is not None or self.pre)

    @property
    def next_major(self) -> PEP440SemVer:
        """The next major version."""
        return PEP440SemVer(f"{self.major + 1}.0.0")

    @property
    def next_minor(self) -> PEP440SemVer:
        """The next minor version."""
        return PEP440SemVer(f"{self.major}.{self.minor + 1}.0")

    @property
    def next_patch(self) -> PEP440SemVer:
        """The next patch version."""
        return PEP440SemVer(f"{self.major}.{self.minor}.{self.patch + 1}")

    @property
    def next_post(self) -> PEP440SemVer:
        """The next post version."""
        if self.dev is not None:
            raise ValueError("Cannot increment post version of dev version")
        base = self.base
        if self.pre:
            base += f".{self.pre[0]}{self.pre[1]}"
        if self.post is None:
            return PEP440SemVer(f"{base}.post0")
        return PEP440SemVer(f"{base}.post{self.post + 1}")

    def __str__(self):
        return str(self._version)

    def __repr__(self):
        return f'PEP440SemVer("{self.input}")'

    def __hash__(self):
        return hash(self._version)

    def __lt__(self, other: str | Version | "PEP440SemVer"):
        if isinstance(other, str):
            return self._version.__lt__(Version(other))
        if isinstance(other, Version):
            return self._version.__lt__(other)
        if isinstance(other, PEP440SemVer):
            return self._version.__lt__(other._version)
        raise TypeError(f"Cannot compare PEP440SemVer with {type(other)}")

    def __le__(self, other: str | Version | "PEP440SemVer"):
        if isinstance(other, str):
            return self._version.__le__(Version(other))
        if isinstance(other, Version):
            return self._version.__le__(other)
        if isinstance(other, PEP440SemVer):
            return self._version.__le__(other._version)
        raise TypeError(f"Cannot compare PEP440SemVer with {type(other)}")

    def __eq__(self, other: str | Version | "PEP440SemVer"):
        if isinstance(other, str):
            return self._version.__eq__(Version(other))
        if isinstance(other, Version):
            return self._version.__eq__(other)
        if isinstance(other, PEP440SemVer):
            return self._version.__eq__(other._version)
        raise TypeError(f"Cannot compare PEP440SemVer with {type(other)}")

    def __ne__(self, other: str | Version | "PEP440SemVer"):
        if isinstance(other, str):
            return self._version.__ne__(Version(other))
        if isinstance(other, Version):
            return self._version.__ne__(other)
        if isinstance(other, PEP440SemVer):
            return self._version.__ne__(other._version)
        raise TypeError(f"Cannot compare PEP440SemVer with {type(other)}")

    def __gt__(self, other: str | Version | "PEP440SemVer"):
        if isinstance(other, str):
            return self._version.__gt__(Version(other))
        if isinstance(other, Version):
            return self._version.__gt__(other)
        if isinstance(other, PEP440SemVer):
            return self._version.__gt__(other._version)
        raise TypeError(f"Cannot compare PEP440SemVer with {type(other)}")

    def __ge__(self, other: str | Version | "PEP440SemVer"):
        if isinstance(other, str):
            return self._version.__ge__(Version(other))
        if isinstance(other, Version):
            return self._version.__ge__(other)
        if isinstance(other, PEP440SemVer):
            return self._version.__ge__(other._version)
        raise TypeError(f"Cannot compare PEP440SemVer with {type(other)}")
