import pyserials as _ps


def create_environment_files(
    dependencies: list[dict],
    env_name: str = "conda_env",
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
    conda_dependencies = ["python"]
    channel_frequency = {}
    pip_full = True
    for dependency in dependencies:
        has_conda = "conda" in dependency
        has_pip = "pip" in dependency
        if has_conda:
            conda_dependencies.append(dependency["conda"]["spec"])
            channel = dependency["conda"].get("channel")
            if channel:
                channel_frequency[channel] = channel_frequency.get(channel, 0) + 1
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
        "channels": sorted(channel_frequency, key=channel_frequency.get, reverse=True) + ["defaults"],
        "dependencies": conda_dependencies,
    }
    conda_env = _ps.write.to_yaml_string(data=env, end_of_file_newline=True)
    pip_env = "\n".join(pip_dependencies) if pip_dependencies else None
    return conda_env, pip_env, pip_full
