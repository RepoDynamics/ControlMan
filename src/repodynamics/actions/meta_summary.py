import json

from markitup import html, md


def meta_summary(cache_hit: bool, force_update: str, metadata_filepath: str) -> tuple[None, str]:
    force_update_emoji = "✅" if force_update == "all" else ("❌" if force_update == "none" else "☑️")
    cache_hit_emoji = "✅" if cache_hit else "❌"
    if not cache_hit or force_update == "all":
        result = "Updated all metadata"
    elif force_update == "core":
        result = "Updated core metadata but loaded API metadata from cache"
    elif force_update == "none":
        result = "Loaded all metadata from cache"
    else:
        raise ValueError(f"Unknown force_update value: {force_update}")
    with open(metadata_filepath) as f:
        metadata_dict = json.load(f)
    metadata_details = html.details(
        content=md.code_block(json.dumps(metadata_dict, indent=4), "json"),
        summary="🖥 Metadata",
        content_indent=""
    )
    results_list = html.ul(
        [
            f"{force_update_emoji}  Force update (input: {force_update})",
            f"{cache_hit_emoji}  Cache hit",
            f"➡️ {result}",
        ],
        content_indent="",
    )
    log = f"{results_list}\n<br>\n{metadata_details}"
    return None, log
