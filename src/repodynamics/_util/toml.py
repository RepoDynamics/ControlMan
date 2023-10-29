import tomlkit
from typing import Literal


def format_object(
    obj: str | list | dict,
    toml_type: Literal[
        "str", "table", "array", "inline_table", "array_of_inline_tables", "table_of_arrays", "table_of_tables"
    ],
):
    match toml_type:
        case "str":
            return obj
        case "table":
            return obj
        case "array":
            return tomlkit.array(obj).multiline(True)
        case "inline_table":
            inline = tomlkit.inline_table()
            inline.update(obj)
            return inline
        case "array_of_inline_tables":
            arr = tomlkit.array().multiline(True)
            for table in obj:
                tab = tomlkit.inline_table()
                tab.update(table)
                arr.append(tab)
            return arr
        case "table_of_arrays":
            return {tab_key: tomlkit.array(arr).multiline(True) for tab_key, arr in obj.items()}
        case "table_of_tables":
            return tomlkit.table(is_super_table=True).update(obj)
        case _:
            raise ValueError(f"Unknown data type {toml_type}.")
