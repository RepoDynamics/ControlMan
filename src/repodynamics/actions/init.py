from pathlib import Path
import json
import subprocess

from markitup import html, md

from repodynamics.logger import Logger


def update_meta(context: dict, meta_modified: bool, logger: Logger = None):
    event_name = context["event_name"]
    ref_name = context["ref_name"]
    output = {"update": True, "commit": True}
    if event_name in ["schedule", "workflow_dispatch"]:
        return output, None, None
    if event_name == "pull_request" or (
        event_name == "push" and (ref_name == "main" or ref_name.startswith("release/"))
    ):
        output["commit"] = False
        return output, None, None
    if event_name != "push":
        logger.error(f"Unsupported event: '{event_name}'.")
    if not meta_modified:
        output["update"] = False
        output['commit'] = False
    return output, None, None


def run_hooks(context: dict, meta_commit_hash: str, logger: Logger = None):
    event_name = context["event_name"]
    output = {"commit": True, "from_ref": "", "to_ref": "", "pull": False}
    if event_name in ["schedule", "workflow_dispatch"]:
        output["pull"] = True
        _create_pull_body()
        return output, None, None
    if event_name == "pull_request":
        output["commit"] = False
        output["from_ref"] = context["event"]["pull_request"]["base"]["sha"]
        output["to_ref"] = context["event"]["pull_request"]["head"]["sha"]
        return output, None, None
    if event_name != "push":
        logger.error(f"Unsupported event: '{event_name}'.")
    output["from_ref"] = context["event"]["before"]
    output["to_ref"] = meta_commit_hash or context["event"]["after"]
    ref_name = context["ref_name"]
    if ref_name == "main" or ref_name.startswith("release/"):
        output["commit"] = False
    return output, None, None


def _create_pull_body():
    path = Path(".local/temp/repodynamics/init/pr_body.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write("")
    return


def finalize(
    context: dict,
    changes: dict,
    meta: dict,
    hooks: dict,
    pull: dict,
    logger: Logger = None,
):
    return Init(context=context, changes=changes, meta=meta, hooks=hooks, pull=pull, logger=logger).run()


class Init:

    def __init__(
        self,
        context: dict,
        changes: dict,
        meta: dict,
        hooks: dict,
        pull: dict,
        logger: Logger = None,
    ):
        self.context = context
        self.changes = self.process_changes_output(changes) if changes else {}
        self.meta = meta or {}
        self.hooks = hooks or {}
        self.pull = pull or {}
        self.logger = logger

        self.summary = ""
        return

    def run(self):
        event = self.context["event_name"]
        ref = self.context["ref_name"]
        if event == "push":
            if ref == "main" or ref.startswith("release/"):
                output = self.case_push_main()
            else:
                output = self.case_push_dev()
        elif event == "pull_request":
            output = self.case_pull()
        elif event in ["schedule", "workflow_dispatch"]:
            output = self.case_schedule()
        else:
            self.logger.error(f"Unsupported event: '{event}'.")
        summary = str(self.assemble_summary())
        return output, None, summary

        # meta_changes = meta["changes"]
        # meta_commit_hash = meta["commit_hash"]
        #
        # hooks_passed = hooks["passed"]
        # hooks_fixed = hooks["fixed"]
        # hooks_commit_hash = hooks["commit-hash"]
        #
        # pr_nr = pull["pull-request-number"]
        # pr_url = pull["pull-request-url"]
        # pr_head_sha = pull["pull-request-head-sha"]
        #
        # return output, None, summary

    def case_push_dev(self):
        output = {
            "hash": self.latest_commit_hash,
            "package_test": self.package_test_needed,
            "package_lint": self.package_lint_needed,
            "docs": self.docs_test_needed,
        }
        return output

    @property
    def latest_commit_hash(self):
        return self.hooks.get("commit-hash") or self.meta.get("commit-hash") or self.context["event"]["after"]

    @property
    def package_test_needed(self):
        if self.meta.get("changes", {}).get("package"):
            return True
        for group in ["src", "tests", "setup-files", "workflow"]:
            if self.changes[group]["any_modified"] == "true":
                return True
        return False

    @property
    def package_lint_needed(self):
        if self.meta["changes"]["package"]:
            return True
        for group in ["src", "setup-files", "workflow"]:
            if self.changes[group]["any_modified"] == "true":
                return True
        return False

    @property
    def docs_test_needed(self):
        if self.meta["changes"]["metadata"] or self.meta["changes"]["package"]:
            return True
        for group in ["src", "docs-website", "workflow"]:
            if self.changes[group]["any_modified"] == "true":
                return True
        return False

    def create_summary(self):
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

    @staticmethod
    def process_changes_output(changes):
        """

        Parameters
        ----------
        changes

        Returns
        -------
        The keys of the JSON dictionary are the groups that the files belong to,
        defined in `.github/config/changed_files.yaml`. Another key is `all`, which is added as extra
        (i.e. without being defined in the config file), which contains details on changes in the entire repository.
        Each value is then a dictionary itself, as defined in the action's documentation.

        Notes
        -----
        The boolean values in the output are given as strings, i.e. `true` and `false`.

        References
        ----------
        - https://github.com/marketplace/actions/changed-files
        """
        sep_groups = dict()
        for item_name, val in changes.items():
            group_name, attr = item_name.split("_", 1)
            group = sep_groups.setdefault(group_name, dict())
            group[attr] = val
        for group_name, group_attrs in sep_groups.items():
            sep_groups[group_name] = dict(sorted(group_attrs.items()))
        return sep_groups

    def changed_files(self):
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

    def check_git_attributes(self):
        command = ["sh", "-c", "git ls-files | git check-attr -a --stdin | grep 'text: auto'"]
        self.logger.info(f"Running command: {' '.join(command)}")
        process = subprocess.run(command, capture_output=True, text=True)
        if process.returncode != 0:
            self.logger.error(f"Failed to check git attributes:", process.stderr)
        output = process.stdout
        if output:
            return False
        return True


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
    output = {"meta": False, "metadata": False, "package": False, "docs": False}
    if not detect:
        meta_summary, meta_changes = _meta_summary()
        output["meta"] = meta_changes["any"]
        output["metadata"] = meta_changes["metadata"]
        output["package"] = meta_changes["package"]
        output["docs"] = meta_changes["package"] or meta_changes["metadata"]
    else:
        all_groups, job_summary = _changed_files(changes)
        output["package"] = any(
            [
                all_groups[group]["any_modified"] == "true" for group in [
                    "src", "tests", "setup-files", "github-workflows"
                ]
            ]
        )
        output["docs"] = any(
            [
                all_groups[group]["any_modified"] == "true" for group in [
                    "src", "meta-out", "docs-website", "github-workflows"
                ]
            ]
        )
        if all_groups["meta"]["any_modified"] == "true":
            meta_summary, meta_changes = _meta_summary()

    # else:
    #     job_summary = html.ElementCollection()
    #
    # job_summary.append(html.h(2, "Metadata"))
    #
    # with open("meta/.out/metadata.json") as f:
    #     metadata_dict = json.load(f)
    #
    # job_summary.append(
    #     html.details(
    #         content=md.code_block(json.dumps(metadata_dict, indent=4), "json"),
    #         summary=" 🖥  Metadata",
    #     )
    # )
    #
    # job_summary.append(
    #     html.details(
    #         content=md.code_block(json.dumps(summary_dict, indent=4), "json"),
    #         summary=" 🖥  Summary",
    #     )
    # )
    # return None, None, str(job_summary)


    # Generate summary
    # force_update_emoji = "✅" if force_update == "all" else ("❌" if force_update == "none" else "☑️")
    # cache_hit_emoji = "✅" if cache_hit else "❌"
    # if not cache_hit or force_update == "all":
    #     result = "Updated all metadata"
    # elif force_update == "core":
    #     result = "Updated core metadata but loaded API metadata from cache"
    # else:
    #     result = "Loaded all metadata from cache"

    # results_list = html.ElementCollection(
    #     [
    #         html.li(f"{force_update_emoji}  Force update (input: {force_update})", content_indent=""),
    #         html.li(f"{cache_hit_emoji}  Cache hit", content_indent=""),
    #         html.li(f"➡️  {result}", content_indent=""),
    #     ],
    # )
    # log = f"<h2>Repository Metadata</h2>{metadata_details}{results_list}"

    # return {"json": json.dumps(all_groups)}, str(log)
