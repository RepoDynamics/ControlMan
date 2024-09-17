from __future__ import annotations

from typing import TYPE_CHECKING as _TYPE_CHECKING

from exceptionman import ReporterException as _ReporterException

if _TYPE_CHECKING:
    from mdit import Document


class ControlManException(_ReporterException):
    """Base class for all exceptions raised by ControlMan."""

    def __init__(self, report: Document):
        super().__init__(
            report=report,
            sphinx_config={
                "extensions": ['myst_parser', 'sphinx_design', 'sphinx_togglebutton'],
                "myst_enable_extensions": ["colon_fence", "fieldlist"],
                "html_theme": "pydata_sphinx_theme",
                "html_title": "ControlMan Error Report",
            }
        )
        return
