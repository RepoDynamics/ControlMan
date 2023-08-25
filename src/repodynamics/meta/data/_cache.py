"""

"""
import datetime
import json
from pathlib import Path
from typing import Optional

from ruamel.yaml import YAML

from repodynamics.logger import Logger

class Cache:
    def __init__(self, filepath: str | Path, expiration_days: int = 7, update: bool = False, logger: Logger = None):
        self._exp_days = expiration_days
        self.logger = logger or Logger("console")
        self.logger.section("Initialize cache")
        if filepath:
            self._write_to_file = True
            self.path = Path(filepath).with_suffix(".yaml")
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"Cache file location specified at '{self.path}'")
            if update:
                self.logger.info(f"Force-update was selected; cache will be updated entirely.")
                self.cache = dict()
            elif not self.path.exists():
                self.logger.info(f"Cache file does not exist; cache will be created.")
                self.cache = dict()
            else:
                self.cache = YAML(typ="safe").load(self.path)
                self.logger.info(f"Loaded cache:")
                self.logger.debug(json.dumps(self.cache, indent=3))
        else:
            self.logger.attention("No cache file specified. Cache will not be saved.")
            self.cache = dict()
            self._write_to_file = False
        self.logger.end_section()
        return

    def __getitem__(self, item):
        self.logger.info(f"Retrieve '{item}' from cache:")
        item = self.cache.get(item)
        if not item:
            self.logger.debug("Item not found.")
            return None
        timestamp = item["timestamp"]
        if self._is_expired(timestamp):
            return None
        self.logger.debug(f"Item found with valid timestamp '{timestamp}': {item['data']}.")
        return item["data"]

    def __setitem__(self, key, value):
        self.cache[key] = {
            "timestamp": self._now,
            "data": value,
        }
        self.logger.success(f"Set cache for '{key}':")
        self.logger.debug(json.dumps(self.cache[key], indent=3))
        if self._write_to_file:
            with open(self.path, "w") as f:
                YAML(typ="safe").dump(self.cache, f)
            self.logger.success(f"Cache file updated.")
        return

    @property
    def _now(self) -> str:
        return datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y.%m.%d-%H:%M:%S")

    def _is_expired(self, timestamp: str) -> bool:
        exp_date = datetime.datetime.strptime(timestamp, "%Y.%m.%d-%H:%M:%S") + datetime.timedelta(
            days=self._exp_days
        )
        if exp_date <= datetime.datetime.now():
            self.logger.debug("Item has expired.")
            return True
        return False
