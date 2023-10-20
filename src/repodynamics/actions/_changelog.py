from pathlib import Path
import re
import datetime

from repodynamics.logger import Logger


class ChangelogManager:
    def __init__(
        self,
        changelog_metadata: dict,
        ver_dist: str,
        commit_type: str,
        commit_title: str,
        parent_commit_hash: str,
        parent_commit_url: str,
        logger: Logger = None
    ):
        self.meta = changelog_metadata
        self.vars = {
            "ver_dist": ver_dist,
            "date": datetime.date.today().strftime("%Y.%m.%d"),
            "commit_type": commit_type,
            "commit_title": commit_title,
            "parent_commit_hash": parent_commit_hash,
            "parent_commit_url": parent_commit_url,
        }
        self.logger = logger or Logger("github")
        self.changes = {}
        return

    def add_change(self, changelog_id: str, section_id: str, change_title: str, change_details: str):
        if changelog_id not in self.meta:
            self.logger.error(f"Invalid changelog ID: {changelog_id}")
        changelog_dict = self.changes.setdefault(changelog_id, {})
        if not isinstance(changelog_dict, dict):
            self.logger.error(
                f"Changelog {changelog_id} is already updated with an entry; cannot add individual changes."
            )
        for section_idx, section in enumerate(self.meta[changelog_id]["sections"]):
            if section["id"] == section_id:
                section_dict = changelog_dict.setdefault(
                    section_idx, {"title": section["title"], "changes": []}
                )
                section_dict["changes"].append({"title": change_title, "details": change_details})
                break
        else:
            self.logger.error(f"Invalid section ID: {section_id}")
        return

    def add_entry(self, changelog_id: str, sections: str):
        if changelog_id not in self.meta:
            self.logger.error(f"Invalid changelog ID: {changelog_id}")
        if changelog_id in self.changes:
            self.logger.error(
                f"Changelog {changelog_id} is already updated with an entry; cannot add new entry."
            )
        self.changes[changelog_id] = sections
        return

    def write_all_changelogs(self):
        for changelog_id in self.changes:
            self.write_changelog(changelog_id)
        return

    def write_changelog(self, changelog_id: str):
        if changelog_id not in self.changes:
            return
        changelog = self.get_changelog(changelog_id)
        with open(self.meta[changelog_id]["path"], "w") as f:
            f.write(changelog)
        return

    def get_changelog(self, changelog_id: str) -> str:
        if changelog_id not in self.changes:
            return ""
        path = Path(self.meta[changelog_id]["path"])
        if not path.exists():
            title = f"# {self.meta[changelog_id]['title']}"
            intro = self.meta[changelog_id]["intro"].strip()
            text_before = f"{title}\n\n{intro}"
            text_after = ""
        else:
            with open(path) as f:
                text = f.read()
            parts = re.split(r'^## ', text, maxsplit=1, flags=re.MULTILINE)
            if len(parts) == 2:
                text_before, text_after = parts[0].strip(), f"## {parts[1].strip()}"
            else:
                text_before, text_after = text.strip(), ""
        entry = self.get_entry(changelog_id).strip()
        changelog = f"{text_before}\n\n{entry}\n\n{text_after}".strip() + "\n"
        return changelog

    def get_entry(self, changelog_id: str) -> str:
        if changelog_id not in self.changes:
            return ""
        entry_title = self.meta[changelog_id]["entry"]["title"].format(**self.vars).strip()
        entry_intro = self.meta[changelog_id]["entry"]["intro"].format(**self.vars).strip()
        entry_sections = self.get_sections(changelog_id)
        entry = f"## {entry_title}\n\n{entry_intro}\n\n{entry_sections}"
        return entry

    def get_sections(self, changelog_id: str) -> str:
        if changelog_id not in self.changes:
            return ""
        if isinstance(self.changes[changelog_id], str):
            return self.changes[changelog_id]
        changelog_dict = self.changes[changelog_id]
        sorted_sections = [value for key, value in sorted(changelog_dict.items())]
        sections_str = ""
        for section in sorted_sections:
            sections_str += f"### {section['title']}\n\n"
            for change in section["changes"]:
                sections_str += f"#### {change['title']}\n\n{change['details']}\n\n"
        return sections_str.strip() + "\n"

    @property
    def open_changelogs(self) -> tuple[str]:
        return tuple(self.changes.keys())
