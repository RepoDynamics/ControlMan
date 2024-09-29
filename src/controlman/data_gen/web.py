from pathlib import Path as _Path

from loggerman import logger as _logger
import pyserials as _ps
import mdit as _mdit
import pylinks as _pl

from controlman import exception as _exception


class WebDataGenerator:

    def __init__(self, data: _ps.NestedDict, source_path: _Path):
        self._data = data
        self._path = source_path
        return

    def generate(self):
        self._process_frontmatter()
        return

    def _process_frontmatter(self) -> None:
        pages = {}
        blog = {}

        for md_filepath in self._path.rglob("*.md", case_sensitive=False):
            if not md_filepath.is_file():
                continue
            rel_path = md_filepath.relative_to(self._path)
            dirhtml_path = str(rel_path.with_suffix("")).removesuffix("/index")
            text = md_filepath.read_text()
            frontmatter = _mdit.parse.frontmatter(text) or {}
            if "ccid" in frontmatter:
                pages[_pl.string.to_slug(frontmatter["ccid"])] = {
                    "title": _mdit.parse.title(text),
                    "path": dirhtml_path,
                    "url": f"{self._data['web.url.home']}/{dirhtml_path}",
                }
            for key in ["category", "tags"]:
                val = frontmatter.get(key)
                if not val:
                    continue
                if isinstance(val, str):
                    val = [item.strip() for item in val.split(",")]
                if not isinstance(val, list):
                    _logger.warning(
                        _mdit.inline_container(
                            "Invalid webpage frontmatter: ",
                            _mdit.element.code_span(str(rel_path)),
                        ),
                        _mdit.inline_container(
                            "Invalid frontmatter value for ",
                            _mdit.element.code_span(key),
                            " :"),
                        _mdit.element.code_block(
                            _ps.write.to_yaml_string(val, end_of_file_newline=False),
                            language="yaml",
                        ),
                    )
                blog.setdefault(key, []).extend(val)
        if "blog" not in pages:
            self._data["web.page"] = pages
            return
        blog_path = self._data["web.extension.ablog.config.blog_path"] or "blog"
        for key, values in blog.items():
            for value in set(values):
                value_slug = _pl.string.to_slug(value)
                key_singular = key.removesuffix('s')
                final_key = f"blog_{key_singular}_{value_slug}"
                if final_key in pages:
                    _logger.error(
                        _mdit.inline_container(
                            "Duplicate webpage ID ",
                            _mdit.element.code_span(final_key)
                        ),
                        f"Generated ID '{final_key}' already exists "
                        f"for page '{pages[final_key]['path']}'. "
                        "Please do not use `ccid` values that start with 'blog_'."
                    )
                blog_group_path = f"{blog_path}/{key_singular}/{value_slug}"
                pages[final_key] = {
                    "title": value,
                    "path": blog_group_path,
                    "url": f"{self._data['web.url.home']}/{blog_group_path}",
                }
        self._data["web.page"] = pages
        return
