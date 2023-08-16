
class URLs:

    def __init__(self, metadata: dict):
        self.metadata = metadata
        return

    def fill(self):
        self.metadata["url"] = dict()
        self.github()
        self.website()
        self.distributions()
        return

    def github(self):
        url = self.metadata['url']['github'] = dict()
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

    def website(self):
        url = self.metadata["url"]["website"] = dict()

        base = self.metadata['website']['custom_base_url']
        if base:
            url['base'] = base
        elif self.metadata['repo']['name'] == f"{self.metadata['owner']}.github.io":
            base = url['base'] = f"https://{self.metadata['owner']}.github.io"
        else:
            base = url['base'] = f"https://{self.metadata['owner']}.github.io/{self.metadata['repo']['name']}"

        url["home"] = base
        url["news"] = f"{base}/news"
        url["announcement"] = (
            f"https://raw.githubusercontent.com/{self.metadata['repo']['full_name']}/"
            f"{self.metadata['repo']['default_branch']}/docs/website/announcement.html"
        )
        url["contributors"] = f"{base}/about#contributors"
        url["contributing"] = f"{base}/contribute"
        url["license"] = f"{base}/license"
        url["security_measures"] = f"{base}/contribute/collaborate/maintain/security"
        url["sponsor"] = f"{base}/contribute/collaborate/maintain/sponsor"
        return

    def distributions(self):
        if not self.metadata.get("package"):
            return
        url = self.metadata["url"]
        package_name = self.metadata["package"]["name"]
        language = self.metadata["package"]["language"]
        match language:
            case "python":
                url["conda"] = f"https://anaconda.org/conda-forge/{package_name}/"
                url["pypi"] = f"https://pypi.org/project/{package_name}/"
            case _:
                raise NotImplementedError(f"Language '{language}' not supported.")
        return


def fill(metadata: dict) -> None:
    URLs(metadata=metadata).fill()
    return
