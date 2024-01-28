from pathlib import Path as _Path

import pyserials as _pyserials
from actionman.logger import Logger as _Logger

from repodynamics import time as _time, file_io as _file_io


class APICacheManager:

    def __init__(
        self,
        path_cachefile: _Path | str,
        retention_days: float,
        logger: _Logger,
        log_section_title: str = "Initialize API Cache Manager",
    ):
        self._logger = logger
        self._logger.section(log_section_title, group=True)
        self._path = _Path(path_cachefile).resolve()
        self._retention_days = retention_days
        if not self._path.is_file():
            self._logger.info(f"API cache file not found at '{self._path}'; initialized new cache.")
            self._cache = {}
        else:
            self._cache = _file_io.read_datafile(
                path_data=self._path, logger=self._logger, log_section_title="Load API Cache File"
            )
        self._logger.section_end()
        return

    def get(self, item):
        log_title = f"Retrieve '{item}' from API cache"
        item = self._cache.get(item)
        if not item:
            self._logger.info(title=log_title, message="Item not found")
            return None
        timestamp = item.get("timestamp")
        if timestamp and self._is_expired(timestamp):
            self._logger.info(
                title=log_title,
                message=f"Item expired; timestamp: {timestamp}, retention days: {self._retention_days}"
            )
            return None
        self._logger.info(title=log_title, message=f"Item found")
        self._logger.debug(title=log_title, message=f"Item data:", code=str(item['data']))
        return item["data"]

    def set(self, key, value):
        new_item = {
            "timestamp": _time.now(),
            "data": value,
        }
        self._cache[key] = new_item
        self._logger.info(f"Set API cache for '{key}'")
        self._logger.debug(
            title=f"Set API cache for '{key}'", message="Cache data:", code=str(new_item)
        )
        return

    def save(self):
        _pyserials.write.to_yaml_file(
            data=self._cache,
            path=self._path,
            make_dirs=True,
        )
        self._logger.info(title="Save API cache file", message=f"Cache file saved at {self._path}.")
        return

    def _is_expired(self, timestamp: str) -> bool:
        return _time.is_expired(
            timestamp=timestamp, expiry_days=self._retention_days
        )
