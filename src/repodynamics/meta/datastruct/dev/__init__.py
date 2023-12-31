from repodynamics.meta.datastruct.dev import branch
from repodynamics.meta.datastruct.dev import label


class Dev:

    def __init__(self, settings: dict):
        self._ccs = settings
        self._branch = branch.Branch(settings)
        self._label = label.Label(settings)
        return

    @property
    def branch(self) -> branch.Branch:
        return self._branch

    @property
    def label(self) -> label.Label:
        return self._label
