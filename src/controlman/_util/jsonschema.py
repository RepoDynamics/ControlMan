import copy
from typing import Literal as _Literal

import jsonschema as _jsonschema
import referencing as _referencing
from referencing import jsonschema as _referencing_jsonschema
import pyserials as _pyserials
import pkgdata as _pkgdata

from controlman import exception as _exception
from controlman._util import file as _file


_schema_dir_path = _pkgdata.get_package_path_from_caller(top_level=True) / "_data" / "schema"


def validate_data(
    data: dict,
    schema: _Literal["full", "local", "cache"],
    before_substitution: bool = False,
    raise_invalid_data: bool = True,
) -> None:
    """Validate data against a schema."""
    schema_dict = _file.read_data_from_file(
        path=_schema_dir_path / f"{schema}.yaml",
        extension="yaml",
        raise_errors=True,
    )
    schema_dict = put_required_at_bottom(schema_dict)
    if before_substitution:
        schema_dict = modify_schema(schema_dict)["anyOf"][0]
    try:
        _pyserials.validate.jsonschema(
            data=data,
            schema=schema_dict,
            validator=_jsonschema.Draft202012Validator,
            registry=_registry_before if before_substitution else _registry_after,
            fill_defaults=True,
            raise_invalid_data=raise_invalid_data,
        )
    except _pyserials.exception.validate.PySerialsSchemaValidationError as e:
        raise _exception.ControlManSchemaValidationError(
            msg="Validation against schema failed."
        ) from e
    return


def modify_schema(schema: dict) -> dict:
    if "properties" in schema:
        for key, subschema in schema["properties"].items():
            schema["properties"][key] = modify_schema(subschema)
    if "additionalProperties" in schema and isinstance(schema["additionalProperties"], dict):
        schema["additionalProperties"] = modify_schema(schema["additionalProperties"])
    if "items" in schema and isinstance(schema["items"], dict):
        schema["items"] = modify_schema(schema["items"])
    alt_schema = {
        "type": "string",
        "minLength": 6,
    }
    new_schema = {"anyOf": [schema, alt_schema]}
    if "default" in schema:
        # If the schema has a default value, add it to the new schema,
        # otherwise it is not filled when inside an 'anyOf' clause.
        new_schema["default"] = schema["default"]
    return new_schema


def put_required_at_bottom(schema: dict) -> dict:
    """Modify JSON schema to recursively put all 'required' fields at the end.

    This is done because otherwise the 'required' fields
    are checked by jsonschema before filling the defaults,
    which can cause the validation to fail.

    Returns
    -------
    dict
        Modified schema.
        Note that the input schema is modified in-place,
        so the return value is a reference to the (now modified) input schema.
    """
    if "required" in schema:
        schema["required"] = schema.pop("required")
    for key in ["anyOf", "allOf", "oneOf"]:
        if key in schema:
            for subschema in schema[key]:
                put_required_at_bottom(subschema)
    for key in ["if", "then", "else", "not", "items", "additionalProperties"]:
        if key in schema and isinstance(schema[key], dict):
            put_required_at_bottom(schema[key])
    if "properties" in schema and isinstance(schema["properties"], dict):
        for subschema in schema["properties"].values():
            put_required_at_bottom(subschema)
    return schema


def _make_registry():
    ref_resources_after = []
    ref_resources_before = []
    def_schemas_path = _schema_dir_path / "def"
    for def_schema_filepath in def_schemas_path.glob("**/*.yaml"):
        def_schema_key = def_schema_filepath.relative_to(def_schemas_path).with_suffix("").as_posix().replace("/", "-")
        def_schema_dict = _file.read_data_from_file(
            path=def_schema_filepath,
            extension="yaml",
            raise_errors=True,
        )
        def_schema_dict_after = put_required_at_bottom(def_schema_dict)
        def_schema_dict_before = modify_schema(copy.deepcopy(def_schema_dict_after))
        def_schema_before_parsed = _referencing.Resource.from_contents(
            def_schema_dict_before, default_specification=_referencing_jsonschema.DRAFT202012
        )
        def_schema_after_parsed = _referencing.Resource.from_contents(
            def_schema_dict, default_specification=_referencing_jsonschema.DRAFT202012
        )
        ref_resources_before.append((def_schema_key, def_schema_before_parsed))
        ref_resources_after.append((def_schema_key, def_schema_after_parsed))
    registry_before = _referencing.Registry().with_resources(ref_resources_before)
    registry_after = _referencing.Registry().with_resources(ref_resources_after)
    return registry_before, registry_after


_registry_before, _registry_after = _make_registry()
