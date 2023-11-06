

class HooksAction:

    def action_hooks(self):
        name = "Workflow Hooks"
        self.logger.h1(name)
        if self.event_type == EventType.DISPATCH:
            action = self._hooks
            self.logger.input(f"Read action from workflow dispatch input: {action}")
        else:
            action = self.metadata["workflow"]["init"]["hooks_check_action"][self.event_type.value]
            self.logger.input(
                f"Read action from 'meta.workflow.init.hooks_check_action.{self.event_type.value}': {action}"
            )
        if action == "none":
            self.add_summary(
                name=name,
                status="skip",
                oneliner="Hooks are disabled for this event type❗",
            )
            self.logger.skip("Hooks are disabled for this event type; skip❗")
            return
        if not self.metadata["workflow"].get("pre_commit"):
            oneliner = "Hooks are enabled but no pre-commit config set in 'meta.workflow.pre_commit'❗"
            self.fail = True
            self.add_summary(
                name=name,
                status="fail",
                oneliner=oneliner,
            )
            self.logger.error(oneliner, raise_error=False)
            return
        if self.event_name == "pull_request" and action != "fail" and not self.pull_is_internal:
            self.logger.attention(
                "Hook fixes cannot be applied as pull request is from a forked repository; "
                f"switching action from '{action}' to 'fail'."
            )
            action = "fail"
        if self.meta_changes.get(DynamicFileType.CONFIG, {}).get("pre-commit-config"):
            for result in self.meta_results:
                if result[0].id == "pre-commit-config":
                    config = result[1].after
                    self.logger.success(
                        "Load pre-commit config from metadata.",
                        "The pre-commit config had been changed in this event, and thus "
                        "the current config file was not valid anymore.",
                    )
                    break
            else:
                self.logger.error(
                    "Could not find pre-commit-config in meta results.",
                    "This is an internal error that should not happen; please report it on GitHub.",
                )
        else:
            config = self.meta.output_path.pre_commit_config.path
        if action == "pull":
            pr_branch = self.switch_to_ci_branch("hooks")
        input_action = (
            action if action in ["report", "amend", "commit"] else ("report" if action == "fail" else "commit")
        )
        commit_msg = (
            CommitMsg(
                typ=self.metadata["commit"]["secondary_action"]["hook_fix"]["type"],
                title="Apply automatic fixes made by workflow hooks",
            )
            if action in ["commit", "pull"]
            else ""
        )
        hooks_output = hook.run(
            ref_range=(self.hash_before, self.hash_after),
            action=input_action,
            commit_message=str(commit_msg),
            config=config,
            git=self.git,
            logger=self.logger,
        )
        passed = hooks_output["passed"]
        modified = hooks_output["modified"]
        # Push/amend/pull if changes are made and action is not 'fail' or 'report'
        if action not in ["fail", "report"] and modified:
            self.push(amend=action == "amend", set_upstream=action == "pull")
            if action == "pull":
                pull_data = self.api.pull_create(
                    head=self.git.current_branch_name(),
                    base=self.ref_name,
                    title=commit_msg.summary,
                    body=commit_msg.body,
                )
                self.switch_to_original_branch()
        if not passed or (action == "pull" and modified):
            self.fail = True
            status = "fail"
        else:
            status = "pass"

        if action == "pull" and modified:
            link = html.a(href=pull_data["url"], content=pull_data["number"])
            target = f"branch '{pr_branch}' and a pull request ({link}) was created"
        if action in ["commit", "amend"] and modified:
            link = html.a(href=str(self.gh_link.commit(self.hash_latest)), content=self.hash_latest[:7])
            target = "the current branch " + (
                f"in a new commit (hash: {link})"
                if action == "commit"
                else f"by amending the latest commit (new hash: {link})"
            )

        if passed:
            oneliner = (
                "All hooks passed without making any modifications."
                if not modified
                else (
                    "All hooks passed in the second run. "
                    f"The modifications made during the first run were applied to {target}."
                )
            )
        elif action in ["fail", "report"]:
            mode = "some failures were auto-fixable" if modified else "failures were not auto-fixable"
            oneliner = f"Some hooks failed ({mode})."
        elif modified:
            oneliner = (
                "Some hooks failed even after the second run. "
                f"The modifications made during the first run were still applied to {target}."
            )
        else:
            oneliner = "Some hooks failed (failures were not auto-fixable)."
        self.add_summary(name=name, status=status, oneliner=oneliner, details=hooks_output["summary"])
        return