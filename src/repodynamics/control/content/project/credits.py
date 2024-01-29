from typing import NamedTuple as _NamedTuple


class AuthorRole(_NamedTuple):
    title: str
    description: str
    abbreviation: str


class AuthorEntry(_NamedTuple):
    username: str
    roles: tuple[str, ...]


class Authors(_NamedTuple):
    role: dict[str, AuthorRole]
    entries: tuple[AuthorEntry, ...]


class Funding(_NamedTuple):
    community_bridge: str
    issuehunt: str
    ko_fi: str
    liberapay: str
    open_collective: str
    otechie: str
    patreon: str
    tidelift: str
    github: tuple[str, ...]
    custom: tuple[str, ...]


class Credits:

    def __init__(self, options: dict):
        self._authors = Authors(
            role={
                role_id: AuthorRole(
                    title=role_data["title"],
                    description=role_data["description"],
                    abbreviation=role_data["abbreviation"],
                )
                for role_id, role_data in options["author"]["role"].items()
            },
            entries=tuple(
                AuthorEntry(username=entry["username"], roles=tuple(entry.get("roles", [])))
                for entry in options["author"]["entries"]
            ),
        )

        funding_github = options["funding"].get("github", [])
        if isinstance(funding_github, str):
            funding_github = [funding_github]
        funding_custom = options["funding"].get("custom", [])
        if isinstance(funding_custom, str):
            funding_custom = [funding_custom]
        self._funding = Funding(
            community_bridge=options["funding"].get("community_bridge", ""),
            issuehunt=options["funding"].get("issuehunt", ""),
            ko_fi=options["funding"].get("ko_fi", ""),
            liberapay=options["funding"].get("liberapay", ""),
            open_collective=options["funding"].get("open_collective", ""),
            otechie=options["funding"].get("otechie", ""),
            patreon=options["funding"].get("patreon", ""),
            tidelift=options["funding"].get("tidelift", ""),
            github=tuple(funding_github),
            custom=tuple(funding_custom),
        )
        return

    @property
    def authors(self) -> Authors:
        return self._authors

    @property
    def funding(self) -> Funding:
        return self._funding
