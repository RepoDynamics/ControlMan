
import re

from repodynamics.logger import Logger


class CommitMsg:
    def __init__(
        self,
        typ: str,
        title: str,
        body: str | None = None,
        scope: str | tuple[str] | list[str] | None = None,
        footer: dict[str, str | list[str]] | None = None,
    ):
        for arg, arg_name in ((typ, "typ"), (title, "title")):
            if not isinstance(arg, str):
                raise TypeError(f"Argument '{arg_name}' must be a string, but got {type(arg)}: {arg}")
            if "\n" in arg:
                raise ValueError(f'Argument `{arg_name}` must not contain a newline, but got: """{arg}"""')
            if ":" in arg:
                raise ValueError(f'Argument `{arg_name}` must not contain a colon, but got: """{arg}"""')
        self.type = typ
        self.title = title
        if isinstance(body, str):
            self.body = body.strip()
        elif body is None:
            self.body = ""
        else:
            raise TypeError(f"Argument 'body' must be a string or None, but got {type(body)}: {body}")
        if scope is None:
            self.scope = []
        if isinstance(scope, (list, tuple)):
            self.scope = [str(s) for s in scope]
        elif isinstance(scope, str):
            self.scope = [scope]
        else:
            raise TypeError(
                f"Argument 'scope' must be a string or list/tuple of strings, but got {type(scope)}: {scope}"
            )
        if footer is None:
            self.footer = {}
        elif isinstance(footer, dict):
            self.footer = footer
        else:
            raise TypeError(
                f"Argument 'footer' must be a dict, but got {type(footer)}: {footer}"
            )
        return

    @property
    def summary(self):
        scope = f"({', '.join(self.scope)})" if self.scope else ""
        return f"{self.type}{scope}: {self.title}"

    def __str__(self):
        commit = self.summary
        if self.body:
            commit += f"\n\n{self.body}"
        if self.footer:
            commit += "\n\n-----------\n\n"
            for key, values in self.footer.items():
                if isinstance(values, str):
                    values = [values]
                for value in values:
                    commit += f"{key}: {value}\n"
        return commit.strip() + "\n"


class CommitParser:
    def __init__(self, types: list[str], logger: Logger = None):
        self._types = types
        self._logger = logger
        pattern = rf"""
            ^(?P<typ>{"|".join(types)})    # type
            (?:\((?P<scope>[^\)\n]+)\))?  # optional scope within parentheses
            :[ ](?P<title>[^\n]+)   # commit description after ": "
            (?:\n(?P<body>.+?))?          # optional commit body after newline
            (?:\n-{{3,}}\n(?P<footer>.*))?  # optional footers after horizontal line
            $
        """
        self._pattern = re.compile(pattern, flags=re.VERBOSE | re.DOTALL)
        return

    def parse(self, msg: str) -> CommitMsg | None:
        match = self._pattern.match(msg)
        if not match:
            return
        commit_parts = match.groupdict()
        if commit_parts["scope"]:
            commit_parts["scope"] = [scope.strip() for scope in commit_parts["scope"].split(",")]
        commit_parts["title"] = commit_parts["title"].strip()
        commit_parts["body"] = commit_parts["body"].strip() if commit_parts["body"] else ""
        if commit_parts["footer"]:
            parsed_footers = {}
            footers = commit_parts["footer"].strip().splitlines()
            for footer in footers:
                match = re.match(r"^(?P<key>\w+)(: | )(?P<value>.+)$", footer)
                if match:
                    footer_list = parsed_footers.setdefault(match.group("key"), [])
                    footer_list.append(match.group("value"))
                    continue
                # Sometimes GitHub adds a second horizontal line after the original footer; skip it
                if footer and not re.fullmatch("-{3,}", footer):
                    # Otherwise, the footer is invalid
                    self._logger.error(f"Invalid footer: {footer}")
            commit_parts["footer"] = parsed_footers
        return CommitMsg(**commit_parts)
