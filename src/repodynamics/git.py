from typing import Literal
import subprocess
from repodynamics.logger import Logger


def set_user(username: str = "RepoDynamics", email: str = "repodynamics@users.noreply.github.com"):
    """
    Set the git username and email.
    """
    subprocess.run(["git", "config", "--global", "user.name", username])
    subprocess.run(["git", "config", "--global", "user.email", email])
    return


def has_changes(check_type: Literal['staged', 'unstaged', 'all'] = 'all') -> bool:
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
        return any(subprocess.run(cmd, capture_output=True).returncode != 0 for cmd in commands.values())
    return subprocess.run(commands[check_type], capture_output=True).returncode != 0


def push(target: str = None, ref: str = None, logger: Logger = None):
    if not logger:
        logger = Logger("console")
    command = ["git", "push"]
    if target:
        command.append(target)
    if ref:
        command.append(ref)
    cmd_str = " ".join(command)
    logger.info(f"Running '{cmd_str}':")
    process = subprocess.run(command, capture_output=True)
    logger.log(process.stdout.decode())
    if process.returncode != 0:
        logger.error(f"Failed to push changes:", process.stderr.decode())
    return commit_hash_normal(logger=logger)


def commit(
    message: str,
    stage: Literal['all', 'tracked', 'none'] = 'tracked',
    username: str = "RepoDynamics",
    email: str = "repodynamics@users.noreply.github.com",
    logger: Logger = None
):
    """
    Commit changes to git.

    Parameters:
    - message (str): The commit message.
    - username (str): The git username.
    - email (str): The git email.
    - add (bool): Whether to add all changes before committing.
    """
    if not logger:
        logger = Logger("console")
    set_user(username, email)
    if stage != 'none':
        flag = "-A" if stage == 'all' else "-u"
        add = subprocess.run(["git", "add", flag], capture_output=True)
        logger.info(f"Running 'git add {flag}':")
        logger.log(add.stdout.decode())
        if add.returncode != 0:
            logger.error(f"Failed to stage changes:", add.stderr.decode())
    commit_hash = None
    if has_changes(check_type="staged"):
        logger.info(f"Running 'git commit -m {message}':")
        commit = subprocess.run(["git", "commit", "-m", message], capture_output=True)
        logger.log(commit.stdout.decode())
        if commit.returncode != 0:
            logger.error(f"Failed to commit changes:", commit.stderr.decode())
        commit_hash = commit_hash_normal()
        logger.success(f"Committed changes. Commit hash: {commit_hash}")
    else:
        logger.attention(f"No changes to commit.")
    return commit_hash


def commit_hash_normal(parent: int = 0, logger: Logger = None):
    """
    Get the commit hash of the current commit.

    Parameters:
    - parent (int): The number of parents to traverse. Default is 0.

    Returns:
    - str: The commit hash.
    """
    if not logger:
        logger = Logger("console")
    logger.info(f"Running 'git rev-parse HEAD~{parent}':")
    process = subprocess.run(
        ["git", "rev-parse", f"HEAD~{parent}"], capture_output=True
    )
    logger.log(process.stdout.decode())
    if process.returncode != 0:
        logger.error(f"Failed to get commit hash:", process.stderr.decode())
    return process.stdout.decode().strip()


def latest_semver_tag() -> tuple[int, int, int] | None:
    process = subprocess.run(
        args=["git", "describe", "--match", "v[0-9]*.[0-9]*.[0-9]*", "--abbrev=0"],
        capture_output=True,
    )
    return (
        tuple(map(int, process.stdout.decode().strip().removeprefix("v").split(".")))
        if process.returncode == 0
        else None
    )


def create_tag(
    tag: str,
    message: str = None,
    username: str = "RepoDynamics",
    email: str = "repodynamics@users.noreply.github.com",
    push_target: str = "origin",
    logger: Logger = None
):
    if not logger:
        logger = Logger("console")
    set_user(username, email)
    if not message:
        logger.info(f"Running 'git tag {tag}':")
        process = subprocess.run(["git", "tag", tag], capture_output=True)
    else:
        logger.info(f"Running 'git tag {tag} -m {message}':")
        process = subprocess.run(["git", "tag", "-a", tag, "-m", message], capture_output=True)
    logger.log(process.stdout.decode())
    if process.returncode != 0:
        logger.error(f"Failed to create tag:", process.stderr.decode())
    process = subprocess.run(["git", "show", tag], capture_output=True)
    logger.log(process.stdout.decode())
    if push_target:
        push(target=push_target, ref=tag, logger=logger)
    return process.stdout.decode()
