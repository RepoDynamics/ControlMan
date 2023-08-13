# Standard libraries
import re
from pathlib import Path
from typing import Literal, Optional
import sys
import os

# Non-standard libraries
import ruamel.yaml


class Templates:
    def __init__(self, metadata: dict, path_root: str | Path, extensions: dict, logger: Optional[Literal["github"]] = None):
        self.metadata = metadata
        self.log = log
        self.path_root = Path(path_root).resolve() if path_root else Path.cwd().resolve()
        self.metadata["path"]["abs"] = self._get_absolute_paths()
        self.metadata["path"]["abs"]["root"] = str(self.path_root)
        return

    def _get_absolute_paths(self):
        def recursive(dic, new_dic):
            for key, val in dic.items():
                if isinstance(val, str):
                    new_dic[key] = str(self.path_root / val)
                else:
                    new_dic[key] = recursive(val, dict())
            return new_dic

        return recursive(self.metadata["path"], dict())

    def update(self):
        self.update_license()
        self.update_health_files()
        self.update_codeowners()
        self.update_package_init_docstring()
        self.update_funding()
        return

    def update_health_files(self):
        def get_allowed_paths(template_name):
            # Health files are only allowed in the root, docs, and .github directories
            return [
                Path(self.metadata["path"]["abs"]["root"]) / allowed_path_rel / f"{template_name}.md"
                for allowed_path_rel in ['.', 'docs', '.github']
            ]
        log = "<h4>Health Files</h4>\n<ul>\n"
        health_files = ["CODE_OF_CONDUCT", "CONTRIBUTING", "GOVERNANCE", "SECURITY", "SUPPORT"]
        for health_file in health_files:
            allowed_paths = get_allowed_paths(health_file)
            if not self.metadata["path"]["health_file"][health_file.casefold()]:
                # Health file is disabled; delete it if it exists
                removed = False
                for path in allowed_paths:
                    if path.exists():
                        path.unlink()
                        removed = True
                log += f"&nbsp;&nbsp;&nbsp;&nbsp;{'🔴' if removed else '⚫'}  {health_file}<br>"
                continue
            path_target = Path(
                self.metadata["path"]["abs"]["health_file"][health_file.casefold()]
            ) / f"{health_file}.md"
            if path_target not in allowed_paths:
                error = f"⛔ ERROR: Path '{path_target}' is not an allowed path for health files."
                if self.log == "github":
                    print(error)
                    sys.exit(1)
                raise ValueError(error)
            if path_target.exists():
                with open(path_target) as f:
                    text_old = f.read()
            else:
                text_old = ""
            allowed_paths.remove(path_target)
            for allowed_path in allowed_paths:
                # Again, make sure no duplicates exist
                if allowed_path.exists():
                    allowed_path.unlink()
            with open(
                Path(self.metadata["path"]["abs"]["meta"]["template"]["health_file"]) / f"{health_file}.md"
            ) as f:
                text_template = f.read()
            text_new = text_template.format(metadata=self.metadata)
            if text_old == text_new:
                # File exists and is unchanged
                log += f"&nbsp;&nbsp;&nbsp;&nbsp;⚪️  {health_file}<br>"
                continue
            elif not text_old:
                # File is being created
                log += f"&nbsp;&nbsp;&nbsp;&nbsp;🟢  {health_file}<br>"
            else:
                # File is being modified
                log += f"""
<details>
    <summary>🟣  {health_file}</summary>
    <table width="100%">
        <tr>
            <th>Before</th>
            <th>After</th>
        </tr>
        <tr>
            <td>
                <pre>
                    <code>
                        {text_old}
                    </code>
                </pre>
            </td>
            <td>
                <pre>
                    <code>
                        {text_new}
                    </code>
                </pre>
            </td> 
        </tr>
    </table>
</details>
"""
            if self.log == "github":
                with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as fh:
                    print(log, file=fh)
            with open(path_target, "w") as f:
                f.write(text_new)
            return

    def update_license(self):
        filename = self.metadata["project"]["license"]['id'].lower().rstrip("+")
        with open(
            Path(self.metadata["path"]["abs"]["meta"]["template"]["license"]) / f"{filename}.txt"
        ) as f:
            text = f.read()
        with open(self._path_root / "LICENSE", "w") as f:
            f.write(text.format(metadata=self.metadata))
        return



    def update_codeowners(self):
        """

        Returns
        -------

        References
        ----------
        https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners#codeowners-syntax
        """
        max_len = max(
            [len(entry["pattern"]) for entry in self.metadata["maintainer"]["pulls"]]
        )
        text = ""
        for entry in self.metadata["maintainer"]["pulls"]:
            reviewers = " ".join([f"@{reviewer}" for reviewer in entry["reviewers"]])
            text += f'{entry["pattern"]: <{max_len}}   {reviewers}\n'
        with open(
            Path(self.metadata["path"]["abs"]["health_file"]["codeowners"]) / "CODEOWNERS", "w"
        ) as f:
            f.write(text)
        return

    def update_funding(self):
        """

        Returns
        -------

        References
        ----------
        https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/displaying-a-sponsor-button-in-your-repository#about-funding-files
        """
        path_funding_file = self._path_root / ".github" / "FUNDING.yml"
        if not self.metadata["project"]["funding"]:
            path_funding_file.unlink(missing_ok=True)
            return
        funding = dict()
        for funding_platform, users in self.metadata["project"]["funding"].items():
            if funding_platform not in [
                "community_bridge",
                "github",
                "issuehunt",
                "ko_fi",
                "liberapay",
                "open_collective",
                "otechie",
                "patreon",
                "tidelift",
                "custom",
            ]:
                raise ValueError(f"Funding platform '{funding_platform}' is not recognized.")
            if funding_platform in ["github", "custom"]:
                if isinstance(users, list):
                    if len(users) > 4:
                        raise ValueError("The maximum number of allowed users is 4.")
                    flow_list = ruamel.yaml.comments.CommentedSeq()
                    flow_list.fa.set_flow_style()
                    flow_list.extend(users)
                    funding[funding_platform] = flow_list
                elif isinstance(users, str):
                    funding[funding_platform] = users
                else:
                    raise ValueError(
                        f"Users of the '{funding_platform}' funding platform must be either "
                        f"a string or a list of strings, but got {users}."
                    )
            else:
                if not isinstance(users, str):
                    raise ValueError(
                        f"User of the '{funding_platform}' funding platform must be a single string, "
                        f"but got {users}."
                    )
                funding[funding_platform] = users
        with open(path_funding_file, "w") as f:
            ruamel.yaml.YAML().dump(funding, f)
        return

    def update_issue_forms(self):
        pass


def sync():
    return