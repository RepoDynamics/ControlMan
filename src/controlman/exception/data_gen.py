from pathlib import Path as _Path

from controlman.exception import ControlManException as _ControlManException
from controlman.exception.base import format_code as _format_code


class ControlManRepositoryError(_ControlManException):
    """Exception raised when issues are encountered with the Git(Hub) repository."""

    def __init__(self, repo_path: _Path, description: str, description_html: str | None = None):
        message_template = "An error occurred with the Git repository at {repo_path}."
        repo_path_console, repo_path_html = _format_code(str(repo_path))
        super().__init__(
            message=message_template.format(repo_path=repo_path_console),
            message_html=message_template.format(repo_path=repo_path_html),
            description=description,
            description_html=description_html,
            report_heading="ControlMan Data Generation Error Report",
        )
        self.repo_path = repo_path
        return


class ControlManWebsiteError(_ControlManException):
    """Exception raised when issues are encountered with the website."""

    def __init__(self, description: str):
        super().__init__(
            message=f"An error occurred with the website.",
            description=description,
            report_heading="ControlMan Data Generation Error Report",
        )
        return
