from typing import Literal, Optional, Sequence, Callable
from pathlib import Path

from repodynamics.logger import Logger


class MetaManager:

    def __init__(
            self,
            path_root: str | Path = ".",
            paths_ext: Optional[Sequence[str | Path]] = None,
            logger: Logger = None
    ):
        self.path_root = Path(path_root).resolve()
        self.path_meta = self.path_root / "meta"
        self.path_extensions = [Path(path_ext).resolve() for path_ext in paths_ext] if paths_ext else []
        self.path_templates = [self.path_root / "meta" / "template"] + [
            path_ext / "template" for path_ext in self.path_extensions
        ]
        self.logger = logger or Logger("github")
        self._metadata = {}
        self.summary = {
            "metadata": {
                "title": "Metadata Files",
                "changes": {"metadata.json": None},
            },
            "license": {
                "title": "License Files",
                "changes": {"LICENSE": None},
            },
            "config": {
                "title": "Configuration Files",
                "changes": {"FUNDING": None},
            },
            'health_file': {
                "title": "Health Files",
                "changes": {
                    "CODE_OF_CONDUCT": None,
                    "CODEOWNERS": None,
                    "CONTRIBUTING": None,
                    "GOVERNANCE": None,
                    "SECURITY": None,
                    "SUPPORT": None,
                }
            },
            "package": {
                "title": "Package Files",
                "changes": {
                    "pyproject.toml": None,
                    "requirements.txt": None,
                    "__init__.py": None,
                }
            }
        }
        return

    def update(
        self,
        category: str,
        name: str,
        path: str | Path,
        new_content: str | Callable = None,
        alt_paths: Sequence[str | Path] = None,
    ):
        output = {"status": "", "before": "", "after": "", "alt": {}}
        path = Path(path)
        exists = path.exists()
        if exists:
            with open(path) as f:
                output['before'] = f.read()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
        alts_removed = 0
        if alt_paths:
            for alt_path in alt_paths:
                alt_path = Path(alt_path)
                if alt_path.exists():
                    if exists or alts_removed:
                        self.logger.warning(
                            f"Removing duplicate health file at '{alt_path.relative_to(self.path_root)}'.")
                    else:
                        with open(alt_path) as f:
                            output['before'] = f.read()
                    alt_path.unlink()
                    alts_removed += 1
        if not new_content:
            path.unlink(missing_ok=True)
            output['status'] = "removed" if exists or alts_removed else "disabled"
            self.summary[category]["changes"][name] = output
            return
        with open(path, "w") as f:
            if isinstance(new_content, str):
                f.write(new_content)
            elif callable(new_content):
                new_content(f)
            else:
                raise TypeError(
                    f"Argument 'new_content' must be a string or a callable, but got {type(new_content)}."
                )
        with open(path) as f:
            output['after'] = f.read()
        output['status'] = "created" if not exists and alts_removed == 0 else (
            "modified" if output['before'] != output['after'] else "unchanged"
        )
        self.summary[category]["changes"][name] = output
        return

    def template(
            self,
            category: Literal['health_file', 'license', 'issue_form', 'discussion_form'],
            name: str
    ):
        ext = {
            'health_file': '.md',
            'license': '.txt',
            'issue_form': '.yaml',
            'discussion_form': '.yaml',
        }
        for path in self.path_templates:
            path_template = (path / category / name).with_suffix(ext[category])
            if path_template.exists():
                with open(path_template) as f:
                    return f.read().format(**self._metadata)
        raise FileNotFoundError(
            f"Template '{name}' not found in any of template sources."
        )

    @property
    def metadata(self):
        return self._metadata

    @metadata.setter
    def metadata(self, metadata: dict):
        self._metadata = metadata
        return

    def _summary(self):
        f"&nbsp;&nbsp;&nbsp;&nbsp;{'🔴' if removed else '⚫'}  {name}<br>"
        f"&nbsp;&nbsp;&nbsp;&nbsp;⚪️  {health_file}<br>"
        # File is being created
        log += f"&nbsp;&nbsp;&nbsp;&nbsp;🟢  {health_file}<br>"
        log += f"""
                        <h4>Health Files</h4>\n<ul>\n
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
