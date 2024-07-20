from pathlib import Path as _Path

from loggerman import logger as _logger
import pyserials as _pyserials

from controlman import _util, exception as _exception, const as _const


class CacheManager:

    @_logger.sectioner("Initialize Cache Manager")
    def __init__(
        self,
        path_repo: _Path,
        retention_hours: dict[str, float],
    ):
        self._path = path_repo / _const.FILEPATH_METADATA_CACHE
        self._retention_hours = retention_hours
        if not self._path.is_file():
            _logger.info("Caching", f"No cache file found at '{self._path}'; initialized new cache.")
            self._cache = {}
        else:
            try:
                self._cache = _util.file.read_data_from_file(
                    path=self._path,
                    base_path=path_repo,
                    extension="yaml",
                    raise_errors=True
                )
            except _exception.ControlManException as e:
                self._cache = {}
                _logger.info(
                    "Caching", f"API cache file at '{self._path}' is corrupted; initialized new cache."
                )
                _logger.debug(code_title="Cache Corruption Details", code=e)
            try:
                _util.jsonschema.validate_data(
                    data=self._cache,
                    schema="cache",
                    raise_invalid_data=True,
                )
            except _exception.ControlManException as e:
                self._cache = {}
                _logger.info(
                    "Caching", f"API cache file at '{self._path}' is invalid; initialized new cache."
                )
                _logger.debug(code_title="Cache Validation Details", code=e)
        return

    def get(self, typ: str, key: str):
        if typ not in self._retention_hours:
            raise RuntimeError(f"Retention hours not defined for type '{typ}'")
        log_title = f"Retrieve '{typ}.{key}' from API cache"
        item = self._cache.get(typ, {}).get(key)
        if not item:
            _logger.info(title=log_title, msg="Item not found")
            return
        timestamp = item.get("timestamp")
        if timestamp and self._is_expired(typ, timestamp):
            _logger.info(
                title=log_title,
                msg=f"Item expired; timestamp: {timestamp}, retention hours: {self._retention_hours}"
            )
            return
        _logger.info(title=log_title, msg=f"Item found")
        _logger.debug(title=log_title, msg=f"Item data:", code=str(item['data']))
        return item["data"]

    def set(self, typ: str, key: str, value: dict | list | str | int | float | bool):
        new_item = {
            "timestamp": _util.time.now(),
            "data": value,
        }
        self._cache.setdefault(typ, {})[key] = new_item
        _logger.info(f"Set API cache for '{key}'")
        _logger.debug(code_title="Cache Data", code=new_item)
        return

    def save(self):
        _pyserials.write.to_yaml_file(
            data=self._cache,
            path=self._path,
            make_dirs=True,
        )
        _logger.debug("Save API cache file", msg=self._path)
        return

    def _is_expired(self, typ: str, timestamp: str) -> bool:
        return _util.time.is_expired(
            timestamp=timestamp, expiry_hours=self._retention_hours[typ]
        )
