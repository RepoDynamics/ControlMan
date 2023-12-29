from repodynamics.meta.datastruct.project.intro import Intro
from repodynamics.meta.datastruct.project.credits import Credits
from repodynamics.meta.datastruct.project.license import License


class Project:

    def __init__(self, options: dict):
        self._intro = Intro(options)
        self._credits = Credits(options)
        self._license = License(options)
        return

    @property
    def intro(self) -> Intro:
        return self._intro

    @property
    def credits(self) -> Credits:
        return self._credits

    @property
    def license(self) -> License:
        return self._license
