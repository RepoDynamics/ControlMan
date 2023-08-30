from typing import Literal
from pathlib import Path
import subprocess
import re
import json

from markitup import html, md

from repodynamics.logger import Logger
from repodynamics import ansi
from repodynamics import git


class PreCommitHooks:

    def __init__(
        self,
        from_ref: str,
        to_ref: str,
        fix: bool,
        config_path: str,
        logger: Logger,
        summary_path: str = ".local/reports/hooks.md"
    ):
        config_path = Path(config_path).resolve()
        if not config_path.exists():
            logger.error(f"Config file '{config_path}' not found.")
        self.from_ref = from_ref
        self.to_ref = to_ref
        self.fix = fix
        self.config_path = config_path
        self.summary_path = Path(summary_path) if summary_path else None
        self.logger = logger
        if not (from_ref and to_ref):
            self.scope = "--all-files"
            self.scope_summary = "Hooks were run on all files."
        else:
            self.scope = f"--from-ref {from_ref} --to-ref {to_ref}"
            self.scope_summary = f"Hooks were run on files changed between '{from_ref}' and '{to_ref}'."
        self.emoji = {"Passed": "✅", "Failed": "❌", "Skipped": "⏭️", "Modified": "✏️️"}
        return

    def run(self):
        if self.fix:
            output, summary = self.run_fix()
        else:
            output, summary = self.run_check()
        if self.summary_path:
            self.summary_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.summary_path, "w") as f:
                f.write(str(summary))
            return output, None, None
        return output, None, summary

    def run_check(self):
        self.logger.section("Run hooks (validation run)")
        results = self.run_hooks()
        outputs, summary_line, details = self.process_results(results, validation_run=True)
        self.logger.end_section()
        results_summary = html.ul([summary_line])
        summary = self.create_summary(results_summary, details)
        outputs["commit_hash"] = ""
        return outputs, summary

    def run_fix(self):
        self.logger.section("Run hooks (fix run)")
        results_fix = self.run_hooks()
        outputs_fix, summary_line_fix, details_fix = self.process_results(results_fix, validation_run=False)
        self.logger.end_section()
        if outputs_fix['passed']:
            self.logger.success("All hooks passed; no modifications to commit.")
            summary = self.create_summary(html.ul([summary_line_fix]), details_fix)
            return outputs_fix, summary
        if not outputs_fix['fixed']:
            self.logger.warning("Some non-fixing hooks failed.")
            summary = self.create_summary(html.ul([summary_line_fix]), details_fix)
            return outputs_fix, summary
        # There were fixes
        self.logger.section("Commit changes")
        commit_hash = git.commit(message="maint: run pre-commit hooks", logger=self.logger)
        self.logger.end_section()
        self.logger.section("Run hooks (validation run)")
        results_validate = self.run_hooks()
        outputs_validate, summary_line_validate, details_validate = self.process_results(results_fix, validation_run=True)
        self.logger.end_section()
        results_summary = html.ul([summary_line_validate, summary_line_fix])
        details = html.ElementCollection([details_validate, details_fix])
        summary = self.create_summary(results_summary, details, commit_hash)
        outputs_validate["commit_hash"] = commit_hash
        return outputs_validate, summary

    def create_summary(self, summary, details, commit_hash: str = None):
        if self.fix:
            if commit_hash:
                changes = f"Modifications were committed with commit hash '{commit_hash}'."
            else:
                changes = "There were no modifications to commit."
        else:
            changes = "Fix-mode was not selected; no modifications were committed."
        html_summary = html.ElementCollection(
            [
                html.h(2, "Hooks"),
                html.h(3, "Summary"),
                html.h(4, "Results"),
                summary,
                html.h(4, "Scope"),
                self.scope_summary,
                html.h(4, "Commit"),
                changes,
                html.h(3, "Details"),
                details,
            ]
        )
        return html_summary

    def process_results(self, results, validation_run: bool):
        details_list = []
        count = {"Passed": 0, "Modified": 0, "Skipped": 0, "Failed": 0}
        for hook_id, result in results.items():
            if result['result'] == 'Failed' and result['modified']:
                result['result'] = 'Modified'
            count[result['result']] += 1
            summary = f"{self.emoji[result['result']]} {hook_id}"
            detail_list = html.ul(
                [
                    f"Description: {result['description']}",
                    f"Result: {result['result']} {result['message']}",
                    f"Modified Files: {result['modified']}",
                    f"Exit Code: {result['exit_code']}",
                    f"Duration: {result['duration']} s"
                ]
            )
            detail = html.ElementCollection([detail_list])
            if result['details']:
                detail.append(md.code_block(result['details']))
            details_block = html.details(content=detail, summary=summary)
            details_list.append(details_block)
        passed = count['Failed'] == 0 and count['Modified'] == 0
        fixed = count['Modified'] != 0
        summary_title = "Validation Run" if validation_run else "Fix Run"
        summary_details = ", ".join([f"{count[key]} {key}" for key in count])
        summary_result = f'{self.emoji["Passed" if passed else "Failed"]} {"Pass" if passed else "Fail"}'
        summary_line = f"{summary_title}: {summary_result} ({summary_details})"
        details = html.ElementCollection(
            [html.h(4, summary_title), html.ul(details_list)]
        )
        outputs = {"passed": passed, "fixed": fixed}
        return outputs, summary_line, details

    def run_hooks(self) -> dict[str, dict]:
        process = subprocess.run(
            [
                "pre-commit",
                "run",
                self.scope,
                "--show-diff-on-failure",
                "--color=always",
                "--verbose",
                "--config",
                self.config_path
            ],
            capture_output=True
        )
        out = process.stdout.decode()
        self.logger.log(out)
        error_intro = "An unexpected error occurred while running pre-commit hooks;"
        if process.stderr:
            self.logger.error(
                f"{error_intro} pre-commit exited with an error message:",
                details=process.stderr.decode()
            )
        out_plain = ansi.remove_formatting(out)
        for line in out_plain.splitlines():
            for prefix in ("An error has occurred", "An unexpected error has occurred", "[ERROR]"):
                if line.startswith(prefix):
                    self.logger.error(f"{error_intro} pre-commit outputted an error message.")
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
            re.VERBOSE | re.MULTILINE
        )
        matches = list(pattern.finditer(out_plain))
        results = {}
        for match in matches:
            data = match.groupdict()
            data['duration'] = data['duration'] or '0'
            data['exit_code'] = data['exit_code'] or '0'
            data['modified'] = bool(match.group('modified'))
            data["details"] = data["details"].strip()
            if data['hook_id'] in results:
                self.logger.error(f"Duplicate hook ID '{data['hook_id']}' found.")
            results[data['hook_id']] = data
        self.logger.success("Successfully extracted results from pre-commit output:")
        self.logger.debug(json.dumps(results, indent=3))
        return results


def hooks(
    from_ref: str,
    to_ref: str,
    fix: bool,
    config_path: str = ".pre-commit-config.yaml",
    summary_path: str = ".local/reports/hooks.md",
    logger: Logger = None
):
    outputs, env_vars, summary = PreCommitHooks(
        from_ref=from_ref,
        to_ref=to_ref,
        fix=fix,
        config_path=config_path,
        summary_path=summary_path,
        logger=logger
    ).run()
    return outputs, env_vars, summary
