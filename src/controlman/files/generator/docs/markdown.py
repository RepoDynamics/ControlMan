
def admonition(title, body, classes: list[str] = None, nested: int = 0):
    num_colons = 3 + nested
    def_line = f"{':' * num_colons}{{admonition}} {title}"
    class_line = f":class: {' '.join(classes)}\n" if classes else ""
    header = f"{def_line}\n{class_line}"
    return f"{header}\n\n{body}\n{':' * num_colons}"


def code_block(text: str, syntax: str = "yaml"):
    return f":::{{code-block}} {syntax}\n{text.strip()}\n:::"


def tab(title: str, content: str, num_colons: int = 4) -> str:
    colons = ":" * num_colons
    return f"{colons}{{tab-item}} {title.strip()}\n\n{content.strip()}\n{colons}"


def heading(title: str, level: int = 1) -> str:
    return f"{'#' * level} {title}\n"


def tag(text: str, ref: str) -> str:
    return f"({ref})=\n{text}"


def field_list(name: str, body: str = "", indent_size: int = 4) -> str:
    first_line, *lines = body.strip().split("\n")
    body = "\n".join([first_line] + [f"{' '*indent_size}{line}" for line in lines])
    return f":{name}: {body}".strip()


def comma_list(items: list[str], item_as_code: bool = False, as_html: bool = False) -> str:
    if item_as_code:
        items = [inline_code(item, as_html=as_html) for item in items]
    return ", ".join(items)


def normal_list(items: list[str], item_as_code: bool = False, indent_level: int = 0, indent_size: int = 4) -> str:
    new_items = []
    for item in items:
        if item_as_code:
            item = inline_code(item)
        new_items.append(indent_level * indent_size * " " + f"- {item}")
    return "\n".join(new_items)


def inline_code(text: str, as_html: bool = False) -> str:
    if as_html:
        return f"<code>{text}</code>"
    return f"`{text}`"


def details(title: str, text: str):
    return f"\n<details><summary>{title}</summary>\n\n{text}\n\n</details>\n"


def card(
    body: str,
    title: str = "",
    header: str | None = None,
    footer: str | None = None,
    nested: int = 0,
    options: dict = None,
):
    num_colons = 3 + nested
    lines = [f"{':' * num_colons}{{card}} {title}"]
    if options:
        lines.extend([f":{key}: {value}" for key, value in options.items()])
    lines.append("\n")
    if header:
        lines.extend([header, "^^^"])
    lines.append(body)
    if footer:
        lines.extend(["+++", footer])
    lines.append(f"{':' * num_colons}")
    return "\n".join(lines)
