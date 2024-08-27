from typing import Literal as _Literal
from pathlib import Path as _Path
import copy
import re as _re

import jsonschema as _jsonschema
import referencing as _referencing
from referencing import jsonschema as _referencing_jsonschema
import jsonschemata as _js
import pkgdata as _pkgdata
from loggerman import logger as _logger
import pyserials as _ps
from docsman import schema as _docsman_schema

from controlman import exception as _exception
from controlman import _file_util


_schema_dir_path = _pkgdata.get_package_path_from_caller(top_level=True) / "_data" / "schema"


def validate(
    data: dict,
    schema: _Literal["main", "local", "cache"] = "main",
    before_substitution: bool = False,
) -> None:
    """Validate data against a schema."""
    schema_dict = _file_util.read_data_from_file(
        path=_schema_dir_path / f"{schema}.yaml",
        extension="yaml",
        raise_errors=True,
    )
    schema_dict = _js.edit.required_last(schema_dict)
    if before_substitution:
        schema_dict = modify_schema(schema_dict)["anyOf"][0]
    try:
        _ps.validate.jsonschema(
            data=data,
            schema=schema_dict,
            validator=_jsonschema.Draft202012Validator,
            registry=_registry_before if before_substitution else _registry_after,
            fill_defaults=True,
            iter_errors=True,
        )
    except _ps.exception.validate.PySerialsJsonSchemaValidationError as e:
        raise _exception.ControlManSchemaValidationError(
            msg="Validation against schema failed."
        ) from e
    if schema == "main" and not before_substitution:
        DataValidator(data).validate()
    return


class DataValidator:
    def __init__(self, data: dict):
        self._data = data
        return

    @_logger.sectioner("Validate Control Center Contents")
    def validate(self):
        # self.branch_names()
        # self.changelogs()
        # self.commits()
        # self.issue_forms()
        # self.labels()
        return

    def dir_paths(self):
        """Verify that main directory paths are not relative to each other."""
        paths = []
        path_keys = []
        for dirpath_key in (
            "control.path",
            "local.path",
            "theme.path",
            "pkg.path.root",
            "test.path.root",
            "web.path.root",
        ):
            if self._data[dirpath_key]:
                path_keys.append(dirpath_key)
                paths.append(_Path(self._data[dirpath_key]))
        for idx, path in enumerate(paths):
            for idx2, path2 in enumerate(paths[idx + 1:]):
                if path.is_relative_to(path2):
                    main_path = path2
                    rel_path = path
                    main_key = path_keys[idx + idx2 + 1]
                    rel_key = path_keys[idx]
                elif path2.is_relative_to(path):
                    main_path = path
                    rel_path = path2
                    main_key = path_keys[idx]
                    rel_key = path_keys[idx + idx2 + 1]
                else:
                    continue
                raise _exception.ControlManSchemaValidationError(
                    f"Directory path '{rel_path}' defined at '{rel_key}' is relative to"
                    f"directory path '{main_path}' defined at '{main_key}'.",
                    key=rel_key,
                )
        return

    def branch_names(self):
        """Verify that branch names/prefixes do not overlap."""
        branch_keys = []
        branch_names = []
        for branch_key, branch_data in self._data["branch"].items():
            branch_keys.append(branch_key)
            branch_names.append(branch_data["name"])
        for idx, branch_name in enumerate(branch_names):
            for idx2, branch_name2 in enumerate(branch_names[idx + 1:]):
                if branch_name.startswith(branch_name2) or branch_name2.startswith(branch_name):
                    raise _exception.ControlManSchemaValidationError(
                        f"Branch name '{branch_name}' defined at 'branch.{branch_keys[idx]}' "
                        f"overlaps with branch name '{branch_name2}' defined at 'branch.{branch_keys[idx + idx2 + 1]}'.",
                        key=branch_keys[idx],
                    )
        return

    def changelogs(self):
        """Verify that changelog paths, names and sections are unique."""
        changelog_paths = []
        changelog_names = []
        for changelog_id, changelog_data in self._data["changelog"].items():
            if changelog_data["path"] in changelog_paths:
                raise _exception.ControlManSchemaValidationError(
                    f"The path '{changelog_data['path']}' set for changelog '{changelog_id}' "
                    f"is already used by another earlier changelog.",
                    key=f"changelog.{changelog_id}.path"
                )
            changelog_paths.append(changelog_data["path"])
            if changelog_data["name"] in changelog_names:
                raise _exception.ControlManSchemaValidationError(
                    f"The name '{changelog_data['name']}' set for changelog '{changelog_id}' "
                    f"is already used by another earlier changelog.",
                    key=f"changelog.{changelog_id}.name"
                )
            changelog_names.append(changelog_data["name"])
            # if changelog_id == "package_public_prerelease": #TODO: check package_public_prerelease
            #     continue
            section_ids = []
            for idx, section in enumerate(changelog_data.get("sections", [])):
                if section["id"] in section_ids:
                    raise _exception.ControlManSchemaValidationError(
                        f"The changelog section ID '{section['id']}' set for changelog '{changelog_id}' "
                        f"is already used by another earlier section.",
                        key=f"changelog.{changelog_id}.sections[{idx}]"
                    )
                section_ids.append(section["id"])
        return

    def commits(self):
        """Verify that commit types are unique, and that subtypes are defined."""
        commit_types = []
        for main_type in ("primary", "primary_custom"):
            for commit_id, commit_data in self._data["commit"][main_type].items():
                if commit_data["type"] in commit_types:
                    raise _exception.ControlManSchemaValidationError(
                        f"The commit type '{commit_data['type']}' set for commit '{main_type}.{commit_id}' "
                        f"is already used by another earlier commit.",
                        key=f"commit.{main_type}.{commit_id}.type"
                    )
                commit_types.append(commit_data["type"])
                for subtype_type, subtypes in commit_data["subtypes"]:
                    for subtype in subtypes:
                        if subtype not in self._data["commit"]["secondary_custom"]:
                            _logger.critical(
                                title=f"Invalid commit subtype: {subtype}",
                                msg=f"The subtype '{subtype}' set for commit '{main_type}.{commit_id}' "
                                f"in 'subtypes.{subtype_type}' is not defined in 'commit.secondary_custom'.",
                            )
        for commit_id, commit_data in self._data["commit"]["secondary_action"].items():
            if commit_data["type"] in commit_types:
                _logger.critical(
                    title=f"Duplicate commit type: {commit_data['type']}",
                    msg=f"The type '{commit_data['type']}' set for commit 'secondary_action.{commit_id}' "
                    f"is already used by another earlier commit.",
                )
            commit_types.append(commit_data["type"])
        changelog_sections = {}
        for commit_type, commit_data in self._data["commit"]["secondary_custom"].items():
            if commit_type in commit_types:
                _logger.critical(
                    title=f"Duplicate commit type: {commit_type}",
                    msg=f"The type '{commit_type}' set in 'secondary_custom' "
                    f"is already used by another earlier commit.",
                )
            commit_types.append(commit_type)
            # Verify that linked changelogs are defined
            changelog_id = commit_data["changelog_id"]
            if changelog_id not in self._data["changelog"]:
                _logger.critical(
                    title=f"Invalid commit changelog ID: {changelog_id}",
                    msg=f"The changelog ID '{changelog_id}' set for commit "
                    f"'secondary_custom.{commit_type}' is not defined in 'changelog'.",
                )
            if changelog_id not in changelog_sections:
                changelog_sections[changelog_id] = [
                    section["id"] for section in self._data["changelog"][changelog_id]["sections"]
                ]
            if commit_data["changelog_section_id"] not in changelog_sections[changelog_id]:
                _logger.critical(
                    title=f"Invalid commit changelog section ID: {commit_data['changelog_section_id']}",
                    msg=f"The changelog section ID '{commit_data['changelog_section_id']}' set for commit "
                    f"'secondary_custom.{commit_type}' is not defined in 'changelog.{changelog_id}.sections'.",
                )
        return

    def issue_forms(self):
        form_ids = []
        form_identifying_labels = []
        for form_idx, form in enumerate(self._data["issue"]["forms"]):
            if form["id"] in form_ids:
                _logger.critical(
                    title=f"Duplicate issue-form ID: {form['id']}",
                    msg=f"The issue-form number {form_idx} has an ID that is already used by another earlier form.",
                )
            form_ids.append(form["id"])
            identifying_labels = (form["primary_type"], form.get("subtype"))
            if identifying_labels in form_identifying_labels:
                _logger.critical(
                    title=f"Duplicate issue-form identifying labels: {identifying_labels}",
                    msg=f"The issue-form number {form_idx} has the same identifying labels as another earlier form.",
                )
            form_identifying_labels.append(identifying_labels)
            element_ids = []
            element_labels = []
            for elem_idx, elem in enumerate(form["body"]):
                if elem["type"] == "markdown":
                    continue
                elem_id = elem.get("id")
                if elem_id:
                    if elem_id in element_ids:
                        _logger.critical(
                            title=f"Duplicate issue-form body-element ID: {elem_id}",
                            msg=f"The element number {elem_idx} has an ID that is "
                            f"already used by another earlier element.",
                        )
                    else:
                        element_ids.append(elem["id"])
                if elem["attributes"]["label"] in element_labels:
                    _logger.critical(
                        title=f"Duplicate issue-form body-element label: {elem['attributes']['label']}",
                        msg=f"The element number {elem_idx} has a label that is already used by another earlier element.",
                    )
                element_labels.append(elem["attributes"]["label"])
            if not any(element_id in ("version", "branch") for element_id in element_ids):
                _logger.critical(
                    title=f"Missing issue-form body-element: version or branch",
                    msg=f"The issue-form number {form_idx} is missing a body-element "
                    f"with ID 'version' or 'branch'.",
                )
            form_post_process = form.get("post_process")
            if form_post_process:
                if form_post_process.get("body"):
                    pattern = r"{([a-zA-Z_][a-zA-Z0-9_]*)}"
                    var_names = _re.findall(pattern, form_post_process["body"])
                    for var_name in var_names:
                        if var_name not in element_ids:
                            _logger.critical(
                                title=f"Unknown issue-form post-process body variable: {var_name}",
                                msg=f"The variable '{var_name}' is not a valid element ID within the issue body.",
                            )
                assign_creator = form_post_process.get("assign_creator")
                if assign_creator:
                    if_checkbox = assign_creator.get("if_checkbox")
                    if if_checkbox:
                        if if_checkbox["id"] not in element_ids:
                            _logger.critical(
                                title=f"Unknown issue-form post-process assign_creator if_checkbox ID: {if_checkbox}",
                                msg=f"The ID '{if_checkbox}' is not a valid element ID within the issue body.",
                            )
                        for elem in form["body"]:
                            elem_id = elem.get("id")
                            if elem_id and elem_id == if_checkbox["id"]:
                                if elem["type"] != "checkboxes":
                                    _logger.critical(
                                        title=f"Invalid issue-form post-process assign_creator if_checkbox ID: {if_checkbox}",
                                        msg=f"The ID '{if_checkbox}' is not a checkbox element.",
                                    )
                                if len(elem["attributes"]["options"]) < if_checkbox["number"]:
                                    _logger.critical(
                                        title=f"Invalid issue-form post-process assign_creator if_checkbox number: {if_checkbox}",
                                        msg=f"The number '{if_checkbox['number']}' is greater than the number of "
                                        f"checkbox options.",
                                    )
                                break
        # Verify that identifying labels are defined in 'label.group' metadata
        for primary_type_id, subtype_id in form_identifying_labels:
            if primary_type_id not in self._data["label"]["group"]["primary_type"]["labels"]:
                _logger.critical(
                    title=f"Unknown issue-form `primary_type`: {primary_type_id}",
                    msg=f"The ID '{primary_type_id}' does not exist in 'label.group.primary_type.labels'.",
                )
            if subtype_id and subtype_id not in self._data["label"]["group"]["subtype"]["labels"]:
                _logger.critical(
                    title=f"Unknown issue-form subtype: {subtype_id}",
                    msg=f"The ID '{subtype_id}' does not exist in 'label.group.subtype.labels'.",
                )
        return

    def labels(self):
        """Verify that label names and prefixes are unique."""
        labels = []
        for main_type in ("auto_group", "group", "single"):
            for label_id, label_data in self._data["label"].get(main_type, {}).items():
                label = label_data["name"] if main_type == "single" else label_data["prefix"]
                label_type = "name" if main_type == "single" else "prefix"
                for set_label in labels:
                    if set_label.startswith(label) or label.startswith(set_label):
                        _logger.critical(
                            title=f"Ambiguous label {label_type}: {label}",
                            msg=f"The {label_type} '{label}' set for label '{main_type}.{label_id}' "
                            f"is ambiguous as it overlaps with the already set name/prefix '{set_label}'.",
                        )
                labels.append(label)
        if len(labels) > 1000:
            _logger.critical(
                title=f"Too many labels: {len(labels)}",
                msg=f"The maximum number of labels allowed by GitHub is 1000.",
            )
        for label_id, label_data in self._data["label"]["group"].items():
            suffixes = []
            for label_type, suffix_data in label_data["labels"].items():
                suffix = suffix_data["suffix"]
                if suffix in suffixes:
                    _logger.critical(
                        title=f"Duplicate label suffix: {suffix}",
                        msg=f"The suffix '{suffix}' set for label 'group.{label_id}.labels.{label_type}' "
                        f"is already used by another earlier label.",
                    )
                suffixes.append(suffix)
        return

    def maintainers(self):
        issue_ids = [issue["id"] for issue in self._data.issue__forms]
        for issue_id in self._data.maintainer__issue.keys():
            if issue_id not in issue_ids:
                _logger.critical(
                    f"Issue ID '{issue_id}' defined in 'maintainer.issue' but not found in 'issue.forms'."
                )
        return


def modify_schema(schema: dict) -> dict:
    schema.pop("$schema", None)  # see: https://github.com/python-jsonschema/jsonschema/issues/1295
    if "properties" in schema:
        for key, subschema in schema["properties"].items():
            schema["properties"][key] = modify_schema(subschema)
    if "additionalProperties" in schema and isinstance(schema["additionalProperties"], dict):
        schema["additionalProperties"] = modify_schema(schema["additionalProperties"])
    if "prefixItems" in schema:
        schema["prefixItems"] = [modify_schema(subschema) for subschema in schema["prefixItems"]]
    if "items" in schema and isinstance(schema["items"], dict):
        schema["items"] = modify_schema(schema["items"])
    alt_schema = {
        "type": "string",
        "minLength": 6,
    }
    new_schema = {}
    if "$id" in schema:
        new_schema["$id"] = schema.pop("$id")
    if "default" in schema:
        # If the schema has a default value, add it to the new schema,
        # otherwise it is not filled when inside an 'anyOf' clause.
        new_schema["default"] = schema["default"]
    new_schema["anyOf"] = [schema, alt_schema]
    return new_schema

import re
re.match(
    r"^https://(www\.)?[a-zA-Z0-9@:%._+~#=]{2,256}\.[a-z]{2,6}\b([-a-zA-Z0-9@:%_+.~#?&/=]*)$",
    "https://pydata-sphinx-theme.readthedocs.io"
)


def _make_registry():

    def make_resource(
        schema: dict, spec: _referencing.Specification = _referencing_jsonschema.DRAFT202012
    ) -> _referencing.Resource:
        return _referencing.Resource.from_contents(schema, default_specification=spec)

    resources = []
    def_schemas_path = _schema_dir_path
    for schema_filepath in def_schemas_path.glob("**/*.yaml"):
        schema_dict = _file_util.read_data_from_file(
            path=schema_filepath,
            extension="yaml",
            raise_errors=True,
        )
        _js.edit.required_last(schema_dict)
        resources.append(make_resource(schema_dict))
    registry_after, _ = _docsman_schema.load(dynamic=False, crawl=True, add_resources=resources)
    resources_before = []
    for registry_schema_id in registry_after:
        registry_schema_dict = registry_after[registry_schema_id].contents
        registry_schema_spec = registry_after[registry_schema_id]._specification
        registry_schema_dict_before = modify_schema(copy.deepcopy(registry_schema_dict))
        resources_before.append(make_resource(registry_schema_dict_before, spec=registry_schema_spec))

    registry_before = resources_before @ _referencing.Registry()
    return registry_before, registry_after


_registry_before, _registry_after = _make_registry()
