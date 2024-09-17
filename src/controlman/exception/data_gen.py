from pathlib import Path as _Path

import mdit as _mdit

from controlman.exception import ControlManException as _ControlManException


class ControlManRepositoryError(_ControlManException):
    """Exception raised when issues are encountered with the Git(Hub) repository."""

    def __init__(self, repo_path: _Path, problem):
        intro = _mdit.inline_container(
            "An error occurred with the Git repository at ",
            _mdit.element.code_span(str(repo_path)),
            ".",
        )
        report = _mdit.document(
            heading="Repository Error",
            body={
                "intro": intro,
                "problem": problem,
            },
        )
        super().__init__(report)
        self.repo_path = repo_path
        return


class ControlManWebsiteError(_ControlManException):
    """Exception raised when issues are encountered with the website."""

    def __init__(self, problem: str):
        report = _mdit.document(
            heading="Website Error",
            body={
                "intro": "An error occurred with the website.",
                "problem": problem,
            },
        )
        super().__init__(report)
        return
