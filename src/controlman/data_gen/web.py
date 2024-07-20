from pathlib import Path as _Path
import re as _re

from loggerman import logger as _logger
import pyserials as _ps
import markitup as _miu

from controlman import exception as _exception
from controlman.nested_dict import NestedDict as _NestedDict


class WebDataGenerator:

    def __init__(self, data: _NestedDict, website_dir_path: _Path):
        self._data = data
        self._path = website_dir_path
        return

    def generate(self):
        self._process_website_toctrees()
        return

    @_logger.sectioner("Website Sections")
    def _process_website_toctrees(self) -> None:
        pages = {}
        blog_pages = {}
        path_docs = self._path / "source"
        for md_filepath in path_docs.rglob("*.md", case_sensitive=False):
            if not md_filepath.is_file():
                continue
            rel_path = str(md_filepath.relative_to(path_docs).with_suffix(""))
            text = md_filepath.read_text()
            frontmatter = self._extract_frontmatter(text)
            if "ccid" in frontmatter:
                pages[frontmatter["ccid"]] = {
                    "title": self._extract_main_heading(text),
                    "path": rel_path,
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
        for potential_post_page_path, keywords_and_tags in blog_pages.items():
            try:
                _Path(potential_post_page_path).relative_to(blog_path)
            except ValueError:
                continue
            for key in ["category", "tags"]:
                for value in keywords_and_tags.get(key, []):
                    value_slug = _miu.txt.slug(value)
                    key_singular = key.removesuffix('s')
                    final_key = f"blog_{key_singular}_{value_slug}"
                    if final_key in pages:
                        raise _exception.ControlManWebsiteError(
                            "Duplicate page ID. "
                            f"Generated ID '{final_key}' already exists for page '{pages[final_key]['path']}'. "
                            "Please do not use `ccid` values that start with 'blog_'."
                        )
                    blog_path_prefix = f"{blog_path_str}/" if blog_path_str != "." else ""
                    pages[final_key] = {"title": value, "path": f"{blog_path_prefix}{key_singular}/{value_slug}"}
        self._data["web.page"] = pages
        return

    @staticmethod
    def _extract_frontmatter(file_content: str) -> dict:
        match = _re.match(r'^---+\s*\n(.*?)(?=\n---+\s*\n)', file_content, _re.DOTALL)
        if not match:
            return {}
        frontmatter_text = match.group(1).strip()
        frontmatter = _ps.read.yaml_from_string(frontmatter_text)
        return frontmatter

    @staticmethod
    def _extract_main_heading(file_content: str) -> str | None:
        match = _re.search(r"^# (.*)", file_content, _re.MULTILINE)
        return match.group(1) if match else None

    @staticmethod
    def _extract_toctree(file_content: str) -> tuple[str, ...] | None:
        matches = _re.findall(r"(:{3,}){toctree}\s((.|\s)*?)\s\1", file_content, _re.DOTALL)
        if not matches:
            return
        toctree_str = matches[0][1]
        toctree_entries = []
        for line in toctree_str.splitlines():
            entry = line.strip()
            if entry and not entry.startswith(":"):
                toctree_entries.append(entry)
        return tuple(toctree_entries)