from pathlib import Path
import json
from typing import Literal, Optional, NamedTuple
import re
import datetime
from enum import Enum

from markitup import html, md
import pylinks
from ruamel.yaml import YAML

import repodynamics as rd
from repodynamics.logger import Logger
from repodynamics.git import Git
from repodynamics.meta.meta import Meta
from repodynamics import hooks, _util
from repodynamics.commits import CommitParser, CommitMsg
from repodynamics.versioning import PEP440SemVer


class PrimaryAction(Enum):
    MAJOR_RE


class Commit(NamedTuple):
    type

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
            self.logger.error(f"Changelog {changelog_id} is already updated with an entry; cannot add individual changes.")
        for section_idx, section in enumerate(self.meta[changelog_id]["sections"]):
            if section["id"] == section_id:
                section_dict = changelog_dict.setdefault(section_idx, {"title": section["title"], "changes": []})
                section_dict["changes"].append({"title": change_title, "details": change_details})
                break
        else:
            self.logger.error(f"Invalid section ID: {section_id}")
        return

    def add_entry(self, changelog_id: str, sections: str):
        if changelog_id not in self.meta:
            self.logger.error(f"Invalid changelog ID: {changelog_id}")
        if changelog_id in self.changes:
            self.logger.error(f"Changelog {changelog_id} is already updated with an entry; cannot add new entry.")
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


class Init:

    def __init__(
        self,
        context: dict,
        admin_token: str = "",
        package_build: bool = False,
        package_lint: bool = False,
        package_test: bool = False,
        website_build: bool = False,
        website_announcement: str = "",
        website_announcement_msg: str = "",
        logger: Logger | None = None
    ):
        self._github_token = context.pop("token")
        self._payload = context.pop("event")
        self._context = context
        self._admin_token = admin_token

        # Inputs when event is triggered by a workflow dispatch
        self._package_build = package_build
        self._package_lint = package_lint
        self._package_test = package_test
        self._website_build = website_build
        self._website_announcement = website_announcement
        self._website_announcement_msg = website_announcement_msg

        self.logger = logger or Logger("github")
        self.git: Git = Git(logger=self.logger)
        self.api = pylinks.api.github(token=self._github_token).user(self.repo_owner).repo(self.repo_name)
        self.meta = Meta(path_root=".", github_token=self._github_token, logger=self.logger)

        self.metadata, self.metadata_ci = self.meta.read_metadata_output()
        self.last_ver, self.dist_ver = self.get_latest_version()

        self.output = {
            "config": {
                "checkout": {
                    "ref": "",
                    "ref_before": "",
                    "repository": "",
                },
                "run": {
                    "package_build": False,
                    "package_test_local": False,
                    "package_lint": False,
                    "website_build": False,
                    "website_deploy": False,
                    "website_rtd_preview": False,
                    "package_publish_testpypi": False,
                    "package_publish_pypi": False,
                    "package_test_testpypi": False,
                    "package_test_pypi": False,
                    "github_release": False,
                },
                "package": {
                    "version": "",
                    "upload_url_testpypi": "https://test.pypi.org/legacy/",
                    "upload_url_pypi": "https://upload.pypi.org/legacy/",
                    "download_url_testpypi": "",
                    "download_url_pypi": "",
                },
                "release": {
                    "tag_name": "",
                    "name": "",
                    "body": "",
                    "prerelease": False,
                    "discussion_category_name": "",
                    "make_latest": "legacy",
                }
            },
            "metadata_ci": self.metadata_ci,
        }
        return

    @property
    def context(self) -> dict:
        """The 'github' context of the triggering event.

        References
        ----------
        - [GitHub Docs](https://docs.github.com/en/actions/learn-github-actions/contexts#github-context)
        """
        return self._context

    @property
    def payload(self) -> dict:
        """The full webhook payload of the triggering event.

        References
        ----------
        - [GitHub Docs](https://docs.github.com/en/webhooks/webhook-events-and-payloads)
        """
        return self._payload

    @property
    def event_name(self) -> str:
        """The name of the triggering event, e.g. 'push', 'pull_request' etc."""
        return self.context["event_name"]

    @property
    def ref(self) -> str:
        """
        The full ref name of the branch or tag that triggered the event,
        e.g. 'refs/heads/main', 'refs/tags/v1.0' etc.
        """
        return self.context["ref"]

    @property
    def ref_name(self) -> str:
        """The short ref name of the branch or tag that triggered the event, e.g. 'main', 'dev/1' etc."""
        return self.context["ref_name"]

    @property
    def repo_owner(self) -> str:
        """GitHub username of the repository owner."""
        return self.context["repository_owner"]

    @property
    def repo_name(self) -> str:
        """Name of the repository."""
        return self.context["repository"].removeprefix(f"{self.repo_owner}/")

    @property
    def default_branch(self) -> str:
        return self.payload["repository"]["default_branch"]

    @property
    def ref_is_main(self) -> bool:
        return self.ref == f"refs/heads/{self.default_branch}"

    @property
    def hash_before(self) -> str:
        """The SHA hash of the most recent commit on the branch before the event."""
        if self.event_name == "push":
            return self.payload["before"]
        if self.event_name == "pull_request":
            return self.payload["pull_request"]["base"]["sha"]
        return self.git.commit_hash_normal()

    @property
    def hash_after(self) -> str:
        """The SHA hash of the most recent commit on the branch after the event."""
        if self.event_name == "push":
            return self.payload["after"]
        if self.event_name == "pull_request":
            return self.payload["pull_request"]["head"]["sha"]
        return self.git.commit_hash_normal()

    def run(self):
        event_handler = {
            "issue_comment": self.event_issue_comment,
            "issues": self.event_issues,
            "pull_request_review": self.event_pull_request_review,
            "pull_request_review_comment": self.event_pull_request_review_comment,
            "pull_request_target": self.event_pull_request_target,
            "schedule": self.event_schedule,
            "workflow_dispatch": self.event_workflow_dispatch,
            "pull_request": self.event_pull_request,
            "push": self.event_push,
        }
        if self.event_name not in event_handler:
            self.logger.error(f"Event '{self.event_name}' is not supported.")
        return event_handler[self.event_name]()

    def event_push(self):

        def ref_type() -> Literal["tag", "branch"]:
            if self.ref.startswith("refs/tags/"):
                return "tag"
            if self.ref.startswith("refs/heads/"):
                return "branch"
            self.logger.error(f"Invalid ref: {self.context['ref']}")

        def change_type() -> Literal["created", "deleted", "modified"]:
            if self.payload["created"]:
                return "created"
            if self.payload["deleted"]:
                return "deleted"
            return "modified"

        event_handler = {
            ("tag", "created"): self.event_push_tag_created,
            ("tag", "deleted"): self.event_push_tag_deleted,
            ("tag", "modified"): self.event_push_tag_modified,
            ("branch", "created"): self.event_push_branch_created,
            ("branch", "deleted"): self.event_push_branch_deleted,
            ("branch", "modified"): self.event_push_branch_modified,
        }
        return event_handler[(ref_type(), change_type())]()

    def event_push_tag_created(self):
        return None, None, None

    def event_push_tag_deleted(self):
        return None, None, None

    def event_push_tag_modified(self):
        return None, None, None

    def event_push_branch_created(self):
        if self.ref_is_main:
            if not self.last_ver:
                return self.event_repository_created()
            return None, None, None
        return None, None, None

    def event_push_branch_deleted(self):
        return None, None, None

    def event_push_branch_modified(self):
        if self.ref_is_main:
            return self.event_push_branch_modified_main()
        return None, None, None

    def event_push_branch_modified_main(self):
        self.metadata, self.metadata_ci = self.meta.read_metadata_full()


    def event_repository_created(self):
        for path_dynamic_file in self.meta.all_dynamic_paths:
            path_dynamic_file.unlink(missing_ok=True)
        for changelog_data in self.metadata["changelog"].values():
            path_changelog_file = Path(changelog_data["path"])
            path_changelog_file.unlink(missing_ok=True)
        self.git.commit(message="init: Create repository from RepoDynamics PyPackIT template", amend=True)
        return None, None, None

    def event_schedule(self):
        cron = self.payload["schedule"]
        schedule_type = self.metadata["workflow"]["init"]["schedule"]
        if cron == schedule_type["sync"]:
            return self.event_schedule_sync()
        if cron == schedule_type["test"]:
            return self.event_schedule_test()
        self.logger.error(
            f"Unknown cron expression for scheduled workflow: {cron}",
            f"Valid cron expressions defined in 'workflow.init.schedule' metadata are:\n"
            f"{schedule_type}"
        )
        return

    def event_schedule_sync(self):
        announcement = self.action_website_announcement_check()
        if announcement["status"] == "expired":
            self.action_website_announcement_update(announcement="null")

        return

    def event_schedule_test(self):
        return

    def event_workflow_dispatch(self):
        if self._website_announcement:
            self.action_website_announcement_update(announcement=self._website_announcement)
        return

    def action_website_announcement_check(self):
        name = "Website Announcement Expiry Check"
        path_announcement_file = Path(self.metadata["path"]["file"]["website_announcement"])
        if not path_announcement_file.exists():
            summary, section = self.get_action_summary(
                name=name,
                status="skip",
                oneliner="🚫 Announcement file does not exist.",
                details=html.ul(
                    [
                        f"❎ No changes were made.",
                        f"🚫 The announcement file was not found at '{path_announcement_file}'"
                    ]
                )
            )
            return summary, section
        with open(path_announcement_file) as f:
            current_announcement = f.read()
        (
            commit_date_relative,
            commit_date_absolute,
            commit_date_epoch,
            commit_details
        ) = (
            self.git.log(
                number=1,
                simplify_by_decoration=False,
                pretty=pretty,
                date=date,
                paths=str(path_announcement_file),
            ) for pretty, date in (
                ("format:%cd", "relative"),
                ("format:%cd", None),
                ("format:%cd", "unix"),
                (None, None),
            )
        )
        if not current_announcement:
            last_commit_details_html = html.details(
                content=md.code_block(commit_details),
                summary="📝 Removal Commit Details",
            )
            summary, section = self.get_action_summary(
                name=name,
                status="skip",
                oneliner="📭 No announcement to check.",
                details=html.ul(
                    [
                        f"❎ No changes were made."
                        f"📭 The announcement file at '{path_announcement_file}' is empty.\n",
                        f"📅 The last announcement was removed {commit_date_relative} on {commit_date_absolute}.\n",
                        last_commit_details_html,
                    ]
                )
            )
            return summary, section

        current_date_epoch = int(
            _util.shell.run_command(["date", "-u", "+%s"], logger=self.logger)
        )
        elapsed_seconds = current_date_epoch - int(commit_date_epoch)
        elapsed_days = elapsed_seconds / (24 * 60 * 60)
        retention_days = self.metadata["web"]["announcement_retention_days"]
        retention_seconds = retention_days * 24 * 60 * 60
        remaining_seconds = retention_seconds - elapsed_seconds
        remaining_days = retention_days - elapsed_days

        if remaining_seconds > 0:
            current_announcement_html = html.details(
                content=md.code_block(current_announcement, "html"),
                summary="📣 Current Announcement",
            )
            last_commit_details_html = html.details(
                content=md.code_block(commit_details),
                summary="📝 Current Announcement Commit Details",
            )
            summary, section = self.get_action_summary(
                name=name,
                status="skip",
                oneliner=f"📬 Announcement is still valid for another {remaining_days:.2f} days.",
                details=html.ul(
                    [
                        "❎ No changes were made.",
                        "📬 Announcement is still valid.",
                        f"⏳️ Elapsed Time: {elapsed_days:.2f} days ({elapsed_seconds} seconds)",
                        f"⏳️ Retention Period: {retention_days} days ({retention_seconds} seconds)",
                        f"⏳️ Remaining Time: {remaining_days:.2f} days ({remaining_seconds} seconds)",
                        current_announcement_html,
                        last_commit_details_html,
                    ]
                )
            )
            return summary, section

        with open(path_announcement_file, "w") as f:
            f.write("")
        commit_title = "Remove expired announcement"
        commit_body = (
            f"The following announcement made {commit_date_relative} on {commit_date_absolute} "
            f"was expired after {elapsed_days:.2f} days and thus automatically removed:\n\n"
            f"{current_announcement}"
        )
        commit_hash, commit_link = self.commit_website_announcement(
            commit_title=commit_title,
            commit_body=commit_body,
            change_title=commit_title,
            change_body=commit_body,
        )
        removed_announcement_html = html.details(
            content=md.code_block(current_announcement, "html"),
            summary="📣 Removed Announcement",
        )
        last_commit_details_html = html.details(
            content=md.code_block(commit_details),
            summary="📝 Removed Announcement Commit Details",
        )
        summary, section = self.get_action_summary(
            name=name,
            status="pass",
            oneliner="🗑 Announcement was expired and thus removed.",
            details=html.ul(
                [
                    f"✅ The announcement was removed (commit {html.a(commit_link, commit_hash)}).",
                    f"⌛ The announcement had expired {abs(remaining_days):.2f} days ({abs(remaining_seconds)} seconds) ago.",
                    f"⏳️ Elapsed Time: {elapsed_days:.2f} days ({elapsed_seconds} seconds)",
                    f"⏳️ Retention Period: {retention_days} days ({retention_seconds} seconds)",
                    removed_announcement_html,
                    last_commit_details_html,
                ]
            )
        )
        return summary, section

    def action_website_announcement_update(self):
        name = "Website Announcement Manual Update"
        announcement = self._website_announcement
        old_announcement = self.read_website_announcement().strip()
        old_announcement_details = self.git.log(
            number=1,
            simplify_by_decoration=False,
            pretty=None,
            date=None,
            paths=self.metadata["path"]["file"]["website_announcement"],
        )
        if announcement == "null":
            if not old_announcement:
                summary, section = self.get_action_summary(
                    name=name,
                    status="skip",
                    oneliner="🚫 No announcement to remove.",
                    details=html.ul(
                        [
                            f"❎ No changes were made.",
                            f"🚫 The 'null' string was passed to delete the current announcement, "
                            f"but the announcement file is already empty."
                        ]
                    )
                )
                return summary, section


            announcement = ""

        if announcement.strip() == old_announcement.strip():
            details_list = ["❎ No changes were made."]
            if not announcement:
                oneliner = "🚫 No announcement to remove."
                details_list.append(
                    "🚫 The announcement file is already empty."
                )
            else:
                details_list.append("🚫 The announcement is already up-to-date.")
            summary, section = self.get_action_summary(
                name=name,
                status="fail",
                oneliner="🚫 The new announcement is the same as the existing announcement.",
                details=html.ul(

                )
            )
            return summary, section
        self.write_website_announcement(announcement)
        commit_title = "Manually update announcement"
        commit_hash, commit_url = self.commit_website_announcement(
            commit_title=commit_title,
            commit_body=self._website_announcement_msg,
            change_title=commit_title,
            change_body=self._website_announcement_msg,
        )

        new_announcement_html = html.details(
            content=md.code_block(announcement, "html"),
            summary="📣 New Announcement",
        )

        summary, section = self.get_action_summary(
            name="Website Announcement Manual Update",
            status="pass",
            oneliner="📝 Announcement was manually updated.",
            details=html.ul(
                [
                    f"✅ The announcement was manually updated (commit {html.a(commit_url, commit_hash)}).",
                    f"📝 New Announcement:\n{announcement}",
                ]
            )
        )
        return summary, section

    def write_website_announcement(self, announcement: str):
        if announcement:
            announcement = f"{announcement.strip()}\n"
        with open(self.metadata["path"]["file"]["website_announcement"], "w") as f:
            f.write(announcement)
        return

    def read_website_announcement(self) -> str:
        with open(self.metadata["path"]["file"]["website_announcement"]) as f:
            return f.read()

    def commit_website_announcement(
        self,
        commit_title: str,
        commit_body: str,
        change_title: str,
        change_body: str,
    ):
        changelog_id = self.metadata["commit"]["primary"]["website"]["announcement"]["changelog_id"]
        if changelog_id:
            changelog_manager = ChangelogManager(
                changelog_metadata=self.metadata["changelog"],
                ver_dist=f"{self.last_ver}+{self.dist_ver}",
                commit_type=self.metadata["commit"]["primary"]["website"]["type"],
                commit_title=commit_title,
                parent_commit_hash=self.hash_after,
                parent_commit_url=f"https://github.com/{self.repo_owner}/{self.repo_name}/commit/{self.hash_after}"
            )
            changelog_manager.add_change(
                changelog_id=changelog_id,
                section_id=self.metadata["commit"]["primary"]["website"]["announcement"]["changelog_section_id"],
                change_title=change_title,
                change_details=change_body,
            )
            changelog_manager.write_all_changelogs()
        commit = CommitMsg(
            typ=self.metadata["commit"]["primary"]["website"]["type"],
            title=commit_title,
            body=commit_body,
            scope=self.metadata["commit"]["primary"]["website"]["announcement"]["scope"]
        )
        commit_hash = self.git.commit(message=str(commit), stage='all')
        commit_link = f"https://github.com/{self.repo_owner}/{self.repo_name}/commit/{commit_hash}"
        return commit_hash, commit_link

    def get_changed_files(self) -> list[str]:
        filepaths = []
        changes = self.git.changed_files(ref_start=self.hash_before, ref_end=self.hash_after)
        for change_type, changed_paths in changes.items():
            if change_type in ["unknown", "broken"]:
                self.logger.warning(
                    f"Found {change_type} files",
                    f"Running 'git diff' revealed {change_type} changes at: {changed_paths}. "
                    "These files will be ignored."
                )
                continue
            if change_type.startswith("copied") and change_type.endswith("from"):
                continue
            filepaths.extend(changed_paths)
        return filepaths

    def get_commits(self):
        commits = self.git.get_commits(f"{self.hash_before}..{self.hash_after}")
        for commit in commits:
            conventional_commit = rd.commits.parse(msg=commit["message"], types=types, logger=self._logger)

    def get_latest_version(self) -> tuple[PEP440SemVer | None, int | None]:
        tags_lists = self.git.get_tags()
        if not tags_lists:
            return None, None
        ver_tag_prefix = self.metadata["tag"]["group"]["version"]["prefix"]
        for tags_list in tags_lists:
            ver_tags = []
            for tag in tags_list:
                if tag.startswith(ver_tag_prefix):
                    ver_tags.append(tag.removeprefix(ver_tag_prefix))
            if ver_tags:
                max_version = max(PEP440SemVer(ver_tag) for ver_tag in ver_tags)
                distance = self.git.get_distance(ref_start=f"refs/tags/{ver_tag_prefix}{max_version.input}")
                return max_version, distance
        self.logger.error(f"No version tags found with prefix '{ver_tag_prefix}'.")

    def assemble_summary(self, intro: str, oneliners: list[str], sections: list[str]):
        github_context, event_payload = (
            html.details(
                content=md.code_block(
                    YAML(typ=['rt', 'string']).dumps(dict(sorted(data.items())), add_final_eol=True),
                    "yaml"
                ),
                summary=summary,
            ) for data, summary in (
                (self.context, "🎬 GitHub Context"), (self.payload, "📥 Event Payload")
            )
        )
        return html.ElementCollection(
            [
                html.h(1, "Workflow Report"),
                intro,
                html.ul([github_context, event_payload]),
                html.h(2, "🏁 Summary"),
                html.ul(oneliners),
                *sections,
            ]
        )

    def get_action_summary(
        self,
        name: str,
        status: Literal['pass', 'fail', 'skip'],
        oneliner: str,
        details: str | html.Element | html.ElementCollection
    ):
        emoji = {
            "pass": "✅",
            "fail": "❌",
            "skip": "❎",
        }
        summary = f"{emoji[status]} <b>{name}</b>: {oneliner}"
        section = f"## {name}\n\n{details}\n\n"
        return summary, section


def init(
    context: dict,
    admin_token: str = "",
    package_build: bool = False,
    package_lint: bool = False,
    package_test: bool = False,
    website_build: bool = False,
    website_announcement: str = "",
    website_announcement_msg: str = "",
    logger=None
):
    return Init(
        context=context,
        admin_token=admin_token,
        package_build=package_build,
        package_lint=package_lint,
        package_test=package_test,
        website_build=website_build,
        website_announcement=website_announcement,
        website_announcement_msg=website_announcement_msg,
        logger=logger,
    ).run()


def pull_post_process(pull):
    pr_nr = pull["pull-request-number"]
    pr_url = pull["pull-request-url"]
    pr_head_sha = pull["pull-request-head-sha"]


class EventHandler:

    def __init__(self, context: dict):
        self._latest_version = self._git.describe()
        self._output_meta: dict = {}
        self._output_hooks: dict = {}
        return

    def _update_meta(self, action: Literal['fail', 'amend', 'commit']):
        self._output_meta = meta.update(
            action="report" if action == "fail" else action,
            github_token=self._context["token"],
            logger=self._logger,
        )
        if action == "fail" and not self._output_meta["passed"]:
            self._logger.error("Dynamic files are not in sync.")
        self._metadata = self._output_meta["metadata"]
        return

    def _update_hooks(self, action: Literal['fail', 'amend', 'commit'], ref_range: Optional[tuple[str, str]] = None):
        self._output_hooks = hooks.run(
            action="report" if action == "fail" else action,
            ref_range=ref_range,
            path_config=self._metadata["workflow_hooks_config_path"],
            logger=self._logger,
        )
        if action == "fail" and not self._output_hooks["passed"]:
            self._logger.error("Hooks failed.")
        return

    def assemble_summary(self):
        sections = [
            html.h(2, "Summary"),
            self.summary,
        ]
        if self.changes:
            sections.append(self.changed_files())
        for job, summary_filepath in zip(
            (self.meta, self.hooks),
            (".local/reports/repodynamics/meta.md", ".local/reports/repodynamics/hooks.md")
        ):
            if job:
                with open(summary_filepath) as f:
                    sections.append(f.read())
        return html.ElementCollection(sections)

    def changed_files_summary(self):
        summary = html.ElementCollection(
            [
                html.h(2, "Changed Files"),
            ]
        )
        for group_name, group_attrs in self.changes.items():
            if group_attrs["any_modified"] == "true":
                summary.append(
                    html.details(
                        content=md.code_block(json.dumps(group_attrs, indent=4), "json"),
                        summary=group_name,
                    )
                )
            # group_summary_list.append(
            #     f"{'✅' if group_attrs['any_modified'] == 'true' else '❌'}  {group_name}"
            # )
        file_list = "\n".join(sorted(self.changes["all"]["all_changed_and_modified_files"].split()))
        # Write job summary
        summary.append(
            html.details(
                content=md.code_block(file_list, "bash"),
                summary="🖥 Changed Files",
            )
        )
        # details = html.details(
        #     content=md.code_block(json.dumps(all_groups, indent=4), "json"),
        #     summary="🖥 Details",
        # )
        # log = html.ElementCollection(
        #     [html.h(4, "Modified Categories"), html.ul(group_summary_list), changed_files, details]
        # )
        return summary


class Push(EventHandler):
    """
    References
    ----------
    - [GitHub Docs: Webhook events & payloads](https://docs.github.com/en/webhooks/webhook-events-and-payloads#push)
    """

    def __init__(self, context: dict):
        super().__init__(context)
        self._changes = self._get_changed_files()
        self._commits = self._get_commits()
        self._head_commit_msg: str = self.payload["head_commit"]["message"]
        return

    @property
    def changed_files(self) -> list[str]:
        """List of changed files."""
        return self._changes

    def _get_tags(self):
        return


class PushRelease(Push):

    def __init__(self, context: dict, changes: dict):
        super().__init__(context, changes)

        self._head_commit_conv: dict = self._parse_commit_msg(self._head_commit_msg)
        if not self._head_commit_conv:
            self._logger.error(f"Invalid commit message: {self._head_commit_msg}")


        self._output = {
            "config-repo": False,

        }
        self._version_new = None
        return

    def _determine_commit_type(self):
        if self._head_commit_conv["breaking"]:
            return "release_major"


        return


    def run(self):
        self._update_meta(action="report")
        if not self._output_meta["passed"]:
            self._logger.error("Dynamic files are not in sync .")

        semver_tag: tuple[int, int, int] | None = self._git.describe()
        if not semver_tag:
            return self._run_initial_release()

        if commit_msg.startswith("feat"):
            release = True
            self._tag = f"v{semver_tag[0]}.{semver_tag[1] + 1}.0"
        elif commit_msg.startswith("fix"):
            release = "patch"
            self._tag = f"v{semver_tag[0]}.{semver_tag[1]}.{semver_tag[2] + 1}"

        output = {
            "hash": self._tag,
            "publish": True,
            "docs": True,
            "website_url": self._metadata['url']['website']['base'],
            "name": self._metadata['name']
        }
        return output, None, None

    def _run_initial_release(self):
        self._tag = "v0.0.0"
        self._create_changelog()
        self._git.commit(
            stage='all',
            amend=True,
        )
        self._git.push(force_with_lease=True)
        self._git.create_tag(tag="v0.0.0", message="Initial Release")
        output = {
            "hash": self._tag,
            "publish": True,
            "docs": True,
            "website_url": self._metadata['url']['website']['base'],
            "name": self._metadata['name']
        }
        self._create_release_notes()
        return output, None, None

    def _create_changelog(self):
        changelog = f"""# Changelog
This document tracks all changes to the {self._metadata['name']} public API.

## [{self._metadata['name']} {self._tag.removesuffix('v')}]({self._metadata['url']['github']['releases']['home']}/tag/{self._tag})
This is the initial release of the project. Infrastructure is now in place to support future releases.
"""
        with open("CHANGELOG.md", "w") as f:
            f.write(changelog)
        return

    def _create_release_notes(self):
        path = Path(".local/temp/repodynamics/release_notes.md")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write(f"[{self._metadata['name']} {self._tag.removesuffix('v')}]({self._metadata['url']['github']['releases']['home']}/tag/{self._tag})")
        return

    def _create_changelog_entry(self):
        log = f"""## [{self._metadata['name']} {self._tag}]()"""

        return


class PushMain(PushRelease):

    def __init__(self, context: dict, admin_token: str = ""):
        super().__init__(context)
        self._admin_token = admin_token
        return

    def update_repo_settings(self):
        data = self._meta["repo"]["config"] | {
            "has_issues": True,
            "allow_squash_merge": True,
            "squash_merge_commit_title": "PR_TITLE",
            "squash_merge_commit_message": "PR_BODY",
        }
        topics = data.pop("topics")
        admin_api = pylinks.api.github(token=self._admin_token).user(self.repo_owner).repo(self.repo_name)
        admin_api.update_settings(settings=data)
        admin_api.replace_topics(topics=topics)
        return


class PushDev(Push):

    def __init__(self, context: dict, changes: dict):
        super().__init__(context, changes)
        issue_nr = self.ref_name.removeprefix("dev/")
        if not issue_nr.isdigit():
            self._logger.error(f"Invalid branch name: {self.ref_name}")
        self._issue_nr = int(issue_nr)
        try:
            self._issue = self._api.issue(self._issue_nr)
        except pylinks.http.WebAPIStatusCodeError as e:
            if e.status_code == 404:
                self._logger.error(f"Invalid issue number: {self._issue_nr}")
            else:
                self._logger.error(f"Could not retrieve issue data", e)
        if self._issue['state'] != 'open':
            self._logger.error(f"Issue #{self._issue_nr} is not open.")
        self._issue_type = self.issue_type()
        return

    def issue_type(self):
        type_labels = []
        for label in self._issue["labels"]:
            if label["name"].startswith("Type: "):
                type_labels.append(label["name"])
        if len(type_labels) == 0:
            self._logger.error(f"Could not determine issue type for issue #{self._issue_nr}")
        elif len(type_labels) > 1:
            self._logger.error(f"Found multiple issue types for issue #{self._issue_nr}: {type_labels}")
        return type_labels[0].removeprefix("Type: ")

    def run(self):
        summary = html.ElementCollection()
        output = {
            "package_test": self.package_test_needed,
            "package_lint": self.package_lint_needed,
            "docs": self.docs_test_needed,
        }
        if self._changes["meta"]["any_modified"] == "true":
            self._update_meta(action=self)
            summary.append(self._output_meta["summary"])
            if self._output_meta["changes"].get("package"):
                output["package_test"] = True
                output["package_lint"] = True
                output["docs"] = True
            if self._output_meta["changes"].get("metadata"):
                output["docs"] = True
            self._metadata = self._output_meta["metadata"]
            hash_after = self._output_meta["commit_hash"] or hash_after

        if self._metadata.get("workflow_hooks_config_path"):
            self._update_hooks(action="commit", ref_range=(self._hash_before, self._hash_after))
            summary.append(self._output_hooks["summary"])
        else:
            self._logger.attention("No workflow hooks config path set in metadata.")


        output["hash"] = self._git.push()
        return output, None, str(summary)

    @property
    def package_test_needed(self):
        return any(
            self._changes[group]["any_modified"] == "true"
            for group in ["src", "tests", "setup-files", "workflow"]
        )

    @property
    def package_lint_needed(self):
        for group in ["src", "setup-files", "workflow"]:
            if self._changes[group]["any_modified"] == "true":
                return True
        return False

    @property
    def docs_test_needed(self):
        return any(
            self._changes[group]["any_modified"] == "true"
            for group in ["src", "docs-website", "workflow"]
        )


class InitialRelease(EventHandler):

    def __init__(self, context: dict):
        super().__init__(context)
        return

    def run(self):
        return


class Pull(EventHandler):

    def __init__(self, context: dict, changes: dict):
        super().__init__(context)



        self._changes = self._process_changes(changes)
        self._output = {}
        return

    def run(self):
        self._update_meta(action="report")
        self._update_hooks(action="report", ref_range=(hash_before, hash_after))
        return

    @property
    def info(self) -> dict:
        return self.payload["pull_request"]

    @property
    def label_names(self):
        return [label["name"] for label in self.info["labels"]]

    @property
    def triggering_action(self) -> str:
        """Pull-request action type that triggered the event, e.g. 'opened', 'closed', 'reopened' etc."""
        return self.payload["action"]

    @property
    def number(self) -> int:
        """Pull-request number."""
        return self.payload["number"]

    @property
    def head(self) -> dict:
        """Pull request's head branch info."""
        return self.info["head"]

    @property
    def base(self) -> dict:
        """Pull request's base branch info."""
        return self.info["base"]

    @property
    def internal(self) -> bool:
        """Whether the pull request is internal, i.e. within the same repository."""
        return self.head["repo"]["full_name"] == self._context["repository"]

    @property
    def body(self) -> str | None:
        """Pull request body."""
        return self.info["body"]

    @property
    def title(self) -> str:
        """Pull request title."""
        return self.info["title"]

    @property
    def state(self) -> Literal["open", "closed"]:
        """Pull request state; either 'open' or 'closed'."""
        return self.info["state"]

    @property
    def merged(self) -> bool:
        """Whether the pull request is merged."""
        return self.state == 'closed' and self.info["merged"]

    @property
    def head_repo(self):
        return self.head["repo"]["full_name"]

    @property
    def head_sha(self):
        return self.head["sha"]


class Issue(EventHandler):

    def __init__(self, context: dict):
        super().__init__(context)
        self._output = {}
        return

    def run(self):
        return


class IssueComment(EventHandler):

    def __init__(self, context: dict):
        super().__init__(context)
        self._output = {}
        return

    def run(self):
        self.run_commands()
        return

    def run_commands(self):
        runner = {
            "test-package": self.command_test_package,
        }
        command, kwargs = self.find_command()
        if not command:
            return
        if command not in runner:
            self._logger.error(f"Command '{command}' is not supported.")
            return
        runner[command](**kwargs)
        return

    def command_test_package(self, operating_systems):
        pass

    def find_command(self) -> tuple[str, dict]:
        pattern_general = r"""
        ^@RepoDynamicsBot[ ]     # Matches the string at the start of a line with a space after "Bot"
        (?P<command>[^\n]+)      # Captures the command until a new line
        \n                       # Matches the newline character after the command
        (?P<arguments>.*)        # Captures everything that comes after the newline
        """
        command_match = re.search(pattern_general, self.comment_body, re.MULTILINE | re.DOTALL | re.VERBOSE)
        if not command_match:
            return "", {}
        pattern_arguments = r"""
        (?P<key>[a-zA-Z][a-zA-Z0-9_-]*)  # Captures the key
        :[ \t]*                          # Colon separator, possibly followed by spaces/tabs
        (?:
            `(?P<value1>[^`]+)`          # Value enclosed in backticks, capturing at least one character
            |                            # OR
            \n```[\w-]*\s*                 # Captures the optional language specifier
            (?P<value2>.+?)              # Captures the content of the multiline code block non-greedily
            \n```                          # Ending delimiter of the multiline code block
        )
        """
        kv_dict = {
            match.group("key"): match.group("value1") or match.group("value2")
            for match in re.finditer(
                pattern_arguments, command_match.group("arguments"), re.MULTILINE | re.DOTALL | re.VERBOSE
            )
        }
        return command_match.group("command"), kv_dict

    @property
    def triggering_action(self) -> str:
        """Comment action type that triggered the event; one of 'created', 'deleted', 'edited'."""
        return self.payload["action"]

    @property
    def comment(self) -> dict:
        """Comment data."""
        return self.payload["comment"]

    @property
    def comment_body(self) -> str:
        """Comment body."""
        return self.comment["body"]

    @property
    def comment_id(self) -> int:
        """Unique identifier of the comment."""
        return self.comment["id"]

    @property
    def commenter(self) -> str:
        """Commenter username."""
        return self.comment["user"]["login"]

    @property
    def issue(self) -> dict:
        """Issue data."""
        return self.payload["issue"]


class Dispatch(EventHandler):

    def __init__(self, context: dict):
        super().__init__(context)
        self._output = {"pull": True}
        return

    def run(self):
        summary = html.ElementCollection()
        self._update_meta(action="commit")
        summary.append(self._output_meta["summary"])
        if self._metadata.get("workflow_hooks_config_path"):
            self._update_hooks(action="commit")
            summary.append(self._output_hooks["summary"])
        self._create_pull_body()
        return self._output, None, str(summary)

    def _create_pull_body(self):
        path = Path(".local/temp/repodynamics/init/pr_body.md")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write("Automatically update all metadata and dynamic files.\nRun hooks.")
        return





def _finalize(
    context: dict,
    changes: dict,
    meta_changes: dict,
    commit_meta: bool,
    hooks_check: str,
    hooks_fix: str,
    commit_hooks: bool,
    push_ref: str,
    pull_number: str,
    pull_url: str,
    pull_head_sha: str,
    logger: Logger = None,
) -> tuple[dict, str]:
    """
    Parse outputs from `actions/changed-files` action.

    This is used in the `repo_changed_files.yaml` workflow.
    It parses the outputs from the `actions/changed-files` action and
    creates a new output variable `json` that contains all the data,
    and writes a job summary.
    """
    job_summary = html.ElementCollection()

    job_summary.append(html.h(2, "Metadata"))

    with open("meta/.out/metadata.json") as f:
        metadata_dict = json.load(f)

    job_summary.append(
        html.details(
            content=md.code_block(json.dumps(metadata_dict, indent=4), "json"),
            summary=" 🖥  Metadata",
        )
    )

    job_summary.append(
        html.details(
            content=md.code_block(json.dumps(summary_dict, indent=4), "json"),
            summary=" 🖥  Summary",
        )
    )

    force_update_emoji = "✅" if force_update == "all" else ("❌" if force_update == "none" else "☑️")
    cache_hit_emoji = "✅" if cache_hit else "❌"
    if not cache_hit or force_update == "all":
        result = "Updated all metadata"
    elif force_update == "core":
        result = "Updated core metadata but loaded API metadata from cache"
    else:
        result = "Loaded all metadata from cache"

    results_list = html.ElementCollection(
        [
            html.li(f"{force_update_emoji}  Force update (input: {force_update})", content_indent=""),
            html.li(f"{cache_hit_emoji}  Cache hit", content_indent=""),
            html.li(f"➡️  {result}", content_indent=""),
        ],
    )
    log = f"<h2>Repository Metadata</h2>{metadata_details}{results_list}"

    return {"json": json.dumps(all_groups)}, str(log)


    def _summary(self, changes):
        results = []
        if not changes["any"]:
            results.append(
                html.li("✅ All dynamic files are in sync with meta content.")
            )
        else:
            emoji = "🔄" if self._applied else "❌"
            results.append(
                html.li(f"{emoji} Following groups were out of sync with source files:")
            )
            results.append(
                html.ul([self._categories[category] for category in self._categories if changes[category]])
            )
            if self._applied:
                results.append(
                    html.li("✏️ Changed files were updated successfully.")
                )
            if self._commit_hash:
                results.append(
                    html.li(f"✅ Updates were committed with commit hash '{self._commit_hash}'.")
                )
            else:
                results.append(html.li(f"❌ Commit mode was not selected; updates were not committed."))
        summary = html.ElementCollection(
            [
                html.h(2, "Meta"),
                html.h(3, "Summary"),
                html.ul(results),
                html.h(3, "Details"),
                self._color_legend(),
                self._summary_section_details(),
                html.h(3, "Log"),
                html.details(self._logger.file_log, "Log"),
            ]
        )
        return summary



def find_command(comment: str) -> tuple[str, dict] | None:
    """
    Find and parse a RepoDynamicsBot command in a comment.

    The comment must only contain one command.
    The command must start with '@RepoDynamicsBot ' at the beginning of a line,
    followed by the command. If the command requires input arguments, they must
    be given in the next line(s).

    Parameters
    ----------
    comment : str

    Returns
    -------
    command, kwargs : tuple[str, dict]

    Examples
    --------
    A sample comment:

    @RepoDynamicsBot test
    operating-systems: `['ubuntu-latest', 'windows-latest']`
    python-versions: `['3.11', '3.10']`
    run:
    ```python
    import package
    print(package.__version__)
    ```

    """
    pattern_general = r"""
    ^@RepoDynamicsBot[ ]     # Matches the string at the start of a line with a space after "Bot"
    (?P<command>[^\n]+)      # Captures the command until a new line
    \n                       # Matches the newline character after the command
    (?P<arguments>.*)        # Captures everything that comes after the newline in a group called "arguments"
    """
    command_match = re.search(pattern_general, comment, re.MULTILINE | re.DOTALL | re.VERBOSE)
    if not command_match:
        return
    pattern_arguments = r"""
        (?P<key>[a-zA-Z][a-zA-Z0-9_-]*)  # Captures the key
        :[ \t]*                          # Colon separator, possibly followed by spaces/tabs
        (?:
            `(?P<value1>[^`]+)`          # Value enclosed in backticks, capturing at least one character
            |                            # OR
            \n```[\w-]*\s*                 # Captures the optional language specifier
            (?P<value2>.+?)              # Captures the content of the multiline code block non-greedily
            \n```                          # Ending delimiter of the multiline code block
        )
        """
    kv_matches = re.finditer(
        pattern_arguments, command_match.group("arguments"), re.MULTILINE | re.DOTALL | re.VERBOSE
    )
    kv_dict = {}
    for match in kv_matches:
        kv_dict[match.group("key")] = match.group("value1") or match.group("value2")
    return command_match.group("command"), kv_dict