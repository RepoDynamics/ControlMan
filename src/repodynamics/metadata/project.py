import datetime
import re
import warnings
from typing import Optional

import pylinks

from repodynamics.metadata import db
from repodynamics.metadata._cache import Cache


class Project:

    def __init__(self, metadata: dict, cache: Cache, github_token: Optional[str] = None):
        self.metadata = metadata
        self.cache = cache
        self.github_token = github_token
        return

    def fill(self):
        self.copyright()
        self.people()
        self.repo()
        self.keywords()
        self.publications()
        return

    def copyright(self):
        start_year = int(self.metadata["copyright"]["year_start"])
        current_year = datetime.date.today().year
        if start_year < 1970 or start_year > current_year:
            raise ValueError(
                f"Project's start year must be between 1970 and {datetime.date.today().year}, "
                f"but got {start_year}."
            )
        year_range = f"{start_year}{'' if start_year == current_year else f'–{current_year}'}"
        self.metadata["copyright"]["year_range"] = year_range

        license_id = self.metadata["copyright"]["license"]["id"].lower()
        license_data = db.license.get(license_id)
        if not license_data:
            raise ValueError(f"License ID '{license_id}' is not supported.")
        self.metadata["copyright"]["license"]["name"] = license_data['name']
        self.metadata["copyright"]["license"]["fullname"] = license_data['fullname']
        return

    def people(self):
        self.add_user(self.metadata["owner"])
        for author in self.metadata["authors"]:
            if not author.get("username"):
                raise ValueError("Author entries must have a `username` key.")
            self.add_user(author["username"])

        for role in ["issues", "discussions"]:
            for people in self.metadata["maintainers"][role].values():
                for person in people:
                    self.add_user(person)

        for codeowner_entry in self.metadata["maintainer"]["pulls"]:
            for person in codeowner_entry["reviewers"]:
                self.add_user(person)
        return

    def repo(self):
        repo_name = self.metadata["repo"]["name"]
        if not re.match(r"^[A-Za-z0-9_.-]+$", repo_name):
            raise ValueError(
                "Repository names can only contain alphanumeric characters, hyphens (-), underscores (_), "
                f"and periods (.), but got {repo_name}."
            )
        if not self.metadata.get("name"):
            self.metadata["name"] = repo_name
        repo_info = self.cache["repo"]
        if repo_info:
            self.metadata["repo"] = repo_info
            return
        repo_api = pylinks.api.github.repo(self.metadata['owner'], repo_name)
        repo_info = repo_api.info
        repo_info.pop("owner")
        if self.github_token:
            repo_info["discussions"] = repo_api.discussion_categories(self.github_token)
        else:
            warnings.warn("GitHub token not provided. Cannot get discussions categories.")
        self.cache["repo"] = repo_info
        return

    def keywords(self):
        self.metadata['keyword_slugs'] = []
        for keyword in self.metadata['keywords']:
            if len(keyword) > 50:
                raise ValueError(
                    f"Keywords can only contain up to 50 characters, "
                    f"but '{keyword}' has {len(keyword)} characters."
                )
            keyword_lower = keyword.lower()
            if not re.match(r"^[a-z0-9][a-z0-9- ]*$", keyword_lower):
                raise ValueError(
                    "Keywords must start with an alphanumeric character, "
                    "and can only contain alphanumeric characters and hyphens (-), "
                    f"but got {keyword}."
                )
            self.metadata['keyword_slugs'].append(keyword_lower.replace(" ", "-"))
        return

    def publications(self):
        if not self.metadata['config']['meta']['get_owner_publications']:
            return
        orcid_id = self.metadata["user"][self.metadata["owner"]]["external_urls"].get("orcid")
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

    def add_user(self, username: str) -> None:
        users = self.metadata.setdefault("user", dict())
        if users.get(username):
            return
        user_info = self.cache[f"user__{username}"]
        if user_info:
            users[username] = user_info
            return
        user = pylinks.api.github.user(username=username)
        user_info = user.info
        # Get website and social accounts
        user_info["external_urls"] = {"website": user_info["blog"]}
        social_accounts = user.social_accounts
        for account in social_accounts:
            if account["provider"] == "twitter":
                user_info["external_urls"]["twitter"] = account["url"]
            elif account["provider"] == "linkedin":
                user_info["external_urls"]["linkedin"] = account["url"]
            else:
                for url, key in [
                    (r"orcid\.org", "orcid"),
                    (r"researchgate\.net/profile", "researchgate"),
                ]:
                    match = re.compile(
                        r"(?:https?://)?(?:www\.)?({}/[\w\-]+)".format(url)
                    ).fullmatch(account["url"])
                    if match:
                        user_info["external_urls"][key] = f"https://{match.group(1)}"
                        break
                else:
                    other_urls = user_info["external_urls"].setdefault("others", list())
                    other_urls.append(account["url"])
        self.cache[f"user__{username}"] = user_info
        users[username] = user_info
        return


def fill(metadata: dict, cache: Cache, github_token: Optional[str] = None):
    project = Project(metadata, cache, github_token)
    project.fill()
    return
