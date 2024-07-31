# Standard libraries
import copy
from typing import Literal
from pathlib import Path as _Path
# Non-standard libraries
import pybadger as bdg
from markitup import html
from loggerman import logger
import pyserials as _ps
from readme_renderer.markdown import render

from controlman import _util
from controlman.nested_dict import NestedDict as _NestedDict
from controlman.file_gen.readme import badge as _badge


class ReadmeFileGenerator:

    def __init__(
        self,
        default_badge: dict | None,
        themed: bool,
        root_path: _Path,
    ):
        self._default_badge = default_badge or {}
        self._theme = themed
        self._root_path = root_path
        self._element_gen = {
            "badges": self._elem_badges,
            "covenant": self._elem_covenant,
            "heading": self._elem_heading,
            "highlights": self._elem_highlights,
            "image": self._elem_image,
            "line": self._elem_line,
            "paragraph": self._elem_paragraph,
            "spacer": self._elem_spacer,
        }
        return

    def generate(self, elements: list) -> str:
        contents = [
            html.Comment(f"Automatically Generated Document")
        ]
        for idx, element in enumerate(elements):
            if isinstance(element, str):
                element_content = element
                marker = str(idx)
            else:
                element_id = element["id"]
                element_gen = self._element_gen[element_id]
                element_content = element_gen(element)
                marker = f"{idx} - {element_id}"
            contents.extend([self._marker(start=marker), "\n", element_content, "\n", self._marker(end=marker)])
        return str(html.ElementCollection(elements=contents))

    def _elem_badges(self, badges: dict) -> str:
        default = copy.deepcopy(badges.get("default", {}))
        _ps.update.dict_from_addon(
            data=default,
            addon=self._default_badge,
            append_list=False,
            append_dict=True,
            raise_duplicates=False,
            raise_type_mismatch=False,
        )
        badges_settings = {k: v for k, v in badges.items() if k not in ("id", "default")} | {"default": default}
        shields_badges = _badge.create_badges(settings=badges_settings, themed=self._theme, root_path=self._root_path)
        badges_str = badges.get("spacer", "").join(str(badge) for badge in shields_badges)
        if "div_align" in badges:
            return str(html.DIV(content=[badges_str], align=badges["div_align"]))
        return badges_str

    @staticmethod
    def _elem_covenant(covenant) -> str:
        raw_text = _util.file.get_package_datafile("db/code_of_conduct/contributor_covenant.txt")
        contact = covenant["contact"]
        return raw_text.format(contact=f"[{contact['name']}]({contact['url']})")

    def _elem_heading(self, heading) -> str:
        content = heading["content"]
        if isinstance(content, dict):
            content = self.generate([content])
        h = html.h(level=heading["level"], content=[content])
        if heading.get("div_align"):
            h = html.DIV(content=[h], align=heading["div_align"])
        return str(h)

    def _elem_highlights(self, highlights: dict):
        elements = [highlight["title"] for highlight in highlights["highlights"]]
        badges_settings = {"elements": elements, "default": highlights["badge_default"]}
        badges = _badge.create_badges(settings=badges_settings, themed=self._theme, root_path=self._root_path)
        contents = []
        spacer = highlights.get("spacer")
        for highlight, badge in zip(highlights["highlights"], badges):
            contents.append(badge)
            if spacer:
                contents.append(spacer)
            paragraph = {
                "align": highlights["text_align"],
                "text": highlight["description"],
                "style": highlights.get("text_style", [])
            }
            text = self._elem_paragraph(paragraph)
            contents.append(text)
        if "div_align" in highlights:
            out = html.DIV(content=contents, align=highlights["div_align"])
        else:
            out = html.ElementCollection(elements=contents)
        return str(out)

    def _elem_image(self, image: dict) -> str:
        image = _NestedDict(image)
        out = html.img(
            src=image["src.light"],
            alt=image.get("alt", image.get("title")),
            title=image.get("title", image.get("alt")),
            width=image.get("width"),
            height=image.get("height"),
            align=image.get("align"),
        )
        if self._theme and image["src.dark"]:
            out = html.PICTURE(
                img=out,
                sources=[
                    html.SOURCE(
                        media=f"(prefers-color-scheme: {theme})",
                        srcset=image[f"src.{theme}"]
                    ) for theme in ("light", "dark")
                ]
            )
        if image.get("href"):
            out = html.A(href=image["href"], content=[out])
        return str(out)

    @staticmethod
    def _elem_line(line: dict):
        elem = html.HR(width=line.get("width"))
        if line.get("div_align"):
            elem = html.DIV(content=[elem], align=line["div_align"])
        return str(elem)

    @staticmethod
    def _elem_paragraph(paragraph: dict) -> str:
        p = html.P(content=[paragraph["text"]], align=paragraph.get("align"))
        for word_config in paragraph.get("style", []):
            p = p.style(**word_config)
        return str(p)

    @staticmethod
    def _elem_spacer(spacer: dict):
        s = html.IMG(
            src="docs/source/_static/img/spacer.svg",
            **{k: v for k, v in spacer.items() if k not in ("id",)},
        )
        return str(s)

    @staticmethod
    def _marker(start=None, end=None):
        if start and end:
            raise ValueError("Only one of `start` or `end` must be provided, not both.")
        if not (start or end):
            raise ValueError("At least one of `start` or `end` must be provided.")
        tag = "START" if start else "END"
        section = start if start else end
        delim = "-" * 40
        return html.Comment(f"{delim} {tag} : {section} {delim}")

    def continuous_integration(self, data):
        def github(filename, **kwargs):
            badge = self._github_badges.workflow_status(filename=filename, **kwargs)
            return badge

        def readthedocs(rtd_name, rtd_version=None, **kwargs):
            badge = bdg.shields.build_read_the_docs(project=rtd_name, version=rtd_version, **kwargs)
            return badge

        def codecov(**kwargs):
            badge = bdg.shields.coverage_codecov(
                user=self.github["user"],
                repo=self.github["repo"],
                branch=self.github["branch"],
                **kwargs,
            )
            return badge

        func_map = {"github": github, "readthedocs": readthedocs, "codecov": codecov}

        badges = []
        for test in copy.deepcopy(data["args"]["tests"]):
            func = test.pop("type")
            if "style" in test:
                style = test.pop("style")
                test = style | test
            badges.append(func_map[func](**test))

        div = html.DIV(
            align=data.get("align") or "center",
            content=[
                self._marker(start="Continuous Integration"),
                self.heading(data=data["heading"]),
                *badges,
                self._marker(end="Continuous Integration"),
            ],
        )
        return div

    def activity(self, data):
        pr_button = bdg.shields.static(text="Pull Requests", style="for-the-badge", color="444")

        prs = []
        issues = []
        for label in (None, "bug", "enhancement", "documentation"):
            prs.append(self._github_badges.pr_issue(label=label, raw=True, logo=None))
            issues.append(self._github_badges.pr_issue(label=label, raw=True, pr=False, logo=None))

        prs_div = html.DIV(align="right", content=html.ElementCollection(prs, "\n<br>\n"))
        iss_div = html.DIV(align="right", content=html.ElementCollection(issues, "\n<br>\n"))

        table = html.TABLE(
            content=[
                html.TR(
                    content=[
                        html.TD(
                            content=html.ElementCollection([pr_button, *prs], seperator="<br>"),
                            align="center",
                            valign="top",
                        ),
                        html.TD(
                            content=html.ElementCollection(
                                [
                                    bdg.shields.static(
                                        text="Milestones",
                                        style="for-the-badge",
                                        color="444",
                                    ),
                                    self._github_badges.milestones(
                                        state="both",
                                        style="flat-square",
                                        logo=None,
                                        text="Total",
                                    ),
                                    "<br>",
                                    bdg.shields.static(
                                        text="Commits",
                                        style="for-the-badge",
                                        color="444",
                                    ),
                                    self._github_badges.last_commit(logo=None),
                                    self._github_badges.commits_since(logo=None),
                                    self._github_badges.commit_activity(),
                                ],
                                seperator="<br>",
                            ),
                            align="center",
                            valign="top",
                        ),
                        html.TD(
                            content=html.ElementCollection(
                                [
                                    bdg.shields.static(
                                        text="Issues",
                                        style="for-the-badge",
                                        logo="github",
                                        color="444",
                                    ),
                                    *issues,
                                ],
                                seperator="<br>",
                            ),
                            align="center",
                            valign="top",
                        ),
                    ]
                )
            ]
        )

        div = html.DIV(
            align=data.get("align") or "center",
            content=[
                self._marker(start="Activity"),
                self.heading(data=data["heading"]),
                table,
                self._marker(end="Activity"),
            ],
        )
        return div

    def pr_issue_badge(
        self,
        pr: bool = True,
        status: Literal["open", "closed", "both"] = "both",
        label: str | None = None,
        raw: bool = False,
        **kwargs,
    ) -> bdg.Badge:
        """Number of pull requests or issues on GitHub.

        Parameters
        ----------
        pr : bool, default: True
            Whether to query pull requests (True, default) or issues (False).
        closed : bool, default: False
            Whether to query closed (True) or open (False, default) issues/pull requests.
        label : str, optional
            A specific GitHub label to query.
        raw : bool, default: False
            Display 'open'/'close' after the number (False) or only display the number (True).
        """

        def get_path_link(closed):
            path = self._url / (
                f"issues{'-pr' if pr else ''}{'-closed' if closed else ''}"
                f"{'-raw' if raw else ''}/{self._address}{f'/{label}' if label else ''}"
            )
            link = self._repo_link.pr_issues(pr=pr, closed=closed, label=label)
            return path, link

        def half_badge(closed: bool):
            path, link = get_path_link(closed=closed)
            if "link" not in args:
                args["link"] = link
            badge = ShieldsBadge(path=path, **args)
            badge.html_syntax = ""
            if closed:
                badge.color = {"right": "00802b"}
                badge.text = ""
                badge.logo = None
            else:
                badge.color = {"right": "AF1F10"}
            return badge

        desc = {
            None: {True: "pull requests in total", False: "issues in total"},
            "bug": {True: "pull requests related to a bug-fix", False: "bug-related issues"},
            "enhancement": {
                True: "pull requests related to new features and enhancements",
                False: "feature and enhancement requests",
            },
            "documentation": {
                True: "pull requests related to the documentation",
                False: "issues related to the documentation",
            },
        }
        text = {
            None: {True: "Total", False: "Total"},
            "bug": {True: "Bug Fix", False: "Bug Report"},
            "enhancement": {True: "Enhancement", False: "Feature Request"},
            "documentation": {True: "Docs", False: "Docs"},
        }

        args = self.args | kwargs
        if "text" not in args:
            args["text"] = text[label][pr]
        if "title" not in args:
            args["title"] = (
                f"Number of {status if status != 'both' else 'open (red) and closed (green)'} "
                f"{desc[label][pr]}. "
                f"Click {'on the red and green tags' if status=='both' else ''} to see the details of "
                f"the respective {'pull requests' if pr else 'issues'} in the "
                f"'{'Pull requests' if pr else 'Issues'}' section of the repository."
            )
        if "style" not in args and status == "both":
            args["style"] = "flat-square"
        if status not in ("open", "closed", "both"):
            raise ValueError()
        if status != "both":
            path, link = get_path_link(closed=status == "closed")
            if "link" not in args:
                args["link"] = link
            return ShieldsBadge(path=path, **args)
        return html.element.ElementCollection(
            [half_badge(closed) for closed in (False, True)], seperator=""
        )


