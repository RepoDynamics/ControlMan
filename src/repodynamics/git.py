from typing import Literal
from pathlib import Path
import re

from repodynamics.logger import Logger
from repodynamics._util.shell import run_command as _run


class Git:
    def __init__(
        self,
        path_repo: str | Path = ".",
        initialize: bool = False,
        username: str = "RepoDynamics[bot]",
        email: str = "repodynamics@users.noreply.github.com",
        logger: Logger = None
    ):
        self._logger = logger or Logger("console")
        git_available = _run(["git", "--version"], raise_command=False, logger=self._logger)
        if not git_available:
            self._logger.error(f"'git' is not installed. Please install 'git' and try again.")
        path_root, err, code = _run(
            ["git", "-C", str(Path(path_repo).resolve()), "rev-parse", "--show-toplevel"],
            raise_returncode=False,
            raise_stderr=False,
        )
        if code != 0:
            if initialize:
                raise NotImplementedError("Git initialization not implemented.")
            else:
                self._logger.error(f"No git repository found at '{path_repo}'.")
        else:
            self._path_root = Path(path_root).resolve()
        self.set_user(username=username, email=email)
        return

    def push(self, target: str = None, ref: str = None, force_with_lease: bool = False):
        command = ["git", "push"]
        if target:
            command.append(target)
        if ref:
            command.append(ref)
        if force_with_lease:
            command.append("--force-with-lease")
        self._run(command)
        return self.commit_hash_normal()

    def commit(
        self,
        message: str = "",
        stage: Literal['all', 'tracked', 'none'] = 'tracked',
        amend: bool = False,
    ):
        """
        Commit changes to git.

        Parameters:
        - message (str): The commit message.
        - username (str): The git username.
        - email (str): The git email.
        - add (bool): Whether to add all changes before committing.
        """
        if not amend and not message:
            self._logger.error("No commit message provided.")
        commit_cmd = ["git", "commit"]
        if amend:
            commit_cmd.append("--amend")
            if not message:
                commit_cmd.append("--no-edit")
        for msg_line in message.splitlines():
            commit_cmd.extend(["-m", msg_line])

        if stage != 'none':
            flag = "-A" if stage == 'all' else "-u"
            self._run(["git", "add", flag])
        commit_hash = None
        if self.has_changes(check_type="staged"):
            out, err, code = self._run(commit_cmd, raise_=False)
            if code != 0:
                self._run(commit_cmd)
            commit_hash = self.commit_hash_normal()
            self._logger.success(f"Committed changes. Commit hash: {commit_hash}")
        else:
            self._logger.attention(f"No changes to commit.")
        return commit_hash

    def create_tag(
        self,
        tag: str,
        message: str = None,
        push_target: str = "origin",
    ):
        if not message:
            self._run(["git", "tag", tag])
        else:
            self._run(["git", "tag", "-a", tag, "-m", message])
        out = self._run(["git", "show", tag])
        if push_target:
            self.push(target=push_target, ref=tag)
        return out

    def has_changes(self, check_type: Literal['staged', 'unstaged', 'all'] = 'all') -> bool:
        """Checks for git changes.

        Parameters:
        - check_type (str): Can be 'staged', 'unstaged', or 'both'. Default is 'both'.

        Returns:
        - bool: True if changes are detected, False otherwise.
        """
        commands = {
            'staged': ['git', 'diff', '--quiet', '--cached'],
            'unstaged': ['git', 'diff', '--quiet']
        }
        if check_type == 'all':
            return any(self._run(cmd, raise_=False)[2] != 0 for cmd in commands.values())
        return self._run(commands[check_type], raise_=False)[2] != 0

    def changed_files(self, ref_start: str, ref_end: str):
        """
        Get a list of files that have changed between two commits.

        Parameters:
        - ref_start (str): The starting commit hash.
        - ref_end (str): The ending commit hash.

        Returns:
        - list[str]: A list of changed files.
        """
        out = self._run(["git", "diff", "--name-only", ref_start, ref_end])
        return out.splitlines()

    def commit_hash_normal(self, parent: int = 0):
        """
        Get the commit hash of the current commit.

        Parameters:
        - parent (int): The number of parents to traverse. Default is 0.

        Returns:
        - str: The commit hash.
        """
        return self._run(["git", "rev-parse", f"HEAD~{parent}"])

    def latest_semver_tag(self) -> tuple[int, int, int] | None:
        out, err, code = self._run(
            ["git", "describe", "--match", "v[0-9]*.[0-9]*.[0-9]*", "--abbrev=0"],
            raise_=False
        )
        return tuple(map(int, out.removeprefix("v").split("."))) if code == 0 else None

    def set_user(
        self,
        username: str = "RepoDynamics[bot]",
        email: str = "repodynamics@users.noreply.github.com",
    ):
        """
        Set the git username and email.
        """
        self._run(["git", "config", "--global", "user.name", username])
        self._run(["git", "config", "--global", "user.email", email])
        return

    @property
    def remotes(self) -> dict:
        """
        Remote URLs of the git repository.

        Returns
        -------
        A dictionary where the keys are the remote names and
        the values are dictionaries of purpose:URL pairs.
        Example:

        {
            "origin": {
                "push": "git@github.com:owner/repo-name.git",
                "fetch": "git@github.com:owner/repo-name.git",
            },
            "upstream": {
                "push": "https://github.com/owner/repo-name.git",
                "fetch": "https://github.com/owner/repo-name.git"
            }
        }
        """
        out = self._run(["git", "remote", "-v"])
        remotes = {}
        for remote in out.splitlines():
            remote_name, url, purpose_raw = remote.split()
            purpose = purpose_raw.removeprefix("(").removesuffix(")")
            remote_dict = remotes.setdefault(remote_name, {})
            if purpose in remote_dict:
                self._logger.error(f"Duplicate remote purpose '{purpose}' for remote '{remote_name}'.")
            remote_dict[purpose] = url
        return remotes

    def repo_name(
        self,
        remote_name: str = "origin",
        remote_purpose: str = "push",
        fallback_name: bool = True,
        fallback_purpose: bool = True,
    ) -> tuple[str, str] | None:

        def extract_repo_name_from_url(url):
            # Regular expression pattern for extracting repo name from GitHub URL
            pattern = re.compile(r'github\.com[/:]([\w\-]+)/([\w\-.]+?)(?:\.git)?$')
            match = pattern.search(url)
            if not match:
                self._logger.attention(f"Failed to extract repo name from URL '{url}'.")
                return None
            owner, repo = match.groups()[0:2]
            return owner, repo

        remotes = self.remotes
        if not remotes:
            return
        if remote_name in remotes:
            if remote_purpose in remotes[remote_name]:
                repo_name = extract_repo_name_from_url(remotes[remote_name][remote_purpose])
                if repo_name:
                    return repo_name
            if fallback_purpose:
                for _remote_purpose, remote_url in remotes[remote_name].items():
                    repo_name = extract_repo_name_from_url(remote_url)
                    if repo_name:
                        return repo_name
        if fallback_name:
            for _remote_name, data in remotes.items():
                if remote_purpose in data:
                    repo_name = extract_repo_name_from_url(data[remote_purpose])
                    if repo_name:
                        return repo_name
                for _remote_purpose, url in data.items():
                    if _remote_purpose != remote_purpose:
                        repo_name = extract_repo_name_from_url(url)
                        if repo_name:
                            return repo_name
        return

    def check_gitattributes(self):
        command = ["sh", "-c", "git ls-files | git check-attr -a --stdin | grep 'text: auto'"]
        out = self._run(command)
        if out:
            return False
        return True

    def file_at_hash(self, commit_hash: str, path: str):
        return self._run(["git", "show", f"{commit_hash}:{path}"])

    @property
    def path_root(self) -> Path:
        return self._path_root

    def _run(self, command: list[str], raise_: bool = True, raise_stderr: bool = False, **kwargs):
        out, err, code = _run(
            command,
            cwd=self._path_root,
            raise_returncode=raise_,
            raise_stderr=raise_stderr,
            logger=self._logger,
            **kwargs
        )
        return out if raise_ else (out, err, code)


