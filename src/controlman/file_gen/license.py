import re as _re
from xml.etree import ElementTree as ET
from textwrap import TextWrapper as _TextWrapper
import pylinks as pl
from pylinks.exception.api import WebAPIError as _WebAPIError


class SPDXLicense:

    def __init__(
        self,
        license_id: str,
    ):
        self._id = license_id
        self._data: ET.Element = None
        self._ns = {'spdx': 'http://www.spdx.org/license'}
        return

    def run(self):
        self._data = self.get_license()

    @property
    def xml_url(self) -> str:
        return f'https://raw.githubusercontent.com/spdx/license-list-data/refs/heads/main/license-list-XML/{self._id}.xml'

    def get_license(self) -> ET.Element:
        """
        Takes an SPDX license ID, downloads the license XML, and returns a parsed data structure.

        Parameters:
            license_id (str): The SPDX license ID (e.g., 'MIT', 'GPL-2.0-or-later').

        Returns:
            ElementTree.Element: The license element of the parsed XML tree.
        """
        # Construct the URL for the raw XML file in the GitHub repository
        try:
            data = pl.http.request(self.xml_url, response_type="str")
        except _WebAPIError as e:
            raise Exception(f"Error downloading license XML for ID '{self._id}") from e
        try:
            root = ET.fromstring(data)
        except ET.ParseError as e:
            raise Exception(f"Error parsing XML content for ID '{self._id}'") from e
        self._data = root.find('spdx:license', self._ns)
        return self._data

    def fullname(self):
        return self._data.attrib.get('name')

    def osi_approved(self) -> bool | None:
        val = self._data.attrib.get('isOsiApproved')
        return val == 'true' if val else None

    def cross_refs(self) -> list[str]:
        cross_refs = self._data.find('spdx:crossRefs', self._ns)
        if not cross_refs:
            return []
        return [ref.text for ref in cross_refs.findall('spdx:crossRef', self._ns)]

    def notes(self) -> str:
        return self._data.find('spdx:notes', self._ns).text

    def text(self) -> ET.Element:
        return self._data.find('spdx:text', self._ns)

    def header(self) -> ET.Element:
        return self._data.find('.//spdx:standardLicenseHeader', self._ns)



class SPDXLicenseTextParser:
    """
    Parses the <text> element from an SPDX license XML and generates a plain-text version of the license.

    Parameters
    ----------
    text_element : xml.etree.ElementTree.Element
        The <text> XML element to parse.
    """

    def __init__(self, text_element: ET.Element):
        self._text = text_element

        self._ns_uri = 'http://www.spdx.org/license'
        self._ns = {'': self._ns_uri}
        self._element_processor = {
            "text": self.process_generic,
            "titleText": self.process_title_text,
            "copyrightText": self.process_copyright_text,
            "standardLicenseHeader": self.process_generic,
            "list": self.process_list,
            "p": self.process_p,
            "br": lambda x: "\n\n",
            "item": self.process_list_item,
            "optional": self.process_optional,
            "alt": self.process_alt,
        }

        self._title: str | bool = True
        self._copyright: str | bool = False
        self._include_optional: bool = True
        self._alt: dict = {}
        self._line_len: int = 88
        self._list_item_indent: int = 1
        self._list_item_vertical_spacing: int = 1
        self._current_list_nesting: int = 0
        self._list_indent: int = 4
        self._list_bullet_prefer_default: bool = True
        self._list_bullet_ordered: bool = True
        self._list_bullet_unordered_char: str = "–"
        self._text_wrapper: _TextWrapper | None = None
        self._curr_bullet_len: int = 0
        return

    def parse(
        self,
        title: str | bool = True,
        copyright: str | bool = False,
        include_optional: bool = True,
        alt: dict[str, str] | None = None,
        line_length: int = 88,
        list_item_indent: int = 2,
        list_item_vertical_spacing: int = 1,
        list_indent: int = 4,
        list_bullet_prefer_default: bool = True,
        list_bullet_ordered: bool = True,
        list_bullet_unordered_char: str = "–",
    ) -> tuple[str, str | None]:
        """Parses the <text> element and generates the plain-text license.

        Parameters
        ----------
        title
            Determines how to treat the license title, if any.
            Since the title is [optional](https://spdx.github.io/spdx-spec/v3.0.1/annexes/license-matching-guidelines-and-templates/#license-name-or-title)
            and not used in matching, it can be omitted or replaced with a custom title.
            If True, the title is included as-is. If False, the title is omitted.
            If a string, the title is replaced with the custom string, if a title is present.
        copyright
            Determines how to treat the copyright notice, if any.
            Since the copyright notice is [optional](https://spdx.github.io/spdx-spec/v3.0.1/annexes/license-matching-guidelines-and-templates/#copyright-notice)
            and not used in matching, it can be omitted or replaced with a custom notice.
            If True, the notice is included as-is. If False, the notice is omitted.
            If a string, the notice is replaced with the custom string, if a notice is present.
        include_optional : bool, optional
            Whether to include <optional> elements in the output, by default True.
        alt : dict[str, int] | None, optional
            A dictionary specifying choices for <alt> elements. Keys are 'name' attributes,
            and values are the value to use.
        line_length
            The maximum line length for the plain-text output.
        list_item_indent
            The number of spaces separating list items from the bullet character.
        Returns
        -------
        The plain-text version of the license,
        and the license header text, if present.
        """
        self._title = title
        self._copyright = copyright
        self._include_optional = include_optional
        self._alt = alt or {}
        self._line_len = line_length
        self._text_wrapper = _TextWrapper(
            width=line_length,
            replace_whitespace=True,
            drop_whitespace=True,
            break_long_words=False,
            break_on_hyphens=False,
        )
        self._current_list_nesting = 0
        self._curr_bullet_len = 0
        self._list_indent = list_indent
        self._list_item_indent = list_item_indent
        self._list_item_vertical_spacing = list_item_vertical_spacing
        self._list_bullet_prefer_default = list_bullet_prefer_default
        self._list_bullet_ordered = list_bullet_ordered
        self._list_bullet_unordered_char = list_bullet_unordered_char
        fulltext = self.process_element(self._text).strip("\n").rstrip() + "\n"
        header = self._text.find('.//standardLicenseHeader', self._ns)
        notice = (self.process_element(header).strip("\n").rstrip() + "\n") if header else None
        return fulltext, notice

    def get_processor(self, tag: str) -> callable:
        if tag not in self._element_processor:
            raise ValueError(f"Unsupported element: {tag}")
        return self._element_processor[tag]

    def process_element(
        self,
        element: ET.Element,
    ) -> str:
        processor = self.get_processor(self.clean_tag(element.tag))
        return processor(element)

    def process_text(self, text: str) -> str:
        text_norm = _re.sub(r'\s+', ' ', text)
        if text_norm == " ":
            return ""
        return self.wrap_text(text_norm)

    def process_generic(
        self,
        element: ET.Element,
        return_list: bool = False,
    ) -> str:
        """Recursively processes an XML element and its children.

        Parameters
        ----------
        element : xml.etree.ElementTree.Element
            The XML element to process.
        """
        out = []
        if element.text:
            out.append(self.process_text(element.text))
        for child in element:
            tag_name = self.clean_tag(child.tag)
            if tag_name not in self._element_processor:
                raise ValueError(f"Unsupported element: {tag_name}")
            content = self._element_processor[tag_name](child)
            if content:
                out.append(content)
            if child.tail:
                out.append(self.process_text(child.tail))
        if element.tail:
            out.append(self.process_text(element.tail))
        if return_list:
            return out
        # full_raw = "".join([line.rstrip(" ") if line.strip() else "\n" for elem in out for line in elem.splitlines()])
        # paragraphs = [paragraph.strip() for paragraph in _re.split(r'\n\s*\n+', full_raw)]
        # processed = [self.wrap_text(paragraph) for paragraph in paragraphs]
        # return "\n\n".join(processed)
        return _re.sub(r'\n\s*\n\s*\n+', "\n\n", "".join(out))

    def process_title_text(self, element: ET.Element) -> str:
        """Process a <titleText> element."""
        if self._title is False:
            return ""
        title = self.process_generic(element) if self._title is True else self._title
        title_lines_centered = [line.strip().center(self._line_len) for line in title.splitlines() if line.strip()]
        title_centered = "\n".join(title_lines_centered)
        return f"{title_centered}\n{'=' * self._line_len}\n\n"

    def process_copyright_text(self, element: ET.Element) -> str:
        """Process a <copyrightText> element."""
        if self._copyright is False:
            return ""
        copyright_text = self.process_generic(element) if self._copyright is True else self._copyright
        return f"\n\n{copyright_text.strip()}\n\n"

    def process_p(self, element: ET.Element) -> str:
        """
        Processes a <p> element and appends its text to the output.

        Parameters
        ----------
        element : xml.etree.ElementTree.Element
            The <p> element.
        """
        out = [[]]
        if element.text:
            out[-1].append(element.text)
        for child in element:
            tag_name = self.clean_tag(child.tag)
            if tag_name not in self._element_processor:
                raise ValueError(f"Unsupported element: {tag_name}")
            if tag_name == "br":
                out.append([])
            else:
                content = self._element_processor[tag_name](child)
                if content:
                    out[-1].append(content)
            if child.tail:
                out[-1].append(child.tail)
        if element.tail:
            out[-1].append(element.tail)

        paragraphs = []
        for paragraph_components in out:
            paragraph_raw = " ".join(paragraph_components)
            paragraph_normalized = _re.sub(r'\s+', ' ', paragraph_raw).strip()
            paragraphs.append(self.wrap_text(paragraph_normalized))
        return f"\n\n{"\n\n".join(paragraphs)}\n\n"

    def process_list(self, elem: ET.Element) -> str:
        """
        Processes a <list> element containing <item> elements.

        Parameters
        ----------
        elem : xml.etree.ElementTree.Element
            The <list> element.
        """
        self._current_list_nesting += 1

        if elem.text and elem.text.strip():
            raise ValueError("List element should not have text content")
        items = []
        for idx, child in enumerate(elem):
            tag = self.clean_tag(child.tag)
            if tag != 'item':
                raise ValueError(f"List element should only contain item elements, not {tag}")
            item_str = self.process_list_item(child, idx)
            item_str_indented = "\n".join([f"{' ' * self._list_indent}{line}" for line in item_str.splitlines()])
            items.append(item_str_indented)
        self._current_list_nesting -= 1
        newlines = max(1, self._list_item_vertical_spacing) * "\n"
        list_str = newlines.join(items)
        return f"{newlines}{list_str}{newlines}"

    def process_list_item(self, elem: ET.Element, idx: int) -> str:
        bullet_elems = elem.findall('bullet', self._ns)
        if len(bullet_elems) > 1:
            raise ValueError("Item element should contain at most one bullet element")
        if len(bullet_elems) == 1:
            bullet = bullet_elems[0].text.strip() if self._list_bullet_prefer_default else (
                f"{idx + 1}." if self._list_bullet_ordered else self._list_bullet_unordered_char
            )
            bullet += self._list_item_indent * " "
            subsequent_indent = len(bullet) * " "
        else:
            bullet = ""
            subsequent_indent = ""
        self._curr_bullet_len += len(bullet)
        content = []
        if elem.text:
            text = self.process_text(elem.text).lstrip()
            if text:
                content.append(text)
        for child in elem:
            tag = self.clean_tag(child.tag)
            if tag == 'bullet':
                bullet_elems.append(child)
            else:
                child_str = self.process_element(child)
                if child_str:
                    content.append(child_str.lstrip(" "))
            if child.tail:
                tail = self.process_text(child.tail)
                if tail:
                    needs_dedent = not content or content[-1].endswith("\n")
                    content.append(tail.lstrip() if needs_dedent else tail)
        if not content:
            raise ValueError("Item element should contain text content")
        content_raw = "".join(content).strip()
        # paragraphs = [paragraph for paragraph in _re.split(r'\n\s*\n+', content_raw)]

        lines = content_raw.splitlines()
        wrapped = "\n".join(
            [f"{bullet}{lines[0]}"] + [f"{subsequent_indent}{line}" for line in lines[1:]]
        )
        self._curr_bullet_len -= len(bullet)
        return wrapped

    def process_optional(self, element: ET.Element) -> str:
        """
        Processes an <optional> element based on the include_optional flag.

        Parameters
        ----------
        element : xml.etree.ElementTree.Element
            The <optional> element.
        """
        if not self._include_optional:
            return ""
        return self.process_generic(element)

    def process_alt(self, element: ET.Element) -> str:
        """Process an <alt> element by selecting the appropriate alternative based on `self._alt`.

        Parameters
        ----------
        element : xml.etree.ElementTree.Element
            The <alt> element.
        """
        name = element.get('name')
        if not name:
            raise ValueError("Alt element must have a 'name' attribute")
        text = self._alt.get(name)
        if not text:
            return element.text
        match = element.get('match')
        if not match:
            raise ValueError("Alt element must have a 'match' attribute")
        if not _re.match(match, text):
            raise ValueError(f"Alt element '{name}' does not match '{match}'")
        return text

    def wrap_text(self, text: str) -> str:
        """Wrap text to the specified line length, preserving indentation.

        Parameters
        ----------
        text : str
            The text to wrap.
        current_indent : int
            The current indentation level.
        """
        if self._current_list_nesting:
            extra_width = (self._current_list_nesting * self._list_indent) + self._curr_bullet_len
        else:
            extra_width = 0
        self._text_wrapper.width = self._line_len - extra_width
        wrapped = self._text_wrapper.fill(text)
        return wrapped

    def clean_tag(self, tag: str) -> str:
        """Strip the namespace URI from XML tag.

        Parameters
        ----------
        tag
            The XML tag with possible namespace.

        Returns
        -------
        The tag without namespace.
        """
        return tag.removeprefix(f'{{{self._ns_uri}}}')
