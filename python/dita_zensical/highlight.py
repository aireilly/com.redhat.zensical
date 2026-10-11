"""Syntax-highlight DITA codeblocks exactly as Zensical highlights fenced code.

Blocks are rendered as superfences through Python-Markdown with the project's
pymdownx.highlight settings, so the output carries the same classes, line
anchors and token spans the theme styles, in light and dark mode.
"""

from __future__ import annotations

import copy
import pathlib
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

import markdown
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

try:
    import tomllib
except ImportError:  # Python < 3.11
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None

# What Zensical applies when a project does not configure pymdownx.highlight
ZENSICAL_DEFAULTS = {"anchor_linenums": True, "line_spans": "__span", "pygments_lang_class": True}

# DITA-flavoured language names Pygments does not know
ALIASES = {"dita": "xml", "ditamap": "xml", "ditaval": "xml",
           "none": "text", "plain": "text", "plaintext": "text", "txt": "text"}

# Content that cannot survive as plain text, so the block keeps its HTML
LINK_ELEMENTS = frozenset({"a", "img", "svg", "object", "video", "audio"})

_BACKTICKS = re.compile(r"`{3,}")
_SPLIT = re.compile(r"<!--dita-code-(\d+)-->")


@dataclass
class CodeBlock:
    source: str
    language: str
    id: str = ""
    classes: list[str] = field(default_factory=list)
    line_numbers: bool = False


def settings_from_config(config_path) -> dict:
    """pymdownx.highlight options from a zensical.toml, or Zensical's defaults."""
    path = pathlib.Path(config_path)
    if tomllib is None or not path.is_file():
        return dict(ZENSICAL_DEFAULTS)
    with path.open("rb") as fh:
        extensions = tomllib.load(fh).get("project", {}).get("markdown_extensions")
    if extensions is None:
        return dict(ZENSICAL_DEFAULTS)
    configured = extensions.get("pymdownx", {}).get("highlight", extensions.get("pymdownx.highlight"))
    return dict(ZENSICAL_DEFAULTS) if configured is None else dict(configured)


def is_codeblock(el) -> bool:
    return el.tag == "pre" and ("codeblock" in el.get("class", "").split() or "data-language" in el.attrib)


def declared_language(pre) -> str | None:
    return pre.get("data-language") or None


def as_code_block(pre, default_language="text") -> CodeBlock | None:
    """A highlightable CodeBlock, or None when the block must keep its markup.

    Links and images always keep their markup. Formatting markup such as <b> or
    <varname> gives way to token colours when a language is declared, and is
    kept when none is.
    """
    descendants = [el for el in pre.iter() if el is not pre and not (el.tag == "code" and el in list(pre))]
    if any(el.tag in LINK_ELEMENTS for el in descendants):
        return None
    language = declared_language(pre)
    if descendants and language is None:
        return None
    return CodeBlock(
        source="".join(pre.itertext()),
        language=language or default_language,
        id=pre.get("id", ""),
        classes=[c for c in pre.get("class", "").split() if not c.startswith("language-")],
        line_numbers=pre.get("data-line-numbers") == "true",
    )


def code_box(pre, default_language="text") -> ET.Element:
    """Wrap a codeblock that keeps its markup in the theme's code box, uncoloured."""
    language = ALIASES.get(declared_language(pre) or default_language, declared_language(pre) or default_language)
    keep = [c for c in pre.get("class", "").split() if not c.startswith("language-")]
    box = ET.Element("div", {"class": " ".join(["language-" + language, "highlight"] + keep)})
    if pre.get("id"):
        box.set("id", pre.get("id"))
    new_pre = ET.SubElement(box, "pre")
    ET.SubElement(new_pre, "span")
    code = ET.SubElement(new_pre, "code")
    inner = next((c for c in pre if c.tag == "code"), pre)
    code.text = inner.text
    for child in list(inner):
        code.append(copy.deepcopy(child))
    box.tail = pre.tail
    return box


class Highlighter:
    def __init__(self, settings: dict, warn=print):
        self._md = markdown.Markdown(
            extensions=["pymdownx.highlight", "pymdownx.superfences"],
            extension_configs={"pymdownx.highlight": settings},
        )
        self._warn = warn

    def language(self, name: str, where: str) -> str:
        name = ALIASES.get(name, name)
        try:
            get_lexer_by_name(name)
            return name
        except ClassNotFound:
            self._warn('{}: unknown code language "{}", highlighted as plain text'.format(where, name))
            return "text"

    def render(self, blocks: list[CodeBlock], where: str = "") -> list[str]:
        """HTML for each block. Render one page's blocks in one call, so line
        anchor ids are numbered per page the way Zensical numbers them."""
        if not blocks:
            return []
        parts = ["<!--dita-code-{}-->\n\n{}".format(i, self._fence(b, where)) for i, b in enumerate(blocks)]
        self._md.reset()
        pieces = _SPLIT.split(self._md.convert("\n\n".join(parts) + "\n"))
        rendered = {int(pieces[i]): pieces[i + 1].strip() for i in range(1, len(pieces), 2)}
        if len(rendered) != len(blocks):
            raise RuntimeError("{}: could not render code blocks".format(where))
        return [rendered[i] for i in range(len(blocks))]

    def _fence(self, block: CodeBlock, where: str) -> str:
        longest = max((len(run) for run in _BACKTICKS.findall(block.source)), default=0)
        ticks = "`" * max(3, longest + 1)
        options = ["." + self.language(block.language, where)]
        if block.id:
            options.append("#" + block.id)
        options += ["." + c for c in block.classes]
        if block.line_numbers:
            options.append('linenums="1"')
        return "{}{{ {} }}\n{}\n{}".format(ticks, " ".join(options), block.source.strip("\r\n"), ticks)
