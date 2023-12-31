from typing import NamedTuple
from enum import Enum


class LabelType(Enum):
    AUTO_GROUP = "auto_group"
    GROUP = "group"
    SINGLE = "single"


class SingleLabel(NamedTuple):
    name: str
    description: str | None
    color: str


class AutoGroupLabel(NamedTuple):
    prefix: str
    description: str | None
    color: str


class FullLabel(NamedTuple):
    type: LabelType
    group_name: str | None
    id: str
    name: str
    description: str
    color: str


class Label:

    def __init__(self, settings: dict):
        self._ccs = settings

        self._version, self._branch = [
            AutoGroupLabel(
                prefix=autogroup_data["prefix"],
                description=autogroup_data["description"],
                color=autogroup_data["color"],
            )
            for autogroup_data in [
                self._ccs["label"]["auto_group"][auto_group] for auto_group in ("version", "branch")
            ]
        ]
        self._full = [
            FullLabel(
                type=LabelType(label_data["type"]),
                group_name=label_data["group_name"],
                id=label_data["id"],
                name=label_data["name"],
                description=label_data["description"],
                color=label_data["color"],
            ) for label_data in self._ccs["label"]["compiled"]
        ] if "compiled" in self._ccs["label"] else None
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
            ) for label_id, label_data in self._ccs["label"]["single"].items()
        }

    @property
    def full_labels(self) -> list[FullLabel] | None:
        return self._full
