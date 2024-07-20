import unicodedata
import re


def replace_tags_with_slugs(markdown_string):
    def slugify_tag(match):
        tag = match.group(2)
        slug = create_slug(tag)
        return f'[{match.group(1)}](#{slug})'
    # Pattern to find markdown tags of the form [text](#TAG)
    pattern = re.compile(r'\[([^\]]+)\]\(#([^\)]+)\)')
    # Replace all matches with their slugs
    updated_markdown_string = pattern.sub(slugify_tag, markdown_string)
    return updated_markdown_string


