from typing import Literal, Optional
import re
from repodynamics import git


class PEP440SemVer:

    def __init__(
        self,
        major: int,
        minor: int,
        patch: int,
        pre_phase: Optional[Literal['a', 'b', 'rc']] = None,
        pre_num: Optional[int] = None,
        post: Optional[int] = None,
        dev: Optional[int] = None,
        epoch: Optional[int] = None,
    ):
        def check_int(name, val):
            if not isinstance(val, int):
                raise TypeError(f"{name} must be an integer")
            if val < 0:
                raise ValueError(f"{name} must be a positive integer")
            return

        for name, val in [("major", major), ("minor", minor), ("patch", patch)]:
            check_int(name=name, val=val)

        for name, val in [("post", post), ("dev", dev), ("epoch", epoch)]:
            if val is not None:
                check_int(name=name, val=val)

        if pre_phase:
            if pre_phase not in ('a', 'b', 'rc'):
                raise ValueError("pre_phase must be one of 'a', 'b', or 'rc'")
            if pre_num is None:
                raise ValueError("pre_num must be specified if pre_phase is specified")
            check_int(name="pre_num", val=pre_num)
        elif pre_num is not None:
            raise ValueError("pre_num must not be specified if pre_phase is not specified")

        self._major = major
        self._minor = minor
        self._patch = patch
        self._pre_phase = pre_phase
        self._pre_num = pre_num
        self._post = post
        self._dev = dev
        self._epoch = epoch
        return

    @property
    def release_type(self) -> Literal['final', 'pre', 'post', 'dev']:
        if self._dev is not None:
            return 'dev'
        if self._post is not None:
            return 'post'
        if self._pre_phase:
            return 'pre'
        return 'final'

    def __str__(self):
        version = f"{self._major}.{self._minor}.{self._patch}"
        if self._pre_phase:
            version += f"{self._pre_phase}{self._pre_num}"
        if self._post:
            version += f".post{self._post}"
        if self._dev:
            version += f".dev{self._dev}"
        if self._epoch:
            version = f"{self._epoch}!{version}"
        return version

    def __repr__(self):
        return (
            f"PEP440SemVer({self._major}, {self._minor}, {self._patch}, "
            f"{self._pre_phase}, {self._pre_num}, {self._post}, {self._dev}, {self._epoch})"
        )


def from_git_tag(prefix: str = "vers/") -> PEP440SemVer:
    tag = git.Git().describe(
        abbrev=0,
        match=f"{prefix}[0-9]*.[0-9]*.[0-9]*"
    )
    if not tag:
        raise ValueError(f"No git tag found with prefix '{prefix}'")
    version = tag.removeprefix(prefix)
    return from_string(version=version)


def from_string(version: str) -> PEP440SemVer:
    components = _parse_pep440_version(version=version)
    if not components:
        raise ValueError(f"Invalid PEP440 version string: {version}")
    release = components.pop("release")
    if len(release) != 3:
        raise ValueError(f"Invalid PEP440 version string: {version}")
    return PEP440SemVer(*release, **components)


def _parse_pep440_version(version: str) -> dict:
    pattern = re.compile(r'''
    ^
    (?:(?P<epoch>0|[1-9]\d*)!)?            # epoch segment (optional)
    (?P<release>0|[1-9]\d*)                # release segment (required)
    (?P<rest>(?:\.(0|[1-9]\d*))*)?         # additional release segment values (optional) 
    (?:                                    # pre-release segment (optional)
        (?P<pre_phase>a|b|rc)              # pre-release phase
        (?P<pre_num>0|[1-9]\d*)            # pre-release number
    )? 
    (?:\.post(?P<post>0|[1-9]\d*))?        # post-release segment (optional)
    (?:\.dev(?P<dev>0|[1-9]\d*))?          # development release segment (optional)
    $
    ''', re.VERBOSE)
    match = pattern.match(version)
    if not match:
        return
    components = match.groupdict()
    for key in ["epoch", "release", "pre_num", "post", "dev"]:
        components[key] = int(components[key]) if components[key] else None
    components["release"] = [components["release"]]
    release_rest = components.pop("rest")
    if release_rest:
        components["release"].extend(
            list(map(int, release_rest.removeprefix(".").split(".")))
        )
    return components
