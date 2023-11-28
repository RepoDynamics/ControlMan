import re

from pylinks.api.github import Repo

from repodynamics.actions.context_manager import ContextManager, IssuesPayload
from repodynamics.datatype import WorkflowTriggeringAction, IssueStatus
from repodynamics.meta.manager import MetaManager
from repodynamics.logger import Logger
from repodynamics.actions import _helpers
from repodynamics.actions.events._base import NonModifyingEventHandler
from repodynamics.meta.files.forms import FormGenerator


class IssuesEventHandler(NonModifyingEventHandler):
    def __init__(self, context_manager: ContextManager, logger: Logger | None = None):
        super().__init__(context_manager=context_manager, logger=logger)
        self._payload: IssuesPayload = self._context.payload
        return

    def run_event(self):
        action = self._payload.action
        if action == WorkflowTriggeringAction.OPENED:
            self._run_opened()
        elif action == WorkflowTriggeringAction.LABELED:
            self._run_labeled()
        else:
            _helpers.error_unsupported_triggering_action(
                event_name=self._context.github.event_name, action=action, logger=self._logger
            )
        return

    def _run_opened(self):
        self._gh_api.issue_comment_create(number=self._payload.number, body="This post tracks the issue.")
        self._post_process_issue()
        return

    def _run_labeled(self):
        label_name = self._payload.label["name"]
        if label_name.startswith(self._metadata_main["label"]["group"]["status"]["prefix"]):
            self._run_labeled_status()
        return

    def _run_labeled_status(self):
        status = self._metadata_main.get_issue_status_from_status_label(self._payload.label["name"])
        if status == IssueStatus.IN_DEV:
            self._run_labeled_status_in_dev()
        return

    def _run_labeled_status_in_dev(self):
        target_label_prefix = self._metadata_main["label"]["auto_group"]["branch"]["prefix"]
        dev_branch_prefix = self._metadata_main["branch"]["group"]["dev"]["prefix"]
        branches = self._gh_api.branches
        branch_sha = {branch["name"]: branch["commit"]["sha"] for branch in branches}
        for issue_label in self._payload.labels:
            if issue_label["name"].startswith(target_label_prefix):
                base_branch_name = issue_label["name"].removeprefix(target_label_prefix)
                head_branch_name = f"{dev_branch_prefix}{self._payload.number}/{base_branch_name}"
                new_branch = self._gh_api.branch_create_linked(
                    issue_id=self._payload.node_id,
                    base_sha=branch_sha[base_branch_name],
                    name=head_branch_name,
                )
                # Create empty commit on dev branch to be able to open a draft pull request
                # Ref: https://stackoverflow.com/questions/46577500/why-cant-i-create-an-empty-pull-request-for-discussion-prior-to-developing-chan
                self._git_head.fetch_remote_branches_by_name(branch_names=head_branch_name)
                self._git_head.checkout(head_branch_name)
                self._git_head.commit(
                    message=f"Create branch '{head_branch_name}' for issue #{self._payload.number}",
                    allow_empty=True,
                )
                self._git_head.push(target="origin", set_upstream=True)
                pull_data = self._gh_api.pull_create(
                    head=new_branch["name"],
                    base=base_branch_name,
                    # title=self._payload.title,
                    # body=f"This is a draft pull request for the issue #{self._payload.number}.",
                    maintainer_can_modify=True,
                    draft=True,
                    issue=self._payload.number,
                )
                self._gh_api.issue_labels_set(number=pull_data["number"], labels=self._payload.label_names)
        return

    def _post_process_issue(self):
        self._logger.success("Retrieve issue labels", self._payload.label_names)
        issue_form = self._metadata_main.get_issue_data_from_labels(self._payload.label_names).form
        self._logger.success("Retrieve issue form", issue_form)
        issue_entries = self._extract_entries_from_issue_body(issue_form["body"])
        labels = []
        branch_label_prefix = self._metadata_main["label"]["auto_group"]["branch"]["prefix"]
        if "branch" in issue_entries:
            branches = [branch.strip() for branch in issue_entries["branch"].split(",")]
            for branch in branches:
                labels.append(f"{branch_label_prefix}{branch}")
        elif "version" in issue_entries:
            versions = [version.strip() for version in issue_entries["version"].split(",")]
            version_label_prefix = self._metadata_main["label"]["auto_group"]["version"]["prefix"]
            for version in versions:
                labels.append(f"{version_label_prefix}{version}")
                branch = self._metadata_main.get_branch_from_version(version)
                labels.append(f"{branch_label_prefix}{branch}")
        else:
            self._logger.error(
                "Could not match branch or version in issue body to pattern defined in metadata.",
            )
        self._gh_api.issue_labels_add(self._payload.number, labels)
        if "post_process" not in issue_form:
            self._logger.skip(
                "No post-process action defined in issue form; skip❗",
            )
            return
        post_body = issue_form["post_process"].get("body")
        if post_body:
            new_body = post_body.format(**issue_entries)
            self._gh_api.issue_update(number=self._payload.number, body=new_body)
        assign_creator = issue_form["post_process"].get("assign_creator")
        if assign_creator:
            if_checkbox = assign_creator.get("if_checkbox")
            if if_checkbox:
                checkbox = issue_entries[if_checkbox["id"]].splitlines()[if_checkbox["number"] - 1]
                if checkbox.startswith("- [X]"):
                    checked = True
                elif not checkbox.startswith("- [ ]"):
                    self._logger.error(
                        "Could not match checkbox in issue body to pattern defined in metadata.",
                    )
                else:
                    checked = False
                if (if_checkbox["is_checked"] and checked) or (not if_checkbox["is_checked"] and not checked):
                    self._gh_api.issue_add_assignees(
                        number=self._payload.number, assignees=self._payload.author_username
                    )
        return

    def _extract_entries_from_issue_body(self, body_elems: list[dict]):
        def create_pattern(parts):
            pattern_sections = []
            for idx, part in enumerate(parts):
                pattern_content = f"(?P<{part['id']}>.*)" if part["id"] else "(?:.*)"
                pattern_section = rf"### {re.escape(part['title'])}\n{pattern_content}"
                if idx != 0:
                    pattern_section = f"\n{pattern_section}"
                if part["optional"]:
                    pattern_section = f"(?:{pattern_section})?"
                pattern_sections.append(pattern_section)
            return "".join(pattern_sections)

        parts = []
        for elem in body_elems:
            if elem["type"] == "markdown":
                continue
            pre_process = elem.get("pre_process")
            if not pre_process or FormGenerator._pre_process_existence(pre_process):
                optional = False
            else:
                optional = True
            parts.append({"id": elem.get("id"), "title": elem["attributes"]["label"], "optional": optional})
        pattern = create_pattern(parts)
        compiled_pattern = re.compile(pattern, re.S)
        # Search for the pattern in the markdown
        self._logger.success("Retrieve issue body", self._payload.body)
        match = re.search(compiled_pattern, self._payload.body)
        if not match:
            self._logger.error("Could not match the issue body to pattern defined in metadata.")
        # Create a dictionary with titles as keys and matched content as values
        sections = {
            section_id: content.strip() if content else None
            for section_id, content in match.groupdict().items()
        }
        return sections
