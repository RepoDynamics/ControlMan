import pyserials as _ps


def create_environment_files(
    dependencies: list[dict],
    env_name: str = "conda_env",
    python_version_spec: str = "",
) -> tuple[str, str | None, bool]:
    """Create pip `requirements.txt` and conda `environment.yml` files from a list of dependencies.

    Parameters
    ----------
    dependencies : list[dict]
        A list of dependencies as dictionaries with paths `pip.spec`, `conda.spec`, and `conda.channel`.
    env_name : str, default: 'conda_env'
        The name of the conda environment.

    Returns
    -------
    conda_env : str
        The contents of the `environment.yaml` conda environment file.
    pip_env : str | None
        The contents of the `requirements.txt` pip requirements file,
        or `None` if no pip dependencies were found.
    pip_full : bool
        Whether the pip requirements file contains all dependencies.
    """
    pip_dependencies = []
    pip_only_dependencies = []
    conda_dependencies = [f"python {python_version_spec}".strip()]
    pip_full = True
    for dependency in dependencies:
        has_pip = "pip" in dependency
        if "conda" in dependency:
            channel = dependency["conda"].get("channel")
            spec = dependency["conda"]["spec"]
            # Specify channels for each package separately:
            #  https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html#creating-an-environment-file-manually
            conda_dependencies.append(f"{channel}::{spec}" if channel else spec)
        else:
            pip_only_dependencies.append(dependency["pip"]["spec"])
        if has_pip:
            pip_dependencies.append(dependency["pip"]["spec"])
        else:
            pip_full = False
    if pip_only_dependencies:
        conda_dependencies.insert(1, "pip")
        conda_dependencies.append({"pip": pip_only_dependencies})
    env = {
        "name": env_name,
        "dependencies": conda_dependencies,
    }
    conda_env = _ps.write.to_yaml_string(data=env, end_of_file_newline=True)
    pip_env = "\n".join(pip_dependencies) if pip_dependencies else None
    return conda_env, pip_env, pip_full
