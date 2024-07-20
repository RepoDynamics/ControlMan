"""Constants for ControlMan.

These include paths to files and directories in the user repository.
"""


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





FILE_ISSUE_TEMPLATE_CHOOSER_CONFIG = ".github/ISSUE_TEMPLATE/config.yml"
FILE_PYTHON_PYPROJECT = "pyproject.toml"
FILE_PYTHON_REQUIREMENTS = "requirements.txt"
FILE_PYTHON_MANIFEST = "MANIFEST.in"
FILE_GITIGNORE = ".gitignore"
FILE_GITATTRIBUTES = ".gitattributes"
DIR_GITHUB = ".github/"
DIR_GITHUB_WORKFLOWS = ".github/workflows/"
DIR_GITHUB_WORKFLOW_REQUIREMENTS = ".github/workflow_requirements/"
DIR_GITHUB_ISSUE_TEMPLATE = ".github/ISSUE_TEMPLATE/"
DIR_GITHUB_PULL_REQUEST_TEMPLATE = ".github/PULL_REQUEST_TEMPLATE/"
DIR_GITHUB_DISCUSSION_TEMPLATE = ".github/DISCUSSION_TEMPLATE/"
