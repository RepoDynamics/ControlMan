from typing import Literal as _Literal
from pathlib import Path as _Path

import pyserials as _ps
from markitup import html as _html
import _ruamel_yaml as _yaml

from controlman.exception import ControlManException as _ControlManException
from controlman.exception.base import format_code as _format_code


class ControlManConfigFileReadException(_ControlManException):
    """Base class for all exceptions raised when a control center configuration file cannot be read."""

    def __init__(
        self,
        filepath: str | _Path,
        data: str | dict,
        description: str,
        description_html: str | _html.Element | None = None,
    ):
        message_template = "Failed to read control center configuration file at {filepath}."
        filepath_console, filepath_html = _format_code(filepath)
        super().__init__(
            message=message_template.format(filepath=filepath_console),
            message_html=message_template.format(filepath=filepath_html),
            description=description,
            description_html=description_html,
            report_heading="ControlMan Configuration File Read Error Report",
        )
        self.filepath = filepath
        self.data = data
        return


class ControlManInvalidConfigFileDataError(ControlManConfigFileReadException):
    """Exception raised when a control center configuration file data is invalid YAML."""

    def __init__(self, cause: _ps.exception.read.PySerialsInvalidDataError):
        super().__init__(
            filepath=cause.filepath,
            data=cause.data,
            description=cause.description,
            description_html=cause.description_html,
        )
        self.cause = cause
        return

    def _report_content(self, mode: _Literal["full", "short"], md: bool) -> _html.elem.Ul:
        return self.cause._report_content(mode=mode, md=md)


class ControlManDuplicateConfigFileDataError(ControlManConfigFileReadException):
    """Exception raised when a control center configuration file contains duplicate data."""

    def __init__(
        self,
        filepath: _Path,
        cause: _ps.exception.update.PySerialsUpdateDictFromAddonError,
    ):
        description_template = (
            "The value of type {type_data_addon} at {path} already exists in another configuration file"
        ) + "." if cause.problem_type == "duplicate" else " with type {type_data}."
        type_data_console, type_data_html = _format_code(cause.type_data.__name__)
        type_data_addon_console, type_data_addon_html = _format_code(cause.type_data_addon.__name__)
        path_console, path_html = _format_code(cause.path)
        kwargs_console, kwargs_html = (
            {"path": path, "type_data": type_data, "type_data_addon": type_data_addon}
            for path, type_data, type_data_addon in zip(
            (path_console, path_html),
            (type_data_console, type_data_html),
            (type_data_addon_console, type_data_addon_html),
        )
        )
        super().__init__(
            filepath=filepath,
            data=cause.data_addon_full,
            description=description_template.format(**kwargs_console),
            description_html=description_template.format(**kwargs_html),
        )
        self.cause = cause
        return


class ControlManInvalidConfigFileTagException(ControlManConfigFileReadException):
    """Base class for all exceptions raised when a control center configuration file contains an invalid tag."""

    def __init__(
        self,
        filepath: str | _Path,
        data: str,
        description: str,
        description_html: str | _html.Element,
        node: _yaml.ScalarNode,
    ):
        self.node = node
        self.start_line = node.start_mark.line + 1
        self.end_line = node.end_mark.line + 1
        self.start_column = node.start_mark.column + 1
        self.end_column = node.end_mark.column + 1
        self.tag_name = node.tag
        tag_name_console, tag_name_html = _format_code(node.tag)
        super().__init__(
            filepath=filepath,
            data=data,
            description=description.format(tag_name=tag_name_console, start_line=self.start_line),
            description_html=description_html.format(tag_name=tag_name_html, start_line=self.start_line),
        )
        return


class ControlManEmptyTagInConfigFileError(ControlManInvalidConfigFileTagException):
    """Exception raised when a control center configuration file contains an empty tag."""

    def __init__(
        self,
        filepath: _Path,
        data: str,
        node: _yaml.ScalarNode,
    ):
        description_template = "The {tag_name} tag at line {start_line} has no value."
        super().__init__(
            filepath=filepath,
            data=data,
            description=description_template,
            description_html=description_template,
            node=node,
        )
        return


class ControlManUnreachableTagInConfigFileError(ControlManInvalidConfigFileTagException):
    """Exception raised when a control center configuration file contains an unreachable tag."""

    def __init__(
        self,
        filepath: _Path,
        data: str,
        node: _yaml.ScalarNode,
        url: str,
        cause
    ):
        description_template = (
            "Failed to download external data from {url} defined in {tag_name} tag at line {start_line}."
        )
        url_console, url_html = _format_code(url)
        super().__init__(
            filepath=filepath,
            data=data,
            description=description_template.format(url=url_console),
            description_html=description_template.format(url=url_html),
            node=node,
        )
        self.cause = cause
        return
