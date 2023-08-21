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
        self.repo()
        self.copyright()
        self.name()
        self.people()
        self.keywords()
        self.labels()
        self.publications()
        return

    def copyright(self):
        start_year = int(self.metadata["copyright"]["year_start"])
        current_year = datetime.date.today().year
        year_range = f"{start_year}{'' if start_year == current_year else f'–{current_year}'}"
        self.metadata["copyright"]["year_range"] = year_range
        # Set license info
        license_id = self.metadata["copyright"]["license"]["id"].lower()
        license_data = db.license.get(license_id)
        if not license_data:
            raise ValueError(f"License ID '{license_id}' is not supported.")
        self.metadata["copyright"]["license"]["name"] = license_data['name']
        self.metadata["copyright"]["license"]["fullname"] = license_data['fullname']
        return

    def repo(self):
        fullname = self.metadata["repo"].split("/")
        if len(fullname) != 2:
            raise ValueError(
                "Repository name must be in the format `owner/repo`, "
                f"but got {self.metadata['repo']}."
            )
        owner_username, repo_name = fullname
        if not re.match(r"^[A-Za-z0-9_.-]+$", repo_name):
            raise ValueError(
                "Repository names can only contain alphanumeric characters, hyphens (-), underscores (_), "
                f"and periods (.), but got {repo_name}."
            )
        target_repo = self.metadata["config"]["target_repo"]
        if target_repo not in ["source", "parent", "self"]:
            raise ValueError(
                f"Target repository must be one of 'source', 'fork', or 'self', "
                f"but got {target_repo}."
            )
        repo_info = self.cache[f"repo__{owner_username}_{repo_name}_{target_repo}"]
        if repo_info:
            self.metadata["repo"] = repo_info
            return
        repo_api = pylinks.api.github.repo(owner_username, repo_name)
        repo_info = repo_api.info
        if target_repo != "self" and repo_info["fork"]:
            repo_info = repo_info[target_repo]
            repo_api = pylinks.api.github.repo(repo_info["owner"]["login"], repo_info["name"])
        repo = {attr: repo_info[attr] for attr in ['id', 'node_id', 'name', 'full_name', 'html_url']}
        if self.github_token:
            repo["discussions"] = repo_api.discussion_categories(self.github_token)
        else:
            warnings.warn("GitHub token not provided. Cannot get discussions categories.")
        self.metadata["repo"] = self.cache["repo"] = repo
        self.metadata["owner"] = self.get_user(repo_info["owner"]["login"])
        self.metadata["copyright"]["year_start"] = datetime.strptime(
            repo_info["created_at"], "%Y-%m-%dT%H:%M:%SZ"
        ).year
        return

    def name(self):
        if not self.metadata.get("name"):
            self.metadata["name"] = self.metadata["repo"]["name"]
        return

    def people(self):
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

    def labels(self):
        # repo labels: https://github.com/marketplace/actions/label-syncer
        repo_labels = []
        pr_labeler = {"version": "v1", "labels": []}
        pr_labels = pr_labeler["labels"]
        labels = self.metadata['maintain']['labels']
        for label in labels:
            repo_labels.append({attr: label[attr] for attr in ["name", "description", "color"]})
            if label.get("pulls"):
                pr_labels.append({"label": label["name"], **label["pulls"]})
        self.metadata['maintain']['_label_syncer'] = repo_labels
        self.metadata['maintain']['_pr_labeler'] = pr_labeler if pr_labels else None
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
