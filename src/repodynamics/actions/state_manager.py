from typing import Literal

from ruamel.yaml import YAML
from markitup import html, md

from repodynamics.git import Git
from repodynamics.version import PEP440SemVer
from repodynamics.datatype import Emoji
from repodynamics.logger import Logger
from repodynamics.actions.context import ContextManager
from repodynamics.meta.manager import MetaManager


class StateManager:
    def __init__(
        self,
        metadata_main: MetaManager,
        metadata_branch: MetaManager,
        context_manager: ContextManager,
        git: Git,
        logger: Logger | None = None,

    ):
        self._metadata_main = metadata_main
        self._metadata_branch = metadata_branch
        self._git = git
        self._context = context_manager
        self._logger = logger or Logger()

        self._run_job = {
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
        }
        self._release_info = {
            "name": "",
            "body": "",
            "prerelease": False,
            "make_latest": "legacy",
        }
        self._summary_oneliners: list[str] = []
        self._summary_sections: list[str | html.ElementCollection | html.Element] = []
        self._amended: bool = False
        self._tag: str = ""
        self._version: str = ""
        self._failed = False
        self._hash_latest: str = ""
        return

    def commit(
        self,
        message: str = "",
        stage: Literal["all", "staged", "unstaged"] = "all",
        amend: bool = False,
        push: bool = False,
        set_upstream: bool = False,
    ):
        commit_hash = self._git.commit(message=message, stage=stage, amend=amend)
        if amend:
            self._amended = True
        if push:
            commit_hash = self.push(set_upstream=set_upstream)
        return commit_hash

    def push(self, amend: bool = False, set_upstream: bool = False):
        new_hash = self._git.push(
            target="origin", set_upstream=set_upstream, force_with_lease=self._amended or amend
        )
        self._amended = False
        if new_hash and self._git.current_branch_name() == self._context.ref_name:
            self._hash_latest = new_hash
        return new_hash

    def tag_version(self, ver: str | PEP440SemVer, msg: str = ""):
        tag_prefix = self._metadata_main.dict["tag"]["group"]["version"]["prefix"]
        tag = f"{tag_prefix}{ver}"
        if not msg:
            msg = f"Release version {ver}"
        self._git.create_tag(tag=tag, message=msg)
        self._tag = tag
        self._version = str(ver)
        return

    def switch_to_ci_branch(self, typ: Literal["hooks", "meta"]):
        current_branch = self._git.current_branch_name()
        new_branch_prefix = self._metadata_main.dict["branch"]["group"]["ci_pull"]["prefix"]
        new_branch_name = f"{new_branch_prefix}{current_branch}/{typ}"
        self._git.checkout(branch=new_branch_name, reset=True)
        self._logger.success(f"Switch to CI branch '{new_branch_name}' and reset it to '{current_branch}'.")
        return new_branch_name

    def switch_to_original_branch(self):
        self._git.checkout(branch=self._context.ref_name)
        return

    def set_job_run(self, job_id: str, run: bool = True):
        if job_id not in self._run_job:
            self._logger.error(f"Invalid job ID: {job_id}")
        self._run_job[job_id] = run
        return

    @property
    def hash_latest(self) -> str:
        """The SHA hash of the most recent commit on the branch,
        including commits made during the workflow run.
        """
        if self._hash_latest:
            return self._hash_latest
        return self._context.hash_after

    def add_summary(
        self,
        name: str,
        status: Literal["pass", "fail", "skip", "warning"],
        oneliner: str,
        details: str | html.Element | html.ElementCollection | None = None,
    ):
        if status == "fail":
            self._failed = True
        self._summary_oneliners.append(f"{Emoji[status]}&nbsp;<b>{name}</b>: {oneliner}")
        if details:
            self._summary_sections.append(f"<h2>{name}</h2>\n\n{details}\n\n")
        return

    @property
    def output(self):
        package_name = self._metadata_branch.dict.get("package", {}).get("name", "")
        out = {
            "config": {
                "fail": self._failed,
                "checkout": {
                    "ref": self.hash_latest,
                    "ref_before": self._context.hash_before,
                    "repository": self._context.target_repo_fullname,
                },
                "run": self._run_job,
                "package": {
                    "version": self._version,
                    "upload_url_testpypi": "https://test.pypi.org/legacy/",
                    "upload_url_pypi": "https://upload.pypi.org/legacy/",
                    "download_url_testpypi": f"https://test.pypi.org/project/{package_name}/{self._version}",
                    "download_url_pypi": f"https://pypi.org/project/{package_name}/{self._version}",
                },
                "release": {
                               "tag_name": self._tag,
                               "discussion_category_name": "",
                           } | self._release_info,
            },
            "metadata_ci": self._generate_metadata_ci(),
        }
        for job_id, dependent_job_id in (
            ("package_publish_testpypi", "package_test_testpypi"),
            ("package_publish_pypi", "package_test_pypi"),
        ):
            if self._run_job[job_id]:
                out["config"]["run"][dependent_job_id] = True
        return out

    def _generate_metadata_ci(self) -> dict:
        out = {}
        metadata = self._metadata_branch.dict
        out["path"] = metadata["path"]
        out["web"] = {
            "readthedocs": {"name": metadata["web"].get("readthedocs", {}).get("name")},
        }
        out["url"] = {"website": {"base": metadata["url"]["website"]["base"]}}
        if metadata.get("package"):
            pkg = metadata["package"]
            out["package"] = {
                "name": pkg["name"],
                "github_runners": pkg["github_runners"],
                "python_versions": pkg["python_versions"],
                "python_version_max": pkg["python_version_max"],
                "pure_python": pkg["pure_python"],
                "cibw_matrix_platform": pkg.get("cibw_matrix_platform", []),
                "cibw_matrix_python": pkg.get("cibw_matrix_python", []),
            }
        return out

    def assemble_summary(self) -> tuple[str, str]:
        github_context, event_payload = (
            html.details(
                content=md.code_block(
                    YAML(typ=["rt", "string"]).dumps(dict(sorted(data.items())), add_final_eol=True),
                    "yaml"
                ),
                summary=summary,
            )
            for data, summary in (
                (self._context.github, "🎬 GitHub Context"),
                (self._context.payload, "📥 Event Payload")
            )
        )
        intro = [
            f"{Emoji.PLAY} The workflow was triggered by a <code>{self._context.event_name}</code> event."
        ]
        if self._failed:
            intro.append(f"{Emoji.FAIL} The workflow failed.")
        else:
            intro.append(f"{Emoji.PASS} The workflow passed.")
        intro = html.ul(intro)
        summary = html.ElementCollection(
            [
                html.h(1, "Workflow Report"),
                intro,
                html.ul([github_context, event_payload]),
                html.h(2, "🏁 Summary"),
                html.ul(self._summary_oneliners),
            ]
        )
        logs = html.ElementCollection(
            [
                html.h(2, "🪵 Logs"),
                html.details(self._logger.file_log, "Log"),
            ]
        )
        summaries = html.ElementCollection(self._summary_sections)
        path_logs = self._meta_main.input_path.dir_local_report_repodynamics
        path_logs.mkdir(parents=True, exist_ok=True)
        with open(path_logs / "log.html", "w") as f:
            f.write(str(logs))
        with open(path_logs / "report.html", "w") as f:
            f.write(str(summaries))
        return str(summary), str(path_logs)
