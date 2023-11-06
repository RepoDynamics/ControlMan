from typing import Literal
from repodynamics.datatype import WorkflowTriggeringAction


class ContextManager:
    def __init__(self, github_context: dict):
        self._github_token = github_context.pop("token")
        self._payload = github_context.pop("event")
        self._context_github = github_context
        return

    @property
    def github(self) -> dict:
        """The 'github' context of the triggering event.

        References
        ----------
        - [GitHub Docs](https://docs.github.com/en/actions/learn-github-actions/contexts#github-context)
        """
        return self._context_github

    @property
    def payload(self) -> dict:
        """The full webhook payload of the triggering event.

        References
        ----------
        - [GitHub Docs](https://docs.github.com/en/webhooks/webhook-events-and-payloads)
        """
        return self._payload

    @property
    def github_token(self) -> str:
        return self._github_token

    @property
    def event_name(self) -> str:
        """The name of the triggering event, e.g. 'push', 'pull_request' etc."""
        return self.github["event_name"]

    @property
    def ref(self) -> str:
        """
        The full ref name of the branch or tag that triggered the event,
        e.g. 'refs/heads/main', 'refs/tags/v1.0' etc.
        """
        return self.github["ref"]

    @property
    def ref_name(self) -> str:
        """The short ref name of the branch or tag that triggered the event, e.g. 'main', 'dev/1' etc."""
        return self.github["ref_name"]

    @property
    def ref_type(self) -> Literal["branch", "tag"]:
        """The type of the ref that triggered the event, either 'branch' or 'tag'."""
        return self.github["ref_type"]

    @property
    def sha(self) -> str:
        """The SHA hash of the most recent commit on the branch that triggered the event."""
        return self.github["sha"]

    @property
    def repo_owner(self) -> str:
        """GitHub username of the repository owner."""
        return self.github["repository_owner"]

    @property
    def repo_fullname(self) -> str:
        """Name of the repository."""
        return self.github["repository"]

    @property
    def repo_name(self) -> str:
        """Name of the repository."""
        return self.repo_fullname.removeprefix(f"{self.repo_owner}/")

    @property
    def target_repo_fullname(self) -> str:
        return self.pull_head_repo_fullname if self.event_name == "pull_request" else self.repo_fullname

    @property
    def default_branch(self) -> str:
        return self.payload["repository"]["default_branch"]

    @property
    def ref_is_main(self) -> bool:
        return self.ref == f"refs/heads/{self.default_branch}"

    @property
    def triggering_actor_username(self) -> str:
        """GitHub username of the user or app that triggered the event."""
        return self.payload["sender"]["login"]

    @property
    def triggering_actor_email(self) -> str:
        return f"{self.payload['sender']['id']}+{self.triggering_actor_username}@users.noreply.github.com"

    @property
    def hash_before(self) -> str:
        """The SHA hash of the most recent commit on the branch before the event."""
        if self.event_name == "push":
            return self.payload["before"]
        if self.event_name == "pull_request":
            return self.pull_base_sha
        return self.sha

    @property
    def hash_after(self) -> str:
        """The SHA hash of the most recent commit on the branch after the event."""
        if self.event_name == "push":
            return self.payload["after"]
        if self.event_name == "pull_request":
            return self.pull_head_sha
        return self.sha

    @property
    def triggering_action(self) -> WorkflowTriggeringAction | None:
        try:
            return WorkflowTriggeringAction(self.payload.get("action"))
        except ValueError:
            return None

    @property
    def issue_triggering_action(self) -> str:
        """
        Issues action type that triggered the event,
        e.g. 'opened', 'closed', 'reopened' etc.
        See references for a full list of possible values.

        References
        ----------
        - [GitHub Docs](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#issues)
        - [GitHub Docs](https://docs.github.com/en/webhooks/webhook-events-and-payloads#issues)
        """
        return self.payload["action"]

    @property
    def issue_payload(self) -> dict:
        return self.payload["issue"]

    @property
    def issue_title(self) -> str:
        return self.issue_payload["title"]

    @property
    def issue_body(self) -> str | None:
        return self.issue_payload["body"]

    @property
    def issue_labels(self) -> list[dict]:
        return self.issue_payload["labels"]

    @property
    def issue_label_names(self) -> list[str]:
        return [label["name"] for label in self.issue_labels]

    @property
    def issue_number(self) -> int:
        return self.issue_payload["number"]

    @property
    def issue_state(self) -> Literal["open", "closed"]:
        return self.issue_payload["state"]

    @property
    def issue_author_association(
        self,
    ) -> Literal[
        "OWNER",
        "MEMBER",
        "COLLABORATOR",
        "CONTRIBUTOR",
        "FIRST_TIMER",
        "FIRST_TIME_CONTRIBUTOR",
        "MANNEQUIN",
        "NONE",
    ]:
        return self.issue_payload["author_association"]

    @property
    def issue_num_comments(self) -> int:
        return self.issue_payload["comments"]

    @property
    def issue_author(self) -> dict:
        return self.issue_payload["user"]

    @property
    def issue_author_username(self) -> str:
        return self.issue_author["login"]

    @property
    def pull_triggering_action(self) -> str:
        """
        Pull-request action type that triggered the event,
        e.g. 'opened', 'closed', 'reopened' etc.
        See references for a full list of possible values.

        References
        ----------
        - [GitHub Docs](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#pull_request)
        - [GitHub Docs](https://docs.github.com/en/webhooks/webhook-events-and-payloads?#pull_request)
        """
        return self.payload["action"]

    @property
    def pull_payload(self) -> dict:
        return self.payload["pull_request"]

    @property
    def pull_number(self) -> int:
        """Pull-request number, when then event is `pull_request`."""
        return self.payload["number"]

    @property
    def pull_state(self) -> Literal["open", "closed"]:
        """Pull request state; either 'open' or 'closed'."""
        return self.pull_payload["state"]

    @property
    def pull_head(self) -> dict:
        """Pull request's head branch info."""
        return self.pull_payload["head"]

    @property
    def pull_head_repo(self) -> dict:
        return self.pull_head["repo"]

    @property
    def pull_head_repo_fullname(self):
        return self.pull_head_repo["full_name"]

    @property
    def pull_head_ref_name(self):
        return self.github["head_ref"]

    @property
    def pull_head_sha(self):
        return self.pull_head["sha"]

    @property
    def pull_base(self) -> dict:
        """Pull request's base branch info."""
        return self.pull_payload["base"]

    @property
    def pull_base_ref_name(self):
        return self.github["base_ref"]

    @property
    def pull_base_sha(self) -> str:
        return self.pull_base["sha"]

    @property
    def pull_label_names(self) -> list[str]:
        return [label["name"] for label in self.pull_payload["labels"]]

    @property
    def pull_title(self) -> str:
        """Pull request title."""
        return self.pull_payload["title"]

    @property
    def pull_body(self) -> str | None:
        """Pull request body."""
        return self.pull_payload["body"]

    @property
    def pull_is_internal(self) -> bool:
        """Whether the pull request is internal, i.e. within the same repository."""
        return self.pull_payload["head"]["repo"]["full_name"] == self.github["repository"]

    @property
    def pull_is_merged(self) -> bool:
        """Whether the pull request is merged."""
        return self.pull_state == "closed" and self.pull_payload["merged"]

    @property
    def push_commit_head(self) -> dict:
        return self.payload["head_commit"]

    @property
    def push_commit_head_message(self) -> str:
        return self.push_commit_head["message"]

    @property
    def issue_comment_triggering_action(self) -> str:
        """Comment action type that triggered the event; one of 'created', 'deleted', 'edited'."""
        return self.payload["action"]

    @property
    def issue_comment_issue(self) -> dict:
        """Issue data."""
        return self.payload["issue"]

    @property
    def issue_comment_payload(self) -> dict:
        """Comment data."""
        return self.payload["comment"]

    @property
    def issue_comment_body(self) -> str:
        """Comment body."""
        return self.issue_comment_payload["body"]

    @property
    def issue_comment_id(self) -> int:
        """Unique identifier of the comment."""
        return self.issue_comment_payload["id"]

    @property
    def issue_comment_commenter(self) -> str:
        """Commenter username."""
        return self.issue_comment_payload["user"]["login"]
