"""Constants for ControlMan.

These include paths to files and directories in the user repository.
"""


# ControlMan Constants
DIRPATH_CC_DEFAULT = ".control"

FILEPATH_METADATA = ".github/.control/.metadata.json"
FILEPATH_METADATA_CACHE = ".github/.control/.metadata_cache.yaml"
FILEPATH_LOCAL_CONFIG = ".github/.control/local_config.yaml"

DIRNAME_CC_HOOK = "hook"

FILENAME_CC_HOOK_REQUIREMENTS = "requirements.txt"
FILENAME_CC_HOOK_MODULE = "generator.py"

FUNCNAME_CC_HOOK_POST_LOAD = "post_load"
FUNCNAME_CC_HOOK_POST_DATA = "post_data"

CC_EXTENSION_TAG = u"!ext"

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

# Python Constants
FILENAME_PACKAGE_TYPING_MARKER = "py.typed"
FILENAME_PACKAGE_MANIFEST = "MANIFEST.in"
FILENAME_PKG_PYPROJECT = "pyproject.toml"
