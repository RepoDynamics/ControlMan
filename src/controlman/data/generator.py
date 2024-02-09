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


@_logger.sectioner("Generate Control Center Contents")
def generate(
    initial_data: dict,
    path_manager: PathManager,
    api_cache_retention_days: float,
    git_manager: _Git,
    github_token: str | None = None,
    ccm_before: ControlCenterContentManager | dict | None = None,
    future_versions: dict[str, str | PEP440SemVer] | None = None,
) -> dict:
    content = _ControlCenterContentGenerator(**locals()).generate()
    return content


class _ControlCenterContentGenerator:
    def __init__(
        self,
        initial_data: dict,
        path_manager: PathManager,
        api_cache_retention_days: float,
        git_manager: _Git,
        github_token: str | None = None,
        ccm_before: ControlCenterContentManager | dict | None = None,
        future_versions: dict[str, str | PEP440SemVer] | None = None,
    ):
        self._data = initial_data
        self._pathman = path_manager
        self._git = git_manager
        self._ccm_before = ccm_before
        self._future_versions = future_versions or {}
        self._cache = APICacheManager(
            path_repo=self._pathman.root,
            path_cachefile=str(self._pathman.file_local_api_cache.relative_to(self._pathman.root)),
            retention_days=api_cache_retention_days,
        )
        self._github_api = pylinks.api.github(token=github_token)
        self._ccm = ControlCenterContentManager(self._data)
        return

    @_logger.sectioner("Generate Contents")
    def generate(self) -> dict:
        self._data["repo"] |= self._repo()
        self._data["owner"] = self._owner()
        self._data["name"] = self._name()
        self._data["keyword_slugs"] = self._keywords()
        self._data["license"] = self._license()
        self._data["copyright"] |= self._copyright()
        self._data["author"]["entries"] = self._authors()
        self._data["discussion"]["categories"] = self._discussion_categories()
        self._data["url"] = {"github": self._urls_github(), "website": self._urls_website()}

        website_main_sections, website_quicklinks = self._process_website_toctrees()
        self._data["web"]["sections"] = website_main_sections

        if self._data["web"]["quicklinks"] == "subsections":
            self._data["web"]["quicklinks"] = website_quicklinks

        self._data["owner"]["publications"] = self._publications()

        if self._data.get("package"):
            package = self._data["package"]
            package_name, import_name = self._package_name()
            package["name"] = package_name
            package["import_name"] = import_name
            testsuite_name, testsuite_import_name = self._package_testsuite_name()
            package["testsuite_name"] = testsuite_name
            package["testsuite_import_name"] = testsuite_import_name

            trove_classifiers = package.setdefault("trove_classifiers", [])
            if self._data["license"].get("trove_classifier"):
                trove_classifiers.append(self._data["license"]["trove_classifier"])
            if self._data["package"].get("typed"):
                trove_classifiers.append("Typing :: Typed")

            package_urls = self._package_platform_urls()
            self._data["url"] |= {"pypi": package_urls["pypi"], "conda": package_urls["conda"]}

            # dev_info = self._package_development_status()
            # package |= {
            #     "development_phase": dev_info["dev_phase"],
            #     "major_ready": dev_info["major_ready"],
            # }
            # trove_classifiers.append(dev_info["trove_classifier"])

            python_ver_info = self._package_python_versions()
            package["python_version_max"] = python_ver_info["python_version_max"]
            package["python_versions"] = python_ver_info["python_versions"]
            package["python_versions_py3x"] = python_ver_info["python_versions_py3x"]
            package["python_versions_int"] = python_ver_info["python_versions_int"]
            trove_classifiers.extend(python_ver_info["trove_classifiers"])

            os_info = self._package_operating_systems()
            trove_classifiers.extend(os_info["trove_classifiers"])
            package |= {
                "os_titles": os_info["os_titles"],
                "os_independent": os_info["os_independent"],
                "pure_python": os_info["pure_python"],
                "github_runners": os_info["github_runners"],
                "cibw_matrix_platform": os_info["cibw_matrix_platform"],
                "cibw_matrix_python": os_info["cibw_matrix_python"],
            }

            release_info = self._package_releases()
            package["releases"] = {
                "per_branch": release_info["per_branch"],
                "branch_names": release_info["branch_names"],
                "os_titles": release_info["os_titles"],
                "python_versions": release_info["python_versions"],
                "package_versions": release_info["package_versions"],
                "package_managers": release_info["package_managers"],
                "cli_scripts": release_info["cli_scripts"],
                "gui_scripts": release_info["gui_scripts"],
                "has_scripts": release_info["has_scripts"],
                "interfaces": release_info["interfaces"],
            }

            for classifier in trove_classifiers:
                if classifier not in _trove_classifiers.classifiers:
                    _logger.error(f"Trove classifier '{classifier}' is not supported.")
            package["trove_classifiers"] = sorted(trove_classifiers)

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
        repo_address = self._git.repo_name(fallback_name=False, fallback_purpose=False)
        if not repo_address:
            _logger.critical(
                "Failed to determine repository GitHub address from 'origin' remote for push events. "
                "Following remotes were found:",
                str(self._git.remotes),
            )
        owner_username, repo_name = repo_address
        _logger.info(title="Owner Username", msg=owner_username)
        _logger.info(title="Name", msg=repo_name)
        target_repo = self._data["repo"]["target"]
        _logger.info(title="Target", msg=target_repo)
        repo_info = self._cache.get(f"repo__{owner_username.lower()}_{repo_name.lower()}_{target_repo}")
        if repo_info:
            return repo_info
        repo_info = self._github_api.user(owner_username).repo(repo_name).info
        _logger.info("Retrieved repository info from GitHub API")
        if target_repo != "self" and repo_info["fork"]:
            repo_info = repo_info[target_repo]
            _logger.info(
                title=f"Set target to {repo_info['full_name']}",
                msg=f"Repository is a fork and target is set to '{target_repo}'.",
            )
        repo = {
            attr: repo_info[attr]
            for attr in ["id", "node_id", "name", "full_name", "html_url", "default_branch", "created_at"]
        }
        repo["owner"] = repo_info["owner"]["login"]
        self._cache.set(f"repo__{owner_username.lower()}_{repo_name.lower()}_{target_repo}", repo)
        return repo

    @_logger.sectioner("Repository Owner Data")
    def _owner(self) -> dict:
        owner_info = self._get_user(self._data["repo"]["owner"].lower())
        return owner_info

    @_logger.sectioner("Project Name")
    def _name(self) -> str:
        name = self._data["name"]
        if name:
            _logger.info(f"Already set manually: '{name}'")
        else:
            name = self._data["repo"]["name"].replace("-", " ")
            _logger.info(f"Set from repository name: {name}")
        return name

    @_logger.sectioner("Keyword Slugs")
    def _keywords(self) -> list:
        slugs = []
        if not self._data["keywords"]:
            _logger.info("No keywords specified.")
        else:
            for keyword in self._data["keywords"]:
                slugs.append(keyword.lower().replace(" ", "-"))
            _logger.info("Set from keywords.")
        _logger.debug("Keyword slugs:", code=str(slugs))
        return slugs

    @_logger.sectioner("Project License")
    def _license(self) -> dict:
        data = self._data["license"]
        if not data:
            _logger.info("No license specified.")
            _logger.section_end()
            return {}
        license_id = self._data["license"].get("id")
        if not license_id:
            _logger.info("License data already set manually.")
            return self._data["license"]
        license_db = _util.file.get_package_datafile("db/license/info.yaml")
        license_info = license_db.get(license_id.lower())
        if not license_info:
            _logger.critical(title=f"License ID not found in database", msg=license_id)
        license_info = _copy.deepcopy(license_info)
        license_info["shortname"] = data.get("shortname") or license_info["shortname"]
        license_info["fullname"] = data.get("fullname") or license_info["fullname"]
        license_info["trove_classifier"] = (
            data.get("trove_classifier")
            or f"License :: OSI Approved :: {license_info['trove_classifier']}"
        )
        filename = license_id.lower().removesuffix("+")
        license_info["text"] = (
            data.get("text") or _util.file.get_package_datafile(f"db/license/text/{filename}.txt")
        )
        license_info["notice"] = (
            data.get("notice") or _util.file.get_package_datafile(f"db/license/notice/{filename}.txt")
        )
        _logger.info(f"License data set from license ID '{license_id}'.")
        _logger.debug("License data:", code=str(license_info))
        return license_info

    @_logger.sectioner("Project Copyright")
    def _copyright(self) -> dict:
        output = {}
        data = self._data["copyright"]
        current_year = _datetime.date.today().year
        if not data.get("year_start"):
            output["year_start"] = year_start = _datetime.datetime.strptime(
                self._data["repo"]["created_at"], "%Y-%m-%dT%H:%M:%SZ"
            ).year
            _logger.info(f"Project start year set from repository creation date: {year_start}")
        else:
            output["year_start"] = year_start = data["year_start"]
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
        output["year_range"] = year_range
        if data.get("owner"):
            output["owner"] = data["owner"]
            _logger.info(f"Copyright owner already set manually in metadata: {data['owner']}")
        else:
            output["owner"] = self._data["owner"]["name"]
            _logger.info(f"Copyright owner set to repository owner name: {output['owner']}")
        output["notice"] = f"{year_range} {output['owner']}"
        _logger.info(title="Copyright notice set", msg=output['notice'])
        return output

    @_logger.sectioner("Project Authors")
    def _authors(self) -> list[dict]:
        authors = []
        if not self._data["author"]["entries"]:
            authors.append(self._data["owner"])
            _logger.info(f"No authors defined; setting owner as sole author.")
        else:
            for author in self._data["author"]["entries"]:
                authors.append(author | self._get_user(author["username"].lower()))
        return authors

    @_logger.sectioner("GitHub Discussions Categories")
    def _discussion_categories(self) -> list[dict] | None:
        discussions_info = self._cache.get(f"discussions__{self._data['repo']['full_name']}")
        if discussions_info:
            _logger.info(f"Set from cache.")
        elif not self._github_api.authenticated:
            _logger.notice("GitHub token not provided. Cannot get discussions categories.")
            discussions_info = []
        else:
            _logger.info("Get repository discussions from GitHub API")
            repo_api = self._github_api.user(self._data["repo"]["owner"]).repo(
                self._data["repo"]["name"]
            )
            discussions_info = repo_api.discussion_categories()
            self._cache.set(f"discussions__{self._data['repo']['full_name']}", discussions_info)
        return discussions_info

    @_logger.sectioner("GitHub URLs")
    def _urls_github(self) -> dict:
        url = {}
        home = url["home"] = self._data["repo"]["html_url"]
        main_branch = self._data["repo"]["default_branch"]
        # Main sections
        for key in ["issues", "pulls", "discussions", "actions", "releases", "security"]:
            url[key] = {"home": f"{home}/{key}"}

        url["tree"] = f"{home}/tree/{main_branch}"
        url["blob"] = f"{home}/blob/{main_branch}"
        url["raw"] = f"https://raw.githubusercontent.com/{self._data['repo']['full_name']}/{main_branch}"

        # Issues
        url["issues"]["template_chooser"] = f"{url['issues']['home']}/new/choose"
        url["issues"]["new"] = {
            issue_type["id"]: f"{url['issues']['home']}/new?template={idx + 1:02}_{issue_type['id']}.yaml"
            for idx, issue_type in enumerate(self._data["issue"]["forms"])
        }
        # Discussions
        url["discussions"]["new"] = {
            slug: f"{url['discussions']['home']}/new?category={slug}"
            for slug in self._data["discussion"]["form"]
        }

        # Security
        url["security"]["policy"] = f"{url['security']['home']}/policy"
        url["security"]["advisories"] = f"{url['security']['home']}/advisories"
        url["security"]["new_advisory"] = f"{url['security']['advisories']}/new"
        url["health_file"] = {}
        for health_file_id, health_file_data in self._data["health_file"].items():
            health_file_rel_path = self._pathman.health_file(
                name=health_file_id, target_path=health_file_data["path"]
            ).rel_path
            url["health_file"][health_file_id] = f"{url['blob']}/{health_file_rel_path}"
        _logger.info("Successfully generated all URLs")
        _logger.debug("Generated data:", code=str(url))
        return url

    @_logger.sectioner("Website URLs")
    def _urls_website(self) -> dict:
        url = {}
        base = self._data["web"].get("base_url")
        if not base:
            base = f"https://{self._data['owner']['username']}.github.io"
            if self._data["repo"]["name"] != f"{self._data['owner']['username']}.github.io":
                base += f"/{self._data['repo']['name']}"
        url["base"] = base
        url["home"] = base
        url["announcement"] = (
            f"https://raw.githubusercontent.com/{self._data['repo']['full_name']}/"
            f"{self._ccm.branch__main__name}/{self._data['path']['dir']['website']}/"
            "announcement.html"
        )
        for path_id, rel_path in self._data["web"]["path"].items():
            url[path_id] = f"{base}/{rel_path}"
        _logger.info("Successfully generated all URLs")
        _logger.debug("Generated data:", code=str(url))
        return url

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
            {**self._get_user(username.lower()), "roles": roles}
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
    def _process_website_toctrees(self) -> tuple[list[dict], list[dict]]:
        path_docs = self._pathman.dir_website / "source"
        main_toctree_entries = self._extract_toctree((path_docs / "index.md").read_text())
        main_sections = []
        quicklinks = []
        for main_toctree_entry in main_toctree_entries:
            text = (path_docs / main_toctree_entry).with_suffix(".md").read_text()
            title = self._extract_main_heading(text)
            path = _Path(main_toctree_entry)
            main_dir = path.parent
            main_sections.append({"title": title, "path": str(path.with_suffix(""))})
            if str(main_dir) == self._data["web"]["path"]["news"]:
                category_titles = self._get_all_blog_categories()
                path_template = f'{self._data["web"]["path"]["news"]}/category/{{}}'
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
                quicklinks.append({"title": title, "entries": quicklink_entries})
        _logger.info("Extracted main sections:", code=str(main_sections))
        _logger.info("Extracted quicklinks:", code=str(quicklinks))
        return main_sections, quicklinks

    def _get_all_blog_categories(self) -> tuple[str, ...]:
        categories = {}
        path_posts = self._pathman.dir_website / "source" / self._data["web"]["path"]["news"] / "post"
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
        if not self._data["workflow"]["init"].get("get_owner_publications"):
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

    @_logger.sectioner("Package Name")
    def _package_name(self) -> tuple[str, str]:
        name = self._data["name"]
        package_name = _re.sub(r"[ ._-]+", "-", name)
        import_name = package_name.replace("-", "_").lower()
        _logger.info(title=f"Package name", msg=package_name)
        _logger.info(title="Package import name", msg=import_name)
        return package_name, import_name

    @_logger.sectioner("Package Test-Suite Name")
    def _package_testsuite_name(self) -> tuple[str, str]:
        testsuite_name = pyserials.update.templated_data_from_source(
            templated_data=self._data["package"]["pyproject_tests"]["project"]["name"],
            source_data=self._data
        )
        import_name = testsuite_name.replace("-", "_").lower()
        _logger.info(title="Test-suite name", msg=testsuite_name)
        return testsuite_name, import_name

    @_logger.sectioner("Package Platform URLs")
    def _package_platform_urls(self) -> dict:
        package_name = self._data["package"]["name"]
        url = {
            "conda": f"https://anaconda.org/conda-forge/{package_name}/",
            "pypi": f"https://pypi.org/project/{package_name}/",
        }
        _logger.info(title="PyPI", msg=url["pypi"])
        _logger.info(title="Conda Forge", msg=url["conda"])
        return url

    def _package_development_status(self) -> dict:
        # TODO: add to data
        _logger.section("Package Development Status")
        phase = {
            1: "Planning",
            2: "Pre-Alpha",
            3: "Alpha",
            4: "Beta",
            5: "Production/Stable",
            6: "Mature",
            7: "Inactive",
        }
        status_code = self._data["package"]["development_status"]
        output = {
            "major_ready": status_code in [5, 6],
            "dev_phase": phase[status_code],
            "trove_classifier": f"Development Status :: {status_code} - {phase[status_code]}",
        }
        _logger.info(f"Development info: {output}")
        _logger.section_end()
        return output

    @_logger.sectioner("Package Python Versions")
    def _package_python_versions(self) -> dict:
        min_ver_str = self._data["package"]["python_version_min"]
        min_ver = list(map(int, min_ver_str.split(".")))
        if len(min_ver) < 3:
            min_ver.extend([0] * (3 - len(min_ver)))
        if min_ver < [3, 10, 0]:
            _logger.critical(
                f"Minimum Python version cannot be less than 3.10.0, but got {min_ver_str}."
            )
        min_ver = tuple(min_ver)
        # Get a list of all Python versions that have been released to date.
        current_python_versions = self._get_released_python3_versions()
        compatible_versions_full = [v for v in current_python_versions if v >= min_ver]
        if len(compatible_versions_full) == 0:
            _logger.error(
                f"python_version_min '{min_ver_str}' is higher than "
                f"latest release version '{'.'.join(current_python_versions[-1])}'."
            )
        compatible_minor_versions = sorted(set([v[:2] for v in compatible_versions_full]))
        vers = [".".join(map(str, v)) for v in compatible_minor_versions]
        py3x_format = [f"py{''.join(map(str, v))}" for v in compatible_minor_versions]
        output = {
            "python_version_max": vers[-1],
            "python_versions": vers,
            "python_versions_py3x": py3x_format,
            "python_versions_int": compatible_minor_versions,
            "trove_classifiers": [
                "Programming Language :: Python :: {}".format(postfix) for postfix in ["3 :: Only"] + vers
            ],
        }
        _logger.info(title="Supported versions", msg=str(output["python_versions"]))
        _logger.debug("Generated data:", code=str(output))
        return output

    @_logger.sectioner("Package Operating Systems")
    def _package_operating_systems(self):
        trove_classifiers_postfix = {
            "windows": "Microsoft :: Windows",
            "macos": "MacOS",
            "linux": "POSIX :: Linux",
            "independent": "OS Independent",
        }
        trove_classifier_template = "Operating System :: {}"
        output = {
            "os_titles": [],
            "os_independent": True,
            "pure_python": True,
            "github_runners": [],
            "trove_classifiers": [],
            "cibw_matrix_platform": [],
            "cibw_matrix_python": [],
        }
        os_title = {
            "linux": "Linux",
            "macos": "macOS",
            "windows": "Windows",
        }
        if not self._data["package"].get("operating_systems"):
            _logger.info("No operating systems provided; package is platform independent.")
            output["trove_classifiers"].append(
                trove_classifier_template.format(trove_classifiers_postfix["independent"])
            )
            output["github_runners"].extend(["ubuntu-latest", "macos-latest", "windows-latest"])
            output["os_titles"].extend(list(os_title.values()))
            _logger.section_end()
            return output
        output["os_independent"] = False
        for os_name, specs in self._data["package"]["operating_systems"].items():
            output["os_titles"].append(os_title[os_name])
            output["trove_classifiers"].append(
                trove_classifier_template.format(trove_classifiers_postfix[os_name])
            )
            default_runner = f"{os_name if os_name != 'linux' else 'ubuntu'}-latest"
            if not specs:
                _logger.info(f"No specifications provided for operating system '{os_name}'.")
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
                [f"cp{ver.replace('.', '')}" for ver in self._data["package"]["python_versions"]]
            )
        _logger.debug("Generated data:", code=str(output))
        return output

    @_logger.sectioner("Package Releases")
    def _package_releases(self) -> dict[str, list[str | dict[str, str | list[str] | PEP440SemVer]]]:
        source = self._ccm_before if self._ccm_before else self._data
        release_prefix, pre_release_prefix = allowed_prefixes = tuple(
            source["branch"][group_name]["prefix"] for group_name in ["release", "pre-release"]
        )
        main_branch_name = source["branch"]["main"]["name"]
        branch_pattern = _re.compile(rf"^({release_prefix}|{pre_release_prefix}|{main_branch_name})")
        releases: list[dict] = []
        self._git.fetch_remote_branches_by_pattern(branch_pattern=branch_pattern)
        curr_branch, other_branches = self._git.get_all_branch_names()
        ver_tag_prefix = source["tag"]["group"]["version"]["prefix"]
        branches = other_branches + [curr_branch]
        self._git.stash()
        for branch in branches:
            if not (branch.startswith(allowed_prefixes) or branch == main_branch_name):
                continue
            self._git.checkout(branch)
            if self._future_versions.get(branch):
                ver = PEP440SemVer(str(self._future_versions[branch]))
            else:
                ver = self._git.get_latest_version(tag_prefix=ver_tag_prefix)
            if not ver:
                _logger.warning(f"Failed to get latest version from branch '{branch}'; skipping branch.")
                continue
            if branch == curr_branch:
                branch_metadata = self._data
            else:
                try:
                    branch_metadata = _util.file.read_datafile(
                        path_repo=self._pathman.root,
                        path_data=self._pathman.metadata.rel_path,
                        relpath_schema="metadata",
                    )
                except _exception.content.ControlManContentException as e:
                    _logger.warning(f"Failed to read metadata from branch '{branch}'; skipping branch.")
                    _logger.debug("Error Details", e)
                    continue
            if not branch_metadata:
                _logger.warning(f"Failed to read metadata from branch '{branch}'; skipping branch.")
                continue
            if not branch_metadata.get("package", {}).get("python_versions"):
                _logger.warning(f"No Python versions specified for branch '{branch}'; skipping branch.")
                continue
            if not branch_metadata.get("package", {}).get("os_titles"):
                _logger.warning(f"No operating systems specified for branch '{branch}'; skipping branch.")
                continue
            if branch == main_branch_name:
                branch_name = self._data["branch"]["main"]["name"]
            elif branch.startswith(release_prefix):
                new_prefix = self._data["branch"]["release"]["prefix"]
                branch_name = f"{new_prefix}{branch.removeprefix(release_prefix)}"
            else:
                new_prefix = self._data["branch"]["pre-release"]["prefix"]
                branch_name = f"{new_prefix}{branch.removeprefix(pre_release_prefix)}"
            release_info = {
                "branch": branch_name,
                "version": str(ver),
                "python_versions": branch_metadata["package"]["python_versions"],
                "os_titles": branch_metadata["package"]["os_titles"],
                "package_managers": ["pip"] + (["conda"] if branch_metadata["package"].get("conda") else []),
                "cli_scripts": [
                    script["name"] for script in branch_metadata["package"].get("cli_scripts", [])
                ],
                "gui_scripts": [
                    script["name"] for script in branch_metadata["package"].get("gui_scripts", [])
                ],
            }
            releases.append(release_info)
        self._git.checkout(curr_branch)
        self._git.stash_pop()
        releases.sort(key=lambda i: i["version"], reverse=True)
        all_branch_names = []
        all_python_versions = []
        all_os_titles = []
        all_package_versions = []
        all_package_managers = []
        all_cli_scripts = []
        all_gui_scripts = []
        for release in releases:
            all_branch_names.append(release["branch"])
            all_os_titles.extend(release["os_titles"])
            all_python_versions.extend(release["python_versions"])
            all_package_versions.append(str(release["version"]))
            all_package_managers.extend(release["package_managers"])
            all_cli_scripts.extend(release["cli_scripts"])
            all_gui_scripts.extend(release["gui_scripts"])
        all_os_titles = sorted(set(all_os_titles))
        all_python_versions = sorted(set(all_python_versions), key=lambda ver: tuple(map(int, ver.split("."))))
        all_package_managers = sorted(set(all_package_managers))
        all_cli_scripts = sorted(set(all_cli_scripts))
        all_gui_scripts = sorted(set(all_gui_scripts))
        out = {
            "per_branch": releases,
            "branch_names": all_branch_names,
            "os_titles": all_os_titles,
            "python_versions": all_python_versions,
            "package_versions": all_package_versions,
            "package_managers": all_package_managers,
            "cli_scripts": all_cli_scripts,
            "gui_scripts": all_gui_scripts,
            "has_scripts": bool(all_cli_scripts or all_gui_scripts),
            "interfaces": ["Python API"],
        }
        if all_cli_scripts:
            out["interfaces"].append("CLI")
        if all_gui_scripts:
            out["interfaces"].append("GUI")
        _logger.debug(f"Generated data:", code=str(out))
        return out

    @_logger.sectioner("Custom Metadata")
    def _generate_custom_metadata(self) -> dict:

        @_logger.sectioner("Install Requirements")
        def install_requirements():
            result = pyshellman.pip.install_requirements(path=dir_path / "requirements.txt")
            for title, detail in result.details:
                _logger.info(code_title=title, code=detail)
            return

        dir_path = self._pathman.dir_meta / "custom"
        if not (dir_path / "generator.py").is_file():
            return {}
        _logger.section("User-Defined Data")
        if (dir_path / "requirements.txt").is_file():
            install_requirements()
        custom_generator = _util.file.import_module_from_path(path=dir_path / "generator.py")
        custom_metadata = custom_generator.run(self._data)
        return custom_metadata

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

    @_logger.sectioner("Get GitHub User Data")
    def _get_user(self, username: str) -> dict:
        user_info = self._cache.get(f"user__{username}")
        if user_info:
            _logger.section_end()
            return user_info
        _logger.info(f"Get user info for '{username}' from GitHub API")
        output = {"username": username}
        user = self._github_api.user(username=username)
        user_info = user.info
        for key in ["name", "company", "location", "email", "bio", "id", "node_id", "avatar_url"]:
            output[key] = user_info[key]
        output["url"] = {"website": user_info["blog"], "github": user_info["html_url"]}
        _logger.section(f"Get Social Accounts")
        social_accounts = user.social_accounts
        for account in social_accounts:
            if account["provider"] == "twitter":
                output["url"]["twitter"] = account["url"]
                _logger.info(title="Twitter account", msg=account['url'])
            elif account["provider"] == "linkedin":
                output["url"]["linkedin"] = account["url"]
                _logger.info(title=f"LinkedIn account", msg=account['url'])
            else:
                for url, key in [
                    (r"orcid\.org", "orcid"),
                    (r"researchgate\.net/profile", "researchgate"),
                ]:
                    match = _re.compile(r"(?:https?://)?(?:www\.)?({}/[\w\-]+)".format(url)).fullmatch(
                        account["url"]
                    )
                    if match:
                        output["url"][key] = f"https://{match.group(1)}"
                        _logger.info(title=f"{key} account", msg=output['url'][key])
                        break
                else:
                    other_urls = output["url"].setdefault("others", list())
                    other_urls.append(account["url"])
                    _logger.info(title=f"Unknown account", msg=account['url'])
        _logger.section_end()
        self._cache.set(f"user__{username}", output)
        return output

    @_logger.sectioner("Get Current Python Versions")
    def _get_released_python3_versions(self) -> list[tuple[int, int, int]]:
        release_versions = self._cache.get("python_versions")
        if release_versions:
            return [tuple(ver) for ver in release_versions]
        _logger.info("Get Python versions from GitHub API")
        vers = self._github_api.user("python").repo("cpython").semantic_versions(tag_prefix="v")
        release_versions = sorted(set([v for v in vers if v[0] >= 3]))
        self._cache.set("python_versions", release_versions)
        return release_versions
