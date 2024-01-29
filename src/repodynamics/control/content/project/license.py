from typing import NamedTuple as _NamedTuple
from enum import Enum as _Enum


class LicenseID(_Enum):
    GNU_AGPL_V3_PLUS = "gnu_agpl_v3+"
    GNU_AGPL_V3 = "gnu_agpl_v3"
    GNU_GPL_V3_PLUS = "gnu_gpl_v3+"
    GNU_GPL_V3 = "gnu_gpl_v3"
    MPL_V2 = "mpl_v2"
    APACHE_V2 = "apache_v2"
    MIT = "mit"
    BSD_2_CLAUSE = "bsd_2_clause"
    BSD_3_CLAUSE = "bsd_3_clause"
    BSL_V1 = "bsl_v1"
    UNLICENSE = "unlicense"


class LicenseData(_NamedTuple):
    id: LicenseID | None = None
    shortname: str = ""
    fullname: str = ""
    trove_classifier: str = ""
    text: str = ""
    notice: str = ""


class Copyright(_NamedTuple):
    year_start: int | None = None
    owner: str = ""


class License:

    def __init__(self, options: dict):
        self._license = LicenseData(
            id=LicenseID(options["license"]["id"]) if "id" in options["license"] else None,
            shortname=options["license"].get("shortname", ""),
            fullname=options["license"].get("fullname", ""),
            trove_classifier=options["license"].get("trove_classifier", ""),
            text=options["license"].get("text", ""),
            notice=options["license"].get("notice", ""),
        )
        self._copyright = Copyright(
            year_start=options["copyright"].get("year_start"),
            owner=options["copyright"].get("owner", "")
        )
        return

    @property
    def license(self) -> LicenseData:
        return self._license

    @property
    def copyright(self) -> Copyright:
        return self._copyright
