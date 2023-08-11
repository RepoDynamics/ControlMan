"""

"""
import datetime
from pathlib import Path

from ruamel.yaml import YAML


class Cache:
    def __init__(self, filepath: str | Path, expiration_days: int, update: bool = False):
        self._exp_days = expiration_days
        self.path = Path(filepath).with_suffix(".yaml")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.cache = dict() if (update or not self.path.exists()) else YAML(typ="safe").load(self.path)
        return

    def __getitem__(self, item):
        item = self.cache.get(item)
        if not item:
            return None
        timestamp = item["timestamp"]
        if self._is_expired(timestamp):
            return None
        return item["data"]

    def __setitem__(self, key, value):
        self.cache[key] = {
            "timestamp": self._now,
            "data": value,
        }
        with open(self.path, "w") as f:
            YAML(typ="safe").dump(self.cache, f)
        return

    @property
    def _now(self) -> str:
        return datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y.%m.%d-%H:%M:%S")

    def _is_expired(self, timestamp: str) -> bool:
        exp_date = datetime.datetime.strptime(timestamp, "%Y.%m.%d-%H:%M:%S") + datetime.timedelta(
            days=self._exp_days
        )
        return exp_date <= datetime.datetime.now()
