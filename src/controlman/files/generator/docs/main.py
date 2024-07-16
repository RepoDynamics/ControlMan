from pathlib import Path as _Path
import re
import unicodedata

import pyserials as _ps
from controlman.files.generator.docs import markdown as _md, jsonschema as _schema, text as _text


#TODO: Replace ${‎{ name }}


KEY_SETTING = {
    "type": {"title": "Type", "processor": _schema.type_to_md, "dynamic_kwargs": ["tag_prefix_refs"]},
    "const": {"title": "Const", "processor": _schema.scalar_to_md},
    "enum": {"title": "Enum", "processor": _schema.enum_to_md},
    "format": {"title": "Format", "processor": _schema.scalar_to_md},
    "pattern": {"title": "Pattern", "processor": _schema.scalar_to_md},
    "maxLength": {"title": "Max Length", "processor": _schema.scalar_to_md},
    "minLength": {"title": "Min Length", "processor": _schema.scalar_to_md},
    "maximum": {"title": "Max", "processor": _schema.scalar_to_md},
    "minimum": {"title": "Min", "processor": _schema.scalar_to_md},
    "exclusiveMaximum": {"title": "Exclusive Max", "processor": _schema.scalar_to_md},
    "exclusiveMinimum": {"title": "Exclusive Min", "processor": _schema.scalar_to_md},
    "multipleOf": {"title": "Multiple Of", "processor": _schema.scalar_to_md},
    "uniqueItems": {"title": "Unique Items", "processor": _schema.scalar_to_md},
    "maxItems": {"title": "Max Items", "processor": _schema.scalar_to_md},
    "minItems": {"title": "Min Items", "processor": _schema.scalar_to_md},
    "maxProperties": {"title": "Max Properties", "processor": _schema.scalar_to_md},
    "minProperties": {"title": "Min Properties", "processor": _schema.scalar_to_md},
    "additionalProperties": {"title": "Add. Properties", "processor": _schema.additional_properties_to_md, "dynamic_kwargs": ["tag_add_props"]},
    "required": {"title": "Required Properties", "processor": _schema.required_to_md},
    "examples": {"title": "Examples", "processor": _schema.examples_to_md},
    "default": {"title": "Default", "processor": _schema.default_to_md, "kwargs": {"key_auto": "default_auto"}},
    "not": {"title": "Not", "processor": _schema.not_to_md, "dynamic_kwargs": ["fullpath", "tag_prefix", "tag_prefix_refs"]},
    "if": {"title": "Condition", "processor": _schema.if_to_md, "dynamic_kwargs": ["fullpath", "tag_prefix", "tag_prefix_refs"]},
    "allOf": {"title": "All Of", "processor": _schema.some_of_to_md, "dynamic_kwargs": ["fullpath", "tag_prefix", "tag_prefix_refs"]},
    "oneOf": {"title": "One Of", "processor": _schema.some_of_to_md, "dynamic_kwargs": ["fullpath", "tag_prefix", "tag_prefix_refs"]},
    "anyOf": {"title": "Any Of", "processor": _schema.some_of_to_md, "dynamic_kwargs": ["fullpath", "tag_prefix", "tag_prefix_refs"]},
}

COMPLEX_KEY = {
    "properties": "Properties",
    "additionalProperties": "Additional Properties",
    "items": "Items",
    "anyOf": "Any Of",
    "oneOf": "One Of",
    "allOf": "All Of",
    "not": "Not",
    "if": "Condition",
    "then": "Condition",
    "else": "Condition",
}


def generate_docs(
    filepath: str | _Path,
    title: str = "",
    root_key: str = "",
    required: bool = True,
    tag_prefix: str = "ccs",
    tag_prefix_refs: str = "ccs-ref",
    max_nesting: int = 3
):
    generator = SchemaDocGenerator()
    return generator.generate(filepath=filepath, title=title, root_key=root_key, required=required, tag_prefix=tag_prefix, tag_prefix_refs=tag_prefix_refs, max_nesting=max_nesting)


def generate_homepage(schema: dict, tag: str):
    title = schema.get("title", "Schema")
    heading = _md.tag(f"# {title}", ref=tag)
    description = schema.get("description", "")
    output = [heading, description, "::::{grid} 1 1 2 2", ":gutter: 3", "\n"]
    sections = schema["allOf"]
    last_idx = len(sections) - 1
    num_sections_is_odd = last_idx % 2 != 0
    for idx, section in enumerate(schema["allOf"]):
        sec_title = section["title"]
        sec_desc = section["description"]
        sec_title_slug = _text.create_slug(sec_title)
        text = f"""
:::{{grid-item-card}} {sec_title}
:class-title: sd-text-center
:link: {sec_title_slug}/index
:link-type: doc
{':margin: 3 3 auto auto' if idx == last_idx and num_sections_is_odd else ''}

{sec_desc}

:::
"""
        output.append(text)
    output.append("::::\n")
    return "\n".join(output)



class SchemaDocGenerator:
    def __init__(self):
        self._path: _Path | None = None
        self._schema: dict = {}
        self._tag_prefix: str = ""
        self._tag_prefix_refs: str = ""
        self._reference_map: dict[str, list[str]] = {}
        self._max_nesting: int = 0
        return

    def generate(
        self,
        filepath: str | _Path,
        title: str = "",
        root_key: str = "",
        required: bool = True,
        tag_prefix: str = "ccs",
        tag_prefix_refs: str = "ccs-ref",
        max_nesting: int = 3,
    ):
        self._tag_prefix = tag_prefix
        self._tag_prefix_refs = tag_prefix_refs
        self._max_nesting = max_nesting
        self._path = _Path(filepath).resolve()
        self._schema: dict = _ps.read.from_file(path=self._path, yaml_safe=False)
        output = self._generate_sections_recursive(
            key=title or self._schema.get("root_key") or root_key or self._path.stem,
            schema=self._schema,
            level=1,
            fullpath=self._schema.get("root_key") or root_key,
            items_required=self._schema.get("schema_required") or required,
            dont_show_fullpath=False,
        )
        return "\n".join(output), self._reference_map

    def _generate_sections_recursive(
        self,
        key: str,
        schema: dict,
        level: int,
        fullpath: str,
        items_required: bool,
        dont_show_fullpath: bool,
    ):
        schema = sanitize_title_description(schema)
        self.check_ref(fullpath, schema)
        heading = _md.tag(
            ref=self.make_tag(fullpath),
            text=_md.heading(title=f"`{key}`" if fullpath else key, level=level),
        )
        sig_tab = self.signature(schema=schema, required=items_required, fullpath=fullpath, expanded=True, dont_show_fullpath=dont_show_fullpath)
        output = [heading, schema["title"], sig_tab, schema["description"]]
        separate_schema = {}
        subschema_map = {}
        for complex_key, complex_key_title in COMPLEX_KEY.items():
            if complex_key in schema:
                subschema_keys, subschemas = _schema.get_subschemas(schema=schema, key=complex_key)
                for subschema_key, subschema in zip(subschema_keys, subschemas):
                    if complex_key != "properties" and "$ref" in subschema:
                        continue
                    if _schema.needs_separate_section(subschema, self._max_nesting):
                        separate_schema[subschema_key] = (complex_key, subschema)
                    else:
                        subschema_text = self._generate_field_list_view(
                            key=subschema_key,
                            schema=subschema,
                            fullpath=self.make_address(fullpath, subschema_key),
                            required=_schema.subschema_is_required(schema=schema, key=complex_key, sub_key=subschema_key),
                            dont_show_fullpath=complex_key not in ["properties", "additionalProperties", "items"],
                        )
                        subschema_map.setdefault(complex_key_title, []).append(subschema_text)
        for subschema_type, subschema_texts in subschema_map.items():
            subschema_text_full = add_horiz_line_between_items(subschema_texts)
            subschema_admonition_text = _md.admonition(
                title=subschema_type,
                body=subschema_text_full,
                classes=["note", "dropdown", "toggle-shown"]
            )
            output.append(subschema_admonition_text)
        # Recursively process complex schemas
        for subkey, (complex_key, subschema) in separate_schema.items():
            sub_out = self._generate_sections_recursive(
                key=subkey,
                schema=subschema,
                level=level + 1,
                fullpath=self.make_address(fullpath, subkey),
                items_required=_schema.subschema_is_required(schema=schema, key=complex_key, sub_key=subkey),
                dont_show_fullpath=complex_key not in ["properties", "additionalProperties", "items"],
            )
            output.extend(sub_out)
        return output

    def _generate_field_list_view(
        self, key: str, schema: dict, fullpath: str, required: bool, dont_show_fullpath: bool
    ) -> str:
        schema = sanitize_title_description(schema)
        body = [
            self.signature(schema, required=required, fullpath=fullpath, expanded=False, dont_show_fullpath=dont_show_fullpath),
            f'**{schema["title"]}**\n' if schema["title"] else "",
            schema["description"],
        ]
        subschema_map = {}
        for complex_key, complex_key_title in COMPLEX_KEY.items():
            if complex_key in schema:
                subschema_keys, subschemas = _schema.get_subschemas(schema=schema, key=complex_key)
                for subschema_key, subschema in zip(subschema_keys, subschemas):
                    if complex_key != "properties" and "$ref" in subschema:
                        continue
                    subschema_text = self._generate_field_list_view(
                        key=subschema_key,
                        schema=subschema,
                        fullpath=self.make_address(fullpath, subschema_key),
                        required=_schema.subschema_is_required(schema=schema, key=complex_key, sub_key=subschema_key),
                        dont_show_fullpath=complex_key not in ["properties", "additionalProperties", "items"],
                    )
                    subschema_map.setdefault(complex_key_title, []).append(subschema_text)
        for subschema_type, subschema_texts in subschema_map.items():
            subschema_text_full = add_horiz_line_between_items(subschema_texts)
            subschema_admonition_text = _md.card(
                header=subschema_type,
                body=subschema_text_full,
                options={"margin": "3 0 0 0"},
            )
            body.append(subschema_admonition_text)
        return _md.field_list(name=f"`{key}`", body=_md.tag("\n".join(body), ref=self.make_tag(fullpath)))

    def signature(self, schema: dict, required: bool, fullpath: str, expanded: bool, dont_show_fullpath: bool) -> str:
        sig = self.make_key_signature(schema, fullpath=fullpath)
        inlines: list[str] = []
        not_inlines: list[dict] = []
        for sig_val in sig.values():
            if sig_val["inline"]:
                inlines.append(
                    _md.field_list(name=sig_val["title"], body=sig_val["value"]) if expanded
                    else f"{sig_val['title']}: {sig_val['value']}"
                )
            else:
                not_inlines.append(sig_val)
        if fullpath and not dont_show_fullpath:
            inlines.append(
                _md.field_list(name="Fullpath", body=f"`{fullpath}`") if expanded
                else f"Fullpath: `{fullpath}`"
            )
        if "default" not in sig and required:
            inlines.append(_md.field_list(name="Required") if expanded else "**Required**")
        parts = [
            _md.tab(title="Summary", content="\n".join(inlines)) if expanded else " | ".join(inlines)
        ]
        for sig_val in not_inlines:
            parts.append(
                _md.tab(title=sig_val["title"], content=sig_val["value"]) if expanded
                else _md.details(title=sig_val["title"], text=sig_val["value"])
            )
        if not expanded and (schema.get("title") or schema.get("description")):
            parts.append("<hr>\n")
        parts_text = "\n".join(parts)
        if not expanded:
            return parts_text
        return f":::::{{tab-set}}\n{parts_text}\n:::::"

    def make_key_signature(self, schema: dict, fullpath: str):
        dynamic_kwargs = {
            "tag_add_props": self.make_tag(f'{fullpath}.*'),
            "tag_prefix_refs": self._tag_prefix_refs,
            "fullpath": fullpath,
            "tag_prefix": self._tag_prefix,
        }
        sig = {}
        for key, setting in KEY_SETTING.items():
            key_kwargs = {
                k: dynamic_kwargs[k] for k in setting.get("dynamic_kwargs", [])
            } | setting.get("kwargs", {})
            value, inline_ok = setting["processor"](schema=schema, key=key, **key_kwargs)
            if value is None:
                continue
            sig[key] = {"title": setting["title"], "value": value, "inline": inline_ok}
        sig["schema"] = {"title": "Schema", "value": _schema.schema_to_md(schema), "inline": False}
        return sig

    def make_tag(self, fullpath: str) -> str:
        return _text.create_slug(f"{self._tag_prefix}-{fullpath}")

    def check_ref(self, key, schema) -> str | None:
        ref = schema.get("$ref")
        if ref:
            self._reference_map.setdefault(ref, []).append(key)
            return ref
        return

    @staticmethod
    def make_address(fullpath: str, key: str) -> str:
        new_fullpath = f"{fullpath}.{key}" if not key.startswith("[") else f"{fullpath}{key}"
        return new_fullpath.removeprefix(".")


def sanitize_title_description(schema: dict):
    schema["title"] = _text.replace_tags_with_slugs(schema.get("title", "").strip().replace("\n", " "))
    schema["description"] = _text.replace_tags_with_slugs(schema.get("description", "").strip())
    if "default_auto" in schema:
        schema["default_auto"] = _text.replace_tags_with_slugs(schema.get("default_auto", "").strip())
    return schema


def add_horiz_line_between_items(items: list[str], indent_size: int = 4) -> str:
    return f'\n\n{" "*indent_size}<hr style="height:5px;margin-bottom:15px;color:#FFF;background-color:#333;">\n\n'.join(items)
