
class FileChangeDetector:

    def action_file_change_detector(self) -> list[str]:
        name = "File Change Detector"
        self.logger.h1(name)
        change_type_map = {
            "added": FileChangeType.CREATED,
            "deleted": FileChangeType.REMOVED,
            "modified": FileChangeType.MODIFIED,
            "unmerged": FileChangeType.UNMERGED,
            "unknown": FileChangeType.UNKNOWN,
            "broken": FileChangeType.BROKEN,
            "copied_to": FileChangeType.CREATED,
            "renamed_from": FileChangeType.REMOVED,
            "renamed_to": FileChangeType.CREATED,
            "copied_modified_to": FileChangeType.CREATED,
            "renamed_modified_from": FileChangeType.REMOVED,
            "renamed_modified_to": FileChangeType.CREATED,
        }
        summary_detail = {file_type: [] for file_type in RepoFileType}
        change_group = {file_type: [] for file_type in RepoFileType}
        changes = self.git.changed_files(ref_start=self.hash_before, ref_end=self.hash_after)
        self.logger.success("Detected changed files", json.dumps(changes, indent=3))
        input_path = self.meta.input_path
        fixed_paths = [outfile.rel_path for outfile in self.meta.output_path.fixed_files]
        for change_type, changed_paths in changes.items():
            # if change_type in ["unknown", "broken"]:
            #     self.logger.warning(
            #         f"Found {change_type} files",
            #         f"Running 'git diff' revealed {change_type} changes at: {changed_paths}. "
            #         "These files will be ignored."
            #     )
            #     continue
            if change_type.startswith("copied") and change_type.endswith("from"):
                continue
            for path in changed_paths:
                if path.endswith("/README.md") or path == ".github/_README.md":
                    typ = RepoFileType.README
                elif path.startswith(f"{input_path.dir_source}/"):
                    typ = RepoFileType.PACKAGE
                elif path in fixed_paths:
                    typ = RepoFileType.DYNAMIC
                elif path.startswith(f"{input_path.dir_website}/"):
                    typ = RepoFileType.WEBSITE
                elif path.startswith(f"{input_path.dir_tests}/"):
                    typ = RepoFileType.TEST
                elif path.startswith(".github/workflows/"):
                    typ = RepoFileType.WORKFLOW
                elif (
                    path.startswith(".github/DISCUSSION_TEMPLATE/")
                    or path.startswith(".github/ISSUE_TEMPLATE/")
                    or path.startswith(".github/PULL_REQUEST_TEMPLATE/")
                    or path.startswith(".github/workflow_requirements")
                ):
                    typ = RepoFileType.DYNAMIC
                elif path.startswith(f"{input_path.dir_meta}/"):
                    typ = RepoFileType.META
                elif path == ".path.json":
                    typ = RepoFileType.SUPERMETA
                else:
                    typ = RepoFileType.OTHER
                summary_detail[typ].append(f"{change_type_map[change_type].value.emoji} {path}")
                change_group[typ].append(path)

        self.changed_files = change_group
        summary_details = []
        changed_groups_str = ""
        for file_type, summaries in summary_detail.items():
            if summaries:
                summary_details.append(html.h(3, file_type.value.title))
                summary_details.append(html.ul(summaries))
                changed_groups_str += f", {file_type.value}"
        if changed_groups_str:
            oneliner = f"Found changes in following groups: {changed_groups_str[2:]}."
            if summary_detail[RepoFileType.SUPERMETA]:
                oneliner = (
                    f"This event modified SuperMeta files; "
                    f"make sure to double-check that everything is correct❗ {oneliner}"
                )
        else:
            oneliner = "No changes were found."
        legend = [f"{status.value.emoji}  {status.value.title}" for status in FileChangeType]
        color_legend = html.details(content=html.ul(legend), summary="Color Legend")
        summary_details.insert(0, html.ul([oneliner, color_legend]))
        self.add_summary(
            name=name,
            status="warning"
            if summary_detail[RepoFileType.SUPERMETA]
            else ("pass" if changed_groups_str else "skip"),
            oneliner=oneliner,
            details=html.ElementCollection(summary_details),
        )
        return