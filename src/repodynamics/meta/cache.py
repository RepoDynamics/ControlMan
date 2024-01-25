from pathlib import Path

import pyserials

from repodynamics import time, file_io


class APICacheManager:

    def __init__(
        self,
        path_cachefile: Path | str,
        retention_days: float,
    ):
        self.logger.h3("Initialize Cache")

        self._path = Path(path_cachefile).resolve()
        self._retention_days = retention_days

        if not self._path.is_file():
            self.logger.info(f"API cache file not found at '{self._path}'.")
            self._cache = {}
        else:
            self._cache = file_io.read_datafile(path_data=self._path)
            self.logger.success(
                f"API cache loaded from '{self._path}'", json.dumps(cache, indent=3)
            )
        return

    def get(self, item):
        log_title = f"Retrieve '{item}' from cache"
        item = self._cache.get(item)
        if not item:
            self.logger.skip(log_title, "Item not found")
            return None
        timestamp = item.get("timestamp")
        if timestamp and self._is_expired(timestamp):
            self.logger.skip(log_title, f"Item found with expired timestamp '{timestamp}:\n{item['data']}.")
            return None
        self.logger.success(log_title, f"Item found with valid timestamp '{timestamp}':\n{item['data']}.")
        return item["data"]

    def set(self, key, value):
        self._cache[key] = {
            "timestamp": time.now(),
            "data": value,
        }
        self.logger.success(f"Set cache for '{key}'", json.dumps(self._cache[key], indent=3))
        return

    def save(self):
        pyserials.write.to_yaml_file(
            data=self._cache,
            path=self._path,
            make_dirs=True,
        )
        self.logger.success(f"Cache file saved at {self._path}.")
        return

    def _is_expired(self, timestamp: str) -> bool:
        return time.is_expired(
            timestamp=timestamp, expiry_days=self._retention_days
        )
