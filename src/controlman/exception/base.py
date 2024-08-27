from exceptionman import ReporterException as _ReporterException
from markitup import html as _html
import ansi_sgr as _sgr


class ControlManException(_ReporterException):
    """Base class for all exceptions raised by ControlMan."""

    def __init__(
        self,
        message: str,
        description: str,
        message_html: str | _html.Element | None = None,
        description_html: str | _html.Element | None = None,
        report_heading: str = "ControlMan Error Report",
    ):
        super().__init__(
            message=message,
            description=description,
            message_html=message_html,
            description_html=description_html,
            report_heading=report_heading,
        )
        return


def format_code(code: str) -> tuple[str, str]:
    console = _sgr.format(
        code, control_sequence=_sgr.style(text_color=(220, 220, 220), background_color=(20, 20, 20))
    )
    html = str(_html.elem.code(code))
    return console, html