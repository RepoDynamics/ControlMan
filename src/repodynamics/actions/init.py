from pathlib import Path
import json
import subprocess

from markitup import html, md

from repodynamics.logger import Logger
from repodynamics.git import Git
from repodynamics import meta
from repodynamics import hooks


def init(context: dict, changes: dict, logger=None):
    event = context["event_name"]
    if event in ["schedule", "workflow_dispatch"]:
        return Dispatch(context=context).run()
    if event == "issue":
        pass
    if event == "pull_request":
        pass
    if event == "push":
        ref = context["ref_name"]
        if ref == "main" or ref.startswith("release/"):
            logger.success("Detected Event: Push to release branch")
            return PushRelease(context=context, changes=changes).run()
        else:
            logger.success("Detected Event: Push to non-release branch")
            return PushDev(context=context, changes=changes).run()
    logger.error(f"Event '{event}' is not supported.")
    return


class EventHandler:

    def __init__(self, context: dict):
        self._context = context
        self._event = context["event_name"]
        self._payload = context["event"]
        self._ref = context["ref_name"]
        self._logger = Logger("github")
        self._git = Git(logger=self._logger)
        self._output_meta = None
        self._output_hooks = None
        self._metadata = self._load_metadata()
        return

    @staticmethod
    def _process_changes(changes):
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

    def _load_metadata(self) -> dict:
        path_metadata = Path("meta/.out/metadata.json")
        metadata = {}
        if path_metadata.is_file():
            with open(path_metadata) as f:
                metadata = json.load(f)
            self._logger.success(
                f"Loaded metadata from {path_metadata}.",
                json.dumps(metadata, indent=3)
            )
        else:
            self._logger.attention(f"No metadata found in {path_metadata}.")
        return metadata


class PushRelease(EventHandler):

    def __init__(self, context: dict, changes: dict):
        super().__init__(context)
        self._changes = self._process_changes(changes)
        self._output = {
            "config-repo": False,

        }
        return

    def run(self):
        semver_tag = self._git.latest_semver_tag()
        if not semver_tag:
            return self._run_initial_release()
        self._output_meta = meta.update(
            action="report",
            github_token=self._context["token"],
            logger=self._logger,
        )
        return

    def _run_initial_release(self):
        self._create_changelog()
        self._git.commit(
            stage='all',
            amend=True,
        )
        self._git.push(force_with_lease=True)
        self._git.create_tag(tag="v0.0.0", message="Initial Release")
        return

    def _create_changelog(self):
        changelog = f"""# Changelog
This document tracks all changes to the {self._metadata['name']} public API.

## [{self._metadata['project']['name']} 0.0.0]({self._metadata['url']['github']['releases']['home']}/tag/v0.0.0)
This is the initial release of the project. Infrastructure is now in place to support future releases.
"""
        with open("CHANGELOG.md", "w") as f:
            f.write(changelog)
        return




class InitialRelease(EventHandler):

    def __init__(self, context: dict):
        super().__init__(context)
        return

    def run(self):
        return


class PushDev(EventHandler):

    def __init__(self, context: dict, changes: dict):
        super().__init__(context)
        self._changes = self._process_changes(changes)
        return

    def run(self):
        summary = html.ElementCollection()
        output = {
            "package_test": self.package_test_needed,
            "package_lint": self.package_lint_needed,
            "docs": self.docs_test_needed,
        }
        hash_before = self._payload["before"]
        hash_after = self._payload["after"]
        if self._changes["meta"]["any_modified"] == "true":
            self._output_meta = meta.update(
                action="commit",
                github_token=self._context["token"],
                logger=self._logger,
            )
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
            self._output_hooks = hooks.run(
                action="commit",
                ref_range=(hash_before, hash_after),
                path_config=self._metadata["workflow_hooks_config_path"],
                logger=self._logger,
            )
            summary.append(self._output_hooks["summary"])
        else:
            self._logger.attention("No workflow hooks config path set in metadata.")
        output["hash"] = self._git.push()
        return output, None, str(summary)

    @property
    def package_test_needed(self):
        for group in ["src", "tests", "setup-files", "workflow"]:
            if self._changes[group]["any_modified"] == "true":
                return True
        return False

    @property
    def package_lint_needed(self):
        for group in ["src", "setup-files", "workflow"]:
            if self._changes[group]["any_modified"] == "true":
                return True
        return False

    @property
    def docs_test_needed(self):
        for group in ["src", "docs-website", "workflow"]:
            if self._changes[group]["any_modified"] == "true":
                return True
        return False


class Dispatch(EventHandler):

    def __init__(self, context: dict):
        super().__init__(context)
        self._output = {"pull": True}
        return

    def run(self):
        summary = html.ElementCollection()
        self._output_meta = meta.update(
            action="commit",
            github_token=self._context["token"],
            logger=self._logger,
        )
        summary.append(self._output_meta["summary"])
        if self._metadata.get("workflow_hooks_config_path"):
            self._output_hooks = hooks.run(
                action="commit",
                path_config=self._metadata["workflow_hooks_config_path"],
                logger=self._logger,
            )
            summary.append(self._output_hooks["summary"])
        self._create_pull_body()
        return self._output, None, str(summary)

    def _create_pull_body(self):
        path = Path(".local/temp/repodynamics/init/pr_body.md")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write("Automatically update all metadata and dynamic files.\nRun hooks.")
        return


class Init:
    def __init__(self, context: dict, changes: dict):

        self._changes = self._process_changes(changes)


        self._metadata = self._load_metadata()
        self._output_meta = None
        self._output_hooks = None
        return


    def pull(self):
        hash_before = self._payload['pull_request']['base']['sha']
        hash_after = self._payload['pull_request']['head']['sha']
        self._output_meta = meta.update(
            action="report",
            github_token=self._context["token"],
            logger=self._logger,
        )
        self._output_hooks = hooks.run(
            action="report",
            ref_range=(hash_before, hash_after),
            path_config=self._metadata["workflow_hooks_config_path"],
            logger=self._logger,
        )
        return

    def dispatch(self):
        changes, summary, commit_hash = meta.update(
            action="commit",
            github_token=self._context["token"],
            logger=self._logger,
        )
        return

    def issue(self):
        return





class _Init:

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
        self.changes = self._process_changes(changes) if changes else {}
        self.meta = meta or {}
        if self.meta:
            self.meta["changes"] = json.loads(self.meta["changes"], strict=False)
        self.hooks = hooks or {}
        self.pull = pull or {}
        self.logger = logger

        self.summary = ""
        return

    def run(self):

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
