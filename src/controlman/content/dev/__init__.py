from controlman.content.dev import branch
from controlman.content.dev import label


class Dev:

    def __init__(self, data: dict):
        self._data = data
        self._branch = branch.Branch(data)
        self._label = label.Label(data)
        return

    @property
    def branch(self) -> branch.Branch:
        return self._branch

    @property
    def label(self) -> label.Label:
        return self._label
