from repodynamics.meta.datastruct.dev import branch


class Dev:

    def __init__(self, options: dict):
        self._options = options
        self._branch = branch.Branch(options)
        return

    @property
    def branch(self) -> branch.Branch:
        return self._branch
