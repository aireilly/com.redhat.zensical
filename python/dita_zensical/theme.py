"""Adapt DITA-OT HTML5 to the markup the Zensical theme styles.

Works on the namespace-free element tree from interchange.Page.element() and
changes it in place. Independent of how the page then reaches Zensical.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

# Elements Python-Markdown treats as block-level raw HTML; also used for note bodies
BLOCK_ELEMENTS = frozenset("""
    address article aside blockquote body canvas center colgroup dd details div dl dt
    fieldset figcaption figure footer form h1 h2 h3 h4 h5 h6 header hgroup hr iframe legend
    li main map math menu nav noscript object ol output p pre progress script section style
    summary table tbody td textarea tfoot th thead tr ul video
""".split())

# DITA note type -> Zensical admonition type (the theme also styles these aliases)
NOTE_TYPES = {
    "note": "note", "notice": "info", "remember": "info", "tip": "tip", "fastpath": "tip",
    "important": "important", "restriction": "warning", "attention": "attention",
    "caution": "caution", "warning": "warning", "danger": "danger", "trouble": "failure",
    "other": "note",
}

TABLE_PRESENTATION_ATTRS = ("border", "cellpadding", "cellspacing", "frame", "rules")


def classes(el) -> list[str]:
    return el.get("class", "").split()


def adapt(root: ET.Element, *, admonitions: bool = True, tables: bool = True) -> ET.Element:
    if root.tag == "article":
        root.attrib.pop("role", None)  # Zensical's page already provides the landmark
    elements = list(root.iter())
    if admonitions:
        for el in elements:
            if el.tag == "div" and "note" in classes(el) and _note_title(el) is not None:
                _note_to_admonition(el)
    if tables:
        for el in elements:
            if el.tag == "table":
                _theme_table(el)
    return root


def _note_title(el):
    for child in el:
        if child.tag == "span" and "note__title" in classes(child):
            return child
    return None


def _note_to_admonition(el):
    title = _note_title(el)
    dita_type = next((c[len("note_"):] for c in classes(el) if c.startswith("note_")), "note")
    label = "".join(title.itertext()).strip().rstrip(":").strip()

    body = next((c for c in el if c.tag == "div" and "note__body" in classes(c)), None)
    if body is not None:
        text, children = body.text, list(body)
    else:
        text, children = title.tail, [c for c in el if c is not title]

    attrs = {k: v for k, v in el.attrib.items() if k != "class"}
    tail = el.tail
    el.clear()  # also drops the tail, which belongs to the parent's content
    el.tail = tail
    el.attrib.update(attrs)
    el.set("class", "admonition {} dita-note note_{}".format(NOTE_TYPES.get(dita_type, "note"), dita_type))
    heading = ET.SubElement(el, "p", {"class": "admonition-title"})
    heading.text = label

    if any(c.tag in BLOCK_ELEMENTS for c in children):
        if text and text.strip():
            ET.SubElement(el, "p").text = text.strip()
        el.extend(children)
    else:
        para = ET.SubElement(el, "p")
        para.text = text.lstrip() if text else text
        para.extend(children)


def _theme_table(table):
    """The theme only styles table:not([class]); keep the DITA classes as data."""
    if "class" in table.attrib:
        table.set("data-dita-class", table.attrib.pop("class"))
    for name in TABLE_PRESENTATION_ATTRS:
        table.attrib.pop(name, None)
