from pathlib import Path as _Path

from loggerman import logger as _logger
import pyserials as _pyserials

from controlman import _util, exception as _exception


class APICacheManager:

    @_logger.sectioner("Initialize API Cache Manager")
    def __init__(
        self,
        path_repo: _Path,
        path_cachefile: str,
        retention_days: float,
    ):
        path_repo = _Path(path_repo).resolve()
        self._path = path_repo / path_cachefile
        self._retention_days = retention_days
        if not self._path.is_file():
            _logger.info(f"API cache file not found at '{self._path}'", "initialize new cache")
            self._cache = {}
        else:
            try:
                self._cache = _util.file.read_datafile(
                    path_repo=path_repo,
                    path_data=path_cachefile,
                    relpath_schema="api_cache",
                    log_section_title="Load API Cache File"
                )
            except _exception.content.ControlManContentException as e:
                self._cache = {}
                _logger.info(f"API cache file at '{self._path}' is corrupted", "initialize new cache")
                _logger.debug(code_title="Cache Corruption Details", code=e)
        return

    def get(self, item):
        log_title = f"Retrieve '{item}' from API cache"
        item = self._cache.get(item)
        if not item:
            _logger.info(title=log_title, msg="Item not found")
            return
        timestamp = item.get("timestamp")
        if timestamp and self._is_expired(timestamp):
            _logger.info(
                title=log_title,
                msg=f"Item expired; timestamp: {timestamp}, retention days: {self._retention_days}"
            )
            return
        _logger.info(title=log_title, msg=f"Item found")
        _logger.debug(title=log_title, msg=f"Item data:", code=str(item['data']))
        return item["data"]

    def set(self, key, value):
        new_item = {
            "timestamp": _util.time.now(),
            "data": value,
        }
        self._cache[key] = new_item
        _logger.info(f"Set API cache for '{key}'")
        _logger.debug(code_title="Cache Data", code=new_item)
        return

    def save(self):
        _pyserials.write.to_yaml_file(
            data=self._cache,
            path=self._path,
            make_dirs=True,
        )
        _logger.info(title="Save API cache file", msg=self._path)
        return

    def _is_expired(self, timestamp: str) -> bool:
        return _util.time.is_expired(
            timestamp=timestamp, expiry_days=self._retention_days
        )
