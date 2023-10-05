
import re

from repodynamics.logger import Logger


def parse(
    msg: str,
    types: list[str],
    logger: Logger = None,
) -> dict:
    pattern = rf"""
        ^(?P<type>{"|".join(types)})    # type
        (?:\((?P<scope>[^\)\n]+)\))?  # optional scope within parentheses
        :[ ](?P<description>[^\n]+)   # commit description after ": "
        (?:\n(?P<body>.+?))?          # optional commit body after newline
        (?:\n-{{3,}}\n(?P<footer>.*))?  # optional footers after horizontal line
        $
    """
    match = re.match(pattern, msg, flags=re.VERBOSE | re.DOTALL)
    if not match:
        return {}
    commit_parts = match.groupdict()
    commit_parts["body"] = commit_parts["body"].strip() if commit_parts["body"] else None
    if not commit_parts["footer"]:
        return commit_parts
    parsed_footers = {}
    footers = commit_parts["footer"].strip().splitlines()
    for footer in footers:
        match = re.match(r"^(?P<key>\w+)(: | )(?P<value>.+)$", footer)
        if match:
            footer_list = parsed_footers.setdefault(match.group("key"), [])
            footer_list.append(match.group("value"))
            continue
        if footer and not re.fullmatch("-{3,}", footer):
            logger.error(f"Invalid footer: {footer}")
    commit_parts["footer"] = parsed_footers
    return commit_parts


types = set(
        ["major", "minor", "patch", "docs", "test", "meta", "build", "ci", "refactor", "style"]
        + [additional_type['type'] for additional_type in self._metadata["conventional_commits_types"]]
    )