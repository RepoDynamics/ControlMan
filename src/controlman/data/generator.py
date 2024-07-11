# Standard libraries
import datetime as _datetime
from pathlib import Path as _Path
import re as _re
import copy as _copy

# Non-standard libraries
import pylinks
import trove_classifiers as _trove_classifiers
import pyserials
from loggerman import logger as _logger
import pyshellman

from controlman import _util, exception as _exception
from versionman import PEP440SemVer
from controlman._path_manager import PathManager
from controlman import ControlCenterContentManager
from controlman.data.cache import APICacheManager
from controlman.protocol import Git as _Git
from controlman.data.generator_custom import ControlCenterCustomContentGenerator


@_logger.sectioner("Generate Control Center Contents")
def generate(
    initial_data: dict,
    path_manager: PathManager,
    api_cache_retention_days: float,
    git_manager: _Git,
    custom_generator: ControlCenterCustomContentGenerator,
    github_token: str | None = None,
    ccm_before: ControlCenterContentManager | dict | None = None,
    future_versions: dict[str, str | PEP440SemVer] | None = None,
) -> dict:
    content = _ControlCenterContentGenerator(**locals()).generate()
    return content


class _ControlCenterContentGenerator:

    _SOCIAL_URL = {
        "orcid": 'orcid.org/',
        "researchgate": 'researchgate.net/profile/',
        "linkedin": 'linkedin.com/in/',
        "twitter": 'twitter.com/',
    }

    def __init__(
        self,
        initial_data: dict,
        path_manager: PathManager,
        api_cache_retention_days: float,
        git_manager: _Git,
        custom_generator: ControlCenterCustomContentGenerator,
        github_token: str | None = None,
        ccm_before: ControlCenterContentManager | dict | None = None,
        future_versions: dict[str, str | PEP440SemVer] | None = None,
    ):
        self._data = initial_data
        self._pathman = path_manager
        self._custom_gen = custom_generator
        self._git = git_manager
        self._ccm_before = ccm_before
        self._future_versions = future_versions or {}
        self._cache = APICacheManager(
            path_repo=self._pathman.root,
            path_cachefile=str(self._pathman.file_local_api_cache.relative_to(self._pathman.root)),
            retention_days=api_cache_retention_days,
        )
        self._github_api = pylinks.api.github(token=github_token)
        return

    @_logger.sectioner("Generate Contents")
    def generate(self) -> dict:
        self._data["repo"]["info"] = self._repo()
        self._people()
        self._data["name"] = self._name()
        # self._data["keywords_slug"] = self._keywords()
        self._license()
        self._copyright()
        # self._data["author"]["entries"] = self._authors()
        discussion = self._data.setdefault("discussion", {})
        self._discussion_categories()
        self._urls_github()
        self._urls_website()
        self._process_website_toctrees()
        # self._data["owner"]["publications"] = self._publications()

        if self._data.get("package"):

        self._data["label"]["compiled"] = self._repo_labels()
        self._data = pyserials.update.templated_data_from_source(
            templated_data=self._data, source_data=self._data
        )

        self._data["maintainer"]["list"] = self._maintainers()

        self._data["custom"] |= self._generate_custom_metadata()

        self._cache.save()
        return self._data

    @_logger.sectioner("Repository Data")
    def _repo(self) -> dict:
        repo_address = self._git.get_remote_repo_name(fallback_name=False, fallback_purpose=False)
        if not repo_address:
            _logger.critical(
                "Failed to determine repository GitHub address from 'origin' remote for push events. "
                "Following remotes were found:",
                str(self._git.get_remotes()),
            )
        owner_username, repo_name = repo_address
        _logger.info(title="Owner Username", msg=owner_username)
        _logger.info(title="Name", msg=repo_name)
        repo_info = self._github_api.user(owner_username).repo(repo_name).info
        _logger.info("Retrieved repository info from GitHub API")
        if "source" in repo_info:
            repo_info = repo_info["source"]
            _logger.info(
                title=f"Fork Detected",
                msg=f"Repository is a fork and target is set to '{repo_info['source']['full_name']}'.",
            )
        for attr in (
            'updated_at', 'pushed_at', 'size', 'stargazers_count', 'watchers_count',
            'forks_count', 'open_issues_count', 'forks', 'open_issues', 'watchers',
        ):
            # Remove unnecessary attributes that often change, to avoid unnecessary changes in metadata
            repo_info.pop(attr, None)
        return repo_info

    @_logger.sectioner("Project People")
    def _people(self) -> None:
        people = self._data.setdefault("people", {})
        owner = people.setdefault("owner", {})
        github = owner.setdefault("github", {})
        github["user"] = self._data["repo"]["info"]["owner"]["login"]
        for person in people.values():
            self.fill_entity(person)
        return

    @_logger.sectioner("Project Name")
    def _name(self) -> str:
        name = self._data.get("name")
        if name:
            _logger.info(f"Already set manually: '{name}'")
        else:
            name = self._data["repo"]["info"]["name"].replace("-", " ")
            _logger.info(f"Set from repository name: {name}")
        return name

    # @_logger.sectioner("Keyword Slugs")
    # def _keywords(self) -> list:
    #     slugs = []
    #     if not self._data.get("keywords"):
    #         _logger.info("No keywords specified.")
    #     else:
    #         for keyword in self._data["keywords"]:
    #             if len(keyword) <= 50:
    #                 slugs.append(keyword.lower().replace(" ", "-"))
    #         _logger.info("Set from keywords.")
    #     _logger.debug("Keyword slugs:", code=str(slugs))
    #     return slugs

    @_logger.sectioner("Project License")
    def _license(self):
        data = self._data.get("license")
        if not data:
            _logger.info("No license specified.")
            return
        license_id = data.get("id")
        license_db = _util.file.get_package_datafile("db/license/info.yaml")
        license_info = license_db.get(license_id)
        if not license_info:
            for key in ("name", "text", "notice"):
                if key not in data:
                    raise ValueError(f"`license.{key}` is required when `license.id` is not a supported ID.")
            return
        if "name" not in data:
            data["name"] = license_info["name"]
        if "trove_classifier" not in data:
            data["trove_classifier"] = f"License :: OSI Approved :: {license_info['trove_classifier']}"
        if "text" not in data:
            filename = license_id.removesuffix("-or-later")
            data["text"] = _util.file.get_package_datafile(f"db/license/text/{filename}.txt")
        if "notice" not in data:
            filename = license_id.removesuffix("-or-later")
            data["notice"] = _util.file.get_package_datafile(f"db/license/notice/{filename}.txt")
        _logger.info(f"License data set for license ID '{license_id}'.")
        _logger.debug("License data:", code=str(license_info))
        return

    @_logger.sectioner("Project Copyright")
    def _copyright(self):
        data = self._data.get("copyright")
        if not data or "period" in data:
            return
        current_year = _datetime.date.today().year
        if not data.get("start_year"):
            data["start_year"] = year_start = _datetime.datetime.strptime(
                self._data["repo"]["info"]["created_at"], "%Y-%m-%dT%H:%M:%SZ"
            ).year
            _logger.info(f"Project start year set from repository creation date: {year_start}")
        else:
            year_start = data["start_year"]
            if year_start > current_year:
                _logger.critical(
                    title="Invalid start year",
                    msg=(
                        f"Project Start year ({year_start}) cannot be greater "
                        f"than current year ({current_year})."
                    ),
                )
            _logger.info(f"Project start year already set manually in metadata: {year_start}")
        year_range = f"{year_start}{'' if year_start == current_year else f'–{current_year}'}"
        data["period"] = year_range
        return

    # @_logger.sectioner("Project Authors")
    # def _authors(self) -> list[dict]:
    #     authors = []
    #     if not self._data["author"]["entries"]:
    #         authors.append(self._data["owner"])
    #         _logger.info(f"No authors defined; setting owner as sole author.")
    #     else:
    #         for author in self._data["author"]["entries"]:
    #             authors.append(author | self._get_github_user(author["username"].lower()))
    #     return authors

    @_logger.sectioner("GitHub Discussions Categories")
    def _discussion_categories(self):
        repo_info = self._data["repo"]["info"]
        repo_full_name = repo_info["full_name"]
        discussions_info = self._cache.get(f"discussions__{repo_full_name}")
        if discussions_info:
            _logger.info(f"Set from cache.")
        elif not self._github_api.authenticated:
            _logger.notice("GitHub token not provided. Cannot get discussions categories.")
            discussions_info = []
        else:
            _logger.info("Get repository discussions from GitHub API")
            repo_api = self._github_api.user(repo_info["owner"]["login"]).repo(repo_info["name"])
            discussions_info = repo_api.discussion_categories()
            self._cache.set(f"discussions__{repo_full_name}", discussions_info)
        discussion = self._data.setdefault("discussion", {})
        form = discussion.setdefault("category", {})
        for category in discussions_info:
            category_obj = form.setdefault(category["slug"], {})
            category_obj["id"] = category["id"]
            category_obj["name"] = category["name"]
        return

    @_logger.sectioner("GitHub URLs")
    def _urls_github(self) -> None:
        gh = self._data.setdefault("url", {}).setdefault("repo", {})
        issues = gh.setdefault("issues", {})
        issues["new"] = {
            issue_type["id"]: f"{gh['issues']['home']}/new?template={idx + 1:02}_{issue_type['id']}.yaml"
            for idx, issue_type in enumerate(self._data.get("issue", {}).get("forms", []))
        }
        discussions = gh.setdefault("discussions", {})
        discussions["new"] = {
            slug: f"{gh['discussions']['home']}/new?category={slug}"
            for slug in self._data.get("discussion", {}).get("category", {}).keys()
        }
        _logger.info("Successfully generated all URLs")
        _logger.debug("Generated data:", code=str(gh))
        return

    @_logger.sectioner("Website URLs")
    def _urls_website(self) -> None:
        url = self._data.setdefault("url", {}).setdefault("web", {})
        for path_id, rel_path in self._data.get("path", {}).get("web", {}).items():
            if path_id in url:
                _logger.warning(
                    f"Website URL at 'url.web.{path_id}' already exists",
                    f"Overwriting with the value from path.web.{path_id}: '{rel_path}'",
                )
            url[path_id] = f"{url['home']}/{rel_path}"
        _logger.info("Successfully generated all URLs")
        _logger.debug("Generated data:", code=str(url))
        return

    @_logger.sectioner("Repository Maintainers")
    def _maintainers(self) -> list[dict]:
        def sort_key(val):
            return val[1]["issue"] + val[1]["pull"] + val[1]["discussion"]
        maintainers = dict()
        for role in ["issue", "discussion"]:
            if not self._data["maintainer"].get(role):
                continue
            for assignees in self._data["maintainer"][role].values():
                for assignee in assignees:
                    entry = maintainers.setdefault(assignee, {"issue": 0, "pull": 0, "discussion": 0})
                    entry[role] += 1
        codeowners_entries = self._data["maintainer"].get("pull", {}).get("reviewer", {}).get("by_path")
        if codeowners_entries:
            for codeowners_entry in codeowners_entries:
                for reviewer in codeowners_entry[list(codeowners_entry.keys())[0]]:
                    entry = maintainers.setdefault(reviewer, {"issue": 0, "pull": 0, "discussion": 0})
                    entry["pull"] += 1
        maintainers_list = [
            {**self._get_github_user(username.lower()), "roles": roles}
            for username, roles in sorted(maintainers.items(), key=sort_key, reverse=True)
        ]
        _logger.info("Successfully generated all maintainers data")
        _logger.debug("Generated data:", code=str(maintainers_list))
        return maintainers_list

    @_logger.sectioner("Repository Labels")
    def _repo_labels(self) -> list[dict[str, str]]:
        out = []
        for group_name, group in self._data["label"]["group"].items():
            prefix = group["prefix"]
            for label_id, label in group["labels"].items():
                suffix = label["suffix"]
                out.append(
                    {
                        "type": "group",
                        "group_name": group_name,
                        "id": label_id,
                        "name": f"{prefix}{suffix}",
                        "description": label["description"],
                        "color": group["color"],
                    }
                )
        release_info = self._data.get("package", {}).get("releases", {})
        for autogroup_name, release_key in (("version", "package_versions"), ("branch", "branch_names")):
            entries = release_info.get(release_key, [])
            label_data = self._data["label"]["auto_group"][autogroup_name]
            for entry in entries:
                out.append(
                    {
                        "type": "auto_group",
                        "group_name": autogroup_name,
                        "id": entry,
                        "name": f"{label_data['prefix']}{entry}",
                        "description": label_data["description"],
                        "color": label_data["color"],
                    }
                )
        for label_id, label_data in self._data["label"].get("single").items():
            out.append(
                {
                    "type": "single",
                    "group_name": None,
                    "id": label_id,
                    "name": label_data["name"],
                    "description": label_data["description"],
                    "color": label_data["color"],
                }
            )
        _logger.info("Successfully compiled all labels")
        _logger.debug("Generated data:", code=str(out))
        return out

    @_logger.sectioner("Website Sections")
    def _process_website_toctrees(self) -> None:
        path_docs = self._pathman.dir_website / "source"
        main_toctree_entries = self._extract_toctree((path_docs / "index.md").read_text())
        main_sections: list[dict[str, str]] = []
        quicklinks: list[dict[str, list[dict[str, str]]]] = []
        for main_toctree_entry in main_toctree_entries:
            text = (path_docs / main_toctree_entry).with_suffix(".md").read_text()
            title = self._extract_main_heading(text)
            path = _Path(main_toctree_entry)
            main_dir = path.parent
            main_sections.append({"title": title, "path": str(path.with_suffix(""))})
            if str(main_dir) == self._data.get("path", {}).get("web", {}).get("blog"):
                category_titles = self._get_all_blog_categories(str(main_dir))
                path_template = f'{main_dir}/category/{{}}'
                entries = [
                    {
                        "title": category_title,
                        "path": path_template.format(category_title.lower().replace(" ", "-"))
                    } for category_title in category_titles
                ]
                quicklinks.append({"title": title, "entries": entries})
                continue
            sub_toctree_entries = self._extract_toctree(text)
            if sub_toctree_entries:
                quicklink_entries = []
                for sub_toctree_entry in sub_toctree_entries:
                    subpath = main_dir / sub_toctree_entry
                    sub_text = (path_docs / subpath).with_suffix(".md").read_text()
                    sub_title = self._extract_main_heading(sub_text)
                    quicklink_entries.append(
                        {"title": sub_title, "path": str(subpath.with_suffix(""))}
                    )
                quicklinks.append({"section_title": title, "subsections": quicklink_entries})
        _logger.info("Extracted main sections:", code=str(main_sections))
        _logger.info("Extracted quicklinks:", code=str(quicklinks))

        web_paths = self._data.setdefault("path", {}).setdefault("web", {})
        web_paths["sections"] = main_sections
        web_paths["subsections"] = quicklinks
        return

    def _get_all_blog_categories(self, blog_dir) -> tuple[str, ...]:
        categories = {}
        path_posts = self._pathman.dir_website / f"{blog_dir}/post"
        for path_post in path_posts.glob("*.md"):
            post_content = path_post.read_text()
            post_categories = self._extract_blog_categories(post_content)
            if not post_categories:
                continue
            for post_category in post_categories:
                categories.setdefault(post_category, 0)
                categories[post_category] += 1
        return tuple(category[0] for category in sorted(categories.items(), key=lambda i: i[1], reverse=True))

    @staticmethod
    def _extract_main_heading(file_content: str) -> str | None:
        match = _re.search(r"^# (.*)", file_content, _re.MULTILINE)
        return match.group(1) if match else None

    @staticmethod
    def _extract_toctree(file_content: str) -> tuple[str, ...] | None:
        matches = _re.findall(r"(:{3,}){toctree}\s((.|\s)*?)\s\1", file_content, _re.DOTALL)
        if not matches:
            return
        toctree_str = matches[0][1]
        toctree_entries = []
        for line in toctree_str.splitlines():
            entry = line.strip()
            if entry and not entry.startswith(":"):
                toctree_entries.append(entry)
        return tuple(toctree_entries)

    @staticmethod
    def _extract_blog_categories(file_content: str) -> tuple[str, ...] | None:
        front_matter_match = _re.search(r'^---[\s\S]*?---', file_content, _re.MULTILINE)
        if front_matter_match:
            front_matter = front_matter_match.group()
            match = _re.search(
                r'^---[\s\S]*?\bcategory:\s*["\']?(.*?)["\']?\s*(?:\n|---)', front_matter, _re.MULTILINE
            )
            if match:
                return tuple(category.strip() for category in match.group(1).split(","))
        return

    @_logger.sectioner("Publications")
    def _publications(self) -> list[dict]:
        if not self._data["workflow"].get("get_owner_publications"):
            return []
        orcid_id = self._data["owner"]["url"].get("orcid")
        if not orcid_id:
            _logger.error(
                "The `get_owner_publications` config is enabled, "
                "but owner's ORCID ID is not set on their GitHub account."
            )
        dois = self._cache.get(f"publications_orcid_{orcid_id}")
        if not dois:
            dois = pylinks.api.orcid(orcid_id=orcid_id).doi
            self._cache.set(f"publications_orcid_{orcid_id}", dois)
        publications = []
        for doi in dois:
            publication_data = self._cache.get(f"doi_{doi}")
            if not publication_data:
                publication_data = pylinks.api.doi(doi=doi).curated
                self._cache.set(f"doi_{doi}", publication_data)
            publications.append(publication_data)
        return sorted(publications, key=lambda i: i["date_tuple"], reverse=True)

    @_logger.sectioner("Custom Metadata")
    def _generate_custom_metadata(self) -> dict:
        return self._custom_gen.generate("generate_config", self._data)

    # def _get_issue_labels(self, issue_number: int) -> tuple[dict[str, str | list[str]], list[str]]:
    #     label_prefix = {
    #         group_id: group_data["prefix"] for group_id, group_data in self._data["label"]["group"].items()
    #     }
    #     version_label_prefix = self._data["label"]["auto_group"]["version"]["prefix"]
    #     labels = (
    #         self._github_api.user(self._data["repo"]["owner"])
    #         .repo(self._data["repo"]["name"])
    #         .issue_labels(number=issue_number)
    #     )
    #     out_dict = {}
    #     out_list = []
    #     for label in labels:
    #         if label["name"].startswith(version_label_prefix):
    #             versions = out_dict.setdefault("version", [])
    #             versions.append(label["name"].removeprefix(version_label_prefix))
    #             continue
    #         for group_id, prefix in label_prefix.items():
    #             if label["name"].startswith(prefix):
    #                 if group_id in out_dict:
    #                     _logger.error(
    #                         f"Duplicate label group '{group_id}' found for issue {issue_number}.",
    #                         label["name"],
    #                     )
    #                 else:
    #                     out_dict[group_id] = label["name"].removeprefix(prefix)
    #                     break
    #         else:
    #             out_list.append(label["name"])
    #     for group_id in ("primary_type", "status"):
    #         if group_id not in out_dict:
    #             _logger.error(
    #                 f"Missing label group '{group_id}' for issue {issue_number}.",
    #                 out_dict,
    #             )
    #     return out_dict, out_list

    def fill_entity(self, data: dict) -> None:
        """Fill all missing information in an `entity` object."""

        def make_name():
            if not user_info.get("name"):
                _logger.warning(
                    f"GitHub user {gh_username} has no name",
                    f"Setting entity to legal person",
                )
                return {"legal": gh_username}
            if user_info["type"] != "User":
                return {"legal": user_info["name"]}
            name_parts = user_info["name"].split(" ")
            if len(name_parts) != 2:
                _logger.warning(
                    f"GitHub user {gh_username} has a non-standard name",
                    f"Setting entity to legal person with name {user_info['name']}",
                )
                return {"legal": user_info["name"]}
            return {"first": name_parts[0], "last": name_parts[1]}

        gh_username = data.get("github", {}).get("user")
        if gh_username:
            user_info = self._get_github_user(gh_username)
            for key_self, key_gh in (
                ("id", "id"),
                ("node_id", "node_id"),
                ("url", "html_url"),
            ):
                data["github"][key_self] = user_info[key_gh]
            if "name" not in data:
                data["name"] = make_name()
            for key_self, key_gh in (
                ("affiliation", "company"),
                ("bio", "bio"),
                ("avatar", "avatar_url"),
                ("website", "blog"),
                ("city", "location")
            ):
                if not data.get(key_self) and user_info.get(key_gh):
                    data[key_self] = user_info[key_gh]
            if not data.get("email", {}).get("user") and user_info.get("email"):
                email = data.setdefault("email", {})
                email["user"] = user_info["email"]
            for social_name, social_data in user_info["socials"].items():
                if social_name in ("orcid", "researchgate", "linkedin", "twitter") and social_name not in data:
                    data[social_name] = social_data
        for social_name, social_base_url in self._SOCIAL_URL.items():
            if social_name in data and not data[social_name].get("url"):
                data[social_name]["url"] = f"https://{social_base_url}{data[social_name]['user']}"
        if "email" in data and not data["email"].get("url"):
            data["email"]["url"] = f"mailto:{data['email']['user']}"
        if "legal" in data["name"]:
            data["name"]["full"] = data["name"]["legal"]
        else:
            full_name = data['name']['first']
            if "particle" in data["name"]:
                full_name += f' {data["name"]["particle"]}'
            full_name += f' {data["name"]["last"]}'
            if "suffix" in data["name"]:
                full_name += f', {data["name"]["suffix"]}'
            data["name"]["full"] = full_name
        return

    @_logger.sectioner("Get GitHub User Data")
    def _get_github_user(self, username: str) -> dict:

        def add_social(name, user, url):
            socials[name] = {"user": user, "url": url}
            return

        user_info = self._cache.get(f"github_user__{username}")
        if user_info:
            _logger.section_end()
            return user_info
        _logger.info(f"Get user info for '{username}' from GitHub API")
        user = self._github_api.user(username=username)
        user_info = user.info
        _logger.section(f"Get Social Accounts")
        social_accounts_info = user.social_accounts
        socials = {}
        user_info["socials"] = socials
        for account in social_accounts_info:
            for provider, base_pattern, id_pattern in (
                ("orcid", r'orcid.org/', r'([0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{3}[0-9X]{1})(.*)'),
                ("researchgate", r'researchgate.net/profile/', r'([a-zA-Z0-9_-]+)(.*)'),
                ("linkedin", r'linkedin.com/in/', r'([a-zA-Z0-9_-]+)(.*)'),
                ("twitter", r'twitter.com/', r'([a-zA-Z0-9_-]+)(.*)'),
                ("twitter", r'x.com/', r'([a-zA-Z0-9_-]+)(.*)'),
            ):
                match = _re.search(rf"{base_pattern}{id_pattern}", account["url"])
                if match:
                    add_social(
                        provider,
                        match.group(1),
                        f"https://{base_pattern}{match.group(1)}{match.group(2)}"
                    )
                    _logger.info(title=f"{provider.capitalize()} account", msg=account['url'])
                    break
            else:
                if account["provider"] != "generic":
                    add_social(account["provider"], None, account["url"])
                else:
                    generics = socials.setdefault("generics", [])
                    generics.append(account["url"])
                    _logger.info(title=f"Unknown account", msg=account['url'])
        _logger.section_end()
        self._cache.set(f"github_user__{username}", user_info)
        return user_info
