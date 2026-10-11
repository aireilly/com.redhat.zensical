"""Reader for the DITA interchange format, version 1 (INTERCHANGE.md)."""

from __future__ import annotations

import json
import pathlib
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

XHTML_NS = "http://www.w3.org/1999/xhtml"
XML_NS = "http://www.w3.org/XML/1998/namespace"
PAGE_FORMAT = ("dita-interchange-page", 1)
SITE_FORMAT = ("dita-interchange-site", 1)
MARKER = ".dita-zensical"


class InterchangeError(Exception):
    """The interchange folder is missing, malformed or of an unknown version."""


def _check_format(value, expected, where):
    name, _, version = str(value or "").partition("/")
    major = version.split(".")[0]
    if name != expected[0] or not major.isdigit():
        raise InterchangeError("{}: not a {} file (format={!r})".format(where, expected[0], value))
    if int(major) != expected[1]:
        raise InterchangeError("{}: format {} is not supported, expected version {}".format(where, value, expected[1]))


@dataclass
class NavItem:
    title: str | None = None
    page: str | None = None
    url: str | None = None
    children: list[NavItem] = field(default_factory=list)

    @classmethod
    def from_json(cls, data):
        return cls(
            title=data.get("title") or None,
            page=data.get("page") or None,
            url=data.get("url") or None,
            children=[cls.from_json(child) for child in data.get("children", [])],
        )


@dataclass
class Page:
    path: str
    """Fragment path relative to content/, such as 'topics/overview.html'."""
    meta: dict
    file: pathlib.Path

    @property
    def title(self) -> str:
        return self.meta.get("title", "")

    @property
    def description(self) -> str:
        return self.meta.get("description", "")

    @property
    def headings(self) -> list[dict]:
        return self.meta.get("headings", [])

    def element(self) -> ET.Element:
        """A fresh, namespace-free copy of the page's <article>, safe to modify."""
        root = ET.parse(self.file).getroot()
        for el in root.iter():
            if el.tag.startswith("{"):
                el.tag = el.tag.split("}", 1)[1]
            for name in [n for n in el.attrib if n.startswith("{")]:
                value = el.attrib.pop(name)
                el.set("lang" if name == "{%s}lang" % XML_NS else name.split("}", 1)[1], value)
        return root


@dataclass
class Site:
    root: pathlib.Path
    meta: dict
    nav: list[NavItem]
    pages: dict[str, Page]
    assets: list[str]

    @property
    def content(self) -> pathlib.Path:
        return self.root / "content"

    @property
    def title(self) -> str:
        return self.meta.get("title", "")


def load(root) -> Site:
    root = pathlib.Path(root)
    site_file = root / "site.json"
    if not site_file.is_file():
        raise InterchangeError("{} not found".format(site_file))
    meta = json.loads(site_file.read_text(encoding="utf-8"))
    _check_format(meta.get("format"), SITE_FORMAT, site_file)

    content = root / "content"
    pages, sidecars = {}, set()
    for sidecar in sorted(content.rglob("*.json")):
        fragment = sidecar.with_suffix(".html")
        if not fragment.is_file():
            continue
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        if not str(data.get("format", "")).startswith(PAGE_FORMAT[0] + "/"):
            continue
        _check_format(data.get("format"), PAGE_FORMAT, sidecar)
        path = fragment.relative_to(content).as_posix()
        pages[path] = Page(path=path, meta=data, file=fragment)
        sidecars.add(sidecar)

    assets = sorted(
        f.relative_to(content).as_posix()
        for f in content.rglob("*")
        if f.is_file() and f not in sidecars and f.relative_to(content).as_posix() not in pages and f.name != MARKER
    )
    nav = [NavItem.from_json(item) for item in meta.get("nav", [])]
    return Site(root=root, meta=meta, nav=nav, pages=pages, assets=assets)
