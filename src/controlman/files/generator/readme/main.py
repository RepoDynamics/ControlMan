# Standard libraries
from pathlib import Path
from typing import Literal, Sequence

# Non-standard libraries
import pybadger as bdg
import pycolorit as pcit
from markitup import html
from loggerman import logger
from readme_renderer.markdown import render

import controlman
from controlman._path_manager import PathManager
from controlman.datatype import DynamicFile
from controlman import ControlCenterContentManager


class ReadmeFileGenerator:
    def __init__(
        self,
        content_manager: ControlCenterContentManager,
        path_manager: PathManager,
        target: Literal["repo", "package"],
    ):
        self._ccm = content_manager
        self._pathman = path_manager

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
        return self.generate_dir_readmes()

    @logger.sectioner("Generate Directory Readme Files")
    def generate_dir_readmes(self) -> list[tuple[DynamicFile, str]]:
        out = []
        for dir_path, readme_text in self._ccm["readme"]["dir"].items():
            logger.section(f"Directory '{dir_path}'", group=True)
            file_info = self._pathman.readme_dir(dir_path)
            file_content = f"{readme_text}\n{self.footer()}"
            out.append((file_info, file_content))
            logger.info(code_title="File info", code=file_info)
            logger.debug(code_title="File content", code=file_content)
            logger.section_end()
        return out

    def footer(self):
        project_badge = self.project_badge()
        project_badge.set(align="left")
        left_badges = [project_badge]
        if self._ccm["license"]:
            license_badge = self.license_badge()
            license_badge.set(align="left")
            left_badges.append(license_badge)
        pypackit_badge = self.pypackit_badge()
        pypackit_badge.set(align="right")
        elements = html.DIV(
            content=[
                "\n",
                html.HR(),
                self.marker(start="Left Side"),
                *left_badges,
                self.marker(end="Left Side"),
                self.marker(start="Right Side"),
                pypackit_badge,
                self.marker(end="Right Side"),
            ]
        )
        return elements

    def project_badge(self) -> bdg.Badge | bdg.ThemedBadge:
        return self.create_static_badge(
            text_right=f'©{self._ccm["copyright"]["notice"]}',
            color_right_light=self._ccm["theme"]["color"]["primary"][0],
            color_right_dark=self._ccm["theme"]["color"]["primary"][1] if self._is_for_gh else None,
            text_left=self._ccm["name"],
            logo=self._pathman.dir_meta / "ui/branding/favicon.svg",
            link=self._ccm["url"]["website"]["home"],
            title=f"{self._ccm['name']} is licensed under the {self._ccm['license']['fullname']}",
        )

    def copyright_badge(self):
        badge = bdg.shields.custom.static(
            message=self._ccm["copyright"]["notice"],
            style="for-the-badge",
            color="AF1F10",
            label="Copyright",
        )
        return badge

    def license_badge(self) -> bdg.Badge | bdg.ThemedBadge:
        return self.create_static_badge(
            text_right=self._ccm["license"]["shortname"],
            color_right_light=self._ccm["theme"]["color"]["secondary"][0],
            color_right_dark=self._ccm["theme"]["color"]["secondary"][1] if self._is_for_gh else None,
            text_left="License",
            link=f"{self._ccm['url']['website']['home']}/{self._ccm['web']['path']['license']}",
            title=f"{self._ccm['name']} is licensed under the {self._ccm['license']['fullname']}",
        )

    def button(
        self,
        text: str,
        color_light: str,
        color_dark: str | None = None,
        height: str | None = "35px",
        link: str | None = None,
        title: str | None = None,
    ) -> bdg.Badge | bdg.ThemedBadge:
        return self.create_static_badge(
            text_right=text,
            color_right_light=color_light,
            color_right_dark=color_dark,
            height=height,
            link=link,
            title=title,
        )

    def create_static_badge(
        self,
        text_right: str,
        color_right_light: str,
        color_right_dark: str | None = None,
        text_left: str | None = None,
        color_left_light: str | None = None,
        color_left_dark: str | None = None,
        style: Literal["plastic", "flat", "flat-square", "for-the-badge", "social"] = "for-the-badge",
        logo: str | Path | None = None,
        logo_color_light: str | None = None,
        logo_color_dark: str | None = None,
        logo_width: int | None = None,
        link: str | None = None,
        title: str | None = None,
        height: str | None = None,
    ):
        badge_light, badge_dark = (
            bdg.shields.custom.static(
                message=text_right,
                style=style,
                color=color_right,
                label=text_left,
                label_color=color_left,
                logo=logo,
                logo_color=color_logo,
                logo_width=logo_width,
                link=link,
            ) for color_right, color_left, color_logo in zip(
                [color_right_light, color_right_dark],
                [color_left_light, color_left_dark],
                [logo_color_light, logo_color_dark],
            )
        )
        alt = f"{f'{text_left}: ' if text_left else ''}{text_right}"
        badge_light.set(
            link=link,
            title=title or alt,
            alt=alt,
            height=height,
        )
        return badge_light + badge_dark if self._is_for_gh else badge_light




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

    @staticmethod
    def marker(start=None, end=None, main: bool = False):
        if start and end:
            raise ValueError("Only one of `start` or `end` must be provided, not both.")
        if not (start or end):
            raise ValueError("At least one of `start` or `end` must be provided.")
        tag = "START" if start else "END"
        section = start if start else end
        delim = "-" * (40 if main else 25)
        return html.Comment(f"{delim} {tag} : {section} {delim}")

    def pypackit_badge(self):
        return self.create_static_badge(
            text_right=f"PyPackIT {controlman.__release__}",
            color_right_light="rgb(0, 100, 0)",
            color_right_dark="rgb(0, 100, 0)" if self._is_for_gh else None,
            text_left="Powered By",
            logo=(
                "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAACXBIWXMAAAsPAAALDwGS"
                "+QOlAAADxklEQVRYhb1XbWxTZRR+3vvR3rt+OsJ2M5CWrKIxZJsm/gITk0XBjYQ4IJshAcJHjIq4HyyKgjJBPiLqwg"
                "8Tk6L80qATgwkLGpUE94OYSBgSIZnTFoK93VxhpV1v73s/TGu6rOu69nZlz6/zvue85zw55z73vZeYpgkraDr85IX7"
                "NLEGFHDrrtDQ8d+WW0owA4yV4LVH2juHyV9rQuYthPQwrqnX/U/3PHNswQhEmbFNCpS8vZgWW71gBFJECRQkIMyK+R"
                "DgZtvsOtV2Om5OBmomPZv795wLz/RLpB5gTMiIImEkF8+HQEEHXvr0xdXjzsjWO67QqiSX6J3uSyPdLEDAI2jc9Tj7"
                "2AGBCPOpnUVBB1Re6UrZkvDEa5HkkgXzlcw6XOr9OZixl/esOATDmopKEtBZKi2JBX7VVTIa4aLr5pW9DBSMQGPVAA"
                "Fu1FDXTw+6eAazqsCpeK+WOti6/zmfYiqlwkpiVhWUAzuxvyDrUfixbM7oXR+s7055wttEkcDBi1yN/lD7kc3np5RV"
                "MYHZsHbP853/mndes4mGkxe1gCDCwTvTgGMMuosBXATC3eaMsrbljlt6ETFgksV8ra8/6/t94npwOHVzVZgON8tmyD"
                "HO3kKCG82L073y1oNft/sqIsCD/7OYTzXUlyNKxFkqh+4eAwjeya2rNoIJbaKl3FhTTKx/v7+jlVXcgqUOzAXVoFK5"
                "sWTS2ff2xrN+tvbuxgICJjGn2iiL/2DDhx3d5SQ1YJRsfwbcmC96cNP5wxm7p+3cYHYE+z7f0UkpWpL2+EqGZRqDr3"
                "7Rt+VkV1mFc6AGbcyYdTYp4bM1fGMngKAxUKm8wcRolhyj2cHG607nEXo3+IqZXirjnn0c96kKQZa+t1J4Jlyse+TH"
                "45enZLbjRFuQ3Fv2BhB7SkiJV492/vBmHoHenZ+QfZ/t7PZwHkmkWEx14z0rBUNqGG171xXt1qm9A4MABov5syM4uj"
                "3YZ6VoNVE1FVSKigkY0CO5D5IbqZsfy+lo1nawjpIX2XRUTODCoYEzEluftUNKGIpR2c1Y9RGwhEssGAE7sQ1NXwus"
                "ADfr+WXBCHgZb568logN0e9ODJypKoEYH5u6ZDRoEg9+JLe+fGxwd5OwMuQXfPCLPjQIDfutFM+g5G14W7jd0XTyiR"
                "ZCWc8I+3f9ozQgT/cPfXTlwfwbUkb9tja9CHFuwjVsH2m+ZvvDn9m3gZeLnakqgS93nw07NFf+Q2YK8Jre/moSmHME"
                "Ts351lL94a+SuupQqY46bdHFSwf+/ympCgD8BxQORGJUan2aAAAAAElFTkSuQmCC"
            ),
            title=f"Project template created by PyPackIT version {controlman.__release__}.",
            link="https://pypackit.repodynamics.com",
        )

    @staticmethod
    def connect(
        data: Sequence[
            tuple[
                Literal[
                    "website",
                    "email",
                    "linkedin",
                    "twitter",
                    "researchgate",
                    "gscholar",
                    "orcid",
                ],
                str,
                str,
            ]
        ]
    ):
        config = {
            "website": {"label": "Website", "color": "21759B", "logo": "wordpress"},
            "email": {"label": "Email", "color": "8B89CC", "logo": "maildotru"},
            "linkedin": {"label": "LinkedIn", "color": "0A66C2", "logo": "linkedin"},
            "twitter": {"label": "Twitter", "color": "1DA1F2", "logo": "twitter"},
            "researchgate": {"label": "ResearchGate", "color": "00CCBB", "logo": "researchgate"},
            "gscholar": {"label": "Google Scholar", "color": "4285F4", "logo": "googlescholar"},
            "orcid": {"label": "ORCID", "color": "A6CE39", "logo": "orcid"},
        }
        badges = []
        for id, display, url in data:
            conf = config.get(id)
            if conf is None:
                raise ValueError(f"Data item {id} not recognized.")
            badge = bdg.shields.static(text={"left": conf["label"], "right": display})
            badge.right_color = conf["color"]
            badge.logo = conf["logo"]
            badge.a_href = url
            badges.append(badge)
        return badges

    @staticmethod
    def render_pypi_readme(markdown_str: str):
        # https://github.com/pypa/readme_renderer/blob/main/readme_renderer/markdown.py
        html_str = render(markdown_str)
        if not html_str:
            raise ValueError("Renderer encountered an error.")
        return html_str


