from controlman.content import dev, project


class ControlCenterContent:

    def __init__(self, data: dict):
        self._data = data
        self._project = project.Project(data)
        self._dev = dev.Dev(data)
        return

    @property
    def as_dict(self) -> dict:
        return self._data

    @property
    def project(self) -> project.Project:
        return self._project

    @property
    def dev(self) -> dev.Dev:
        return self._dev
