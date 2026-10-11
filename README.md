# DITA-OT Zensical plug-in

Use this plug-in to publish a DITA map as a [Zensical](https://zensical.org) documentation site.

Tested with DITA-OT 4.3.4, Zensical 0.0.69, and pymdownx 11.0 and 12.2.

## Quick start

You need [DITA-OT](https://www.dita-ot.org/download) 4.x with Java 17 or later, and Python 3.11 or later.

1. Install Zensical and the plug-in (once):

   ```bash
   pip install zensical
   dita install com.redhat.zensical.zip
   ```

2. Generate the Zensical project from your map:

   ```bash
   dita -i guide.ditamap -f zensical -o out -Dzensical.stage=sources
   ```

3. Serve it:

   ```bash
   cd out
   zensical serve --open
   ```

   The site opens at <http://localhost:8000>. Add `-a 0.0.0.0:8000` to reach it from other machines.

To see edits, leave `zensical serve` running and repeat step 2 in a second terminal. The browser reloads once DITA-OT finishes.

`-Dzensical.stage=sources` stops before `zensical build`, which `zensical serve` would repeat anyway. Leave it out for a deployable static site in `out/site/`:

```bash
dita -i guide.ditamap -f zensical -o out
```

To try it without a map of your own, use `sample/sample.ditamap` from this plug-in.

## Build the plug-in ZIP

From the repository root, with the `zip` command installed, run:

```bash
rm -f com.redhat.zensical.zip
zip -r com.redhat.zensical.zip \
  plugin.xml build_zensical.xml conductor.xml \
  xsl python resources sample \
README.md INTERCHANGE.md LICENSE
```

This creates `com.redhat.zensical.zip` in the repository root, with `plugin.xml` at the archive root. The first command removes an earlier archive so it cannot retain files that have since been deleted. Install the ZIP with `dita install com.redhat.zensical.zip`. The GitHub release workflow packages the same files.

## Architecture

The build runs in three stages. Each one writes files the next one reads, and `zensical.stage` chooses where to stop.

```
              DITA-OT (Java, XSLT)                  Python adapter                 Zensical
DITA map ──► 1. interchange/  ──────────────────► 2. docs/ + zensical.toml ────► 3. site/
             XHTML5 fragments, JSON metadata,     Markdown pages, nav, theme      zensical build
             site.json   (Zensical-agnostic)      tweaks, code highlighting
```

1. **Interchange.** DITA-OT preprocesses the map (keys, conrefs, DITAVAL filtering, chunking) and runs its standard HTML5 topic transformation. The plug-in keeps each topic's `<article>`, serializes it as an XHTML5 fragment, and writes a JSON sidecar with the title, description, headings and anchors. The map becomes `site.json` with the nav. Nothing in this stage knows about Zensical. [INTERCHANGE.md](INTERCHANGE.md) defines the format.
2. **Sources.** `python/dita_zensical` reads the interchange and writes what Zensical accepts today: one Markdown page per topic, plus `zensical.toml`. This stage applies the theme mapping (notes to admonitions, table styling) and highlights codeblocks the way Zensical highlights fenced code.
3. **Site.** `zensical build`.

### Why the split

Zensical's planned [module API](https://zensical.org/roadmap/) will let custom steps join its publishing pipeline. When that is available, a module can read the interchange directly and hand Zensical finished HTML pages, while stage 2 becomes unnecessary. The Python package is laid out for that move:

| Module | Purpose | With a Zensical module |
|---|---|---|
| `interchange` | Load `site.json`, pages and assets | Reused |
| `theme` | Adapt DITA-OT HTML to the Zensical theme | Reused |
| `highlight` | Highlight codeblocks with `pymdownx.highlight` | Reused |
| `carrier` | Write pages as Markdown files | Replaced |
| `config` | Write `zensical.toml` with the nav | Replaced |

Stage 1, where all the DITA knowledge lives, stays as it is.

### Why HTML5, serialized as XHTML

DITA-OT has two HTML transformations. `html5` is the maintained one: it emits `<section>`, `<figure>`, `<nav>` and ARIA attributes, and DITA-OT and most plug-ins put new features there. `xhtml` is the older XHTML 1.0 transformation, kept mainly for compatibility.

Markup vocabulary and serialization are separate choices. This plug-in uses the HTML5 transformation, then writes its output with the XSLT `xhtml` method. Each fragment is a well-formed XML document in the XHTML namespace. Python's standard XML parser can read it. HTML serialization leaves void elements such as `<img>` unclosed, which requires an HTML5 parser.

## Output

| Path | Contents |
|---|---|
| `out/interchange/` | Stage 1 output, see [INTERCHANGE.md](INTERCHANGE.md) |
| `out/docs/` | Markdown pages, images, `stylesheets/dita.css` |
| `out/zensical.toml` | Generated config, or yours with the nav added |
| `out/site/` | The finished static site |

Preview with live reload while adjusting theme settings:

```bash
cd out && zensical serve
```

`interchange/` and `docs/` are deleted at the start of each build only when they carry the plug-in's `.dita-zensical` marker. A folder with either name from anything else stops the build.

## Parameters

| Parameter | Default | Purpose |
|---|---|---|
| `zensical.stage` | `site` | Last stage: `interchange`, `sources` or `site` |
| `zensical.site.name` | map title | `site_name` |
| `zensical.site.url` | | `site_url`, needed for sitemaps and canonical links |
| `zensical.site.description` | map shortdesc | `site_description` |
| `zensical.repo.url` | | `repo_url` |
| `zensical.config` | | Your own `zensical.toml` |
| `zensical.home` | `generated` | `generated` writes `docs/index.md` from the map when no topic publishes as `index`; `none` skips it |
| `zensical.admonitions` | `yes` | Render DITA notes as admonitions |
| `zensical.theme.tables` | `yes` | Let the theme style DITA tables |
| `zensical.highlight` | `yes` | Syntax-highlight codeblocks |
| `zensical.code.default-lang` | `text` | Language for codeblocks without `outputclass="language-*"` |
| `zensical.source.links` | `none` | Edit and view-source buttons on every topic, linking to `git` or `aem` (see [Source links](#source-links)) |
| `zensical.python` | found automatically | The Python that Zensical is installed in |
| `zensical.strict` | `no` | Pass `--strict` so warnings fail the build |
| `zensical.executable` | `zensical` | Command used to run Zensical |

Standard DITA-OT and HTML5 parameters still apply, for example `--filter`, `args.draft` and `args.gen.task.lbl`.

### Your own zensical.toml

Pass a path such as `-Dzensical.config=site.toml` to keep theme, palette and extensions under version control. Relative paths are resolved from the directory where you run `dita`; absolute paths are also accepted. The plug-in copies the config to `out/zensical.toml` and adds `site_name`, `extra_css` and `nav` under `[project]` when the file does not set them. If you set `markdown_extensions`, keep `attr_list` enabled, because page headings carry their DITA ids through it. Codeblocks follow your `pymdownx.highlight` settings.

### Source links

Each topic page can show two Zensical page actions: **Edit this page** and **View source of this page**. They link to the topic's DITA source in a git repository or the AEM Guides DAM:

```bash
# Git: repository, branch and host are detected from the checkout
dita -i guide.ditamap -f zensical -o out -Dzensical.source.links=git -Dzensical.source.action=both

# AEM Guides: you supply the DAM URL root, and each topic's path is appended to it
dita -i guide.ditamap -f zensical -o out -Dzensical.source.links=aem \
     -Dzensical.aem.dam-url=https://author.example.com/assetdetails.html/content/dam/widget-docs
```

The buttons are Zensical's, with its markup, icons and translated tooltips. Zensical builds their links from `repo_url` and `edit_uri`, which would point at the generated Markdown, and it has no per-page setting. So the plug-in overrides one theme partial, `partials/actions.html`, to take each page's `source_edit_url` and `source_view_url` from front matter in place of `page.edit_url`. Nothing else in the theme changes. With source links on, the plug-in also:

* turns on the `content.action.edit` and `content.action.view` features to match `zensical.source.action`
* sets `custom_dir = "overrides"` under `[project.theme]` and writes the partial to `out/overrides/partials/actions.html`

It does this in the generated config, and in yours when you pass `zensical.config` (it adds only what's missing). If your config sets a `custom_dir` outside the output folder, the plug-in tells you to copy the partial there, from `resources/overrides/partials/actions.html` in the plug-in. Change the icons with Zensical's usual `theme.icon.edit` and `theme.icon.view` settings.

Each topic's path is its source file relative to `zensical.source.root`. For git that root defaults to the top of the checkout. For AEM it defaults to the map's folder, which should correspond to the DAM URL root, so `topics/install.dita` beside the map becomes `…/content/dam/widget-docs/topics/install.dita`. If the path belongs elsewhere in the URL, put `{path}` there:

```bash
-Dzensical.aem.dam-url="https://author.example.com/your/editor/url?src=/content/dam/widget-docs/{path}"
```

Use whichever AEM URL your authors open topics with. The plug-in doesn't assume an editor URL, because Adobe doesn't document one as stable. For both buttons in AEM, give the view button its own root with `zensical.aem.view-url`; otherwise both open the same URL.

| Parameter | Default | Purpose |
|---|---|---|
| `zensical.source.links` | `none` | `git`, `aem` or `none` |
| `zensical.source.action` | `edit` | Buttons to show: `edit`, `view` or `both` |
| `zensical.source.root` | checkout top (git), map folder (aem) | Local folder matching the repository root or the DAM URL root |
| `zensical.aem.dam-url` | | DAM URL root. Required for `aem` |
| `zensical.aem.view-url` | `zensical.aem.dam-url` | DAM URL root for the view button |
| `zensical.git.url` | `zensical.repo.url`, then `origin` | Repository web URL. SSH remotes are converted to HTTPS |
| `zensical.git.branch` | checked-out branch | Branch to link to. A detached checkout, common in CI, links to the commit |
| `zensical.git.host` | guessed from the URL | `github`, `gitlab`, `bitbucket`, `gitea` or `azure` URL style |
| `zensical.source.url-template` | | Full URL template replacing the preset (edit, and view unless set below) |
| `zensical.source.view-url-template` | | Full URL template for the view button |

Templates accept `{path}` (URL-encoded), `{raw_path}`, `{repo}`, `{branch}` and `{topic_id}`. Unsafe characters in the configured URL, such as a space in a DAM folder name, are percent-encoded. A topic whose source lies outside the root gets no buttons, and the build lists those topics in a warning. The generated home page has no DITA source, so it gets none either.

Git view links open the hosting service's file view, where Zensical's default would open the raw file. Edit links open the web editor, which offers a fork or merge request to contributors without write access. Azure Repos has no direct edit URL, so both buttons open the file view there.

### Finding Python

Stage 2 runs on the Python that Zensical is installed in, because it uses Zensical's Python-Markdown, pymdownx and Pygments. The first interpreter that can import them wins:

1. `zensical.python`, when you set it
2. a `python` next to the `zensical` command (virtualenv, pipx, `uv tool`, Windows `Scripts\`)
3. the interpreter in the `zensical` script's shebang
4. `python3`, `python` or `py` on `PATH`

You can also run stage 2 by hand on an existing interchange:

```bash
python python/write_site.py --interchange out/interchange --docs out/docs --config out/zensical.toml
```

## Stage 2 details

### Pages

* Front matter carries `title`, `description` and `keywords` from the page metadata.
* Headings become Markdown headings such as `## Key concepts { #overview__concepts .title .sectiontitle }`, which give Zensical its "On this page" sidebar, permalinks and section search results.
* Wrappers that contain headings are unwrapped. A section's id moves onto its title, or stays as an empty `div.dita-anchor`, so xrefs still land.
* Everything else stays raw HTML, one block per line, with newlines inside `<pre>` written as `&#10;`. Python-Markdown passes top-level raw HTML through untouched, while `md_in_html` containers re-parse nested HTML and break common task markup.
* Cross-page links are rewritten to relative URLs for Zensical's directory-style page routes. Local image paths are adjusted for those routes too.

### Theme mapping

* Notes become `div.admonition.<type>` with an `admonition-title`, and keep `note_<type>`.
* Tables lose their DITA `class`, kept in `data-dita-class`, because the theme only styles class-less tables.
* `dita.css` covers DITA classes the theme has no styles for.

### Code blocks

Set the language with `outputclass`, as DITA-OT expects:

```xml
<codeblock outputclass="language-python show-line-numbers">def build(parts):
    return "-".join(parts)</codeblock>
```

Each page's codeblocks are rendered as fenced blocks through `pymdownx.superfences` with the project's `pymdownx.highlight` settings. The HTML matches Zensical's own fenced code, including colours in both schemes, the copy button and line anchors.

* `show-line-numbers` adds line numbers. The codeblock `id` and other classes carry over.
* `dita`, `ditamap` and `ditaval` are highlighted as XML. An unknown language falls back to plain text with a build warning.
* Formatting markup such as `<b>` or `<varname>` gives way to token colours when a language is set, and is kept when none is.
* A codeblock containing a link or image keeps its HTML inside the same code box, uncoloured.

### Nav

`site.json` mirrors the map. Topicheads and titled topicgroups become sections, a topicref with children becomes a section whose first entry is its own page, and external links stay links. `toc="no"` and resource-only refs are left out of the nav, though their pages are still built.

## Extending

| Extension point | Use |
|---|---|
| `dita.xsl.interchange.topic` | XSLT imported after `topic2interchangeImpl.xsl`. Override `z:page-metadata-extra` to add sidecar keys, or any template to change the fragment |
| `dita.xsl.interchange.map` | XSLT imported after `map2interchangeImpl.xsl`. Override `z:site-metadata-extra` or the nav functions |
| `dita.xsl.html5` | Regular HTML5 overrides, since fragments come from the html5 stylesheets |

The XSLT namespace is `urn:x-dita-interchange` (prefix `z`). Stage 2 behaviour is changed in `python/dita_zensical`.

## Limitations

* Family links (parent, child, sibling) are off through `args.rellinks=nofamily`, since the Zensical nav and footer cover them. Reltable links still appear.
* `zensical serve` live-reloads theme and config changes. DITA edits need another DITA-OT run, which a Zensical module could later automate.
* The plug-in ID is `com.redhat.zensical`. DITA-OT sets the matching `dita.plugin.com.redhat.zensical.dir` property for the plug-in directory.

## Sample

`sample/sample.ditamap` covers DITA concepts and tasks, nested topics, tables, notes, and an image. It also includes xrefs, a topichead, an external link, a topic with `toc="no"`, and codeblock examples.

```bash
dita -i sample/sample.ditamap -f zensical -o out -Dzensical.config=sample/zensical.toml && cd out && zensical serve
```

## Releases

The initial `0.0.1` release is published. To publish a later version, tag the commit and push the tag. For example:

```bash
git tag 0.0.2
git push origin 0.0.2
```

Pushing any tag creates a GitHub release with `com.redhat.zensical.zip` attached. The archive keeps `plugin.xml` at its root so DITA-OT can install it directly.
