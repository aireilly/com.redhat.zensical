"""Carry interchange pages into Zensical as Markdown files.

Zensical currently themes only Markdown pages, so each page becomes a .md file:
YAML front matter, headings as Markdown (for the "On this page" sidebar,
permalinks and search sections) and everything else as raw HTML.

The page is deliberately flat. Python-Markdown passes top-level raw HTML through
byte for byte, but md_in_html containers re-parse nested HTML and mis-nest common
DITA output such as <li><span/> <div/></li> in task steps. So wrappers holding
headings are unwrapped, each raw block is one line, and newlines inside <pre>
are written as &#10;.

This module is the part a future Zensical module replaces.
"""

from __future__ import annotations

import copy
import html
import json
import posixpath
import re
import xml.etree.ElementTree as ET

from . import highlight, theme

CONTAINERS = frozenset({"article", "section", "div", "main", "aside", "header", "footer", "nav"})
PREFORMATTED = frozenset({"pre", "textarea", "listing", "xmp"})
PLACEHOLDER_TAG = "dita-code"
_NEWLINE = ""
_HEADING = re.compile(r"^h[1-6]$")
_MD_SPECIAL = re.compile(r"([\\`*_{}\[\]#])")
_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:")


class Options:
    def __init__(self, admonitions=True, theme_tables=True, highlight=True, default_language="text",
                 source_links=None):
        self.admonitions = admonitions
        self.theme_tables = theme_tables
        self.highlight = highlight
        self.default_language = default_language
        self.source_links = source_links  # a source_links.SourceLinks, or None


def markdown_path(page_path: str) -> str:
    return posixpath.splitext(page_path)[0] + ".md"


# ============ Page ============

def page_markdown(page, site, options: Options, highlighter: highlight.Highlighter | None) -> str:
    root = theme.adapt(page.element(), admonitions=options.admonitions, tables=options.theme_tables)
    _rewrite_links(root, page.path, site.pages)
    code_html = _prepare_code(root, page.path, options, highlighter)

    body = []
    _emit(root, None, body)
    text = "".join(body)
    for number, rendered in enumerate(code_html):
        text = text.replace("<{0} n=\"{1}\"></{0}>".format(PLACEHOLDER_TAG, number), _one_line(rendered))

    extra = {}
    links = options.source_links
    if links is not None:
        urls = links.urls_for(page)
        if urls:
            # Rendered by Zensical's own page-action buttons (resources/overrides/partials/actions.html)
            extra["dita_source"] = links.relative_path(page)
            extra.update({"source_{}_url".format(action): url for action, url in urls.items()})
    return front_matter(page.meta, extra) + text


def front_matter(meta: dict, extra: dict | None = None) -> str:
    lines = ["---"]
    if meta.get("title"):
        lines.append("title: " + _yaml(meta["title"]))
    if meta.get("description"):
        lines.append("description: " + _yaml(meta["description"]))
    if meta.get("keywords"):
        lines.append("keywords: " + _yaml(", ".join(meta["keywords"])))
    for key, value in (extra or {}).items():
        lines.append("{}: {}".format(key, _yaml(value)))
    lines += ["---", "", ""]
    return "\n".join(lines)


def _rewrite_links(root, page_path, pages):
    """Links between pages end in .html in the interchange; Zensical resolves .md links."""
    base = posixpath.dirname(page_path)
    for a in root.iter("a"):
        href = a.get("href")
        if not href or href.startswith(("#", "/")) or _SCHEME.match(href):
            continue
        path, hash_, fragment = href.partition("#")
        target = posixpath.normpath(posixpath.join(base, path))
        if target in pages:
            new_href = markdown_path(path) + hash_ + fragment
            a.set("href", new_href)
            if len(a) == 0 and (a.text or "").strip() == href:
                a.text = new_href  # DITA-OT's fallback text for an untitled target is the href


def _prepare_code(root, page_path, options, highlighter):
    """Swap highlightable codeblocks for placeholders; box the rest. Returns the HTML per placeholder."""
    parents = {child: parent for parent in root.iter() for child in parent}
    blocks = []
    for pre in [el for el in root.iter() if highlight.is_codeblock(el)]:
        parent = parents.get(pre)
        if parent is None:
            continue
        block = highlight.as_code_block(pre, options.default_language) if highlighter else None
        if block is None:
            replacement = highlight.code_box(pre, options.default_language)
        else:
            replacement = ET.Element(PLACEHOLDER_TAG, {"n": str(len(blocks))})
            replacement.tail = pre.tail
            blocks.append(block)
        index = list(parent).index(pre)
        parent.remove(pre)
        parent.insert(index, replacement)
    return highlighter.render(blocks, page_path) if blocks else []


# ============ Flattening ============

def _is_heading(el) -> bool:
    return bool(_HEADING.match(el.tag))


def _has_heading(el) -> bool:
    return any(_is_heading(d) for d in el.iter() if d is not el)


def _heading_id(h, parent):
    """The heading's id, or for an id-less heading that opens a container, the container's id."""
    if h.get("id"):
        return h.get("id")
    if parent is not None and parent.tag in CONTAINERS and len(parent) and parent[0] is h and not (parent.text or "").strip():
        return parent.get("id")
    return None


def _emit(el, parent, out):
    if _is_heading(el):
        out.append(_heading_markdown(el, parent))
    elif el.tag in CONTAINERS and _has_heading(el):
        first = el[0] if len(el) else None
        if el.get("id") and not (first is not None and _is_heading(first) and not first.get("id")
                                 and not (el.text or "").strip()):
            out.append('<div id="{}" class="dita-anchor"></div>\n\n'.format(html.escape(el.get("id"))))
        _emit_text(el.text, out)
        for child in el:
            _emit(child, el, out)
            _emit_text(child.tail, out)
    elif el.tag in theme.BLOCK_ELEMENTS or el.tag == PLACEHOLDER_TAG:
        out.append(serialize(el) + "\n\n")
    else:
        out.append('<div class="dita-inline">' + serialize(el) + "</div>\n\n")


def _emit_text(text, out):
    if text and text.strip():
        out.append("<p>" + html.escape(" ".join(text.split()), quote=False) + "</p>\n\n")


def _heading_markdown(h, parent) -> str:
    level = int(h.tag[1])
    inner = _md_escape(html.escape(h.text or "", quote=False))
    for child in h:
        inner += serialize(child) + _md_escape(html.escape(child.tail or "", quote=False))
    attrs = []
    anchor = _heading_id(h, parent)
    if anchor:
        attrs.append("#" + anchor)
    attrs += ["." + c for c in theme.classes(h)]
    suffix = " { " + " ".join(attrs) + " }" if attrs else ""
    return "#" * level + " " + " ".join(inner.split()) + suffix + "\n\n"


def _md_escape(text: str) -> str:
    return _MD_SPECIAL.sub(r"\\\1", text)


# ============ Serialization ============

def serialize(el) -> str:
    """One element as HTML on a single line (tail excluded)."""
    clone = copy.deepcopy(el)
    clone.tail = None
    _protect(clone, False)
    return ET.tostring(clone, encoding="unicode", method="html").replace(_NEWLINE, "&#10;")


def _protect(el, in_pre):
    pre = in_pre or el.tag in PREFORMATTED
    el.text = _fold(el.text, pre)
    for child in el:
        _protect(child, pre)
        child.tail = _fold(child.tail, pre)


def _fold(text, preformatted):
    if not text:
        return text
    if preformatted:
        return text.replace("\r", "").replace("\n", _NEWLINE)
    return re.sub(r"[ \t]*[\r\n]+[ \t]*", " ", text)


_PRE_BLOCK = re.compile(r"<pre\b.*?</pre>", re.S)


def _one_line(fragment: str) -> str:
    """Highlighter output on one line: newlines inside <pre> become &#10;, others go."""
    fragment = _PRE_BLOCK.sub(lambda m: m.group(0).replace("\r", "").replace("\n", "&#10;"), fragment)
    return fragment.replace("\r", "").replace("\n", "")


def _yaml(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)  # a JSON string is a valid YAML scalar


# ============ Site ============

def write_pages(site, docs_dir, options: Options, highlighter, warn=print) -> int:
    links = options.source_links
    if links is not None:
        unmapped = sorted(p.path for p in site.pages.values() if not links.urls_for(p))
        if unmapped:
            warn("{} page(s) have no source link, because their source is outside {}: {}".format(
                len(unmapped), links.root, ", ".join(unmapped[:5]) + (" ..." if len(unmapped) > 5 else "")))
    for page in site.pages.values():
        target = docs_dir / markdown_path(page.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page_markdown(page, site, options, highlighter), encoding="utf-8")
    return len(site.pages)


def home_page_markdown(site, title: str) -> str:
    """docs/index.md listing the top two levels of the nav."""
    lines = [front_matter({"title": title, "description": site.meta.get("description", "")}).rstrip("\n"), "",
             "# " + _md_escape(html.escape(title, quote=False)), ""]
    if site.meta.get("description"):
        lines += [_md_escape(html.escape(site.meta["description"], quote=False)), ""]

    def walk(items, depth):
        for item in items:
            label = item.title or (markdown_path(item.page) if item.page else item.url or "")
            text = _md_escape(html.escape(label, quote=False))
            indent = "    " * depth
            if item.page or item.url:
                link = markdown_path(item.page) if item.page else item.url
                lines.append("{}- [{}]({})".format(indent, text, link.replace(" ", "%20").replace("(", "%28").replace(")", "%29")))
            elif item.title:
                lines.append("{}- {}".format(indent, text))
            if depth < 1:
                walk(item.children, depth + 1 if (item.page or item.url or item.title) else depth)

    walk(site.nav, 0)
    return "\n".join(lines) + "\n"
