from typing import Literal as _Literal
from pathlib import Path as _Path
import pyserials as _ps



class SchemaDocGenerator:
    def __init__(self, dir_path: str | _Path):
        self._dir_path = _Path(dir_path).resolve()
        self._curr_rel_path = None
        self._curr_schema = None
        self._curr_schema_text = None
        self._curr_schema_root_path = None
        self._sections_text = None
        self._curr_schema_tabs = None
        return

    def generate(self, file_type: _Literal["yaml", "yml", "json"] = "yaml"):
        filepaths = list(self._dir_path.glob(f"**/*.{file_type}"))
        out = {}
        for filepath in filepaths:
            self._curr_rel_path = filepath.relative_to(self._dir_path)
            self._curr_schema_text = filepath.read_text()
            self._curr_schema: dict = _ps.read.from_string(
                data=self._curr_schema_text, data_type=file_type
            )
            self._curr_schema_root_path = self._curr_schema.get("root_path", "")
            self._sections_text = ""
            self._curr_schema_tabs = {}
            self._generate_doc_for_schema()
            out[str(self._curr_rel_path.with_suffix(""))] = self._sections_text
        return out

    def _generate_doc_for_schema(self):
        data = self._curr_schema
        if data["type"] != "object":
            raise ValueError("Only object schemas are supported.")
        defaults = {}
        required = {}
        self._generate_sections_recursive(
            data=data, defaults=defaults, required=required, current_address=[]
        )

    def _generate_sections_recursive(self, data: dict, defaults: dict, required: dict, current_address: list[str]):
        level = len(current_address) + 1
        if data["type"] == "object":
            self._add_heading(title=data["title"], level=level)
            self._sections_text += f"{data['description'].strip()}\n\n"
            curr_add = "tab" + "".join([f"[{e}]" for e in current_address])
            tabs = {
                "info": {},
                "schema": data,
                "defaults": {},
                "required": {}
            }
            self._curr_schema_tabs[curr_add] = tabs
            self._sections_text += f"{{{curr_add}}}\n\n"
            primitive_types = {}
            complex_types = {}
            for key, value in data["properties"].items():
                if value["type"] in ["object", "array"]:
                    complex_types[key] = value
                else:
                    primitive_types[key] = value
                    defaults[key] = ("default" in value, value.get("default"), None)
                    required[key] = (key in data["required"] and "default" not in value, None)
            if primitive_types:
                self._add_heading(title="Primitive Properties", level=level + 1)
                for key, value in primitive_types.items():
                    self._sections_text += self._generate_entry_primitive(
                        path=current_address + [key], required=key in data["required"], data=value
                    )
            if complex_types:
                for key, value in complex_types.items():
                    self._generate_sections_recursive(
                        data=value, defaults=defaults, required=required, current_address=current_address + [key]
                    )
        return

    def _gen(self, data: dict, current_address: list[str], required: bool):
        dtype = data["type"]
        if dtype not in ["object", "array"]:
            text = self._generate_entry_primitive(path=current_address, required=required, data=data)
            is_required = required and "default" not in data
            default = ("default" in data, data.get("default"))
            return text, is_required, default
        if d



    def _add_heading(self, title: str, level: int) -> None:
        self._sections_text += f"{'#' * level} {title.strip()}\n\n"
        return

    def _generate_entry_primitive(self, path: list[str], required: bool, data: dict):
        root_path = f'{self._curr_schema_root_path}.' if self._curr_schema_root_path else ""
        info = f"""{data['description'].strip()}
- Path: `{root_path}{'.'.join(path)}`
- Type: `{data['type']}`
"""
        enums = data.get("enum")
        if enums:
            info += f"""- Allowed Values: {{{', '.join([f"'{enum}'" for enum in enums])}}}\n"""
        info += f"- Required: {'`True`' if required and 'default' not in data else '`False`'}\n"
        if "default" in data:
            info += f"- Default: `{data['default']}`\n"
        for key in ["minimum"]:
            if key in data:
                info += f"- {key.capitalize()}: `{data[key]}`\n"
        title = data["title"].strip()
        info_formatted = "\n".join([f"\t{line}" if line else line for line in info.split("\n")])
        return f"""\n:`{path[-1]}`: **{title}**\n\n{info_formatted}\n"""

    def _generate_tabs(self) -> str:
        tabs = ":::::{{tab-set}}\n"
        for tab in [
            self._generate_tab_info(),
            self._generate_tab_defaults(),
            self._generate_tab_examples(),
            self._generate_tab_schema(),
        ]:
            if tab:
                tabs = f"{tabs}\n{tab.strip}\n"
        return f"{tabs}\n:::::"

    def _generate_tab_info(self) -> str:
        content = ""
        return self._generate_tab(title="Info", content=content)

    def _generate_tab_defaults(self) -> str:
        content = ""
        return self._generate_tab(title="Defaults", content=content)

    def _generate_tab_examples(self) -> str:
        content = ""
        return self._generate_tab(title="Examples", content=content)

    def _generate_tab_schema(self) -> str:
        content = f":::{{code-block}} yaml\n{self._curr_schema_text.strip()}\n:::"
        return self._generate_tab(title="Schema", content=content)

    @staticmethod
    def _generate_tab(title: str, content: str, num_colons: int = 4) -> str:
        colons = ":" * num_colons
        return f"{colons}{{tab-item}} {title.strip()}\n\n{content.strip()}\n{colons}"






def generate_doc_for_schema(schema: dict):
    doc = f"""
# {schema["title"]}

{schema["description"]}



    """

    """
    All configurations in this file have default values.
Therefore, if you do not need to change any of the default values,
you can also delete this file entirely.
    """



