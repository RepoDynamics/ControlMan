from typing import Literal as _Literal

import jsonschema as _jsonschema
import referencing as _referencing
import pyserials as _pyserials
import pkgdata as _pkgdata

from controlman import exception as _exception
from controlman._util import file as _file


_schema_dir_path = _pkgdata.get_package_path_from_caller(top_level=True) / "_data" / "schema"


def validate_data(
    data: dict,
    schema: _Literal["full", "local", "cache"],
    raise_invalid_data: bool = True,
) -> None:
    """Validate data against a schema."""
    schema_dict = _file.read_data_from_file(
        path=_schema_dir_path / f"{schema}.yaml",
        extension="yaml",
        raise_errors=True,
    )
    try:
        _pyserials.validate.jsonschema(
            data=data,
            schema=schema_dict,
            validator=_jsonschema.Draft202012Validator,
            registry=_registry,
            fill_defaults=True,
            raise_invalid_data=raise_invalid_data,
        )
    except _pyserials.exception.validate.PySerialsSchemaValidationError as e:
        raise _exception.ControlManSchemaValidationError(
            msg="Validation against schema failed."
        ) from e
    return


def _make_registry():
    ref_resources = []
    added_keys = []
    for schema_type in ("def", "main"):
        path_schema_type = _schema_dir_path / schema_type
        for schema_filepath in path_schema_type.glob("*.yaml"):
            schema_dict = _file.read_data_from_file(
                path=schema_filepath,
                extension="yaml",
                raise_errors=True,
            )
            if schema_type == "main":
                key = f"{schema_type}/{schema_filepath.stem}"
                if key in added_keys:
                    raise RuntimeError(f"Duplicate schema key '{key}'")
                added_keys.append(key)
                ref_resources.append((key, schema_dict))
            else:
                for def_schema_key, def_schema in schema_dict.items():
                    if def_schema_key in added_keys:
                        raise RuntimeError(f"Duplicate schema key '{def_schema_key}'")
                    added_keys.append(def_schema_key)
                    def_schema_parsed = _referencing.Resource.from_contents(def_schema)
                    ref_resources.append((def_schema_key, def_schema_parsed))
    registry = _referencing.Registry().with_resources(ref_resources)
    return registry


_registry = _make_registry()
