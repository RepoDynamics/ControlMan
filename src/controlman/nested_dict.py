import pyserials as _ps

class NestedDict:

    def __init__(self, data: dict):
        self._data = data
        self._templater = _ps.update.TemplateFiller(
            template_start="${{",
            template_end="}}",
            path_prefix="$."
        )
        return

    def fill(self, path: str | None = None):
        if not path:
            value = self._data
        else:
            value = self.__getitem__(path)
        if not value:
            return
        filled_value = self._templater.fill(
            templated_data=value,
            source_data=self._data,
            single_as_list=False,
            recursive=True,
        )
        self.__setitem__(path, filled_value)
        return filled_value

    def __call__(self):
        return self._data

    def __getitem__(self, item: str):
        keys = item.split(".")
        data = self._data
        for key in keys:
            if not isinstance(data, dict):
                raise KeyError(f"Key '{key}' not found in '{data}'.")
            if key not in data:
                return
            data = data[key]
        # if isinstance(data, dict):
        #     return NestedDict(data)
        # if isinstance(data, list) and all(isinstance(item, dict) for item in data):
        #     return [NestedDict(item) for item in data]
        return data

    def __setitem__(self, key, value):
        key = key.split(".")
        data = self._data
        for k in key[:-1]:
            if k not in data:
                data[k] = {}
            data = data[k]
        data[key[-1]] = value
        return

    def __contains__(self, item):
        keys = item.split(".")
        data = self._data
        for key in keys:
            if not isinstance(data, dict) or key not in data:
                return False
            data = data[key]
        return True

    def __bool__(self):
        return bool(self._data)

    def setdefault(self, key, value):
        key = key.split(".")
        data = self._data
        for k in key[:-1]:
            if k not in data:
                data[k] = {}
            data = data[k]
        return data.setdefault(key[-1], value)

    def get(self, key, default=None):
        keys = key.split(".")
        data = self._data
        for key in keys:
            if not isinstance(data, dict) or key not in data:
                return default
            data = data[key]
        return data

    def items(self):
        return self._data.items()

    def keys(self):
        return self._data.keys()

    def values(self):
        return self._data.values()

    def update(self, data: dict):
        self._data.update(data)
        return
