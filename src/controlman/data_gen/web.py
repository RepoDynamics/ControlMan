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
        self._process_website_toctrees()
        return

    @_logger.sectioner("Website Sections")
    def _process_website_toctrees(self) -> None:
        pages = {}
        blog_pages = {}
        for md_filepath in self._path.rglob("*.md", case_sensitive=False):
            if not md_filepath.is_file():
                continue
            rel_path = str(md_filepath.relative_to(self._path).with_suffix(""))
            text = md_filepath.read_text()
            frontmatter = _mdit.parse.frontmatter(text)
            if "ccid" in frontmatter:
                pages[_pl.string.to_slug(frontmatter["ccid"])] = {
                    "title": _mdit.parse.title(text),
                    "path": rel_path,
                    "url": f"{self._data['web.url.home']}/{rel_path}",
                }
            for key in ["category", "tags"]:
                key_val = frontmatter.get(key)
                if not key_val:
                    continue
                if isinstance(key_val, str):
                    key_val = [item.strip() for item in key_val.split(",")]
                blog_pages.setdefault(rel_path, {}).setdefault(key, []).extend(key_val)
        if "blog" not in pages:
            self._data["web.page"] = pages
            return
        blog_path = _Path(pages["blog"]["path"]).parent
        blog_path_str = str(blog_path)
        blog_pages_final = {}
        for potential_post_page_path, keywords_and_tags in blog_pages.items():
            try:
                _Path(potential_post_page_path).relative_to(blog_path)
            except ValueError:
                continue
            for key in ["category", "tags"]:
                for value in keywords_and_tags.get(key, []):
                    value_slug = _pl.string.to_slug(value)
                    key_singular = key.removesuffix('s')
                    final_key = f"blog_{key_singular}_{value_slug}"
                    if final_key in pages:
                        raise _exception.data_gen.ControlManWebsiteError(
                            "Duplicate page ID. "
                            f"Generated ID '{final_key}' already exists "
                            f"for page '{pages[final_key]['path']}'. "
                            "Please do not use `ccid` values that start with 'blog_'."
                        )
                    blog_path_prefix = f"{blog_path_str}/" if blog_path_str != "." else ""
                    blog_group_path = f"{blog_path_prefix}{key_singular}/{value_slug}"
                    blog_pages_final[final_key] = {
                        "title": value,
                        "path": blog_group_path,
                        "url": f"{self._data['web.url.home']}/{blog_group_path}",
                    }
        self._data["web.page"] = pages | blog_pages_final
        return
