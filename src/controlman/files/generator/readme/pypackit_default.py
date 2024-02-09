# Standard libraries
import copy
from typing import Literal

# Non-standard libraries
import pybadger as bdg
import pycolorit as pcit
from markitup import html
from loggerman import logger

import controlman
from controlman._path_manager import PathManager
from controlman.datatype import DynamicFile
from controlman import ControlCenterContentManager
from controlman.files.generator.readme.main import ReadmeFileGenerator


class PyPackITDefaultReadmeFileGenerator(ReadmeFileGenerator):
    def __init__(
        self,
        content_manager: ControlCenterContentManager,
        path_manager: PathManager,
        target: Literal["repo", "package"],
    ):
        super().__init__(content_manager=content_manager, path_manager=path_manager, target=target)
        self._data = self._ccm["readme"][target]["config"]
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
        logger.section(f"{'Repository' if self._is_for_gh else 'PyPI'} ReadMe File", group=True)
        html_content = html.ElementCollection(
            elements=[
                html.Comment(f"{self._ccm['name']} ReadMe File"),
                html.Comment(f"Document automatically generated by RepoDynamics v{controlman.__release__}."),
                "\n",
                self.marker(start="Header", main=True),
                self.header(),
                "\n",
                self.marker(end="Header", main=True),
                "\n",
                self.marker(start="Body", main=True),
                "\n",
                self.body(),
                "\n",
                self.marker(end="Body", main=True),
                "\n",
                self.marker(start="Footer", main=True),
                "\n",
                self.footer(),
                "\n",
                self.marker(end="Footer", main=True),
                "\n",
            ]
        )
        file_info = self._pathman.readme_main if self._is_for_gh else self._pathman.readme_pypi
        file_content = str(html_content)
        logger.info(code_title="File info", code=str(file_info))
        logger.debug(code_title="File content", code=file_content)
        logger.section_end()
        return [(file_info, file_content)]

    def header(self):
        top_menu, bottom_menu = self.menu()
        return html.DIV(
            content=[
                self.marker(start="Logo"),
                self.logo(),
                self.marker(end="Logo"),
                self.marker(start="Top Panel"),
                top_menu,
                self.marker(end="Top Panel"),
                self.marker(start="Description"),
                self.header_body(),
                self.marker(end="Description"),
                self.marker(start="Bottom Panel"),
                bottom_menu,
                self.marker(end="Bottom Panel"),
            ],
            align="center",
        )

    def body(self):
        section_gen = {
            "keynotes": self.body_keynotes
        }
        data = self._data["body"]
        content = []
        for section in data["sections"]:
            content.append(self.marker(start=f"Body section: {section['type']}"))
            content.append(html.h(2, section["config"]["title"]))
            content.append(section_gen[section["type"]](section["config"]))
            content.append(self.marker(end=f"Body section: {section['type']}"))
        return html.DIV(content=content, align="center")

    def logo(self) -> html.A:
        style = self._data["header"]["style"]
        data = self._data["header"]["logo"]

        url = (
            f"{self._ccm['path']['dir']['control']}/ui/branding/logo_full_{{}}.svg" if self._is_for_gh
            else f"{self._ccm['url']['website']['home']}/_static/logo_full_{{}}.svg"
        )
        img = html.img(
            src=url.format("light"),
            alt=data["alt_text"],
            title=data["title"],
            width=data["width"] if style == "vertical" else "auto",
            height=data["height"] if style == "horizontal" else "auto",
            align="center" if style == "vertical" else "left",
        )
        tag = html.PICTURE(
            img=img,
            sources=[
                html.SOURCE(media=f"(prefers-color-scheme: {theme})", srcset=url.format(theme))
                for theme in ("light", "dark")
            ],
        ) if self._is_for_gh else img
        logo = html.A(href=self._ccm["url"]["website"]["home"], content=[tag])
        if style == "horizontal":
            logo.content.elements.append(self.spacer(width="10px", height=data["height"], align="left"))
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
        return description

    def body_keynotes(self, config: dict):
        content = []
        for key_point in self._ccm["keynotes"]:
            content.extend(
                [
                    # self.spacer(width="10%", align="left"),
                    # self.spacer(width="10%", align="right"),
                    self.button(
                        text=key_point["title"],
                        color_light=self._ccm["theme"]["color"]["primary"][0],
                        color_dark=self._ccm["theme"]["color"]["primary"][1],
                    ),
                    html.p(content=[key_point["description"].replace("\n\n", "<br>")], align="justify"),
                ]
            )
        return html.ElementCollection(elements=content)

    def menu(self):
        top_data = self._ccm["web"]["sections"]
        bottom_data = self._data["header"]["menu_bottom"]["buttons"]
        colors_light, colors_dark = [
            pcit.gradient.interpolate_rgb(
                color_start=pcit.color.hexa(self._ccm["theme"]["color"]["primary"][theme]),
                color_end=pcit.color.hexa(self._ccm["theme"]["color"]["secondary"][theme]),
                count=len(top_data) + len(bottom_data),
            ).hex() for theme in (0, 1)
        ]
        buttons = [
            self.button(
                text=data["title"],
                color_light=color_light,
                color_dark=color_dark if self._is_for_gh else None,
                link=f"{self._ccm['url']['website']['home']}/{data['path']}",
            )
            for data, color_light, color_dark in zip(top_data + bottom_data, colors_light, colors_dark)
        ]
        menu_top, menu_bottom = [
            html.DIV(
                content=[f"{'&nbsp;' * num_spaces} ".join([str(badge) for badge in badges])],
                align="center",
            ) for badges, num_spaces in zip(
                (buttons[:len(top_data)], buttons[len(top_data):]),
                [self._data["header"][f"menu_{side}"]["num_spaces"] for side in ("top", "bottom")],
            )
        ]
        menu_bottom.content.elements.insert(0, html.HR(width="100%"))
        menu_bottom.content.elements.append(html.HR(width="80%"))
        if self._data["header"]["style"] == "vertical":
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
                self.marker(start="Continuous Integration"),
                self.heading(data=data["heading"]),
                *badges,
                self.marker(end="Continuous Integration"),
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
                self.marker(start="Activity"),
                self.heading(data=data["heading"]),
                table,
                self.marker(end="Activity"),
            ],
        )
        return div

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
            src=f"{self._ccm['url']['website']['home']}/_static/img/spacer.svg",
            **args,
        )
        return spacer
