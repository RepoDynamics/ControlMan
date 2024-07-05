# Standard libraries
from pathlib import Path
from typing import Literal, Sequence

# Non-standard libraries
import pybadger as bdg
from markitup import html
from loggerman import logger
from readme_renderer.markdown import render

import controlman
from controlman._path_manager import PathManager
from controlman.datatype import DynamicFile
from controlman import ControlCenterContentManager, _util
from controlman.data.generator_custom import ControlCenterCustomContentGenerator as _ControlCenterCustomContentGenerator


class ReadmeFileGenerator:

    SUPPORTS_DARK_THEME = {
        "github": True,
        "pypi": False,
        "conda": False,
    }

    _TARGET_NAME = {
        "github": "GitHub",
        "pypi": "PyPI",
        "conda": "Conda",
    }

    def __init__(
        self,
        content_manager: ControlCenterContentManager,
        path_manager: PathManager,
        custom_generator: _ControlCenterCustomContentGenerator,
        target: Literal["github", "pypi", "conda"],
    ):
        self._ccm = content_manager
        self._pathman = path_manager
        self._custom_gen = custom_generator
        self._target = target
        self._target_name = self._TARGET_NAME[target]

        self.repo_readme_path = {
            "github": path_manager.readme_main,
            "pypi": path_manager.readme_pypi,
            "conda": path_manager.readme_conda,
        }

        self._badge_default = self._ccm["badge"]["default"]

        self._supports_dark = self.SUPPORTS_DARK_THEME[target]
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
        footer = self._generate_footer(config=self._ccm["readme"]["repo"]["footer"])
        return self.generate_health_files(footer=footer) + self.generate_dir_readmes(footer=footer)

    @logger.sectioner("Generate Health Files")
    def generate_health_files(self, footer: str) -> list[tuple[DynamicFile, str]]:

        def generate_codeowners() -> str:
            """

            Returns
            -------

            References
            ----------
            https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners#codeowners-syntax
            """
            codeowners = self._ccm["maintainer"].get("pull", {}).get("reviewer", {}).get("by_path")
            if not codeowners:
                return ""
            # Get the maximum length of patterns to align the columns when writing the file
            max_len = max([len(list(codeowner_dic.keys())[0]) for codeowner_dic in codeowners])
            text = ""
            for entry in codeowners:
                pattern = list(entry.keys())[0]
                reviewers_list = entry[pattern]
                reviewers = " ".join([f"@{reviewer.removeprefix('@')}" for reviewer in reviewers_list])
                text += f"{pattern: <{max_len}}   {reviewers}\n"
            return text

        def generate_code_of_conduct() -> str:
            if data["type"] == "contributor_covenant":
                raw_text = _util.file.get_package_datafile("db/code_of_conduct/contributor_covenant.txt")
                contact = data["config"]["contact"]
                contact_address = (
                    f'mailto:{contact["address"].removeprefix("mailto:")}' if contact["type"] == "email"
                    else contact["address"]
                )
                return raw_text.format(contact=f"[{contact['display_name']}]({contact_address})")
            logger.critical(f"Code of conduct type '{data['type']}' not recognized.")
            return

        out = []
        for health_file_id, data in self._ccm["readme"]["repo"]["health"].items():
            logger.section(health_file_id.replace("_", " ").title())
            file_info = self._pathman.health_file(health_file_id, target_path=data["path"])
            if health_file_id == "codeowners":
                file_content = generate_codeowners()
            elif data["type"] == "custom":
                file_content = self._custom_gen.generate("generate_health_file", health_file_id, self._ccm, self._pathman)
                if file_content is None:
                    logger.critical("Custom health file generator not found.")
            elif data["type"] == "manual":
                file_content = data["config"]
            elif health_file_id == "code_of_conduct":
                file_content = generate_code_of_conduct()
            else:
                logger.critical(f"Health file type '{data['type']}' not recognized.")

            if file_content and footer and data.get("include_footer"):
                file_content = f"{file_content.strip()}\n{footer}\n"
            out.append((file_info, file_content))
            logger.info(code_title="File info", code=str(file_info))
            logger.debug(code_title="File content", code=file_content)
            logger.section_end()
        return out

    @logger.sectioner("Generate Directory Readme Files")
    def generate_dir_readmes(self, footer: str) -> list[tuple[DynamicFile, str]]:
        out = []
        for dir_path, readme_config in self._ccm["readme"]["repo"]["dir"].items():
            logger.section(f"Directory '{dir_path}'", group=True)
            file_info = self._pathman.readme_dir(dir_path)
            if readme_config["type"] == "custom":
                file_content = self._custom_gen.generate("generate_directory_readme", dir_path, self._ccm, self._pathman)
                if file_content is None:
                    logger.critical("Custom directory README generator not found.")
                    continue
            else:
                # type is 'manual'
                file_content = readme_config["config"]
            if file_content and footer and readme_config["include_footer"]:
                file_content = f"{file_content.strip()}\n{footer}\n"
            out.append((file_info, file_content))
            logger.info(code_title="File info", code=file_info)
            logger.debug(code_title="File content", code=file_content)
            logger.section_end()
        return out

    def _generate_footer(self, config: dict):
        if not config:
            return ""
        if config["type"] == "pypackit-default":
            return self.footer(settings=config["config"])
        if config["type"] == "custom":
            content = self._custom_gen.generate("generate_footer", self._ccm, self._pathman)
            if content is None:
                logger.critical("Custom footer generator not found.")
            return f"{content.strip()}\n"
        # type is 'manual'
        return f'{config["config"].strip()}\n'

    def footer(self, settings: dict):
        project_badge = self.create_static_badge(settings["project"] | settings["common"])
        project_badge.set(settings=bdg.BadgeSettings(align="left"))
        left_badges = [project_badge]
        right_badges = []
        if self._ccm["license"]:
            license_badge = self.create_static_badge(settings["license"] | settings["common"])
            license_badge.set(settings=bdg.BadgeSettings(align="left" if settings["show_pypackit_badge"] else "right"))
            side = left_badges if settings["show_pypackit_badge"] else right_badges
            side.append(license_badge)
        if settings["show_pypackit_badge"]:
            pypackit_badge = self.pypackit_badge(settings=settings["common"])
            pypackit_badge.set(settings=bdg.BadgeSettings(align="right"))
            right_badges.append(pypackit_badge)
        elements = html.DIV(
            content=[
                "\n",
                html.HR(),
                self.marker(start="Left Side"),
                *left_badges,
                self.marker(end="Left Side"),
                self.marker(start="Right Side"),
                *right_badges,
                self.marker(end="Right Side"),
            ]
        )
        return elements

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
            message=text,
            color_right_light=color_light,
            color_right_dark=color_dark,
            height=height,
            link=link,
            title=title,
        )

    def create_static_badge(self, settings: dict) -> bdg.Badge | bdg.ThemedBadge:

        def set_value(k: str, d: dict) -> None:
            value = settings.get(k) or self._badge_default.get(k)
            if value:
                d[k] = value
            return

        shields_settings = {}
        for key in ["style", "logo", "logo_color", "logo_size", "logo_width", "label", "label_color", "color"]:
            set_value(key, shields_settings)
        if self._supports_dark:
            for key in ["logo_dark", "logo_color_dark", "label_color_dark", "color_dark"]:
                set_value(key, shields_settings)
        badge_settings = {}
        for key in ["link", "title", "alt", "width", "height", "align", "tag_seperator", "content_indent"]:
            set_value(key, badge_settings)
        badge = bdg.shields.core.static(
            message=settings["message"],
            shields_settings=bdg.shields.ShieldsSettings(**shields_settings),
            badge_settings=bdg.BadgeSettings(**badge_settings),
        )
        return badge

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

    def pypackit_badge(self, settings: dict):
        settings_ = {
            "style": "for-the-badge",
            "logo": (
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
            "label": "Powered by",
            "color": "rgb(0, 100, 0)",
            "color_dark": "rgb(0, 100, 0)",
            "message": f"PyPackIT {controlman.__release__}",
            "title": f"Project template created by PyPackIT version {controlman.__release__}.",
            "alt": "Powered by PyPackIT",
            "link": "https://pypackit.repodynamics.com",
        }
        if settings:
            settings_ = settings_ | settings
        return self.create_static_badge(settings_)

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


