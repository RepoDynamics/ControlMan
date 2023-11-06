from markitup import html


class MetaAction:

    def action_meta(self):
        name = "Meta Sync"
        self.logger.h1(name)
        if self.event_type == EventType.DISPATCH:
            action = self._meta_sync
            self.logger.input(f"Read action from workflow dispatch input: {action}")
        else:
            metadata_raw = self.meta.read_metadata_raw()
            action = metadata_raw["workflow"]["init"]["meta_check_action"][self.event_type.value]
            self.logger.input(
                f"Read action from 'meta.workflow.init.meta_check_action.{self.event_type.value}': {action}"
            )
        if action == "none":
            self.add_summary(
                name=name,
                status="skip",
                oneliner="Meta synchronization is disabled for this event type❗",
            )
            self.logger.skip("Meta synchronization is disabled for this event type; skip❗")
            return
        if self.event_name == "pull_request" and action != "fail" and not self.pull_is_internal:
            self.logger.attention(
                "Meta synchronization cannot be performed as pull request is from a forked repository; "
                f"switching action from '{action}' to 'fail'."
            )
            action = "fail"
        if action == "pull":
            pr_branch = self.switch_to_ci_branch("meta")
        self.metadata, self.metadata_ci = self.meta.read_metadata_full()
        self.meta_results, self.meta_changes, meta_summary = self.meta.compare_files()
        meta_changes_any = any(any(change.values()) for change in self.meta_changes.values())

        # Push/amend/pull if changes are made and action is not 'fail' or 'report'
        if action not in ["fail", "report"] and meta_changes_any:
            self.meta.apply_changes()
            if action == "amend":
                self.commit(stage="all", amend=True, push=True)
            else:
                commit_msg = CommitMsg(
                    typ=self.metadata["commit"]["secondary_action"]["meta_sync"]["type"],
                    title="Sync dynamic files with meta content",
                )
                self.commit(message=str(commit_msg), stage="all", push=True, set_upstream=action == "pull")
            if action == "pull":
                pull_data = self.api.pull_create(
                    head=self.git.current_branch_name(),
                    base=self.ref_name,
                    title=commit_msg.summary,
                    body=commit_msg.body,
                )
                self.switch_to_original_branch()

        if meta_changes_any and action in ["fail", "report", "pull"]:
            self.fail = True
            status = "fail"
        else:
            status = "pass"

        if not meta_changes_any:
            oneliner = "All dynamic files are in sync with meta content."
            self.logger.success(oneliner)
        else:
            oneliner = "Some dynamic files were out of sync with meta content."
            if action in ["pull", "commit", "amend"]:
                oneliner += " These were resynchronized and applied to "
                if action == "pull":
                    link = html.a(href=pull_data["url"], content=pull_data["number"])
                    oneliner += f"branch '{pr_branch}' and a pull request ({link}) was created."
                else:
                    link = html.a(
                        href=str(self.gh_link.commit(self.hash_latest)), content=self.hash_latest[:7]
                    )
                    oneliner += "the current branch " + (
                        f"in a new commit (hash: {link})"
                        if action == "commit"
                        else f"by amending the latest commit (new hash: {link})"
                    )
        self.add_summary(name=name, status=status, oneliner=oneliner, details=meta_summary)
        return