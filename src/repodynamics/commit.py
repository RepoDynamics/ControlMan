import re
import json

from repodynamics.datatype import CommitMsg
from repodynamics.logger import Logger


class CommitParser:
    def __init__(self, types: list[str], logger: Logger = None):
        self._types = types
        self._logger = logger or Logger()
        pattern_summary = rf"""
            ^
            (?P<typ>{"|".join(types)})         # type
            (?:\((?P<scope>[^\)]+)\))?       # optional scope within parentheses
            :[ ](?P<title>.+)              # commit description after ": "
            $
        """
        self._pattern = re.compile(pattern_summary, flags=re.VERBOSE | re.DOTALL)
        return

    def parse(self, msg: str) -> CommitMsg | None:
        if not isinstance(msg, str):
            raise TypeError(f"Invalid commit message type: {type(msg)}")
        if not msg:
            return
        lines = msg.splitlines()
        summary = lines[0]
        summary_match = self._pattern.match(summary)
        if not summary_match:
            return
        commit_parts = summary_match.groupdict()
        if commit_parts["scope"]:
            commit_parts["scope"] = [scope.strip() for scope in commit_parts["scope"].split(",")]
        commit_parts["title"] = commit_parts["title"].strip()
        commit_parts |= {"body": None, "footer": None}
        if len(lines) == 1:
            return CommitMsg(**commit_parts)
        for line_idx, line in enumerate(lines[1:]):
            if line.startswith("---") and all(c == "-" for c in line):
                break
        else:
            line_idx += 1
        commit_parts["body"] = "\n".join(lines[1:line_idx + 1]).strip() or None
        commit_parts["footer"] = self._parse_footer(lines[line_idx + 2:]) or None
        return CommitMsg(**commit_parts)

    def _parse_footer(self, footers: list[str]) -> dict:
        parsed_footers = {}
        for footer in footers:
            # Sometimes GitHub adds a second horizontal line after the original footer; skip it
            if not footer or re.fullmatch("-{3,}", footer):
                continue
            match = re.match(r"^(?P<key>[\w-]+)( *:* *(?P<value>.*))?$", footer)
            if match:
                key = match.group("key")
                val = match.group("value").strip() if match.group("value") else "true"
                if key in parsed_footers:
                    self._logger.error(f"Duplicate footer: {footer}")
                try:
                    parsed_footers[key] = json.loads(val)
                except json.JSONDecodeError:
                    self._logger.error(f"Invalid footer value: {footer}")
                # footer_list = parsed_footers.setdefault(match.group("key"), [])
                # footer_list.append(match.group("value").strip() if match.group("value") else True)
            else:
                # Otherwise, the footer is invalid
                self._logger.warning(f"Invalid footer: {footer}")
        return parsed_footers


# class CommitParser:
#     def __init__(self, types: list[str], logger: Logger = None):
#         self._types = types
#         self._logger = logger or Logger()
#         pattern = rf"""
#             ^
#             (?P<typ>{"|".join(types)})         # type
#             (?:\((?P<scope>[^\)\n]+)\))?       # optional scope within parentheses
#             :[ ](?P<title>[^\n]+)              # commit description after ": "
#             (?:(?P<body>.*?)(\n-{{3,}}\n)|$)?  # optional commit body
#                                                #   everything until first "\n---" or end of string
#             (?P<footer>.*)?                    # optional footers
#             $
#         """
#         self._pattern = re.compile(pattern, flags=re.VERBOSE | re.DOTALL)
#         return
#
#     def parse(self, msg: str) -> CommitMsg | None:
#         match = self._pattern.match(msg)
#         if not match:
#             return
#         commit_parts = match.groupdict()
#         if commit_parts["scope"]:
#             commit_parts["scope"] = [scope.strip() for scope in commit_parts["scope"].split(",")]
#         commit_parts["title"] = commit_parts["title"].strip()
#         commit_parts["body"] = commit_parts["body"].strip() if commit_parts["body"] else ""
#         if commit_parts["footer"]:
#             parsed_footers = {}
#             footers = commit_parts["footer"].strip().splitlines()
#             for footer in footers:
#                 # Sometimes GitHub adds a second horizontal line after the original footer; skip it
#                 if not footer or re.fullmatch("-{3,}", footer):
#                     continue
#                 match = re.match(r"^(?P<key>[\w-]+)( *:* *(?P<value>.*))?$", footer)
#                 if match:
#                     key = match.group("key")
#                     val = match.group("value").strip() if match.group("value") else "true"
#                     if key in parsed_footers:
#                         self._logger.error(f"Duplicate footer: {footer}")
#                     try:
#                         parsed_footers[key] = json.loads(val)
#                     except json.JSONDecodeError:
#                         self._logger.error(f"Invalid footer value: {footer}")
#                     # footer_list = parsed_footers.setdefault(match.group("key"), [])
#                     # footer_list.append(match.group("value").strip() if match.group("value") else True)
#                 else:
#                     # Otherwise, the footer is invalid
#                     self._logger.warning(f"Invalid footer: {footer}")
#             commit_parts["footer"] = parsed_footers
#         return CommitMsg(**commit_parts)
