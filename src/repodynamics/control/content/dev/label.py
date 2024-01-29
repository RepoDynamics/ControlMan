from typing import NamedTuple as _NamedTuple
from enum import Enum as _Enum


class LabelType(_Enum):
    AUTO_GROUP = "auto_group"
    GROUP = "group"
    SINGLE = "single"


class SingleLabel(_NamedTuple):
    name: str
    description: str | None
    color: str


class AutoGroupLabel(_NamedTuple):
    prefix: str
    description: str | None
    color: str


class FullLabel(_NamedTuple):
    type: LabelType
    group_name: str | None
    id: str
    name: str
    description: str
    color: str


class Label:

    def __init__(self, data: dict):
        self._data = data

        self._version, self._branch = [
            AutoGroupLabel(
                prefix=autogroup_data["prefix"],
                description=autogroup_data["description"],
                color=autogroup_data["color"],
            )
            for autogroup_data in [
                self._data["label"]["auto_group"][auto_group] for auto_group in ("version", "branch")
            ]
        ]
        self._full = tuple(
            FullLabel(
                type=LabelType(label_data["type"]),
                group_name=label_data["group_name"],
                id=label_data["id"],
                name=label_data["name"],
                description=label_data["description"],
                color=label_data["color"],
            ) for label_data in self._data["label"]["compiled"]
        ) if "compiled" in self._data["label"] else None
        return

    @property
    def version(self) -> AutoGroupLabel:
        return self._version

    @property
    def branch(self) -> AutoGroupLabel:
        return self._branch

    @property
    def single(self) -> dict[str, SingleLabel]:
        return {
            label_id: SingleLabel(
                name=label_data["name"],
                description=label_data["description"],
                color=label_data["color"],
            ) for label_id, label_data in self._data["label"]["single"].items()
        }

    @property
    def full_labels(self) -> tuple[FullLabel] | None:
        return self._full
