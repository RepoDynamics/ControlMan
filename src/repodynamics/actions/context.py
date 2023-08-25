import json

from markitup import html, md

from repodynamics.logger import Logger


def context(
    github: dict,
    env: dict,
    job: dict,
    steps: dict,
    runner: dict,
    strategy: dict,
    matrix: dict,
    inputs: dict,
    logger: Logger = None,
) -> tuple[None, None, str]:
    github["token"] = "***REDACTED***"
    payload_data = github.pop("event")
    summary = html.ElementCollection([html.h(2, "Workflow Context")])
    if inputs['event-payload'] == 'true':
        summary.append(html.h(3, "📥 Event Payload"))
        summary.append(
            html.details(
                content=md.code_block(json.dumps(dict(sorted(payload_data.items())), indent=4), "json"),
                summary=f"<code>{github['event_name']}</code>",
            )
        )
    added_header = False
    for name, data in (
        ("github", github),
        ("env", env),
        ("job", job),
        ("steps", steps),
        ("runner", runner),
        ("strategy", strategy),
        ("matrix", matrix),
    ):
        if data and inputs[name] == 'true':
            if not added_header:
                summary.append(html.h(3, "🎬 Contexts"))
                added_header = True
            summary.append(
                html.details(
                    content=md.code_block(json.dumps(dict(sorted(data.items())), indent=4), "json"),
                    summary=f"<code>{name}</code> context",
                )
            )
    return None, None, str(summary)
