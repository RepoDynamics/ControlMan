# Standard libraries
import datetime
import json
import re
import copy

# Non-standard libraries
import pylinks
import trove_classifiers

from repodynamics.meta.reader import MetaReader
from repodynamics import git
from repodynamics import _util
from repodynamics.logger import Logger


class MetadataGenerator:
    def __init__(
        self,
        reader: MetaReader,
        logger: Logger = None
    ):
        if not isinstance(reader, MetaReader):
            raise TypeError(f"reader must be of type MetaReader, not {type(reader)}")
        self._reader = reader
        self._logger = logger or reader.logger
        self._logger.h2("Generate Metadata")
        self._logger.h3("Detect Git Repository")
        self._git = git.Git(path_repo=reader.path_root, logger=self._logger)
        self._metadata = copy.deepcopy(reader.metadata)
        self._metadata["repo"] = self._repo()
        self._metadata["owner"] = self._owner()
        return

    def generate(self) -> dict:
        self._metadata["name"] = self._name()
        self._metadata["authors"] = self._authors()
        self._metadata["maintainers"] = self._maintainers()
        self._metadata["discussions"] = self._discussions()
        self._metadata['keyword_slugs'] = self._keywords()
        self._metadata["url"] = {
            "github": self._urls_github(),
            "website": self._urls_website()
        }

        copyright_info = self._copyright()
        self._metadata |= {
            "year_start": copyright_info["year_start"],
            "year_range": copyright_info["year_range"],
            "copyright_notice": copyright_info["copyright_notice"],
        }

        license_info = self._license()
        if license_info:
            self._metadata |= {
                "license_name_short": license_info['name'],
                "license_name_full": license_info['fullname'],
            }
        self._metadata["license_txt"] = license_info["license_txt"].format(**self._metadata)
        self._metadata["license_notice"] = license_info["license_notice"].format(**self._metadata)

        owner_publications = self._publications()
        if owner_publications:
            self._metadata['owner_publications'] = owner_publications

        if self._metadata.get("package"):
            package = self._metadata["package"]
            package["name"] = self._package_name()
            package["trove_classifiers"].append(license_info["trove_classifier"])

            package_urls = self._package_platform_urls()
            self._metadata["url"] |= {
                "pypi": package_urls["pypi"],
                "conda": package_urls["conda"]
            }

            dev_info = self._package_development_status()
            package |= {
                "development_phase": dev_info["dev_phase"],
                "major_ready": dev_info["major_ready"],
            }
            package["trove_classifiers"].append(dev_info["trove_classifier"])

            python_ver_info = self._package_python_versions()
            package["python_versions"] = python_ver_info["python_versions"]
            package["trove_classifiers"].extend(python_ver_info["trove_classifiers"])

            os_info = self._package_operating_systems()
            package |= {
                "os_independent": os_info["os_independent"],
                "pure_python": os_info["pure_python"],
                "github_runners": os_info["github_runners"],
            }
            if not os_info["pure_python"]:
                package["cibw_matrix_platform"] = os_info["cibw_matrix_platform"]
                package["cibw_matrix_python"] = os_info["cibw_matrix_python"]
            package["trove_classifiers"].extend(os_info["trove_classifiers"])

            for classifier in package["trove_classifiers"]:
                if classifier not in trove_classifiers.classifiers:
                    self._logger.error(f"Trove classifier '{classifier}' is not supported.")
        self._reader.cache_save()
        return self._metadata

    def _repo(self) -> dict:
        self._logger.h3("Generate 'repo' metadata")
        repo_address = self._git.repo_name(fallback_name=False, fallback_purpose=False)
        if not repo_address:
            self._logger.error(
                "Failed to determine repository GitHub address from 'origin' remote for push events. "
                "Following remotes were found:",
                str(self._git.remotes),
            )
        owner_username, repo_name = repo_address
        self._logger.success(
            "Extract remote GitHub repository address",
            f"Owner Username: {owner_username}\nRepository Mame: {repo_name}"
        )
        target_repo = self._metadata["repo_target"]
        self._logger.input(f"Target repository", target_repo)
        repo_info = self._reader.cache_get(f"repo__{owner_username.lower()}_{repo_name.lower()}_{target_repo}")
        if repo_info:
            self._logger.success(f"Repo metadata set from cache", json.dumps(repo_info, indent=3))
            return repo_info
        self._logger.debug("Get repository info from GitHub API")
        repo_api = self._reader.github.user(owner_username).repo(repo_name)
        repo_info = repo_api.info
        if target_repo != "self" and repo_info["fork"]:
            repo_info = repo_info[target_repo]
            self._logger.debug(
                f"Repository is a fork and target is set to '{target_repo}'; "
                f"set target to {repo_info['full_name']}."
            )
        repo = {
            attr: repo_info[attr]
            for attr in ['id', 'node_id', 'name', 'full_name', 'html_url', 'default_branch', "created_at"]
        }
        repo["owner"] = repo_info["owner"]["login"]
        self._reader.cache_set(f"repo__{owner_username.lower()}_{repo_name.lower()}_{target_repo}", repo)
        self._logger.debug(f"Set 'repo': {repo}")
        return repo

    def _owner(self) -> dict:
        self._logger.h3("Generate 'owner' metadata")
        owner_info = self._get_user(self._metadata["repo"]["owner"].lower())
        self._logger.debug(f"Set 'owner': {json.dumps(owner_info)}")
        return owner_info

    def _name(self) -> str:
        self._logger.h3("Generate 'name' metadata")
        name = self._metadata.get("name")
        if not name:
            name = self._metadata["repo"]["name"].replace("-", " ")
            self._logger.success(f"Set from repository name: {name}")
            return name
        self._logger.success(f"Already set in metadata: {name}")
        return name

    def _authors(self) -> list[dict]:
        self._logger.h3("Generate 'authors' metadata")
        authors = []
        if not self._metadata.get("authors"):
            authors.append(self._metadata["owner"])
            self._logger.success(f"Set from owner: {json.dumps(self._metadata['authors'])}")
            return authors
        for author in self._metadata["authors"]:
            authors.append(author | self._get_user(author["username"].lower()))
            self._logger.debug(f"Set author '{author['username']}': {json.dumps(author)}")
        return authors

    def _maintainers(self) -> list[dict]:
        def sort_key(val):
            return len(val[1]["issues"]) + len(val[1]["pulls"]) + len(val[1]["discussions"])

        self._logger.h3("Generate 'maintainers' metadata")
        maintainers = dict()
        for role in ["issues", "discussions"]:
            if not self._metadata.get(role):
                continue
            for item in self._metadata[role]:
                assignees = item.get("assignees")
                if assignees is None:
                    entry = maintainers.setdefault(
                        self._metadata["owner"]["username"], {"issues": [], "pulls": [], "discussions": []}
                    )
                    entry[role].append(item["slug"])
                    continue
                for assignee in assignees:
                    entry = maintainers.setdefault(assignee, {"issues": [], "pulls": [], "discussions": []})
                    entry[role].append(item["slug"])
        if self._metadata.get("pulls"):
            for codeowner_entry in self._metadata["pulls"]:
                for reviewer in codeowner_entry["reviewers"]:
                    entry = maintainers.setdefault(reviewer, {"issues": [], "pulls": [], "discussions": []})
                    entry["pulls"].append(codeowner_entry["pattern"])
        maintainers_list = [
            {**self._get_user(username.lower()), "roles": roles} for username, roles in sorted(
                maintainers.items(), key=sort_key, reverse=True
            )
        ]
        self._logger.success(f"Set 'maintainers': {json.dumps(maintainers_list)}")
        return maintainers_list

    def _discussions(self) -> list[dict] | None:
        self._logger.h3("Generate 'discussions' metadata")
        discussions_info = self._reader.cache_get(f"discussions__{self._metadata['repo']['full_name']}")
        if discussions_info:
            self._logger.debug(f"Set from cache: {discussions_info}")
        elif not self._reader.github.authenticated:
            self._logger.attention("GitHub token not provided. Cannot get discussions categories.")
            return
        else:
            self._logger.debug("Get repository discussions from GitHub API")
            repo_api = self._reader.github.user(self._metadata["repo"]["owner"]).repo(
                self._metadata["repo"]["name"]
            )
            discussions_info = repo_api.discussion_categories()
            self._logger.debug(f"Set from API: {discussions_info}")
            self._reader.cache_set(f"discussions__{self._metadata['repo']['full_name']}", discussions_info)
        discussions = copy.deepcopy(self._metadata["discussions"]) if self._metadata.get("discussions") else []
        for discussion_info in discussions_info:
            for discussion in discussions:
                if discussion_info["slug"] == discussion["slug"]:
                    discussion |= discussion_info
                    break
            else:
                discussions.append(discussion_info)
        return discussions

    def _license(self) -> dict | None:
        self._logger.h3("Set 'license' metadata")
        license_id = self._metadata.get("license_id")
        if not license_id:
            self._logger.attention("No license ID specified; skip.")
            return
        license_info = self._reader.db['license_id'].get(license_id.lower())
        if not license_info:
            self._logger.error(f"License ID '{license_id}' not found in database.")
        else:
            license_info = copy.deepcopy(license_info)
            license_info["trove_classifier"] = f"License :: OSI Approved :: {license_info['trove_classifier']}"
            filename = license_id.lower().removesuffix('+')
            license_info["license_txt"] = _util.file.datafile(f"license/{filename}.txt").read_text()
            license_info["license_notice"] = _util.file.datafile(f"license/{filename}_notice.txt").read_text()
        self._logger.success(f"License metadata set.", license_info)
        return license_info

    def _copyright(self) -> dict:
        self._logger.h3("Generate 'copyright' metadata")
        output = {}
        if "year_start" not in self._metadata:
            output["year_start"] = year_start = datetime.datetime.strptime(
                self._metadata["repo"]["created_at"], "%Y-%m-%dT%H:%M:%SZ"
            ).year
            self._logger.success(f"'year_start' set from repository creation date: {year_start}")
        else:
            output["year_start"] = year_start = self._metadata["year_start"]
            self._logger.info(f"'year_start' already set: {year_start}")
        current_year = datetime.date.today().year
        year_range = f"{year_start}{'' if year_start == current_year else f'–{current_year}'}"
        output["year_range"] = year_range
        self._logger.success(f"'year_range' set: {year_range}")
        output["copyright_notice"] = f"{year_range} {self._metadata['owner']['name']}"
        self._logger.success(f"'copyright_notice' set: {output['copyright_notice']}")
        return output

    def _keywords(self) -> list:
        self._logger.h3("Generate 'keywords' metadata")
        slugs = []
        if not self._metadata.get("keywords"):
            self._logger.attention("No keywords specified; skip.")
            return slugs
        for keyword in self._metadata['keywords']:
            slugs.append(keyword.lower().replace(" ", "-"))
        return slugs

    def _urls_github(self) -> dict:
        url = {}
        home = url["home"] = self._metadata["repo"]["html_url"]
        main_branch = self._metadata["repo"]["default_branch"]
        # Main sections
        for key in ["issues", "pulls", "discussions", "actions", "releases", "security"]:
            url[key] = {"home": f"{home}/{key}"}

        url["tree"] = f"{home}/tree/{main_branch}"
        url["raw"] = f"https://raw.githubusercontent.com/{self._metadata['repo']['full_name']}/{main_branch}"

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
        return url

    def _urls_website(self) -> dict:
        url = {}
        base = self._metadata.get('base_url')
        if not base:
            base = f"https://{self._metadata['owner']['username']}.github.io"
            if self._metadata['repo']['name'] != f"{self._metadata['owner']['username']}.github.io":
                base += f"/{self._metadata['repo']['name']}"
        url['base'] = base
        url["home"] = base
        url["news"] = f"{base}/news"
        url["announcement"] = (
            f"https://raw.githubusercontent.com/{self._metadata['repo']['full_name']}/"
            f"announcement/announcement.html"
        )
        url["contributors"] = f"{base}/about#contributors"
        url["contributing"] = f"{base}/contribute"
        url["license"] = f"{base}/license"
        url["security_measures"] = f"{base}/contribute/collaborate/maintain/security"
        url["sponsor"] = f"{base}/contribute/collaborate/maintain/sponsor"
        return url

    def _publications(self) -> list[dict] | None:
        if not self._metadata['get_owner_publications']:
            return
        orcid_id = self._metadata["owner"]["url"].get("orcid")
        if not orcid_id:
            self._logger.error(
                "The `get_owner_publications` config is enabled, "
                "but owner's ORCID ID is not set on their GitHub account."
            )
        dois = self._reader.cache_get(f'publications_orcid_{orcid_id}')
        if not dois:
            dois = pylinks.api.orcid(orcid_id=orcid_id).doi
            self._reader.cache_set(f'publications_orcid_{orcid_id}', dois)
        publications = []
        for doi in dois:
            publication_data = self._reader.cache_get(f'doi_{doi}')
            if not publication_data:
                publication_data = pylinks.api.doi(doi=doi).curated
                self._reader.cache_set(f'doi_{doi}', publication_data)
            publications.append(publication_data)
        return sorted(publications, key=lambda i: i["date_tuple"], reverse=True)

    def _package_name(self) -> str:
        self._logger.h3("Process metadata: package.name")
        name = self._metadata["name"]
        package_name = re.sub(r"[ ._-]+", "-", name.lower())
        self._logger.success(f"package.name: {package_name}")
        return package_name

    def _package_platform_urls(self) -> dict:
        package_name = self._metadata["package"]["name"]
        url = {
            "conda": f"https://anaconda.org/conda-forge/{package_name}/",
            "pypi": f"https://pypi.org/project/{package_name}/",
        }
        return url

    def _package_development_status(self) -> dict:
        self._logger.h3("Process metadata: package.development_status")
        phase = {
            1: "Planning",
            2: "Pre-Alpha",
            3: "Alpha",
            4: "Beta",
            5: "Production/Stable",
            6: "Mature",
            7: "Inactive",
        }
        status_code = self._metadata["package"]["development_status"]
        output = {
            "major_ready": status_code in [5, 6],
            "dev_phase": phase[status_code],
            "trove_classifier": f"Development Status :: {status_code} - {phase[status_code]}"
        }
        self._logger.success(f"Development info: {output}")
        return output

    def _package_python_versions(self) -> dict:
        self._logger.h3("Process metadata: package.python_version_min")
        min_ver = self._metadata["package"]["python_version_min"]
        ver = tuple(map(int, min_ver.split(".")))
        if ver[0] != 3:
            self._logger.error(f"Minimum Python version must be 3.x, but got {min_ver}.")
        # Get a list of all Python versions that have been released to date.
        current_python_versions = self._get_released_python_versions()
        vers = [
            ".".join(map(str, v))
            for v in sorted(
                set([tuple(v[:2]) for v in current_python_versions if v[0] == 3 and v[1] >= ver[1]])
            )
        ]
        if len(vers) == 0:
            self._logger.error(
                f"python_version_min '{min_ver}' is higher than "
                f"latest release version '{'.'.join(current_python_versions[-1])}'."
            )
        output = {
            "python_versions": vers,
            "trove_classifiers": [
                "Programming Language :: Python :: {}".format(postfix)
                for postfix in ["3 :: Only"] + vers
            ]
        }
        self._logger.success(f"Set package Python versions data: {output}")
        return output

    def _package_operating_systems(self):
        self._logger.h3("Process metadata: package.operating_systems")
        trove_classifiers_postfix = {
            "windows": "Microsoft :: Windows",
            "macos": "MacOS",
            "linux": "POSIX :: Linux",
            "independent": "OS Independent",
        }
        trove_classifier_template = "Operating System :: {}"
        output = {
            "os_independent": True,
            "pure_python": True,
            "github_runners": [],
            "trove_classifiers": [],
            "cibw_matrix_platform": [],
            "cibw_matrix_python": [],
        }
        if not self._metadata["package"].get("operating_systems"):
            self._logger.attention("No operating systems provided.")
            output["trove_classifiers"].append(trove_classifier_template.format(trove_classifiers_postfix["independent"]))
            output["github_runners"].extend(["ubuntu-latest", "macos-latest", "windows-latest"])
            return output
        output["os_independent"] = False
        for os_name, specs in self._metadata["package"]["operating_systems"].items():
            output["trove_classifiers"].append(
                trove_classifier_template.format(trove_classifiers_postfix[os_name])
            )
            default_runner = f"{os_name if os_name != 'linux' else 'ubuntu'}-latest"
            if not specs:
                self._logger.attention(f"No specifications provided for operating system '{os_name}'.")
                output["github_runners"].append(default_runner)
                continue
            runner = default_runner if not specs.get("runner") else specs["runner"]
            output["github_runners"].append(runner)
            if specs.get("cibw_build"):
                for cibw_platform in specs["cibw_build"]:
                    output["cibw_matrix_platform"].append({"runner": runner, "cibw_platform": cibw_platform})
        if output["cibw_matrix_platform"]:
            output["pure_python"] = False
            output["cibw_matrix_python"].extend(
                [f"cp{ver.replace('.', '')}" for ver in self._metadata["package"]["python_versions"]]
            )
        return output

    def _get_user(self, username: str) -> dict:
        user_info = self._reader.cache_get(f"user__{username}")
        if user_info:
            return user_info
        self._logger.info(f"Get user info for '{username}' from GitHub API")
        output = {"username": username}
        user = self._reader.github.user(username=username)
        user_info = user.info
        # Get website and social accounts
        for key in ['name', 'company', 'location', 'email', 'bio', 'id', 'node_id', 'avatar_url']:
            output[key] = user_info[key]
        output["url"] = {"website": user_info["blog"], "github": user_info["html_url"]}
        self._logger.info(f"Get social accounts for '{username}' from GitHub API")
        social_accounts = user.social_accounts
        for account in social_accounts:
            if account["provider"] == "twitter":
                output["url"]["twitter"] = account["url"]
                self._logger.success(f"Found Twitter account for '{username}': {account['url']}")
            elif account["provider"] == "linkedin":
                output["url"]["linkedin"] = account["url"]
                self._logger.success(f"Found LinkedIn account for '{username}': {account['url']}")
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
                        self._logger.success(f"Found {key} account for '{username}': {output['url'][key]}")
                        break
                else:
                    other_urls = output["url"].setdefault("others", list())
                    other_urls.append(account["url"])
                    self._logger.success(f"Found unknown account for '{username}': {account['url']}")
        self._reader.cache_set(f"user__{username}", output)
        return output

    def _get_released_python_versions(self):
        release_versions = self._reader.cache_get('python_versions')
        if release_versions:
            return release_versions
        vers = self._reader.github.user("python").repo("cpython").semantic_versions(tag_prefix="v")
        release_versions = sorted(set([v[:2] for v in vers if v[0] >= 3]))
        self._reader.cache_set("python_versions", release_versions)
        return release_versions
