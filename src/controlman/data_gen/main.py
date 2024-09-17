# Standard libraries
import datetime as _datetime
import re as _re

# Non-standard libraries
from gittidy import Git as _Git
import pylinks
from loggerman import logger as _logger
import pyserials as _ps

from controlman import _file_util
from controlman.cache_manager import CacheManager
from controlman import exception as _exception


class MainDataGenerator:

    _SOCIAL_URL = {
        "orcid": 'orcid.org/',
        "researchgate": 'researchgate.net/profile/',
        "linkedin": 'linkedin.com/in/',
        "twitter": 'twitter.com/',
    }

    def __init__(
        self,
        data: _ps.NestedDict,
        cache_manager: CacheManager,
        git_manager: _Git,
        github_api: pylinks.api.GitHub,
    ):
        self._data = data
        self._git = git_manager
        self._cache = cache_manager
        self._gh_api = github_api
        self._gh_api_repo = None
        return

    @_logger.sectioner("Generate Contents")
    def generate(self) -> None:
        self._repo()
        self._team()
        self._name()
        self._keywords()
        self._license()
        self._copyright()
        self._discussion_categories()
        self._urls_github()
        self._urls_website()
        return

    @_logger.sectioner("Repository Data")
    def _repo(self) -> None:
        repo_address = self._git.get_remote_repo_name(
            remote_name="origin",
            remote_purpose="push",
            fallback_name=False,
            fallback_purpose=False
        )
        if not repo_address:
            raise _exception.data_gen.ControlManRepositoryError(
                repo_path=self._git.repo_path,
                problem="Failed to determine GitHub address. "
                "The Git repository has no remote set for push to origin. "
                f"Following remotes were found: {str(self._git.get_remotes())}",
            )
        username, repo_name = repo_address
        self._gh_api_repo = self._gh_api.user(username).repo(repo_name)
        _logger.info("GitHub API Call", f"Retrieve info for repository '{username}/{repo_name}'.")
        repo_info = self._gh_api.user(username).repo(repo_name).info
        if "source" in repo_info:
            repo_info = repo_info["source"]
            _logger.info(
                f"Fork Detected",
                f"Repository is a fork and target is set to '{repo_info['source']['full_name']}'.",
            )
        repo_info["created_at"] = _datetime.datetime.strptime(
            repo_info["created_at"], "%Y-%m-%dT%H:%M:%SZ"
        ).strftime("%Y-%m-%d")
        ccm_repo = self._data.setdefault("repo", {})
        ccm_repo.update(
            {k: repo_info[k] for k in ("id", "node_id", "name", "full_name", "created_at", "default_branch")}
        )
        ccm_repo.setdefault("url", {})["home"] = repo_info["html_url"]
        self._data["team.owner.github.id"] = repo_info["owner"]["login"]
        return

    @_logger.sectioner("Project People")
    def _team(self) -> None:
        for person_id in self._data["team"].keys():
            self._data.fill(f"team.{person_id}")
            self.fill_entity(self._data[f"team.{person_id}"])
        return

    @_logger.sectioner("Project Name")
    def _name(self) -> None:
        name = self._data.fill("name")
        repo_name = self._data["repo.name"]
        if not name:
            name = self._data["name"] = repo_name.replace("-", " ")
            _logger.info(f"Set `name`", f"Set to '{name}' from repository name")
        self._data["slug.name"] = pylinks.string.to_slug(name)
        self._data["slug.repo_name"] = pylinks.string.to_slug(repo_name)
        return

    @_logger.sectioner("Keyword slugs")
    def _keywords(self) -> None:
        keywords = self._data.fill("keywords")
        if not keywords:
            _logger.info("No keywords specified.")
        slugs = [pylinks.string.to_slug(keyword) for keyword in keywords if len(keyword) <= 50]
        self._data["slug.keywords"] = slugs
        _logger.info("Set `slug.keywords`", f"Set from `keywords`")
        _logger.debug(f"Keyword slugs: {str(slugs)}")
        return

    @_logger.sectioner("Project License")
    def _license(self):
        data = self._data["license"]
        if not data:
            _logger.info("No license specified.")
            return
        license_id = self._data.fill("license.id")
        license_db = _file_util.get_package_datafile("db/license/info.yaml")
        license_info = license_db.get(license_id)
        if not license_info:
            for key in ("name", "text", "notice"):
                if key not in data:
                    raise _exception.load.ControlManSchemaValidationError(
                        source="source",
                        before_substitution=True,
                        problem=f"`license.{key}` is required when `license.id` is not a supported ID.",
                        json_path="license",
                        data=self._data(),
                    )
            _logger.info("License data is manually set.")
            return
        if "name" not in data:
            data["name"] = license_info["name"]
        if "trove" not in data:
            data["trove"] = f"License :: OSI Approved :: {license_info['trove_classifier']}"
        if "text" not in data:
            filename = license_id.removesuffix("-or-later")
            data["text"] = _file_util.get_package_datafile(f"db/license/text/{filename}.txt")
        if "notice" not in data:
            filename = license_id.removesuffix("-or-later")
            data["notice"] = _file_util.get_package_datafile(f"db/license/notice/{filename}.txt")
        _logger.info(f"License data set for license ID '{license_id}'.")
        _logger.debug("License data:", str(license_info))
        return

    @_logger.sectioner("Project Copyright")
    def _copyright(self):
        data = self._data["copyright"]
        if not data or "period" in data:
            return
        current_year = _datetime.date.today().year
        start_year = self._data.fill("copyright.start_year")
        if not start_year:
            data["start_year"] = start_year = _datetime.datetime.strptime(
                self._data["repo.created_at"], "%Y-%m-%d"
            ).year
            _logger.info(f"Project start year set from repository creation date: {start_year}")
        else:
            if start_year > current_year:
                raise _exception.load.ControlManSchemaValidationError(
                    source="source",
                    problem=(
                        f"Project start year ({start_year}) cannot be greater "
                        f"than current year ({current_year})."
                    ),
                    json_path="copyright.start_year",
                    data=self._data(),
                )
            _logger.info(f"Project start year already set manually in metadata: {start_year}")
        year_range = f"{start_year}{'' if start_year == current_year else f'–{current_year}'}"
        data["period"] = year_range
        return

    @_logger.sectioner("GitHub Discussions Categories")
    def _discussion_categories(self):
        discussions_info = self._cache.get("repo", f"discussion_categories")
        if discussions_info:
            _logger.info(f"Set from cache.")
            return
        if not self._gh_api.authenticated:
            _logger.notice("GitHub token not provided. Cannot get discussions categories.")
            return
        _logger.info("Get repository discussions from GitHub API")
        discussions_info = self._gh_api_repo.discussion_categories()
        self._cache.set("repo", f"discussions_categories", discussions_info)
        discussion = self._data.setdefault("discussion.category", {})
        for category in discussions_info:
            category_obj = discussion.setdefault(category["slug"], {})
            category_obj["id"] = category["id"]
            category_obj["name"] = category["name"]
        return

    @_logger.sectioner("GitHub URLs")
    def _urls_github(self) -> None:
        self._data["repo.url.issues.new"] = {
            issue_type["id"]: f"{self._data['repo.url.home']}/issues/new?template={idx + 1:02}_{issue_type['id']}.yaml"
            for idx, issue_type in enumerate(self._data.get("issue.forms", []))
        }
        self._data["repo.url.discussions.new"] = {
            slug: f"{self._data['repo.url.home']}/discussions/new?category={slug}"
            for slug in self._data.get("discussion.category", {}).keys()
        }
        return

    @_logger.sectioner("Website URLs")
    def _urls_website(self) -> None:
        base_url = self._data.get("web.url.base")
        if not base_url:
            custom = self._data.fill("web.url.custom")
            if custom:
                protocol = "https" if custom["enforce_https"] else "http"
                domain = custom["name"]
                base_url = f"{protocol}://{domain}"
            elif self._data["repo.name"] == f"{self._data['team.owner.github.id']}.github.io":
                base_url = f"https://{self._data['team.owner.github.user']}.github.io"
            else:
                base_url = f"https://{self._data['team.owner.github.id']}.github.io/{self._data['repo.name']}"
            self._data["web.url.base"] = base_url
        if not self._data["web.url.home"]:
            self._data["web.url.home"] = base_url
        return

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

        gh_username = data.get("github", {}).get("id")
        if gh_username:
            user_info = self._get_github_user(gh_username)
            for key_self, key_gh in (
                ("rest_id", "id"),
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
            if not data.get("email", {}).get("id") and user_info.get("email"):
                email = data.setdefault("email", {})
                email["id"] = user_info["email"]
            for social_name, social_data in user_info["socials"].items():
                if social_name in ("orcid", "researchgate", "linkedin", "twitter") and social_name not in data:
                    data[social_name] = social_data
        # for social_name, social_base_url in self._SOCIAL_URL.items():
        #     if social_name in data and not data[social_name].get("url"):
        #         data[social_name]["url"] = f"https://{social_base_url}{data[social_name]['user']}"
        # if "email" in data and not data["email"].get("url"):
        #     data["email"]["url"] = f"mailto:{data['email']['user']}"
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
        if "orcid" in data and data["orcid"].get("get_pubs"):
            data["orcid"]["pubs"] = self._get_orcid_publications(orcid_id=data["orcid"]["user"])
        return

    @_logger.sectioner("Get GitHub User Data")
    def _get_github_user(self, username: str) -> dict:

        def add_social(name, user, url):
            socials[name] = {"id": user, "url": url}
            return

        user_info = self._cache.get("user", username)
        if user_info:
            _logger.section_end()
            return user_info
        _logger.info(f"Get user info for '{username}' from GitHub API")
        user = self._gh_api.user(username=username)
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
                    _logger.info(f"{provider.capitalize()} account", account['url'])
                    break
            else:
                if account["provider"] != "generic":
                    add_social(account["provider"], None, account["url"])
                else:
                    generics = socials.setdefault("generics", [])
                    generics.append(account["url"])
                    _logger.info(f"Unknown account", account['url'])
        _logger.section_end()
        self._cache.set("user", username, user_info)
        return user_info

    @_logger.sectioner("Get Publications")
    def _get_orcid_publications(self, orcid_id: str) -> list[dict]:
        dois = self._cache.get("orcid", orcid_id)
        if not dois:
            dois = pylinks.api.orcid(orcid_id=orcid_id).doi
            self._cache.set("orcid", orcid_id, dois)
        publications = []
        for doi in dois:
            publication_data = self._cache.get("doi", doi)
            if not publication_data:
                publication_data = pylinks.api.doi(doi=doi).curated
                self._cache.set("doi", doi, publication_data)
            publications.append(publication_data)
        return sorted(publications, key=lambda i: i["date_tuple"], reverse=True)
