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


def create_slug(string: str) -> str:
    # Normalize the string to decompose special characters
    normalized_string = unicodedata.normalize('NFKD', string)
    # Encode the string to ASCII bytes, ignoring non-ASCII characters
    ascii_bytes = normalized_string.encode('ascii', 'ignore')
    # Decode back to a string
    ascii_string = ascii_bytes.decode('ascii')
    # Convert to lowercase
    lower_case_string = ascii_string.lower()
    # Replace spaces and special characters with hyphens
    slug = re.sub(r'[^a-z0-9]+', '-', lower_case_string)
    # Remove leading and trailing hyphens
    slug = slug.strip('-')
    return slug


def camel_to_title(camel_str):
    # Insert spaces before each uppercase letter (except the first letter)
    spaced_str = re.sub(r'(?<!^)(?=[A-Z])', ' ', camel_str)
    # Convert to title case
    title_str = spaced_str.title()
    return title_str