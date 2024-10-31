"""Constants for ControlMan.

These include paths to files and directories in the user repository.
"""


# ControlMan Constants
DIRPATH_CC_DEFAULT = ".control"

DIRNAME_LOCAL_REPORT = "reports"
DIRNAME_LOCAL_REPODYNAMICS = "RepoDynamics"

FILEPATH_METADATA = ".github/.repodynamics/metadata.json"
FILENAME_METADATA_CACHE = ".metadata_cache.yaml"
FILENAME_LOCAL_CONFIG = "config.yaml"

DIRNAME_CC_HOOK = "hook"

FILENAME_CC_HOOK_REQUIREMENTS = "requirements.txt"
FILENAME_CC_HOOK_STAGED = "staged.py"
FILENAME_CC_HOOK_INLINE = "inline.py"

FUNCNAME_CC_HOOK_POST_LOAD = "post_load"
FUNCNAME_CC_HOOK_POST_DATA = "post_data"

CC_EXTENSION_TAG = u"!ext"

RELATIVE_TEMPLATE_KEYS = ["__custom_template__"]
CUSTOM_KEY = "__custom__"

# GitHub Constants
DIRPATH_ISSUES = ".github/ISSUE_TEMPLATE"
FILEPATH_ISSUES_CONFIG = f"{DIRPATH_ISSUES}/config.yml"
FILEPATH_FUNDING_CONFIG = ".github/FUNDING.yml"
FILEPATH_CITATION_CONFIG = "CITATION.cff"
DIRPATH_DISCUSSIONS = ".github/DISCUSSION_TEMPLATE"
FILEPATH_PULL_TEMPLATE_MAIN = ".github/pull_request_template.md"
DIRPATH_PULL_TEMPLATES = ".github/PULL_REQUEST_TEMPLATE"

# Git Constants
FILEPATH_GITIGNORE = ".gitignore"
FILEPATH_GIT_ATTRIBUTES = ".gitattributes"
ISSUE_FORM_TOP_LEVEL_KEYS = (
    "name",
    "description",
    "body",
    "assignees",
    "labels",
    "title",
    "projects",
)
ISSUE_FORM_BODY_KEY = "body"
ISSUE_FORM_BODY_TOP_LEVEL_KEYS = (
    "type",
    "id",
    "attributes",
    "validations",
)

# Python Constants
FILENAME_PACKAGE_TYPING_MARKER = "py.typed"
FILENAME_PACKAGE_MANIFEST = "MANIFEST.in"
FILENAME_PKG_PYPROJECT = "pyproject.toml"
