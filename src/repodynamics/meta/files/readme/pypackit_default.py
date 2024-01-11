# Standard libraries
import copy
import datetime
import itertools
import re
from pathlib import Path
from typing import Literal, Optional, Sequence

# Non-standard libraries
import pybadger as bdg
import pycolorit as pcit
from markitup import html
from readme_renderer.markdown import render

import repodynamics
from repodynamics.path import PathFinder
from repodynamics.datatype import DynamicFile
from repodynamics.logger import Logger
from repodynamics.meta.manager import MetaManager
from repodynamics.meta.files.readme.main import ReadmeFileGenerator


class PypackitDefaultReadmeFileGenerator(ReadmeFileGenerator):
    def __init__(
        self, ccm: MetaManager,
        path: PathFinder,
        target: Literal["repo", "package"],
        logger: Logger | None = None
    ):
        super().__init__(ccm=ccm, path=path, logger=logger)
        self._data = self._ccm["readme"][target]
        self._is_for_gh = target == "repo"
        # self._github_repo_link_gen = pylinks.github.user(self.github["user"]).repo(
        #     self.github["repo"]
        # )
        # self._github_badges = bdg.shields.GitHub(
        #     user=self.github["user"],
        #     repo=self.github["repo"],
        #     branch=self.github["branch"],
        # )
        return

    def generate(self) -> list[tuple[DynamicFile, str]]:
        # file_content = html.ElementCollection(
        #     elements=[
        #         html.Comment(f"{self._metadata['name']} ReadMe File"),
        #         # html.Comment(
        #         #     f"Document automatically generated on "
        #         #     f"{datetime.datetime.utcnow().strftime('%Y.%m.%d at %H:%M:%S UTC')} "
        #         #     f"by PyPackIT {pypackit.__version__}"
        #         # ),
        #         "\n",
        #         marker(start="Header", main=True),
        #         self.header(),
        #         "\n",
        #         marker(end="Header", main=True),
        #         "\n",
        #         marker(start="Body", main=True),
        #         "\n",
        #         self.body(),
        #         "\n",
        #         marker(end="Body", main=True),
        #         "\n",
        #         marker(start="Footer", main=True),
        #         "\n",
        #         self.footer(),
        #         "\n",
        #         marker(end="Footer", main=True),
        #         "\n",
        #     ]
        # )
        file_content = self.header()
        return [(self._path.readme_main, str(file_content))]

    def header(self):
        top_menu, bottom_menu = self.menu()
        return html.DIV(
            align="center",
            content=[
                marker(start="Logo"),
                self.logo(),
                marker(end="Logo"),
                marker(start="Top Panel"),
                top_menu,
                marker(end="Top Panel"),
                marker(start="Description"),
                *self.header_body(),
                marker(end="Description"),
                marker(start="Bottom Panel"),
                bottom_menu,
                marker(end="Bottom Panel"),
            ],
        )

    def body(self):
        data = self._ccm["readme"]["repo"]["body"]
        return html.DIV(content=[getattr(self, f'{section["id"]}')(section) for section in data])

    def footer(self):
        """ """
        project_badge = self.project_badge()
        project_badge.align = "left"
        copyright_badge = self.copyright_badge()
        copyright_badge.align = "left"
        license_badge = self.license_badge()
        license_badge.align = "right"
        pypackit_badge_ = pypackit_badge()
        pypackit_badge_.align = "right"
        elements = html.DIV(
            content=[
                html.HR(),
                marker(start="Left Side"),
                project_badge,
                copyright_badge,
                marker(end="Left Side"),
                marker(start="Right Side"),
                pypackit_badge,
                license_badge,
                marker(end="Right Side"),
            ]
        )
        return elements

    def logo(self) -> html.A:
        style = self._ccm["readme"]["repo"]["header"]["style"]
        url = f"{self._ccm['path']['dir']['control']}/ui/branding/logo_full_{{}}.svg"
        picture_tag = html.PICTURE(
            img=html.IMG(
                src=url.format("light"),
                alt=f"{self._ccm['name']}: {self._ccm['tagline']}",
                title=f"Welcome to {self._ccm['name']}! Click to visit our website and learn more.",
                width="80%" if style == "vertical" else "auto",
                height="300px" if style == "horizontal" else "auto",
                align="center" if style == "vertical" else "left",
            ),
            sources=[
                html.SOURCE(media=f"(prefers-color-scheme: {theme})", srcset=url.format(theme))
                for theme in ("dark", "light")
            ],
        )
        logo = html.A(href=self._ccm["url"]["website"]["home"], content=[picture_tag])
        if self._ccm["readme"]["repo"]["header"]["style"] == "horizontal":
            logo.content.elements.append(self.spacer(width="10px", height="300px", align="left"))
        return logo

    def header_body(self):
        description = html.P(align="justify", content=[self._ccm["description"]]).style(
            {
                self._ccm["name"]: {
                    "bold": True,
                    "italic": True,
                    "link": self._ccm["url"]["website"]["home"],
                }
            }
        )
        content = [description]
        for key_point in self._ccm["keynotes"]:
            content.extend(
                [
                    # self.spacer(width="10%", align="left"),
                    # self.spacer(width="10%", align="right"),
                    self.button(text=key_point["title"], color="primary"),
                    html.P(align="justify", content=[key_point["description"]]),
                ]
            )
        return content

    def menu(self):
        def get_top_data():
            with open(path_docs / "index.md") as f:
                text = f.read()
            toctree = re.findall(r":::{toctree}\s((.|\s)*?)\s:::", text, re.DOTALL)[0][0]
            top_section_filenames = [entry for entry in toctree.splitlines() if not entry.startswith(":")]
            top_section_names = []
            for filename in top_section_filenames:
                with open((path_docs / filename).with_suffix(".md")) as f:
                    text = f.read()
                top_section_names.append(re.findall(r"^# (.*)", text, re.MULTILINE)[0])
            return [
                {"text": text, "link": str(Path(link).with_suffix(""))}
                for text, link in zip(top_section_names, top_section_filenames)
            ]

        def get_bottom_data():
            return [
                {"text": item["title"], "link": item["path"]}
                for group in self._ccm["web"].get("quicklinks")
                for item in group
                if item.get("include_in_readme")
            ]

        path_docs = self._path.dir_website / "source"
        top_data = get_top_data()
        bottom_data = get_bottom_data()
        colors = [
            pcit.gradient.interpolate_rgb(
                color_start=pcit.color.hexa(self._ccm["theme"]["color"]["primary"][theme]),
                color_end=pcit.color.hexa(self._ccm["theme"]["color"]["secondary"][theme]),
                count=len(top_data) + len(bottom_data),
            ).hex()
            for theme in (0, 1)
        ]
        buttons = [
            self.button(
                text=data["text"],
                color=(color_light, color_dark),
                link=f"{self._ccm['url']['website']['home']}/{data['link']}",
            )
            for data, color_light, color_dark in zip(top_data + bottom_data, colors[0], colors[1])
        ]
        menu_top, menu_bottom = [
            html.DIV(
                align="center",
                content=[
                    f"{'&nbsp;' * 2} ".join(
                        [str(badge.as_html_picture(tag_seperator="", content_indent="")) for badge in badges]
                    )
                ],
            )
            for badges in (buttons[: len(top_data)], buttons[len(top_data) :])
        ]
        menu_bottom.content.elements.insert(0, html.HR(width="100%"))
        menu_bottom.content.elements.append(html.HR(width="80%"))
        if self._ccm["readme"]["repo"]["header"]["style"] == "vertical":
            menu_top.content.elements.insert(0, html.HR(width="80%"))
            menu_top.content.elements.append(html.HR(width="100%"))
        else:
            menu_top.content.elements.append("<br><br>")
        return menu_top, menu_bottom

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
                marker(start="Continuous Integration"),
                self.heading(data=data["heading"]),
                *badges,
                marker(end="Continuous Integration"),
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
                marker(start="Activity"),
                self.heading(data=data["heading"]),
                table,
                marker(end="Activity"),
            ],
        )
        return div

    def project_badge(self):
        data = self._ccm["footer"]["package_badge"]
        badge = self._github_badges.release_version(
            display_name="release",
            include_pre_release=True,
            text=self._ccm["name"],
            style="for-the-badge",
            link=data["link"],
            logo=data["logo"],
        )

        badge.right_color = data["color"]
        return badge

    def copyright_badge(self):
        data = self._ccm["footer"]["copyright_badge"]
        right_text = (
            f"{data['first_release_year']}–{datetime.date.today().year} "
            if data["first_release_year"] != datetime.date.today().year
            else f"{data['first_release_year']} "
        ) + data["owner"]
        badge = bdg.shields.static(
            text={"left": "Copyright", "right": right_text},
            style="for-the-badge",
            color="AF1F10",
        )
        return badge

    def license_badge(self):
        data = self._ccm["footer"]["license_badge"]
        badge = self._github_badges.license(
            filename=data["license_path"],
            style="for-the-badge",
            color={"right": "AF1F10"},
        )
        return badge

    def button(
        self,
        text: str,
        color: Literal["primary", "secondary"] | tuple[str, str],
        link: Optional[str] = None,
        title: Optional[str] = None,
    ):
        return bdg.shields.static(
            text=text,
            style="for-the-badge",
            color={
                theme: (self._ccm["theme"]["color"][color][idx] if isinstance(color, str) else color[idx])
                for idx, theme in enumerate(("light", "dark"))
            },
            alt=text,
            title=title or text,
            height="35px",
            link=link,
        )

    @property
    def github(self):
        return self._ccm["globals"]["github"]

    def github_link_gen(self, branch: bool = False):
        if branch:
            return self._github_repo_link_gen.branch(self.github["branch"])
        return self._github_repo_link_gen

    def resolve_link(self, link: str, raw: bool = False):
        if link.startswith(("http://", "https://", "ftp://")):
            return link
        return self.github_link_gen(branch=True).file(link, raw=raw)

    def spacer(self, **args):
        spacer = html.IMG(
            src="docs/source/_static/img/spacer.svg",
            **args,
        )
        return spacer
