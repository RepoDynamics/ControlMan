from typing import Literal, Optional, Sequence
from pathlib import Path
import json


class FileSyncManager:

    def __init__(
            self,
            path_root: str | Path = ".",
            paths_ext: Optional[Sequence[str | Path]] = None,
            metadata: Optional[dict] = None,
            logger: Optional[Literal["github"]] = None
    ):
        self._path_root = Path(path_root).resolve()
        if metadata:
            self._metadata = metadata
        else:
            with open(self.path_root / "meta" / ".out" / "metadata.json") as f:
                self._metadata = json.load(f)

        self._logger = logger

        self._paths_templates = [self.path_root / "meta" / "template"]
        if paths_ext:
            self._paths_templates += [Path(path_ext) / "template" for path_ext in paths_ext]
        self.summary = {
            "license": {
                "title": "License",
                "changes": {"status": "", "before": "", "after": ""},
            },
            "funding": {
                "title": "Funding",
                "changes": {"status": "", "before": "", "after": ""},
            },
            'health_file': {
                "title": "Health Files",
                "changes": {
                    "CODE_OF_CONDUCT": {"status": "", "before": "", "after": ""},
                    "CODEOWNERS": {"status": "", "before": "", "after": ""},
                    "CONTRIBUTING": {"status": "", "before": "", "after": ""},
                    "GOVERNANCE": {"status": "", "before": "", "after": ""},
                    "SECURITY": {"status": "", "before": "", "after": ""},
                    "SUPPORT": {"status": "", "before": "", "after": ""},
                }
            },
        }
        return

    @property
    def has_changes(self):
        return

    @property
    def path_root(self) -> Path:
        return self.path_root

    @property
    def metadata(self):
        return self._metadata

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
        for path in self._paths_templates:
            path_template = (path / category / name).with_suffix(ext[category])
            if path_template.exists():
                with open(path_template) as f:
                    return f.read().format(metadata=self._metadata)
        raise FileNotFoundError(
            f"Template '{name}' not found in any of template sources."
        )

    def log(self, message: str):
        if self._logger:
            self._logger.log(message)
        return

    def add_summary(
            self,
            category: Literal['health_file', 'license', 'issue_form', 'discussion_form'],
            name: str,
            status: Literal['created', 'modified', 'removed', 'unchanged', 'disabled'],
            before: str = "",
            after: str = "",
    ):
        if category not in ['health_file', 'license', 'issue_form', 'discussion_form']:
            raise ValueError(f"category '{category}' not recognized.")
        if status not in ['created', 'modified', 'removed', 'unchanged', 'disabled']:
            raise ValueError(f"status '{status}' not recognized.")
        self.summary += text
        return

    def summary(self):
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

