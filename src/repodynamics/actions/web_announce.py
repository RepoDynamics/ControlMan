from markitup import html, md


class WebAnnouncement:

    def __init__(self, release):
        self.release = release

    def action_website_announcement_check(self):
        name = "Website Announcement Expiry Check"
        path_announcement_file = Path(self.metadata["path"]["file"]["website_announcement"])
        if not path_announcement_file.exists():
            self.add_summary(
                name=name,
                status="skip",
                oneliner="Announcement file does not exist❗",
                details=html.ul(
                    [
                        f"❎ No changes were made.",
                        f"🚫 The announcement file was not found at '{path_announcement_file}'",
                    ]
                ),
            )
            return
        with open(path_announcement_file) as f:
            current_announcement = f.read()
        (commit_date_relative, commit_date_absolute, commit_date_epoch, commit_details) = (
            self.git.log(
                number=1,
                simplify_by_decoration=False,
                pretty=pretty,
                date=date,
                paths=str(path_announcement_file),
            )
            for pretty, date in (
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
            self.add_summary(
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
                ),
            )
            return

        current_date_epoch = int(_util.shell.run_command(["date", "-u", "+%s"], logger=self.logger))
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
            self.add_summary(
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
                ),
            )
            return

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
        self.add_summary(
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
            ),
        )
        return

    def action_website_announcement_update(self):
        name = "Website Announcement Manual Update"
        self.logger.h1(name)
        if not self.ref_is_main:
            self.add_summary(
                name=name,
                status="skip",
                oneliner="Announcement can only be updated from the main branch❗",
            )
            self.logger.warning("Announcement can only be updated from the main branch; skip❗")
            return
        announcement = self._website_announcement
        self.logger.input(f"Read announcement from workflow dispatch input: '{announcement}'")
        if not announcement:
            self.add_summary(
                name=name,
                status="skip",
                oneliner="No announcement was provided.",
            )
            self.logger.skip("No announcement was provided.")
            return
        old_announcement = self.read_website_announcement().strip()
        old_announcement_details = self.git.log(
            number=1,
            simplify_by_decoration=False,
            pretty=None,
            date=None,
            paths=self.metadata["path"]["file"]["website_announcement"],
        )
        old_md = md.code_block(old_announcement_details)

        if announcement == "null":
            announcement = ""

        if announcement.strip() == old_announcement.strip():
            details_list = ["❎ No changes were made."]
            if not announcement:
                oneliner = "No announcement to remove❗"
                details_list.extend(
                    [
                        f"🚫 The 'null' string was passed to delete the current announcement, "
                        f"but the announcement file is already empty.",
                        html.details(content=old_md, summary="📝 Last Removal Commit Details"),
                    ]
                )
            else:
                oneliner = "The provided announcement was identical to the existing announcement❗"
                details_list.extend(
                    [
                        "🚫 The provided announcement was the same as the existing one.",
                        html.details(content=old_md, summary="📝 Current Announcement Commit Details"),
                    ]
                )
            self.add_summary(name=name, status="skip", oneliner=oneliner, details=html.ul(details_list))
            return
        self.write_website_announcement(announcement)
        new_html = html.details(
            content=md.code_block(announcement, "html"),
            summary="📣 New Announcement",
        )
        details_list = []
        if not announcement:
            oneliner = "Announcement was manually removed 🗑"
            details_list.extend(
                [
                    f"✅ The announcement was manually removed.",
                    html.details(content=old_md, summary="📝 Removed Announcement Details"),
                ]
            )
            commit_title = "Manually remove announcement"
            commit_body = f"Removed announcement:\n\n{old_announcement}"
        elif not old_announcement:
            oneliner = "A new announcement was manually added 📣"
            details_list.extend([f"✅ A new announcement was manually added.", new_html])
            commit_title = "Manually add new announcement"
            commit_body = announcement
        else:
            oneliner = "Announcement was manually updated 📝"
            details_list.extend(
                [
                    f"✅ The announcement was manually updated.",
                    new_html,
                    html.details(content=old_md, summary="📝 Old Announcement Details"),
                ]
            )
            commit_title = "Manually update announcement"
            commit_body = f"New announcement:\n\n{announcement}\n\nRemoved announcement:\n\n{old_announcement}"

        commit_hash, commit_url = self.commit_website_announcement(
            commit_title=commit_title,
            commit_body=commit_body,
            change_title=commit_title,
            change_body=commit_body,
        )
        details_list.append(f"✅ Changes were applied (commit {html.a(commit_url, commit_hash)}).")
        self.add_summary(name=name, status="pass", oneliner=oneliner, details=html.ul(details_list))
        return

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
        changelog_id = self.metadata["commit"]["primary"]["website"]["announcement"].get("changelog_id")
        if changelog_id:
            changelog_manager = ChangelogManager(
                changelog_metadata=self.metadata["changelog"],
                ver_dist=f"{self.last_ver}+{self.dist_ver}",
                commit_type=self.metadata["commit"]["primary"]["website"]["type"],
                commit_title=commit_title,
                parent_commit_hash=self.hash_after,
                parent_commit_url=str(self.gh_link.commit(self.hash_after)),
            )
            changelog_manager.add_change(
                changelog_id=changelog_id,
                section_id=self.metadata["commit"]["primary"]["website"]["announcement"][
                    "changelog_section_id"
                ],
                change_title=change_title,
                change_details=change_body,
            )
            changelog_manager.write_all_changelogs()
        commit = CommitMsg(
            typ=self.metadata["commit"]["primary"]["website"]["type"],
            title=commit_title,
            body=commit_body,
            scope=self.metadata["commit"]["primary"]["website"]["announcement"]["scope"],
        )
        commit_hash = self.commit(message=str(commit), stage="all")
        commit_link = str(self.gh_link.commit(commit_hash))
        self._hash_latest = commit_hash
        return commit_hash, commit_link