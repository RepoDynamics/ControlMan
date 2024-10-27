"""Helper functions to retrieve and generate data."""

from __future__ import annotations as _annotations

from typing import TYPE_CHECKING as _TYPE_CHECKING
import re as _re

from loggerman import logger as _logger
import pylinks as _pl

if _TYPE_CHECKING:
    from typing import Sequence
    from controlman.cache_manager import CacheManager


def team_members_with_role_types(
    role_types: str | Sequence[str],
    team_data: dict[str, dict],
    role_data: dict[str, dict],
    active_only: bool = True,
) -> list[dict]:
    """Get team members with a specific role type.

    Parameters
    ----------
    role_types
        The role type(s) to filter for.
    team_data
        The team data.
    role_data
        The role data.
    active_only
        Whether to filter for active team members only.

    Returns
    -------
    list[dict]
        A list of dictionaries, each representing a team member.
    """
    out = []
    if isinstance(role_types, str):
        role_types = [role_types]
    for member_id, member_data in team_data.items():
        if active_only and not member_data["active"]:
            continue
        for role_id in member_data.get("roles", []):
            if role_data[role_id]["type"] in role_types:
                out.append(member_data | {"id": member_id})
                break
    return out


def team_members_without_role_types(
    role_types: str | Sequence[str],
    team_data: dict[str, dict],
    role_data: dict[str, dict],
    include_other_roles: bool = True,
    active_only: bool = True,
) -> list[dict]:
    """Get team members without a specific role type.

    Parameters
    ----------
    role_types
        The role type(s) to filter out.
    team_data
        The team data.
    role_data
        The role data.
    include_other_roles
        Whether to include team members that have roles
        other than the excluded role types.
    active_only
        Whether to filter for active team members only.

    Returns
    -------
    list[dict]
        A list of dictionaries, each representing a team member.
    """
    out = []
    if isinstance(role_types, str):
        role_types = [role_types]
    excluded_role_types = set(role_types)
    for member_id, member_data in team_data.items():
        if active_only and not member_data["active"]:
            continue
        member_role_types = set(
            role_data[role_id]["type"] for role_id in member_data.get("roles", [])
        )
        if not excluded_role_types.intersection(member_role_types):
            out.append(member_data | {"id": member_id})
            continue
        if not include_other_roles:
            continue
        if member_role_types - excluded_role_types:
            out.append(member_data | {"id": member_id})
    return out


def fill_entity(
    entity: dict,
    github_api: _pl.api.GitHub,
    cache_manager: CacheManager | None = None,
) -> tuple[dict, dict | None]:
    """Fill all missing information in an `entity` object."""

    def _get_github_user(username: str) -> dict:

        def add_social(name, user, url):
            socials[name] = {"id": user, "url": url}
            return

        user_info = {}
        if cache_manager:
            user_info = cache_manager.get("user", username)
        if user_info:
            return user_info
        user = github_api.user(username=username)
        user_info = user.info
        if user_info["blog"] and "://" not in user_info["blog"]:
            user_info["blog"] = f"https://{user_info['blog']}"
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
                    break
            else:
                if account["provider"] != "generic":
                    add_social(account["provider"], None, account["url"])
                else:
                    generics = socials.setdefault("generics", [])
                    generics.append(account["url"])
                    _logger.info(f"Unknown account", account['url'])
        if cache_manager:
            cache_manager.set("user", username, user_info)
        return user_info

    def get_orcid_publications(orcid_id: str) -> list[dict]:
        dois = []
        if cache_manager:
            dois = cache_manager.get("orcid", orcid_id)
        if not dois:
            dois = _pl.api.orcid(orcid_id=orcid_id).doi
            if cache_manager:
                cache_manager.set("orcid", orcid_id, dois)
        publications = []
        for doi in dois:
            publication_data = {}
            if cache_manager:
                publication_data = cache_manager.get("doi", doi)
            if not publication_data:
                publication_data = _pl.api.doi(doi=doi).curated
                if cache_manager:
                    cache_manager.set("doi", doi, publication_data)
            publications.append(publication_data)
        return sorted(publications, key=lambda i: i["date_tuple"], reverse=True)

    def make_name():
        if not github_user_info.get("name"):
            _logger.warning(
                f"GitHub user {gh_username} has no name",
                f"Setting entity to legal person",
            )
            return {"legal": gh_username}
        if github_user_info["type"] != "User":
            return {"legal": github_user_info["name"]}
        name_parts = github_user_info["name"].split(" ")
        if len(name_parts) != 2:
            _logger.warning(
                f"GitHub user {gh_username} has a non-standard name",
                f"Setting entity to legal person with name {github_user_info['name']}",
            )
            return {"legal": github_user_info["name"]}
        return {"first": name_parts[0], "last": name_parts[1]}

    gh_username = entity.get("github", {}).get("id")
    github_user_info = None
    if gh_username:
        github_user_info = _get_github_user(gh_username)
        for key_self, key_gh in (
            ("rest_id", "id"),
            ("node_id", "node_id"),
            ("url", "html_url"),
        ):
            entity["github"][key_self] = github_user_info[key_gh]
        if "name" not in entity:
            entity["name"] = make_name()
        for key_self, key_gh in (
            ("affiliation", "company"),
            ("bio", "bio"),
            ("avatar", "avatar_url"),
            ("website", "blog"),
            ("city", "location")
        ):
            if not entity.get(key_self) and github_user_info.get(key_gh):
                entity[key_self] = github_user_info[key_gh]
        if not entity.get("email", {}).get("id") and github_user_info.get("email"):
            email = entity.setdefault("email", {})
            email["id"] = github_user_info["email"]
        for social_name, social_data in github_user_info["socials"].items():
            if social_name in ("orcid", "researchgate", "linkedin", "twitter") and social_name not in entity:
                entity[social_name] = social_data
    if "orcid" in entity and entity["orcid"].get("get_pubs"):
        entity["orcid"]["pubs"] = get_orcid_publications(orcid_id=entity["orcid"]["user"])
    return entity, github_user_info


