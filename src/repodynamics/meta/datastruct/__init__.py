from repodynamics.meta.datastruct import project, dev, package_python, ui


class ControlCenterOptions:

    def __init__(self, options: dict):
        self._options = options
        self._project = project.Project(options)
        self._dev = dev.Dev(options)
        return

    @property
    def project(self) -> project.Project:
        return self._project

    @property
    def dev(self) -> dev.Dev:
        return self._dev
