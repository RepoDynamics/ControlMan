from typing import NamedTuple as _NamedTuple


class KeyNote(_NamedTuple):
    title: str
    description: str


class Intro:

    def __init__(self, options: dict):
        self._name: str = options["name"]
        self._tagline: str = options["tagline"]
        self._description: str = options["description"]
        self._keywords: tuple[str, ...] = tuple(options["keywords"])
        self._keynotes: tuple[KeyNote, ...] = tuple(
            [
                KeyNote(title=keynote["title"], description=keynote["description"])
                for keynote in options["keynotes"]
            ]
        )
        return

    @property
    def name(self) -> str:
        return self._name

    @property
    def tagline(self) -> str:
        return self._tagline

    @property
    def description(self) -> str:
        return self._description

    @property
    def keywords(self) -> tuple[str, ...]:
        return self._keywords

    @property
    def keynotes(self) -> tuple[KeyNote, ...]:
        return self._keynotes
