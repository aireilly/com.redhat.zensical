# DITA interchange format, version 1

The DITA-OT side of this plug-in writes its result to `interchange/` and knows nothing about Zensical. Anything that publishes the content reads this folder: the Markdown adapter shipped today (`python/dita_zensical`), and later a Zensical module.

```
interchange/
  site.json                     site metadata and nav, from the map
  content/
    topics/overview.html        page fragment (XHTML5)
    topics/overview.json        page metadata
    images/kitteh.png          assets, at the paths the fragments reference
```

Paths are POSIX, relative to `content/`. A page is any `*.html` file with a sibling `*.json` whose `format` is `dita-interchange-page/1`. Every other file in `content/` is an asset.

## Page fragment (`*.html`)

* One well-formed XML document with a single `<article>` root in the XHTML namespace (`http://www.w3.org/1999/xhtml`), serialized as polyglot XHTML5 with no XML declaration and no doctype.
* The content is DITA-OT's `html5` output for the topic, unchanged except for the additions listed below. Classes, ids, ARIA attributes and nested topics keep their DITA-OT form. Customizations made through `dita.xsl.html5` still apply.
* Links between pages are relative and end in `.html`, plus an optional `#fragment`. They resolve against the fragment's own location.
* Codeblocks gain these attributes:
  * `data-language`: the language from `outputclass="language-*"`, lower-cased, when one is set
  * `data-line-numbers="true"`: present when `outputclass` contains `show-line-numbers`

Nothing in the fragment is specific to a theme or a site generator.

## Page metadata (`*.json`)

| Key | Type | Notes |
|---|---|---|
| `format` | string | `dita-interchange-page/1` |
| `title` | string | Plain text of the topic title |
| `title_html` | string | Title with inline markup, as an HTML string without namespace declarations |
| `description` | string | Optional. Plain text of `shortdesc` |
| `keywords` | array of strings | Optional. Prolog keywords |
| `language` | string | Optional. `xml:lang` of the topic |
| `id` | string | Topic id |
| `type` | string | Topic type from `@class`, such as `concept` or `task` |
| `outputclass` | string | Optional |
| `source` | string | URI of the source topic file as DITA-OT saw it, before preprocessing. Publishers use it for edit and view-source links |
| `headings` | array | One entry per heading in document order |

A heading entry holds `level` (1 to 6), `text` (plain), `html` (inner markup, as for `title_html`), `classes` (array) and `anchor`. `anchor` is the id a table of contents should link to: the heading's own id, otherwise the id of the section or nested topic it titles. It is omitted when neither exists.

## Site (`site.json`)

| Key | Type | Notes |
|---|---|---|
| `format` | string | `dita-interchange-site/1` |
| `title` | string | Map title, or `booktitle/mainbooktitle` |
| `source` | string | URI of the source map as DITA-OT saw it |
| `description` | string | Optional. Map `topicmeta/shortdesc` |
| `language` | string | Optional. `xml:lang` of the map |
| `chunk_to_content` | boolean | Optional. Present when the map sets `chunk="to-content"`; publishers can use the map as the source for links to combined output. |
| `nav` | array | Nav items, see below |

A nav item has `title` (optional) and `children` (array, possibly empty), plus at most one of `page` (a page path such as `topics/overview.html`) or `url` (an external link). An item with neither is a heading, such as a `topichead` or titled `topicgroup`. Untitled topicgroups are flattened into their parent. Topicrefs with `toc="no"` or `processing-role="resource-only"` are left out, but their pages are still in `content/`.

## Compatibility

Readers check `format` and refuse a major version they do not know. Additive changes such as new keys or new `data-*` attributes keep version 1, so readers ignore keys they do not recognize.
