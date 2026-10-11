"""Publish the DITA interchange (see INTERCHANGE.md) with Zensical.

Modules, and which of them a future Zensical module would reuse:

    interchange   read site.json, pages and assets                     reuse
    theme         adapt DITA-OT HTML to the Zensical theme             reuse
    highlight     syntax-highlight codeblocks like fenced code         reuse
    source_links  edit/view links to git or an AEM Guides DAM          reuse
    carrier       write pages as Markdown files (today's only route)   replace
    config        write zensical.toml with the nav                     replace

A module would load the interchange, call theme.adapt() and highlight on each
page's element, and hand Zensical the HTML, the page metadata and the headings,
skipping carrier and config entirely.
"""

__version__ = "0.5.1"
