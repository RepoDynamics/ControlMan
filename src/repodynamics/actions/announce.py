import subprocess

from markitup import html, md


class Announcement:
    def __init__(self, retention_days: int, announcement: str, description: str, logger=None):
        if announcement or description:
            if not (announcement and description):
                logger.error("`announcement` and `description` must be provided together.")
        self.retention_days = retention_days
        self.announcement = announcement
        self.description = description
        self.filepath = "announcement.html"
        with open(self.filepath) as f:
            self.current_announcement = f.read()
        self.current_announcement_code_block = md.code_block(self.current_announcement, "html")
        self.new_announcement_code_block = md.code_block(self.announcement, "html")
        self.output = {"commit_message": ""}
        self.summary = html.ElementCollection()
        return

    def run(self):
        return self.update() if self.announcement else self.check()

    def check(self):
        self.summary.append(html.h(2, "Announcement Expiry Check"))
        self.summary.append(html.h(3, "🏁 Results"))

        last_commit_date_relative = subprocess.run(
            ["git", "log", "-1", "--format=%cd", "--date=relative", self.filepath], capture_output=True
        ).stdout.decode().strip()
        last_commit_date_abs = subprocess.run(
            ["git", "log", "-1", "--format=%cd", self.filepath], capture_output=True
        ).stdout.decode().strip()
        last_commit_details = subprocess.run(
            ["git", "log", "-1", self.filepath], capture_output=True
        ).stdout.decode().strip()

        if not self.current_announcement:
            self.summary.extend(
                [
                    "✅ 📭 No announcement to check.",
                    html.h(3, "ℹ️ Details"),
                    f"📅 The last announcement was removed {last_commit_date_relative} "
                    f"on {last_commit_date_abs}:",
                    md.code_block(last_commit_details),
                ]
            )
            return self.output, None, str(self.summary)

        last_commit_epoch_time = int(
            subprocess.run(
                ["git", "log", "-1", "--format=%cd", "--date=unix", self.filepath], capture_output=True
            ).stdout.decode().strip()
        )
        current_epoch_time = int(
            subprocess.run(
                ["date", "-u", "+%s"], capture_output=True
            ).stdout.decode().strip()
        )
        elapsed_seconds = current_epoch_time - last_commit_epoch_time
        retention_seconds = self.retention_days * 24 * 60 * 60
        elapsed_days = elapsed_seconds / (24 * 60 * 60)
        remaining_days = self.retention_days - elapsed_days
        if elapsed_seconds > retention_seconds:
            self.output["commit_message"] = (
                "website(announcement): expire\n\n"
                f"Expired announcement:\n{self.current_announcement}\n\n"
                f"Retention period: {self.retention_days} days\n"
                f"Elapsed: {elapsed_days:.2f} days"
            )
            self.summary.append("✅ 🗑 Announcement was expired and removed.")
        else:
            self.summary.append(
                f"❎ 📬 Announcement is still valid. It will expire in {remaining_days:.2f} days."
            )
        self.summary.extend(
            [
                html.h(3, "ℹ️ Details"),
                html.h(4, "📣 Announcement"),
                self.current_announcement_code_block,
                html.h(4, "📝 Commit Details"),
                md.code_block(last_commit_details),
                html.h(4, "⏳️ Retention Period"),
                html.ul(
                    [
                        f"Allowed: {self.retention_days} days ({retention_seconds} seconds)",
                        f"Elapsed: {elapsed_days:.2f} days ({elapsed_seconds} seconds)",
                    ]
                )
            ]
        )
        return self.output, None, str(self.summary)

    def update(self):
        if self.announcement == "null":
            self.announcement = ""
        with open(self.filepath, "w") as f:
            f.write(self.announcement)
        self.output["commit_message"] = (
            "website(announcement): update\n\n"
            f"Updated announcement:\n{self.announcement}\n\n"
            f"{self.description}"
        )
        self.summary.extend(
            [
                html.h(2, "Announcement Update"),
                html.h(3, "📣 New Announcement"),
                self.new_announcement_code_block,
                html.h(3, "ℹ️ Details"),
                self.description
            ]
        )
        return self.output, None, str(self.summary)


def announce(
    retention_days: int = 30,
    announcement: str = "",
    description: str = "",
    logger=None,
):
    return Announcement(
        retention_days=retention_days,
        announcement=announcement,
        description=description,
        logger=logger
    ).run()
