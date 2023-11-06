
class IssuePostProcessorAction:

    def action_post_process_issue(self):
        self.logger.success("Retrieve issue labels", self.issue_label_names)
        issue_form = self.meta.manager.get_issue_data_from_labels(self.issue_label_names).form
        self.logger.success("Retrieve issue form", issue_form)
        issue_entries = self._extract_entries_from_issue_body(issue_form["body"])
        labels = []
        branch_label_prefix = self.metadata["label"]["auto_group"]["target"]["prefix"]
        if "branch" in issue_entries:
            branches = [branch.strip() for branch in issue_entries["branch"].split(",")]
            for branch in branches:
                labels.append(f"{branch_label_prefix}{branch}")
        elif "version" in issue_entries:
            versions = [version.strip() for version in issue_entries["version"].split(",")]
            version_label_prefix = self.metadata["label"]["auto_group"]["version"]["prefix"]
            for version in versions:
                labels.append(f"{version_label_prefix}{version}")
                branch = self.meta.manager.get_branch_from_version(version)
                labels.append(f"{branch_label_prefix}{branch}")
        else:
            self.logger.error(
                "Could not match branch or version in issue body to pattern defined in metadata.",
            )
        self.api.issue_labels_add(self.issue_number, labels)
        if "post_process" not in issue_form:
            self.logger.skip(
                "No post-process action defined in issue form; skip❗",
            )
            return
        post_body = issue_form["post_process"].get("body")
        if post_body:
            new_body = post_body.format(**issue_entries)
            self.api.issue_update(number=self.issue_number, body=new_body)
        assign_creator = issue_form["post_process"].get("assign_creator")
        if assign_creator:
            if_checkbox = assign_creator.get("if_checkbox")
            if if_checkbox:
                checkbox = issue_entries[if_checkbox["id"]].splitlines()[if_checkbox["number"] - 1]
                if checkbox.startswith("- [X]"):
                    checked = True
                elif not checkbox.startswith("- [ ]"):
                    self.logger.error(
                        "Could not match checkbox in issue body to pattern defined in metadata.",
                    )
                else:
                    checked = False
                if (if_checkbox["is_checked"] and checked) or (not if_checkbox["is_checked"] and not checked):
                    self.api.issue_add_assignees(
                        number=self.issue_number, assignees=self.issue_author_username
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
        self.logger.success("Retrieve issue body", self.issue_body)
        match = re.search(compiled_pattern, self.issue_body)
        if not match:
            self.logger.error("Could not match the issue body to pattern defined in metadata.")
        # Create a dictionary with titles as keys and matched content as values
        sections = {
            section_id: content.strip() if content else None
            for section_id, content in match.groupdict().items()
        }
        return sections