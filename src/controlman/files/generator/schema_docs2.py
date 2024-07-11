from typing import Literal as _Literal
from pathlib import Path as _Path
import re

import pyserials as _ps

#TODO: Replace ${‎{ name }}

class SchemaDocGenerator:
    def __init__(self, dir_path: str | _Path):
        self._dir_path = _Path(dir_path).resolve()
        self._output_text = ""
        self._curr_schema_rel_path = ""
        return

    def generate(self, file_type: _Literal["yaml", "yml", "json"] = "yaml"):
        filepaths = list(self._dir_path.glob(f"**/*.{file_type}"))
        out = {}
        for filepath in filepaths:
            self._output_text = ""
            rel_path = filepath.relative_to(self._dir_path)
            schema: dict = _ps.read.from_file(path=filepath)
            if schema["type"] != "object":
                raise ValueError("Only object schemas are supported.")
            self._curr_schema_rel_path = str(rel_path)
            self._generate_sections_recursive(schema=schema, level=1, current_address="")
            out[str(rel_path.with_suffix(""))] = self._output_text
        return out

    def _generate_sections_recursive(self, schema: dict, level: int, current_address: str, required: bool = False, title: str = ""):
        self._add_heading(
            title=title or schema["title"],
            level=level,
            current_address=current_address
        )
        dtype = schema.get("type")
        if not dtype:
            if "$ref" in schema:
                self._output_text += self.generate_section_info(
                    data=schema, current_address=current_address, required=required
                )
                self._output_text += f"{schema['description'].strip()}\n\n"
                return
            raise ValueError(f"Schema type not found: {schema}")
        if dtype == "object":
            if level == 1:
                self._output_text += f"{schema['description'].strip()}\n\n"
                self._output_text += self._generate_tabs(schema=schema)
                root_key = schema.get("root_key")
                if root_key:
                    current_address = root_key
            else:
                self._output_text += self.generate_section_info(
                    data=schema, current_address=current_address, required=required
                )
                self._output_text += f"{schema['description'].strip()}\n\n"

            dependent_keys = self._process_all_of(all_of=schema["allOf"]) if "allOf" in schema else {}
            for key, subschema in schema["properties"].items():
                if key not in dependent_keys:
                    self._generate_sections_recursive(
                        schema=subschema,
                        level=level + 1,
                        current_address=self.make_address(current_address, key),
                        required=key in schema["required"],
                    )
                else:
                    main_address = self.make_address(current_address, key)
                    self._add_heading(title=key["title"], level=level + 1, current_address=main_address)
                    desc = subschema.get("description")
                    if desc:
                        self._output_text += f"{desc.strip()}\n\n"
                    dependency_address = self.make_address(current_address, dependent_keys[key][0])
                    mappings = []
                    for idx, (dependency_value, dependent_schema) in enumerate(dependent_keys[key][1]):
                        variant_address = self.make_address(main_address, f"{idx+1}")
                        mappings.append(f"- `{dependency_value}`: [Case {idx + 1}](#{variant_address}])")

                    self._output_text += f""":::{{admonition}} Conditional Value
:class: attention

The schema for this value depends on the value of `{dependency_address}`.
The possible values of `{dependency_address}` and their corresponding schemas are as follows:
"""
                    for idx, (dependency_value, dependent_schema) in enumerate(dependent_keys[key][1]):
                        self._generate_sections_recursive(
                            schema=subschema | dependent_schema,
                            level=level + 2,
                            current_address=self.make_address(main_address, f"{idx+1}"),
                            required=key in schema["required"],
                            title=f"Case {idx + 1}: `{dependent_keys[key][0]}` = `{dependency_value}`",
                        )

            add_props = schema.get("additionalProperties")
            if isinstance(add_props, dict):
                self._generate_sections_recursive(
                    schema=add_props, level=level + 1, current_address=f"{current_address}.*".removeprefix("."), required=False
                )
            if level == 1 and "definitions" in schema:
                self._add_heading(title="Common Definitions", level=2)
                for key, subschema in schema["definitions"].items():
                    self._generate_sections_recursive(
                        schema=subschema, level=3, current_address=f"#/definitions/{key}", required=False
                    )
        elif dtype == "array":
            self._output_text += self.generate_section_info(
                data=schema, current_address=current_address, required=required
            )
            self._output_text += f"{schema['description'].strip()}\n\n"
            self._generate_sections_recursive(
                schema=schema["items"], level=level + 1, current_address=f"{current_address}[i]", required=True
            )
        else:
            # dtype is primitive
            self._output_text += self.generate_section_info(
                data=schema, current_address=current_address, required=required
            )
            self._output_text += f"{schema['description'].strip()}\n\n"
        return

    @staticmethod
    def make_address(current_address: str, key: str) -> str:
        return f"{current_address}.{key}".removeprefix(".")

    @staticmethod
    def _process_all_of(all_of: list):
        dependent_keys = {}
        for cond in all_of:
            req = cond["if"]["properties"]
            dependency = req.keys()[0]
            condition = req[dependency]["const"]
            conseq = cond["then"]["properties"]
            dependent_key = conseq.keys()[0]
            dependent_schema = conseq[dependent_key]
            pairs = dependent_keys.setdefault(dependent_key, (dependency, []))
            pairs[0].append((condition, dependent_schema))
        return dependent_keys

    @staticmethod
    def generate_section_info(data: dict, current_address: str, required: bool) -> str:

        def make_sublist(lis: list):
            lines = '\n'.join([f"\t- `{elem}`" for elem in lis])
            return f"\n{lines}"

        if current_address[-1] == "]":
            curr_key = "[Array Item]"
        elif current_address[-1] == "*":
            curr_key = "{Custom Key}"
        else:
            curr_key = current_address.split(".")[-1]
        dtype = data.get("type")
        if not dtype:
            if "$ref" in data:
                ref_key = data["$ref"].split("/")[-1]
                dtype = f"[{ref_key}](#{data['$ref']})"
            else:
                raise ValueError(f"Schema type not found: {data}")
        items = [
            ("Key", f"`{curr_key}`"),
            ("Type", f"`{dtype}`"),
            ("Required", f"`{required and 'default' not in data}`"),
        ]
        if "default" in data:
            items.append(("Default", f"`{data['default']}`"))
        enums = data.get("enum")
        if enums:
            items.append(("Allowed Values", make_sublist(enums)))
        if data["type"] == "object":
            if "required" in data:
                items.append(("Required Keys", make_sublist(data['required'])))
            if "additionalProperties" not in data:
                add_prop = "Allowed"
            elif data["additionalProperties"] is True:
                add_prop = "Allowed"
            elif data["additionalProperties"] is False:
                add_prop = "Not Allowed"
            else:
                add_prop = f"Defined"
            items.append(("Additional Properties", add_prop))
        if "oneOf" in data:
            one_ofs = {}
            for cond in data["oneOf"]:
                for key, val in cond.items():
                    final_key = key if key != "required" else "requiredKeys"
                    key_list = one_ofs.setdefault(final_key, [])
                    key_list.append(val)
            for key, val in one_ofs.items():
                items.append((SchemaDocGenerator.camel_to_title(key), f"""{{{' or '.join([f"`{v}`" for v in val])}}}"""))

        for key in ["uniqueItems", "maxItems", "minItems", "maxLength", "minLength", "maximum", "minimum", "pattern"]:
            if key in data:
                items.append((SchemaDocGenerator.camel_to_title(key), f"`{data[key]}`"))
        list_text = "\n".join([f"- {item[0]}: {item[1]}" for item in items])
        text = f"""\n:::{{admonition}} `{current_address}`\n:class: note dropdown\n\n{list_text}\n:::\n\n"""
        return text

    def _add_heading(self, title: str, level: int, current_address: str) -> None:
        self._output_text += f"({current_address})=\n{'#' * level} {title.strip()}\n\n"
        return

    def _generate_tabs(self, schema: dict) -> str:
        tabs = ":::::{tab-set}\n"
        for tab in [
            self._generate_tab_info(schema=schema),
            self._generate_tab_defaults(schema=schema),
            self._generate_tab_schema(schema=schema),
        ]:
            tabs += f"\n{tab.strip()}\n"
        return f"{tabs}\n:::::\n\n"

    def _generate_tab_info(self, schema: dict) -> str:
        root_key = schema.get("root_key")
        root_key_val = f"`{root_key}`" if root_key else "This file has no root key; all properties are at the root level."
        required = bool(schema.get("required"))
        content = f"""- Filepath: `{self._curr_schema_rel_path}`
- Root Key: {root_key_val}
- Required: `{required}`"""
        return self._generate_tab(title="Info", content=content)

    def _generate_tab_defaults(self, schema: dict) -> str:
        text = _ps.write.to_yaml_string(data=schema["examples"][0])
        content = self._generate_code_block(text)
        return self._generate_tab(title="Default", content=content)

    def _generate_tab_schema(self, schema: dict) -> str:
        schema_text = _ps.write.to_yaml_string(data=self._clean_schema(schema=schema))
        content = self._generate_code_block(schema_text)
        return self._generate_tab(title="Schema", content=content)

    @staticmethod
    def _clean_schema(schema: dict | list, is_prop_dict: bool = False) -> dict:
        if isinstance(schema, dict):
            clean = {}
            for key, val in schema.items():
                if key in ["description", "examples", "root_key"] and not is_prop_dict:
                    continue
                if isinstance(val, (dict, list)):
                    clean[key] = SchemaDocGenerator._clean_schema(
                        schema=val, is_prop_dict=isinstance(val, dict) and key == "properties"
                    )
                else:
                    clean[key] = val
        elif isinstance(schema, list):
            clean = []
            for item in schema:
                if isinstance(item, (dict, list)):
                    clean.append(SchemaDocGenerator._clean_schema(schema=item))
                else:
                    clean.append(item)
        else:
            raise ValueError(f"Unsupported schema type: {type(schema)}")
        return clean

    @staticmethod
    def _generate_code_block(text: str):
        return f"\n:::{{code-block}} yaml\n{text.strip()}\n:::\n"

    @staticmethod
    def _generate_tab(title: str, content: str, num_colons: int = 4) -> str:
        colons = ":" * num_colons
        return f"{colons}{{tab-item}} {title.strip()}\n\n{content.strip()}\n{colons}"

    @staticmethod
    def camel_to_title(camel_str):
        # Insert spaces before each uppercase letter (except the first letter)
        spaced_str = re.sub(r'(?<!^)(?=[A-Z])', ' ', camel_str)
        # Convert to title case
        title_str = spaced_str.title()
        return title_str
