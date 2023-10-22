from typing import Literal, Optional
from pathlib import Path
import re
from contextlib import contextmanager

from repodynamics.logger import Logger
from repodynamics import _util


class Git:

    _COMMITTER_USERNAME = "RepoDynamicsBot"
    _COMMITTER_EMAIL = "146771514+RepoDynamicsBot@users.noreply.github.com"

    def __init__(
        self,
        path_repo: str | Path = ".",
        initialize: bool = False,
        logger: Logger | None = None
    ):
        self._logger = logger or Logger()
        git_available = _util.shell.run_command(["git", "--version"], raise_command=False, logger=self._logger)
        if not git_available:
            self._logger.error(f"'git' is not installed. Please install 'git' and try again.")
        path_root, err, code = _util.shell.run_command(
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
        return

    def push(self, target: str = None, ref: str = None, force_with_lease: bool = False) -> str | None:
        command = ["git", "push"]
        if target:
            command.append(target)
        if ref:
            command.append(ref)
        if force_with_lease:
            command.append("--force-with-lease")
        with self._temp_committer():
            self._run(command)
        return self.commit_hash_normal()

    def commit(
        self,
        message: str = "",
        stage: Literal['all', 'tracked', 'none'] = 'all',
        amend: bool = False,
    ) -> str | None:
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
            if msg_line:
                commit_cmd.extend(["-m", msg_line])

        if stage != 'none':
            flag = "-A" if stage == 'all' else "-u"
            with self._temp_committer():
                self._run(["git", "add", flag])
        commit_hash = None
        if self.has_changes(check_type="staged"):
            with self._temp_committer():
                out, err, code = self._run(commit_cmd, raise_=False)
            if code != 0:
                with self._temp_committer():
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
        cmd = ["git", "tag"]
        if not message:
            cmd.append(tag)
        else:
            cmd.extend(["-a", tag, "-m", message])
        with self._temp_committer():
            self._run(cmd)
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

    def changed_files(self, ref_start: str, ref_end: str) -> dict[str, list[str]]:
        """
        Get all files that have changed between two commits, and the type of changes.

        Parameters
        ----------
        ref_start : str
            The starting commit hash.
        ref_end : str
            The ending commit hash.

        Returns
        -------
        dict[str, list[str]]
            A dictionary where the keys are the type of change, and the values are lists of paths.
            The paths are given as strings, and are relative to the repository root.
            The keys are one of the following:

            - 'added': Files that have been added.
            - 'deleted': Files that have been deleted.
            - 'modified': Files that have been modified.
            - 'unmerged': Files that have been unmerged.
            - 'unknown': Files with unknown changes.
            - 'broken': Files that are broken.
            - 'copied_from': Source paths of files that have been copied.
            - 'copied_to': Destination paths of files that have been copied.
            - 'renamed_from': Source paths of files that have been renamed.
            - 'renamed_to': Destination paths of files that have been renamed.
            - 'copied_modified_from': Source paths of files that have been copied and modified.
            - 'copied_modified_to': Destination paths of files that have been copied and modified.
            - 'renamed_modified_from': Source paths of files that have been renamed and modified.
            - 'renamed_modified_to': Destination paths of files that have been renamed and modified.

            In the case of keys that end with '_from' and '_to', the elements of the corresponding
            lists are in the same order, e.g. 'copied_from[0]' and 'copied_to[0]' are the source and
            destination paths of the same file.

        """
        key_def = {
            "A": "added",
            "D": "deleted",
            "M": "modified",
            "U": "unmerged",
            "X": "unknown",
            "B": "broken",
            "C": "copied",
            "R": "renamed",
        }
        out = {}
        changes = self._run(["git", "diff", "--name-status", ref_start, ref_end]).splitlines()
        for change in changes:
            key, *paths = change.split("\t")
            if key in key_def:
                out.setdefault(key_def[key], []).extend(paths)
                continue
            key, similarity = key[0], int(key[1:])
            if key not in ["C", "R"]:
                self._logger.error(f"Unknown change type '{change}'.")
            out_key = key_def[key]
            if similarity != 100:
                out_key += "_modified"
            out.setdefault(f"{out_key}_from", []).append(paths[0])
            out.setdefault(f"{out_key}_to", []).append(paths[1])
        return out

    def commit_hash_normal(self, parent: int = 0) -> str | None:
        """
        Get the commit hash of the current commit.

        Parameters:
        - parent (int): The number of parents to traverse. Default is 0.

        Returns:
        - str: The commit hash.
        """
        return self._run(["git", "rev-parse", f"HEAD~{parent}"])

    def describe(
        self,
        abbrev: int | None = None,
        first_parent: bool = True,
        match: str | None = None
    ) -> str | None:
        cmd = ["git", "describe"]
        if abbrev is not None:
            cmd.append(f"--abbrev={abbrev}")
        if first_parent:
            cmd.append("--first-parent")
        if match:
            cmd.extend(["--match", match])
        out, err, code = self._run(command=cmd, raise_=False)
        return out if code == 0 else None

    def log(
        self,
        number: int | None = None,
        simplify_by_decoration: bool = True,
        tags: bool | str = True,
        pretty: str | None = "format:%D",
        date: str | None = None,
        revision_range: str | None = None,
        paths: str | list[str] | None = None
    ):
        cmd = ["git", "log"]
        if number:
            cmd.append(f"-{number}")
        if simplify_by_decoration:
            cmd.append("--simplify-by-decoration")
        if tags:
            cmd.append(f"--tags={tags}" if isinstance(tags, str) else "--tags")
        if pretty:
            cmd.append(f"--pretty={pretty}")
        if date:
            cmd.append(f"--date={date}")
        if revision_range:
            cmd.append(revision_range)
        if paths:
            cmd.extend(["--"] + (paths if isinstance(paths, list) else [paths]))
        return self._run(cmd)

    def set_user(
        self,
        username: str | None,
        email: str | None,
        user_type: Literal['user', 'author', 'committer'] = 'user',
        scope: Optional[Literal['system', 'global', 'local', 'worktree']] = 'global'
    ):
        """
        Set the git username and email.
        """
        cmd = ["git", "config"]
        if scope:
            cmd.append(f"--{scope}")
        if not (
            (username is None or isinstance(username, str))
            and (email is None or isinstance(email, str))
        ):
            raise ValueError("username and email must be either a string or None.")
        for key, val in [("name", username), ("email", email)]:
            if val is None:
                self._run([*cmd, "--unset", f"{user_type}.{key}"])
            else:
                self._run([*cmd, f"{user_type}.{key}", val])
        return

    def get_user(
        self,
        user_type: Literal['user', 'author', 'committer'] = 'user',
        scope: Optional[Literal['system', 'global', 'local', 'worktree']] = None
    ) -> tuple[str | None, str | None]:
        """
        Get the git username and email.
        """
        cmd = ["git", "config"]
        if scope:
            cmd.append(f"--{scope}")
        user = []
        for key in ["name", "email"]:
            out, err, code = self._run([*cmd, f"{user_type}.{key}"], raise_=False)
            if code == 0:
                user.append(out)
            elif code == 1 and not out:
                user.append(None)
            else:
                self._logger.error(f"Failed to get {user_type}.{key}.", details=err, exit_code=code)
        return tuple(user)

    def get_commits(
        self,
        revision_range: str | None = None
    ) -> list[dict[str, str | list[str]]]:
        """
        Get a list of commits.

        Parameters:
        - revision_range (str): The revision range to get commits from.

        Returns:
        - list[str]: A list of commit hashes.
        """
        marker_start = "<start new commit>"
        hash = "%H"
        author = "%an"
        date = "%ad"
        commit = "%B"
        marker_commit_end = "<end of commit message>"

        format = f"{marker_start}%n{hash}%n{author}%n{date}%n{commit}%n{marker_commit_end}"
        cmd = ['git', 'log', f'--pretty=format:{format}', "--name-only"]

        if revision_range:
            cmd.append(revision_range)
        out = self._run(cmd)

        pattern = re.compile(
            rf"{re.escape(marker_start)}\n(.*?)\n(.*?)\n(.*?)\n(.*?){re.escape(marker_commit_end)}\n(.*?)\n\n",
            re.DOTALL
        )

        matches = pattern.findall(out)

        commits = []
        for match in matches:
            commit_info = {
                'hash': match[0].strip(),
                'author': match[1].strip(),
                'date': match[2].strip(),
                'msg': match[3].strip(),
                'files': list(filter(None, match[4].strip().split('\n')))
            }
            commits.append(commit_info)

        return commits

    def current_branch_name(self) -> str:
        """Get the name of the current branch."""
        return self._run(["git", "branch", "--show-current"])

    def get_all_branch_names(self) -> tuple[str, list[str]]:
        """Get the name of the current branch."""
        branches_str = self._run(["git", "branch"])
        branches_other = []
        branch_current = []
        for branch in branches_str.split("\n"):
            branch = branch.strip()
            if not branch:
                continue
            if branch.startswith("*"):
                branch_current.append(branch.removeprefix("*").strip())
            else:
                branches_other.append(branch)
        if len(branch_current) > 1:
            raise RuntimeError("More than one current branch found.")
        return branch_current[0], branches_other

    def checkout(self, branch: str, create: bool = False, reset: bool = False):
        """Checkout a branch."""
        cmd = ["git", "checkout"]
        if reset:
            cmd.append("-B")
        elif create:
            cmd.append("-b")
        cmd.append(branch)
        return self._run(cmd)

    def get_distance(self, ref_start: str, ref_end: str = "HEAD") -> int:
        """
        Get the distance between two commits.

        Parameters:
        - ref_start (str): The starting commit hash.
        - ref_end (str): The ending commit hash.

        Returns:
        - int: The distance between the two commits.
        """
        return int(self._run(["git", "rev-list", "--count", f"{ref_start}..{ref_end}"]))

    def get_tags(self) -> list[list[str]]:
        """Get a list of tags reachable from the current commit

        This returns a list of tags ordered by the commit date (newest first).
        Each element is a list itself, containing all tags that point to the same commit.
        """
        output = self.log(simplify_by_decoration=True, tags=True, pretty="format:%D")
        tags = []
        for line in output.splitlines():
            potential_tags = line.split(", ")
            sub_list_added = False
            for potential_tag in potential_tags:
                if potential_tag.startswith("tag: "):
                    tag = potential_tag.removeprefix("tag: ")
                    if not sub_list_added:
                        tags.append([])
                        sub_list_added = True
                    tags[-1].append(tag)
        return tags

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

    def discard_changes(self, path: str | Path = "."):
        """Revert all uncommitted changes in the specified path, back to the state of the last commit."""
        return self._run(["git", "checkout", "--", str(path)])

    def stash(
        self,
        name: str = "Stashed by RepoDynamics",
        include: Literal['tracked', 'untracked', 'all'] = 'all'
    ):
        """Stash changes in the working directory.

        This takes the modified files, stages them and saves them on a stack of unfinished changes
        that can be reapplied at any time.

        Parameters
        ----------
        name : str, default: "Stashed by RepoDynamics"
            The name of the stash.
        include : {'tracked', 'untracked', 'all'}, default: 'all'
            Which files to include in the stash.

            - 'tracked': Stash tracked files only.
            - 'untracked': Stash tracked and untracked files.
            - 'all': Stash all files, including ignored files.
        """
        command = ["git", "stash"]
        if include in ['untracked', 'all']:
            command.extend(["save", "--include-untracked" if include == 'untracked' else "--all"])
        if name:
            command.append(str(name))
        return self._run(command)

    def stash_pop(self):
        """Reapply the most recently stashed changes and remove the stash from the stack.

        This will take the changes stored in the stash and apply them back to the working directory,
        removing the stash from the stack.
        """
        return self._run(["git", "stash", "pop"])

    @property
    def path_root(self) -> Path:
        return self._path_root

    def _run(
        self, command: list[str], raise_: bool = True, raise_stderr: bool = False, **kwargs
    ) -> str | tuple[str, str, int]:
        out, err, code = _util.shell.run_command(
            command,
            cwd=self._path_root,
            raise_returncode=raise_,
            raise_stderr=raise_stderr,
            logger=self._logger,
            **kwargs
        )
        return out if raise_ else (out, err, code)

    @contextmanager
    def _temp_committer(self):
        committer_username, committer_email = self.get_user(user_type="committer", scope="local")
        if committer_username != self._COMMITTER_USERNAME or committer_email != self._COMMITTER_EMAIL:
            self.set_user(
                username=self._COMMITTER_USERNAME,
                email=self._COMMITTER_EMAIL,
                user_type="committer",
                scope="local"
            )
        yield
        if committer_username != self._COMMITTER_USERNAME or committer_email != self._COMMITTER_EMAIL:
            self.set_user(
                username=committer_username,
                email=committer_email,
                user_type="committer",
                scope="local"
            )
        return

    @contextmanager
    def temp_author(self, username: str = None, email: str = None):
        author_username, author_email = self.get_user(user_type="author", scope="local")
        username = username or self._COMMITTER_USERNAME
        email = email or self._COMMITTER_EMAIL
        if author_username != username or author_email != email:
            self.set_user(
                username=username,
                email=email,
                user_type="author",
                scope="local"
            )
        yield
        if author_username != username or author_email != email:
            self.set_user(
                username=author_username,
                email=author_email,
                user_type="author",
                scope="local"
            )
        return
