from typing import Literal as _Literal
from pathlib import Path as _Path

import pyserials as _ps
from markitup import html as _html
import _ruamel_yaml as _yaml

from controlman.exception import ControlManException as _ControlManException
from controlman.exception.base import format_code as _format_code


class ControlManDataReadException(_ControlManException):
    """Base class for all exceptions raised when a data cannot be read."""

    def __init__(
        self,
        message: str,
        description: str,
        message_html: str | _html.Element | None = None,
        description_html: str | _html.Element | None = None,
        data: str | dict | None = None,
        cause: Exception | None = None,
    ):
        super().__init__(
            message=message,
            message_html=message_html,
            description=description,
            description_html=description_html,
            cause=cause,
            report_heading="ControlMan Data Read Error Report",
        )
        self.data = data
        return


class ControlManConfigFileReadException(ControlManDataReadException):
    """Base class for all exceptions raised when a control center configuration file cannot be read."""

    def __init__(
        self,
        filepath: str | _Path,
        data: str | dict,
        description: str,
        description_html: str | _html.Element | None = None,
        cause: Exception | None = None,
    ):
        message_template = "Failed to read control center configuration file at {filepath}."
        filepath_console, filepath_html = _format_code(filepath)
        super().__init__(
            data=data,
            message=message_template.format(filepath=filepath_console),
            message_html=message_template.format(filepath=filepath_html),
            description=description,
            description_html=description_html,
            cause=cause,
        )
        self.filepath = filepath
        return


class ControlManInvalidConfigFileDataError(ControlManConfigFileReadException):
    """Exception raised when a control center configuration file data is invalid YAML."""

    def __init__(self, cause: _ps.exception.read.PySerialsInvalidDataError):
        super().__init__(
            filepath=cause.filepath,
            data=cause.data,
            description=cause.description,
            description_html=cause.description_html,
            cause=cause,
        )
        return


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
            cause=cause,
        )
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
        cause: Exception | None = None,
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
            cause=cause,
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
        cause: Exception,
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
            cause=cause,
        )
        return


class ControlManInvalidMetadataError(ControlManDataReadException):
    """Exception raised when a control center metadata file contains invalid data."""

    def __init__(
        self,
        cause: _ps.exception.read.PySerialsReadException,
        filepath: str | _Path | None = None,
        commit_hash: str | None = None,
    ):
        filepath_console, filepath_html = _format_code(str(filepath))
        commit_hash_console, commit_hash_html = _format_code(str(commit_hash))
        if filepath:
            from_source = "file at {filepath}"
            if commit_hash:
                from_source += " from commit hash {commit_hash}"
        else:
            from_source = "from input string"
        message_template = f"Failed to read project metadata {from_source}."
        super().__init__(
            data=getattr(cause, "data", None),
            message=message_template.format(filepath=filepath_console, commit_hash=commit_hash_console),
            message_html=message_template.format(filepath=filepath_html, commit_hash=commit_hash_html),
            description=cause.description,
            description_html=cause.description_html,
            cause=cause,
        )
        return


class ControlManSchemaValidationError(ControlManDataReadException):
    """Exception raised when a control center file is invalid against its schema."""

    def __init__(
        self,
        source: _Literal["source", "compiled"] = "source",
        before_substitution: bool = False,
        cause: _ps.exception.validate.PySerialsValidateException | None = None,
        description: str | None = None,
        description_html: str | _html.Element | None = None,
        json_path: str | None = None,
        data: dict | None = None,
    ):
        source_desc = "Control center configurations are" if source == "source" else "Project metadata is"
        problem_end = "." if not json_path else f" at path '$.{json_path}'."
        message = f"{source_desc} invalid against the schema{problem_end}"

        super().__init__(
            data=data or cause.data,
            message=message,
            message_html=message,
            description=description or cause.description,
            description_html=description_html or cause.description_html if cause else None,
            cause=cause,
        )
        self.source = source
        self.before_substitution = before_substitution
        self.key = json_path
        return
