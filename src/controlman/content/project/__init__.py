from controlman.content.project import intro, license
from controlman.content.project import credits


class Project:

    def __init__(self, options: dict):
        self._options = options
        self._intro = intro.Intro(options)
        self._credits = credits.Credits(options)
        self._license = license.License(options)
        return

    @property
    def intro(self) -> intro.Intro:
        return self._intro

    @property
    def credits(self) -> credits.Credits:
        return self._credits

    @property
    def license(self) -> license.License:
        return self._license
