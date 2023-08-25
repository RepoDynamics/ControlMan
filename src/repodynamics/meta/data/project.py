import datetime
import re
from typing import Optional
import json

import pylinks

from repodynamics.meta import db
from repodynamics.meta.data._cache import Cache
from repodynamics.logger import Logger


class Project:

    def __init__(self, metadata: dict, cache: Cache, github_token: Optional[str] = None, logger: Logger = None):
        self.metadata = metadata
        self.cache = cache
        self.github_token = github_token
        self.logger = logger or Logger("console")
        return

    def fill(self):
        self.repo()
        self.owner()
        self.discussions()
        self.name()
        self.authors()
        self.maintainers()
        self.copyright()
        self.license()
        self.keywords()
        self.labels()
        self.urls_github()
        self.urls_website()
        self.publications()
        return

    def repo(self):
        self.logger.section("Generate 'repo' metadata")
        owner_username, repo_name = self.metadata["repo"].split("/")
        self.logger.debug(f"Owner username: {owner_username}\nRepository name: {repo_name}")
        target_repo = self.metadata.get("repo_target") or "source"
        self.logger.debug(f"Target repository: {target_repo}")
        repo_info = self.cache[f"repo__{owner_username}_{repo_name}_{target_repo}"]
        if repo_info:
            self.logger.debug(f"Set from cache: {repo_info}")
            self.metadata["repo"] = repo_info
            return
        self.logger.debug("Get repository info from GitHub API")
        repo_api = pylinks.api.github.repo(owner_username, repo_name)
        repo_info = repo_api.info
        if target_repo != "self" and repo_info["fork"]:
            repo_info = repo_info[target_repo]
            self.logger.debug(
                f"Repository is a fork and target is set to '{target_repo}'; "
                f"set target to {repo_info['full_name']}."
            )
        repo = {
            attr: repo_info[attr]
            for attr in ['id', 'node_id', 'name', 'full_name', 'html_url', 'default_branch', "created_at"]
        }
        repo["owner"] = repo_info["owner"]["login"]
        self.metadata["repo"] = self.cache["repo"] = repo
        self.logger.debug(f"Set 'repo': {repo}")
        return

    def owner(self):
        self.logger.section("Generate 'owner' metadata")
        self.metadata["owner"] = self.get_user(self.metadata["repo"]["owner"])
        self.logger.debug(f"Set 'owner': {json.dumps(self.metadata['owner'])}")
        return

    def discussions(self):
        self.logger.section("Generate 'discussions' metadata")
        discussions_info = self.cache[f"discussions__{self.metadata['repo']['full_name']}"]
        if not discussions_info:
            self.logger.debug("Get repository discussions from GitHub API")
            if self.github_token:
                repo_api = pylinks.api.github.repo(
                    self.metadata["repo"]["owner"], self.metadata["repo"]["name"]
                )
                discussions_info = repo_api.discussion_categories(self.github_token)
                self.logger.debug(f"Set from API: {discussions_info}")
                self.cache[f"discussions__{self.metadata['repo']['full_name']}"] = discussions_info
            else:
                self.logger.attention("GitHub token not provided. Cannot get discussions categories.")
                return
        else:
            self.logger.debug(f"Set from cache: {discussions_info}")
        discussions = self.metadata.get("discussions") or []
        for discussion_info in discussions_info:
            for discussion in discussions:
                if discussion_info["slug"] == discussion["slug"]:
                    discussion |= discussion_info
                    break
            else:
                discussions.append(discussion_info)
        self.metadata["discussions"] = discussions
        return

    def name(self):
        self.logger.section("Generate 'name' metadata")
        if not self.metadata.get("name"):
            self.metadata["name"] = self.metadata["repo"]["name"].replace("-", " ").title()
            self.logger.success(f"Set from repository name: {self.metadata['name']}")
            return
        self.logger.success(f"Already set in metadata: {self.metadata['name']}")
        return

    def license(self):
        self.logger.section("Set 'license' metadata")
        license_id = self.metadata.get("license_id")
        if license_id:
            license_data = db.license.get(license_id.lower())
            if not license_data:
                self.logger.error(f"License ID '{license_id}' is not supported.")
            self.metadata["license_name_short"] = license_data['name']
            self.metadata["license_name_full"] = license_data['fullname']
            self.logger.success(f"license_name_short: {license_data['name']}")
            self.logger.success(f"license_name_full: {license_data['fullname']}")
        else:
            self.logger.attention("No license ID specified; skip.")
        return

    def authors(self):
        self.logger.section("Generate 'authors' metadata")
        if not self.metadata.get("authors"):
            self.metadata["authors"] = [self.metadata["owner"]]
            self.logger.success(f"Set from owner: {json.dumps(self.metadata['authors'])}")
            return
        for author in self.metadata["authors"]:
            author |= self.get_user(author["username"])
            self.logger.debug(f"Set author '{author['username']}': {json.dumps(author)}")
        return

    def maintainers(self):
        self.logger.section("Generate 'maintainers' metadata")
        maintainers = dict()
        for role in ["issues", "discussions"]:
            if not self.metadata.get(role):
                continue
            for item in self.metadata[role]:
                assignees = item.get("assignees")
                if assignees is None:
                    entry = maintainers.setdefault(
                        self.metadata["owner"]["username"], {"issues": [], "pulls": [], "discussions": []}
                    )
                    entry[role].append(item["slug"])
                    continue
                for assignee in assignees:
                    entry = maintainers.setdefault(assignee, {"issues": [], "pulls": [], "discussions": []})
                    entry[role].append(item["slug"])
        if self.metadata.get("pulls"):
            for codeowner_entry in self.metadata["pulls"]:
                for reviewer in codeowner_entry["reviewers"]:
                    entry = maintainers.setdefault(reviewer, {"issues": [], "pulls": [], "discussions": []})
                    entry["pulls"].append(codeowner_entry["pattern"])

        def sort_key(val):
            return len(val[1]["issues"]) + len(val[1]["pulls"]) + len(val[1]["discussions"])

        self.metadata["maintainers"] = [
            {**self.get_user(username), "roles": roles} for username, roles in sorted(
                maintainers.items(), key=sort_key, reverse=True
            )
        ]
        self.logger.success(f"Set 'maintainers': {json.dumps(self.metadata['maintainers'])}")
        return

    def copyright(self):
        self.logger.section("Generate 'copyright' metadata")
        if "year_start" not in self.metadata:
            self.metadata["year_start"] = year_start = datetime.datetime.strptime(
                self.metadata["repo"]["created_at"], "%Y-%m-%dT%H:%M:%SZ"
            ).year
            self.logger.success(f"'year_start' set from repository creation date: {year_start}")
        else:
            year_start = self.metadata["year_start"]
            self.logger.info(f"'year_start' already set: {year_start}")
        current_year = datetime.date.today().year
        year_range = f"{year_start}{'' if year_start == current_year else f'–{current_year}'}"
        self.metadata["year_range"] = year_range
        self.logger.success(f"'year_range' set: {year_range}")
        self.metadata["copyright_notice"] = f"{year_range} {self.metadata['owner']['name']}"
        self.logger.success(f"'copyright_notice' set: {self.metadata['copyright_notice']}")
        return

    def keywords(self):
        self.logger.section("Generate 'keywords' metadata")
        if not self.metadata.get("keywords"):
            self.logger.attention("No keywords specified; skip.")
            return
        self.metadata['keyword_slugs'] = []
        for keyword in self.metadata['keywords']:
            self.metadata['keyword_slugs'].append(keyword.lower().replace(" ", "-"))
        return

    def labels(self):
        self.logger.section("Process metadata: labels")
        # repo labels: https://github.com/marketplace/actions/label-syncer
        repo_labels = []
        pr_labeler = {"version": "v1", "labels": []}
        pr_labels = pr_labeler["labels"]
        labels = self.metadata['labels']
        for label in labels:
            repo_labels.append({attr: label[attr] for attr in ["name", "description", "color"]})
            if label.get("pulls"):
                pr_labels.append({"label": label["name"], **label["pulls"]})
        self.metadata['_label_syncer'] = repo_labels
        self.metadata['_pr_labeler'] = pr_labeler if pr_labels else None
        return

    def urls_github(self):
        urls_dict = self.metadata.setdefault('url', {})
        url = urls_dict.setdefault('github', {})
        home = url["home"] = self.metadata["repo"]["html_url"]
        main_branch = self.metadata["repo"]["default_branch"]
        # Main sections
        for key in ["issues", "pulls", "discussions", "actions", "releases", "security"]:
            url[key] = {"home": f"{home}/{key}"}

        url["tree"] = f"{home}/tree/{main_branch}"
        url["raw"] = f"https://raw.githubusercontent.com/{self.metadata['repo']['full_name']}/{main_branch}"

        # Issues
        url["issues"]["template_chooser"] = f"{url['issues']['home']}/new/choose"
        url["issues"]["new"] = {
            issue_type: f"{url['issues']['home']}/new?template={idx + 1:02}_{issue_type}.yaml"
            for idx, issue_type in enumerate(
                [
                    "app_bug_setup",
                    "app_bug_api",
                    "app_request_enhancement",
                    "app_request_feature",
                    "app_request_change",
                    "docs_bug_content",
                    "docs_bug_site",
                    "docs_request_content",
                    "docs_request_feature",
                    "tests_bug",
                    "tests_request",
                    "devops_bug",
                    "devops_request",
                    "maintenance_request",
                ]
            )
        }
        # Security
        url["security"]["policy"] = f"{url['security']['home']}/policy"
        url["security"]["advisories"] = f"{url['security']['home']}/advisories"
        url["security"]["new_advisory"] = f"{url['security']['advisories']}/new"
        return

    def urls_website(self):
        urls_dict = self.metadata.setdefault('url', {})
        url = urls_dict.setdefault('website', {})

        base = self.metadata.get('base_url')
        if base:
            url['base'] = base
        elif self.metadata['repo']['name'] == f"{self.metadata['owner']['username']}.github.io":
            base = url['base'] = f"https://{self.metadata['owner']['username']}.github.io"
        else:
            base = url['base'] = f"https://{self.metadata['owner']['username']}.github.io/{self.metadata['repo']['name']}"

        url["home"] = base
        url["news"] = f"{base}/news"
        url["announcement"] = (
            f"https://raw.githubusercontent.com/{self.metadata['repo']['full_name']}/"
            f"announcement/announcement.html"
        )
        url["contributors"] = f"{base}/about#contributors"
        url["contributing"] = f"{base}/contribute"
        url["license"] = f"{base}/license"
        url["security_measures"] = f"{base}/contribute/collaborate/maintain/security"
        url["sponsor"] = f"{base}/contribute/collaborate/maintain/sponsor"
        return

    def publications(self):
        if not self.metadata.get('get_owner_publications'):
            return
        orcid_id = self.metadata["owner"]["url"].get("orcid")
        if not orcid_id:
            raise ValueError(
                "The `get_owner_publications` config is enabled, "
                "but owner's ORCID ID is not set on their GitHub account."
            )
        dois = self.cache[f'publications_orcid_{orcid_id}']
        if not dois:
            dois = pylinks.api.orcid(orcid_id=orcid_id).doi
            self.cache[f'publications_orcid_{orcid_id}'] = dois
        publications = []
        for doi in dois:
            publication_data = self.cache[f'doi_{doi}']
            if not publication_data:
                publication_data = pylinks.api.doi(doi=doi).curated
                self.cache[f'doi_{doi}'] = publication_data
            publications.append(publication_data)
        self.metadata['owner_publications']: list[dict] = sorted(
            publications, key=lambda i: i["date_tuple"], reverse=True
        )
        return

    def get_user(self, username: str) -> dict:
        user_info = self.cache[f"user__{username}"]
        if user_info:
            return user_info
        self.logger.info(f"Get user info for '{username}' from GitHub API")
        output = {"username": username}
        user = pylinks.api.github.user(username=username)
        user_info = user.info
        # Get website and social accounts
        for key in ['name', 'company', 'location', 'email', 'bio', 'id', 'node_id', 'avatar_url']:
            output[key] = user_info[key]
        output["url"] = {"website": user_info["blog"], "github": user_info["html_url"]}
        self.logger.info(f"Get social accounts for '{username}' from GitHub API")
        social_accounts = user.social_accounts
        for account in social_accounts:
            if account["provider"] == "twitter":
                output["url"]["twitter"] = account["url"]
                self.logger.success(f"Found Twitter account for '{username}': {account['url']}")
            elif account["provider"] == "linkedin":
                output["url"]["linkedin"] = account["url"]
                self.logger.success(f"Found LinkedIn account for '{username}': {account['url']}")
            else:
                for url, key in [
                    (r"orcid\.org", "orcid"),
                    (r"researchgate\.net/profile", "researchgate"),
                ]:
                    match = re.compile(
                        r"(?:https?://)?(?:www\.)?({}/[\w\-]+)".format(url)
                    ).fullmatch(account["url"])
                    if match:
                        output["url"][key] = f"https://{match.group(1)}"
                        self.logger.success(f"Found {key} account for '{username}': {output['url'][key]}")
                        break
                else:
                    other_urls = output["url"].setdefault("others", list())
                    other_urls.append(account["url"])
                    self.logger.success(f"Found unknown account for '{username}': {account['url']}")
        self.cache[f"user__{username}"] = user_info
        return output


def fill(metadata: dict, cache: Cache, github_token: Optional[str] = None, logger: Logger = None):
    project = Project(metadata, cache, github_token, logger)
    project.fill()
    return
