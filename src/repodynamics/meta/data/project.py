import datetime
import re
import warnings
from typing import Optional

import pylinks

from repodynamics.meta import db
from repodynamics.meta.data._cache import Cache


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
        self.metadata["owner"] = self.get_user(self.metadata["owner"]["username"])
        for author in self.metadata["authors"]:
            if not author.get("username"):
                raise ValueError("Author entries must have a `username` key.")
            author |= self.get_user(author["username"])

        maintainers = dict()

        for role in ["issues", "discussions"]:
            for category, people in self.metadata["maintain"][role].items():
                for person in people:
                    entry = maintainers.setdefault(person, {"issues": [], "pulls": [], "discussions": []})
                    entry[role].append(category)

        for codeowner_entry in self.metadata["maintain"]["pulls"]:
            for person in codeowner_entry["reviewers"]:
                entry = maintainers.setdefault(person, {"issues": [], "pulls": [], "discussions": []})
                entry["pulls"].append(codeowner_entry["pattern"])

        def sort_key(val):
            return len(val[1]["issues"]) + len(val[1]["pulls"]) + len(val[1]["discussions"])

        self.metadata["maintainers"] = [
            {**self.get_user(username), "roles": roles} for username, roles in sorted(
                maintainers.items(), key=sort_key, reverse=True
            )
        ]
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
        repo_api = pylinks.api.github.repo(self.metadata['owner']["username"], repo_name)
        repo_info = repo_api.info
        repo_info.pop("owner")
        if self.github_token:
            repo_info["discussions"] = repo_api.discussion_categories(self.github_token)
        else:
            warnings.warn("GitHub token not provided. Cannot get discussions categories.")
        self.metadata["repo"] = self.cache["repo"] = repo_info
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
        output = {"username": username}
        user = pylinks.api.github.user(username=username)
        user_info = user.info
        # Get website and social accounts
        for key in ['name', 'company', 'location', 'email', 'bio', 'id', 'node_id', 'avatar_url']:
            output[key] = user_info[key]
        output["url"] = {"website": user_info["blog"], "github": user_info["html_url"]}
        social_accounts = user.social_accounts
        for account in social_accounts:
            if account["provider"] == "twitter":
                output["url"]["twitter"] = account["url"]
            elif account["provider"] == "linkedin":
                output["url"]["linkedin"] = account["url"]
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
                        break
                else:
                    other_urls = output["url"].setdefault("others", list())
                    other_urls.append(account["url"])
        self.cache[f"user__{username}"] = user_info
        return output


def fill(metadata: dict, cache: Cache, github_token: Optional[str] = None):
    project = Project(metadata, cache, github_token)
    project.fill()
    return
