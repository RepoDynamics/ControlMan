from typing import Literal

from ruamel.yaml import YAML

from repodynamics.datatype import WorkflowTriggeringAction


class GitHubContext:
    """
    The 'github' context of the workflow run.

    It contains information about the workflow run and the event that triggered the run.

    References
    ----------
    - [GitHub Docs](https://docs.github.com/en/actions/learn-github-actions/contexts#github-context)
    """

    def __init__(self, context: dict):
        self._token = context.pop("token")
        self._context = dict(sorted(context.items()))
        return

    def __str__(self):
        return YAML(typ=["rt", "string"]).dumps(self._context, add_final_eol=True)

    @property
    def event_name(self) -> str:
        """The name of the triggering event, e.g. 'push', 'pull_request' etc."""
        return self._context["event_name"]

    @property
    def ref(self) -> str:
        """
        The fully formed reference of the branch or tag that triggered the workflow run,
        e.g. 'refs/heads/main', 'refs/tags/v1.0' etc.

        Notes
        -----
        For workflows triggered by push, this is the branch or tag ref that was pushed.
        For workflows triggered by pull_request, this is the pull request merge branch.
        For workflows triggered by release, this is the release tag created.
        For other triggers, this is the branch or tag ref that triggered the workflow run.
        This is only set if a branch or tag is available for the event type.
        The ref given is fully-formed, meaning that for branches the format is refs/heads/<branch_name>,
        for pull requests it is refs/pull/<pr_number>/merge,
        and for tags it is refs/tags/<tag_name>.
        """
        return self._context["ref"]

    @property
    def ref_name(self) -> str:
        """The short reference name of the branch or tag that triggered the event, e.g. 'main', 'dev/1' etc."""
        return self._context["ref_name"]

    @property
    def ref_type(self) -> Literal["branch", "tag"]:
        """The type of the ref that triggered the event, either 'branch' or 'tag'."""
        return self._context["ref_type"]

    @property
    def base_ref(self):
        return self._context["base_ref"]

    @property
    def head_ref(self):
        return self._context["head_ref"]

    @property
    def repo_fullname(self) -> str:
        """Full name of the repository, i.e. <owner_username>/<repo_name>, e.g., 'RepoDynamics/RepoDynamics'"""
        return self._context["repository"]

    @property
    def repo_name(self) -> str:
        """Name of the repository, e.g., 'RepoDynamics'."""
        return self.repo_fullname.removeprefix(f"{self.repo_owner}/")

    @property
    def repo_owner(self) -> str:
        """GitHub username of the repository owner."""
        return self._context["repository_owner"]

    @property
    def sha(self) -> str:
        """The SHA hash of the most recent commit on the branch that triggered the workflow.

        The value of this commit SHA depends on the event that triggered the workflow.
        For more information, see References.

        References
        ----------
        - [GitHub Docs: Events that trigger workflows](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows)
        """
        return self._context["sha"]

    @property
    def token(self) -> str:
        """
        A token to authenticate on behalf of the GitHub App installed on your repository.

        This is functionally equivalent to the GITHUB_TOKEN secret.
        """
        return self._token


class EventPayload:
    """
    The full webhook payload of the triggering event.

    References
    ----------
    - [GitHub Docs](https://docs.github.com/en/webhooks/webhook-events-and-payloads)
    """

    def __init__(self, payload: dict):
        self._payload = dict(sorted(payload.items()))
        return

    def __str__(self):
        return YAML(typ=["rt", "string"]).dumps(self._payload, add_final_eol=True)

    @property
    def action(self) -> WorkflowTriggeringAction | None:
        action = self._payload.get("action")
        if not action:
            return None
        return WorkflowTriggeringAction(action)

    @property
    def repository(self) -> dict:
        """The repository on GitHub where the event occurred."""
        return self._payload["repository"]

    @property
    def sender(self) -> dict:
        """The GitHub user that triggered the event."""
        return self._payload["sender"]

    @property
    def repository_default_branch(self) -> str:
        return self.repository["default_branch"]

    @property
    def sender_username(self) -> str:
        """GitHub username of the user or app that triggered the event."""
        return self.sender["login"]

    @property
    def sender_email(self) -> str:
        return f"{self.sender['id']}+{self.sender_username}@users.noreply.github.com"


class IssueCommentPayload(EventPayload):
    def __init__(self, payload: dict):
        super().__init__(payload=payload)
        self._payload = payload
        self._comment = payload["comment"]
        return

    @property
    def action(self) -> Literal["created", "deleted", "edited"]:
        """Comment action type that triggered the event; one of 'created', 'deleted', 'edited'."""
        return self._payload["action"]

    @property
    def author_association(
        self,
    ) -> Literal[
        "COLLABORATOR",
        "CONTRIBUTOR",
        "FIRST_TIMER",
        "FIRST_TIME_CONTRIBUTOR",
        "MANNEQUIN",
        "MEMBER",
        "NONE",
        "OWNER",
    ]:
        return self._comment["author_association"]

    @property
    def body(self) -> str:
        """Contents of the issue comment."""
        return self._comment["body"]

    @property
    def id(self) -> int:
        """Unique identifier of the comment."""
        return self._comment["id"]

    @property
    def issue(self) -> dict:
        """Issue data."""
        return self._payload["issue"]

    @property
    def commenter_username(self) -> str:
        """Commenter username."""
        return self._comment["user"]["login"]


class IssuesPayload(EventPayload):
    def __init__(self, payload: dict):
        super().__init__(payload=payload)
        self._payload = payload
        self._issue = payload["issue"]
        return

    @property
    def author(self) -> dict:
        return self._issue["user"]

    @property
    def author_association(
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
        return self._issue["author_association"]

    @property
    def author_username(self) -> str:
        return self.author["login"]

    @property
    def title(self) -> str:
        """Title of the issue."""
        return self._issue["title"]

    @property
    def body(self) -> str | None:
        """Contents of the issue."""
        return self._issue["body"]

    @property
    def comments_count(self) -> int:
        return self._issue["comments"]

    @property
    def label(self) -> dict | None:
        """
        The label that was added or removed from the issue.

        This is only available for the 'labeled' and 'unlabeled' events.
        """
        return self._payload.get("label")

    @property
    def labels(self) -> list[dict]:
        return self._issue["labels"]

    @property
    def label_names(self) -> list[str]:
        return [label["name"] for label in self.labels]

    @property
    def node_id(self) -> str:
        return self._issue["node_id"]

    @property
    def number(self) -> int:
        return self._issue["number"]

    @property
    def state(self) -> Literal["open", "closed"]:
        return self._issue["state"]


class PullRequestPayload(EventPayload):
    def __init__(self, payload: dict):
        super().__init__(payload=payload)
        self._payload = payload
        self._pull_request = payload["pull_request"]
        return

    @property
    def number(self) -> int:
        """Pull-request number, when then event is `pull_request`."""
        return self._payload["number"]

    @property
    def title(self) -> str:
        """Pull request title."""
        return self._pull_request["title"]

    @property
    def body(self) -> str | None:
        """Pull request body."""
        return self._pull_request["body"]

    @property
    def state(self) -> Literal["open", "closed"]:
        """Pull request state; either 'open' or 'closed'."""
        return self._pull_request["state"]

    @property
    def head(self) -> dict:
        """Pull request's head branch info."""
        return self._pull_request["head"]

    @property
    def base(self) -> dict:
        """Pull request's base branch info."""
        return self._pull_request["base"]

    @property
    def head_sha(self):
        return self.head["sha"]

    @property
    def base_sha(self) -> str:
        return self.base["sha"]

    @property
    def head_repo(self) -> dict:
        return self.head["repo"]

    @property
    def head_repo_fullname(self):
        return self.head_repo["full_name"]

    @property
    def internal(self) -> bool:
        """Whether the pull request is internal, i.e., within the same repository."""
        return self.head_repo_fullname == self.repository["full_name"]

    @property
    def label(self) -> dict | None:
        """
        The label that was added or removed from the issue.

        This is only available for the 'labeled' and 'unlabeled' events.
        """
        return self._payload.get("label")

    @property
    def label_names(self) -> list[str]:
        return [label["name"] for label in self._pull_request["labels"]]

    @property
    def merged(self) -> bool:
        """Whether the pull request is merged."""
        return self.state == "closed" and self._pull_request["merged"]


class PushPayload(EventPayload):
    def __init__(self, payload: dict):
        super().__init__(payload=payload)
        self._payload = payload
        return

    @property
    def action(
        self,
    ) -> Literal[
        WorkflowTriggeringAction.CREATED, WorkflowTriggeringAction.DELETED, WorkflowTriggeringAction.EDITED
    ]:
        """Push action type."""
        if self._payload["created"]:
            return WorkflowTriggeringAction.CREATED
        if self._payload["deleted"]:
            return WorkflowTriggeringAction.DELETED
        return WorkflowTriggeringAction.EDITED

    @property
    def head_commit(self) -> dict:
        return self._payload["head_commit"]

    @property
    def head_commit_message(self) -> str:
        return self.head_commit["message"]

    @property
    def before(self) -> str:
        """The SHA hash of the most recent commit on the branch before the event."""
        return self._payload["before"]

    @property
    def after(self) -> str:
        """The SHA hash of the most recent commit on the branch after the event."""
        return self._payload["after"]


class ContextManager:
    def __init__(self, github_context: dict):
        payload_manager = {
            "issues": IssuesPayload,
            "push": PushPayload,
            "issue_comment": IssueCommentPayload,
            "pull_request": PullRequestPayload,
        }
        payload = github_context.pop("event")
        self._github = GitHubContext(context=github_context)
        event_name = self.github.event_name
        if event_name not in payload_manager:
            raise ValueError(f"Unsupported event name: {event_name}")
        self._payload = payload_manager[event_name](payload=payload)
        return

    @property
    def github(self) -> GitHubContext:
        """The 'github' context of the workflow run."""
        return self._github

    @property
    def payload(self) -> EventPayload:
        """The full webhook payload of the triggering event."""
        return self._payload

    @property
    def target_repo_fullname(self) -> str:
        return (
            self.payload.head_repo_fullname
            if self.github.event_name == "pull_request"
            else self.github.repo_fullname
        )

    @property
    def target_branch_name(self) -> str:
        return self.github.base_ref if self.github.event_name == "pull_request" else self.github.ref_name

    @property
    def ref_is_main(self) -> bool:
        return self.github.ref == f"refs/heads/{self.payload.repository_default_branch}"

    @property
    def hash_before(self) -> str:
        """The SHA hash of the most recent commit on the branch before the event."""
        if self.github.event_name == "push":
            return self.payload.before
        if self.github.event_name == "pull_request":
            return self.payload.base_sha
        return self.github.sha

    @property
    def hash_after(self) -> str:
        """The SHA hash of the most recent commit on the branch after the event."""
        if self.github.event_name == "push":
            return self.payload.after
        if self.github.event_name == "pull_request":
            return self.payload.head_sha
        return self.github.sha
