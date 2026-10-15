"""Write Zensical sources (docs/ and zensical.toml) from the DITA interchange.

Run by the com.redhat.zensical DITA-OT plug-in with the Python Zensical is
installed in. Can also be run by hand on an existing interchange folder:

    python write_site.py --interchange out/interchange --docs out/docs --config out/zensical.toml
"""

import argparse
import pathlib
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from dita_zensical import carrier, config, highlight, interchange, source_links  # noqa: E402


def yes(value: str) -> bool:
    return value.lower() in ("yes", "true", "1")


def install_actions_partial(project_dir, custom_dir, overrides, warnings):
    """Put the page-action partial into the theme custom_dir, when that folder is ours to write."""
    source = (overrides or pathlib.Path(__file__).resolve().parent.parent / "resources" / "overrides") \
        / "partials" / "actions.html"
    target_dir = (project_dir / custom_dir).resolve()
    if not target_dir.is_relative_to(project_dir.resolve()):
        warnings.append("custom_dir {} is outside the output folder; copy {} into its partials/ folder "
                        "so the source-link buttons render".format(custom_dir, source))
        return
    (target_dir / "partials").mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target_dir / "partials" / "actions.html")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--interchange", required=True, type=pathlib.Path)
    parser.add_argument("--docs", required=True, type=pathlib.Path)
    parser.add_argument("--config", required=True, type=pathlib.Path, help="zensical.toml to write")
    parser.add_argument("--user-config", type=pathlib.Path)
    parser.add_argument("--site-name", default="")
    parser.add_argument("--site-url", default="")
    parser.add_argument("--site-description", default="")
    parser.add_argument("--repo-url", default="")
    parser.add_argument("--home", choices=("generated", "none"), default="generated")
    parser.add_argument("--directory-urls", default="yes", help="no publishes pages as other.html")
    parser.add_argument("--admonitions", default="yes")
    parser.add_argument("--theme-tables", default="yes")
    parser.add_argument("--highlight", default="yes")
    parser.add_argument("--default-lang", default="text")
    parser.add_argument("--css", type=pathlib.Path)
    links = parser.add_argument_group("source links")
    links.add_argument("--source-links", choices=("none", "git", "aem"), default="none")
    links.add_argument("--source-action", choices=("edit", "view", "both"), default="edit")
    links.add_argument("--source-root", default="", help="local folder matching the repository or DAM root")
    links.add_argument("--source-url-template", default="")
    links.add_argument("--source-view-url-template", default="")
    links.add_argument("--git-url", default="")
    links.add_argument("--git-branch", default="")
    links.add_argument("--git-host", default="auto")
    links.add_argument("--dam-url", default="", help="DAM URL root; the topic path is appended or replaces {path}")
    links.add_argument("--dam-view-url", default="", help="DAM URL root for the view button; default --dam-url")
    links.add_argument("--source-path-map", default="",
                       help="tab-separated source file name to path under the root, for staged builds")
    links.add_argument("--overrides", type=pathlib.Path, help="the plug-in's theme overrides folder")
    args = parser.parse_args(argv)

    warnings = []
    try:
        site = interchange.load(args.interchange)
    except interchange.InterchangeError as exc:
        sys.exit("error: {}".format(exc))

    links = None
    if args.source_links != "none":
        try:
            links = source_links.SourceLinks.configure(
                args.source_links, site_source=site.meta.get("source", ""), root=args.source_root,
                action=args.source_action, template=args.source_url_template,
                view_template=args.source_view_url_template,
                git_url=args.git_url or args.repo_url, git_branch=args.git_branch, git_host=args.git_host,
                dam_url=args.dam_url, dam_view_url=args.dam_view_url,
                path_map=args.source_path_map)
        except source_links.SourceLinkError as exc:
            sys.exit("error: source links: {}".format(exc))

    actions = links.actions if links else ()

    site_name = args.site_name or site.title or "Documentation"
    with_home = args.home == "generated" and "index.html" not in site.pages
    nav_block = config.nav_toml(site.nav, with_home)

    # zensical.toml first: the highlighter reads its pymdownx.highlight settings
    custom_dir = config.OVERRIDES_DIR
    if args.user_config:
        toml = config.merge_user_config(args.user_config.read_text(encoding="utf-8"), site_name, nav_block,
                                        directory_urls=yes(args.directory_urls))
        if actions:
            toml, custom_dir, notes = config.ensure_source_actions(toml, actions)
            warnings.extend(notes)
    else:
        toml = config.default_config(
            site_name, nav_block,
            description=args.site_description or site.meta.get("description", ""),
            url=args.site_url, repo_url=args.repo_url,
            language=(site.meta.get("language") or "en").split("-")[0].lower(),
            source_actions=actions, directory_urls=yes(args.directory_urls))
    args.config.write_text(toml, encoding="utf-8")
    if actions:
        install_actions_partial(args.config.parent, custom_dir, args.overrides, warnings)

    highlighter = None
    if yes(args.highlight):
        highlighter = highlight.Highlighter(highlight.settings_from_config(args.config), warn=warnings.append)

    edit_icon = None
    if links is not None:
        icon_name = config.theme_icon(toml, "edit", "material/file-edit-outline")
        edit_icon = carrier.load_theme_icon(icon_name)
        if edit_icon is None:
            warnings.append("could not load theme edit icon {!r}; child-topic links use text".format(icon_name))

    options = carrier.Options(
        admonitions=yes(args.admonitions), theme_tables=yes(args.theme_tables),
        highlight=highlighter is not None, default_language=args.default_lang or "text",
        source_links=links, edit_icon=edit_icon)

    args.docs.mkdir(parents=True, exist_ok=True)
    count = carrier.write_pages(site, args.docs, options, highlighter, warn=warnings.append)
    if with_home:
        (args.docs / "index.md").write_text(carrier.home_page_markdown(site, site_name), encoding="utf-8")
    for asset in site.assets:
        target = args.docs / asset
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(site.content / asset, target)
    if args.css:
        (args.docs / "stylesheets").mkdir(exist_ok=True)
        shutil.copy2(args.css, args.docs / "stylesheets" / config.CSS_FILENAME)

    for warning in warnings:
        # stderr: Ant logs it, and the plug-in re-emits it as a DITA-OT warning
        print("warning: " + warning, file=sys.stderr)
    print("wrote {} page(s), {} asset(s), {}".format(count, len(site.assets), args.config.name))
    if links is not None:
        print("source links: {} ({}), root {}".format(links.kind, "+".join(links.actions), links.root))


if __name__ == "__main__":
    main()
