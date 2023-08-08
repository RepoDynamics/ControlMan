import json

from markitup import html, md


def context(github: dict) -> tuple[None, str]:
    _ = github.pop("token")
    payload_data = github.pop("event")
    context_details = html.details(
        content=md.code_block(json.dumps(dict(sorted(github.items())), indent=4), "json"),
        summary="🖥 GitHub Context",
        content_indent=""
    )
    payload_details = html.details(
        content=md.code_block(json.dumps(dict(sorted(payload_data.items())), indent=4), "json"),
        summary="🖥 Event Payload",
        content_indent=""
    )
    return None, f"<h2>Workflow Context</h2>{context_details}\n{payload_details}"


