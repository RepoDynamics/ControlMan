from typing import Literal as _Literal

import pyserials as _ps

from controlman.files.generator.docs import markdown as _md, text as _text


INLINE_MAX_LINE_LENGTH = 50


def get_subschemas(
    schema: dict,
    key: _Literal["properties", "additionalProperties", "items", "not", "if", "then", "else", "anyOf", "oneOf", "allOf"]
) -> tuple[list[str], list[dict]]:
    if key == "properties":
        return schema[key].keys(), schema[key].values()
    if key == "additionalProperties":
        return (["*"], [schema[key]]) if isinstance(schema[key], dict) else ([], [])
    if key == "items":
        return ["[i]"], [schema[key]]
    if key in ["not", "if", "then", "else"]:
        return [key], [schema[key]]
    return [f"{key}[{i}]" for i in range(1, len(schema[key])+1)], schema[key]


def needs_separate_section(schema: dict, max_nesting: int = 2, _rec: int = 0) -> bool:
    """Check if a schema needs a separate section in the same file.

    A schema needs a separate section if it has more than two
    nested levels (e.g. `properties` or `items`), or if it has
    any of the following keys: `anyOf`, `oneOf`, `allOf`, `not`, `if`.
    A schema that uses `$ref` is not considered nested,
    because the reference must be documented in another file.
    """
    if "$ref" in schema:
        return False
    for key in [
        "properties",
        "additionalProperties",
        "items", "not", "if", "then", "else",
        "anyOf", "oneOf", "allOf",
    ]:
        if key in schema:
            if _rec >= max_nesting:
                return True
            for subschema in get_subschemas(schema, key)[1]:
                if needs_separate_section(subschema, max_nesting=max_nesting, _rec=_rec+1):
                    return True
    return False


def subschema_is_required(schema: dict, key: str, sub_key: str = "") -> bool:
    if key == "properties":
        return sub_key in schema.get("required", [])
    if key == "items":
        return array_items_are_required(schema)
    return False


def array_items_are_required(schema: dict) -> bool:
    return "minItems" in schema and schema["minItems"] > 0


def clean_schema(schema: dict | list, is_prop_dict: bool = False) -> dict:
    if isinstance(schema, dict):
        clean = {}
        for key, val in schema.items():
            if key in ["title", "description", "examples", "root_key", "default_auto", "default"] and not is_prop_dict:
                continue
            if isinstance(val, (dict, list)):
                clean[key] = clean_schema(
                    schema=val, is_prop_dict=isinstance(val, dict) and key == "properties"
                )
            else:
                clean[key] = val
    elif isinstance(schema, list):
        clean = []
        for item in schema:
            if isinstance(item, (dict, list)):
                clean.append(clean_schema(schema=item))
            else:
                clean.append(item)
    else:
        raise ValueError(f"Unsupported schema type: {type(schema)}")
    return clean


def ref_name(ref: str) -> str:
    parts = ref.split("#")
    if len(parts) == 1:
        # there is no # in the ref; it is a filepath or -url; return the filename.
        return parts[0].split(".")[-2]
    return parts[-1].split("/")[-1]


def schema_to_md(schema: dict) -> str:
    schema_text = _ps.write.to_yaml_string(data=clean_schema(schema=schema))
    return _md.code_block(schema_text)


def default_to_md(schema: dict, key: str = "default", key_auto: str = "default_auto") -> tuple[str | None, bool]:
    if key in schema:
        text = _ps.write.to_yaml_string(
            data=schema[key],
            end_of_file_newline=False
        ).removesuffix("\n...")
        inline_ok = _text_can_be_inline(text)
        return f"`{text}`" if inline_ok else _md.code_block(text), inline_ok
    if key_auto in schema:
        text = schema[key_auto].strip().replace("\n", " ")
        return text, _text_can_be_inline(text)
    return None, False


def examples_to_md(schema: dict, key: str = "examples") -> tuple[str | None, bool]:
    if key not in schema:
        return None, False
    examples = schema[key]
    all_can_be_inline = True
    examples_text = []
    for example in examples:
        example_str = _ps.write.to_yaml_string(
            data=example,
            end_of_file_newline=False
        ).removesuffix("\n...")
        examples_text.append(example_str)
        if not _text_can_be_inline(example_str):
            all_can_be_inline = False
    total_can_be_inline = sum((len(e) for e in examples_text)) <= INLINE_MAX_LINE_LENGTH
    if all_can_be_inline and total_can_be_inline:
        return f"{_md.comma_list(examples_text, item_as_code=True, as_html=False)}", True
    if all_can_be_inline:
        return _md.normal_list(examples_text, item_as_code=True), False
    return "\n".join([_md.code_block(text) for text in examples_text]), False


def not_to_md(
    schema: dict,
    fullpath: str,
    tag_prefix: str = "",
    tag_prefix_refs: str = "",
    key: str = "not",
) -> tuple[str | None, bool]:
    if key not in schema:
        return None, False
    _not = schema[key]
    if "$ref" in _not:
        ref = _not["$ref"]
        ref_tag = _text.create_slug(f"{tag_prefix_refs}-{ref}")
        return f"[`{ref_name(ref)}`](#{ref_tag})", True
    tag = _text.create_slug(f"{tag_prefix}-{fullpath}-not")
    return f"[`not`](#{tag})", True


def some_of_to_md(
    schema: dict,
    fullpath: str,
    tag_prefix: str = "",
    tag_prefix_refs: str = "",
    key: _Literal["allOf", "anyOf", "oneOf"] = "allOf",
) -> tuple[str | None, bool]:
    if key not in schema:
        return None, False
    some_of = schema[key]
    outputs = []
    for i, subschema in enumerate(some_of):
        idx = i + 1
        if "$ref" in subschema:
            ref = subschema["$ref"]
            ref_tag = _text.create_slug(f"{tag_prefix_refs}-{ref}")
            outputs.append(f"[`{ref_name(ref)}`](#{ref_tag})")
        else:
            tag = _text.create_slug(f"{tag_prefix}-{fullpath}-{key}-{idx}")
            title = f"{key}[{idx}]"
            outputs.append(f"[`{title}`](#{tag})")
    return _md.comma_list(outputs, item_as_code=False, as_html=False), True


def if_to_md(
    schema: dict,
    fullpath: str,
    tag_prefix: str = "",
    tag_prefix_refs: str = "",
    key: str = "if",
) -> tuple[str | None, bool]:
    output = []
    for key in ("if", "then", "else"):
        if key not in schema:
            break
        output.append(key)
        sub = schema[key]
        if "$ref" in sub:
            ref = sub["$ref"]
            ref_tag = _text.create_slug(f"{tag_prefix_refs}-{ref}")
            output.append(f"[`{ref_name(ref)}`](#{ref_tag})")
            continue
        tag = _text.create_slug(f"{tag_prefix}-{fullpath}-{key}")
        output.append(f"[`{key}`](#{tag})")
    if not output:
        return None, False
    return " ".join(output), True


def type_to_md(schema: dict, key: str = "type", tag_prefix_refs: str = "") -> tuple[str | None, bool]:
    if "$ref" in schema:
        ref = schema["$ref"]
        ref_tag = _text.create_slug(f"{tag_prefix_refs}-{ref}")
        return f"[`{ref_name(ref)}`](#{ref_tag})", True
    dtype = schema.get(key)
    if isinstance(dtype, str):
        return f"`{dtype}`", True
    if isinstance(dtype, list):
        return " or ".join([f"`{v}`" for v in dtype]), True
    if dtype is None:
        if any(key in schema for key in ["anyOf", "oneOf", "allOf", "not", "if"]):
            return "`complex`", True
        else:
            return "`any`", True
    raise ValueError(f"Unsupported value for `type`: `{dtype}`")


def additional_properties_to_md(schema: dict, key: str = "additionalProperties", tag_add_props: str | None = None) -> tuple[str | None, bool]:
    value = schema.get(key)
    if value is False:
        return "`false`", True
    if value is True:
        return "`any`", True
    if value is None:
        if any(key in schema for key in ["$ref", "anyOf", "oneOf", "allOf", "not", "if"]):
            return None, False
        if schema.get("type") == "object":
            return "`any`", True
        return None, False
    return (f"[`true`](#{tag_add_props})" if tag_add_props else "[`true`]"), True


def required_to_md(schema: dict, key: str = "required") -> tuple[str | None, bool]:
    if key not in schema:
        return None, False
    return make_code_list(schema["required"])


def enum_to_md(schema: dict, key: str = "enum") -> tuple[str | None, bool]:
    if key not in schema:
        return None, False
    return make_code_list(array=schema[key])


def scalar_to_md(schema: dict, key: str):
    if key not in schema:
        return None, False
    value = schema[key]
    if isinstance(value, bool):
        value = str(value).lower()
    return f"`{value}`", True


def make_code_list(array: list) -> tuple[str, bool]:
    array_text_len = sum((len(e) for e in array))
    if array_text_len < INLINE_MAX_LINE_LENGTH:
        return _md.comma_list(array, item_as_code=True, as_html=False), True
    return _md.normal_list(items=array, item_as_code=True), False


def _text_can_be_inline(text: str) -> bool:
    return "\n" not in text and len(str(text)) <= INLINE_MAX_LINE_LENGTH
