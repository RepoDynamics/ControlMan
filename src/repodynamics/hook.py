from typing import Literal
from pathlib import Path
import re
import json

from ruamel.yaml import YAML
from markitup import html, md, sgr

from repodynamics.logger import Logger
from repodynamics.git import Git
from repodynamics import _util


class PreCommitHooks:
    def __init__(
        self,
        path_root: str = ".",
        config: dict | str | Path = Path(".github/.pre-commit-config.yaml"),
        git: Git = None,
        logger: Logger = None,
    ):
        self._logger = logger or Logger()
        self._logger.h2("Run Hooks")
        self._path_root = Path(path_root).resolve()

        if isinstance(config, Path):
            config = Path(config).resolve()
            if not config.is_file():
                self._logger.error(f"pre-commit config file not found at '{config}'.")
        self._config = config

        self._git = git or Git(path_repo=self._path_root, logger=self._logger)

        self._emoji = {"Passed": "✅", "Failed": "❌", "Skipped": "⏭️", "Modified": "✏️️"}

        self._action: Literal["report", "amend", "commit"] = "report"
        self._commit_message: str = ""
        self._commit_hash: str = ""

        self._from_ref: str = ""
        self._to_ref: str = ""
        return

    def run(
        self,
        action: Literal["report", "amend", "commit"] = "report",
        commit_message: str = "",
        ref_range: tuple[str, str] = None,
    ) -> dict:
        if action not in ["report", "amend", "commit"]:
            self._logger.error(
                f"Argument 'action' must be one of 'report', 'amend', or 'commit', but got '{action}'."
            )
        if action == "commit" and not commit_message:
            self._logger.error("Argument 'commit_message' must be specified if action is 'commit'.")
        self._action = action
        self._commit_message = commit_message
        if ref_range:
            if (
                not isinstance(ref_range, (tuple, list))
                or len(ref_range) != 2
                or not all(isinstance(ref, str) for ref in ref_range)
            ):
                self._logger.error(
                    f"Argument 'ref_range' must be a list or tuple of two strings, but got {ref_range}."
                )
            self._from_ref, self._to_ref = ref_range
        else:
            self._from_ref = self._to_ref = None
        output, summary = self._run_check() if action == "report" else self._run_fix()
        output["summary"] = summary
        return output

    def _run_check(self):
        self._logger.h3("Validation Run")
        self._git.stash(include="all")
        results = self._run_hooks()
        output, result_line, details = self._process_results(results, validation_run=True)
        summary = self._create_summary(
            output=output,
            run_summary=[result_line],
            details=details,
        )
        self._git.discard_changes()
        self._git.stash_pop()
        return output, summary

    def _run_fix(self):
        self._logger.h3("Fix Run")
        results_fix = self._run_hooks()
        outputs_fix, summary_line_fix, details_fix = self._process_results(results_fix, validation_run=False)
        if outputs_fix["passed"] or not outputs_fix["modified"]:
            summary = self._create_summary(
                output=outputs_fix, run_summary=[summary_line_fix], details=details_fix
            )
            return outputs_fix, summary
        # There were fixes
        self._commit_hash = self._git.commit(
            message=self._commit_message,
            stage="all",
            amend=self._action == "amend",
        )
        self._logger.h3("Run hooks (validation run)")
        results_validate = self._run_hooks()
        outputs_validate, summary_line_validate, details_validate = self._process_results(
            results_validate, validation_run=True
        )
        outputs_validate["modified"] = outputs_validate["modified"] or outputs_fix["modified"]
        outputs_validate["commit_hash"] = self._commit_hash
        run_summary = [summary_line_fix, summary_line_validate]
        details = html.ElementCollection([details_fix, details_validate])
        # if action in ['amend', 'commit']:
        #     self._logger.h4("Commit changes")
        #     commit_hash = git.Git(path_repo=self._path_root, logger=self._logger).commit(
        #         message="" if action == "amend" else "style: fix files with pre-commit hooks",
        #         amend=action == "amend"
        #     )
        #     outputs_validate["commit_hash"] = commit_hash
        summary = self._create_summary(outputs_validate, run_summary, details)
        return outputs_validate, summary

    def _run_hooks(self) -> dict[str, dict]:
        scope = ["--from-ref", self._from_ref, "--to-ref", self._to_ref] if self._from_ref else ["--all-files"]

        if isinstance(self._config, (str, dict)):
            temp = True
            path = self._path_root.parent / ".__temporary_pre_commit_config__.yaml"
            with open(path, "w") as f:
                config = (
                    self._config
                    if isinstance(self._config, str)
                    else YAML(typ=["rt", "string"]).dumps(self._config, add_final_eol=True)
                )
                f.write(config)
            self._logger.success(
                "Write temporary pre-commit config file.", f"Path: {path}\nContent:\n{self._config}"
            )

        else:
            temp = False
            path = self._config

        command = [
            "pre-commit",
            "run",
            *scope,
            "--hook-stage",
            "manual",
            "--show-diff-on-failure",
            "--color=always",
            "--verbose",
            "--config",
            str(path),
        ]
        out, err, code = _util.shell.run_command(
            command, cwd=self._path_root, raise_returncode=False, logger=self._logger
        )
        if temp:
            path.unlink()
            self._logger.success("Remove temporary pre-commit config file.")
        error_intro = "An unexpected error occurred while running pre-commit hooks."
        if err:
            self._logger.error(error_intro, f"Exit Code: {code}\nError Message: {err}\nOutput: {out}")
        out_plain = sgr.remove_format(out)
        for line in out_plain.splitlines():
            for prefix in ("An error has occurred", "An unexpected error has occurred", "[ERROR]"):
                if line.startswith(prefix):
                    self._logger.error(error_intro, f"Exit Code: {code}\nOutput: {out}\nError Message: {err}")
        pattern = re.compile(
            r"""
                ^(?P<description>[^\n]+?)
                \.{3,}
                (?P<message>[^\n]*(?=\(Passed|Failed|Skipped\))?)?
                (?P<result>Passed|Failed|Skipped)\n
                -\s*hook\s*id:\s*(?P<hook_id>[^\n]+)\n
                (-\s*duration:\s*(?P<duration>\d+\.\d+)s\n)?
                (-\s*exit\s*code:\s*(?P<exit_code>\d+)\n)?
                (-\s*files\s*were\s*modified\s*by\s*this\s*hook(?P<modified>\n))?
                (?P<details>(?:^(?![^\n]+?\.{3,}.*?(Passed|Failed|Skipped)).*\n)*)
            """,
            re.VERBOSE | re.MULTILINE,
        )
        matches = list(pattern.finditer(out_plain))
        results = {}
        for match in matches:
            data = match.groupdict()
            data["duration"] = data["duration"] or "0"
            data["exit_code"] = data["exit_code"] or "0"
            data["modified"] = bool(match.group("modified"))
            data["details"] = data["details"].strip()
            if data["hook_id"] in results:
                self._logger.error(f"Duplicate hook ID '{data['hook_id']}' found.")
            results[data["hook_id"]] = data
        self._logger.success(
            "Successfully extracted results from pre-commit output", json.dumps(results, indent=3)
        )
        return results

    def _process_results(self, results: dict[str, dict], validation_run: bool):
        details_list = []
        count = {"Passed": 0, "Modified": 0, "Skipped": 0, "Failed": 0}
        for hook_id, result in results.items():
            if result["result"] == "Failed" and result["modified"]:
                result["result"] = "Modified"
            count[result["result"]] += 1
            summary = f"{self._emoji[result['result']]} {hook_id}"
            detail_list = html.ul(
                [
                    f"Description: {result['description']}",
                    f"Result: {result['result']} {result['message']}",
                    f"Modified Files: {result['modified']}",
                    f"Exit Code: {result['exit_code']}",
                    f"Duration: {result['duration']} s",
                ]
            )
            detail = html.ElementCollection([detail_list])
            if result["details"]:
                detail.append(md.code_block(result["details"]))
            details_block = html.details(content=detail, summary=summary)
            details_list.append(details_block)
        passed = count["Failed"] == 0 and count["Modified"] == 0
        modified = count["Modified"] != 0
        summary_title = "Validation Run" if validation_run else "Fix Run"
        summary_details = ", ".join([f"{count[key]} {key}" for key in count])
        summary_result = f'{self._emoji["Passed" if passed else "Failed"]} {"Pass" if passed else "Fail"}'
        result_line = f"{summary_title}: {summary_result} ({summary_details})"
        details = html.ElementCollection([html.h(4, summary_title), html.ul(details_list)])
        outputs = {"passed": passed, "modified": modified, "count": count}
        return outputs, result_line, details

    def _create_summary(
        self,
        output: dict,
        run_summary: list,
        details,
    ):
        passed = output["passed"]
        modified = output["modified"]
        result_emoji = self._emoji["Passed" if passed else "Failed"]
        result_keyword = "Pass" if passed else "Fail"
        summary_result = f"{result_emoji} {result_keyword}"
        if modified:
            summary_result += " (modified files)"
        action_emoji = {"report": "📄", "commit": "💾", "amend": "📌"}[self._action]
        action_title = {"report": "Validate & Report", "commit": "Fix & Commit", "amend": "Fix & Amend"}[
            self._action
        ]

        scope = f"From ref. '{self._from_ref}' to ref. '{self._to_ref}'" if self._from_ref else "All files"
        summary_list = [
            f"Result: {summary_result}",
            f"Action: {action_emoji} {action_title}",
            f"Scope: {scope}",
            f"Runs: ",
            html.ul(run_summary),
        ]

        html_summary = html.ElementCollection(
            [
                html.h(2, "Hooks"),
                html.h(3, "Summary"),
                html.ul(summary_list),
                html.h(3, "Details"),
                details,
                html.h(3, "Log"),
                html.details(self._logger.file_log, summary="Log"),
            ]
        )
        return html_summary


def run(
    ref_range: tuple[str, str] = None,
    action: Literal["report", "amend", "commit"] = "amend",
    commit_message: str = "",
    path_root: str = ".",
    config: dict | str | Path = Path(".github/.pre-commit-config.yaml"),
    git: Git | None = None,
    logger: Logger = None,
):
    output = PreCommitHooks(path_root=path_root, config=config, git=git, logger=logger).run(
        action=action, ref_range=ref_range, commit_message=commit_message
    )
    return output
