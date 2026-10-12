# DITA-OT Zensical plug-in

Use this plug-in to build a [Zensical](https://zensical.org) site from a DITA map. See the [plug-in documentation](docs/guide.ditamap) for setup and options.

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

To try the documentation shipped with this plug-in, build `docs/guide.ditamap` with `-Dzensical.config=docs/zensical.toml` as described in [Build and preview the documentation](docs/topics/getting-started.dita).

`-Dzensical.stage=sources` stops before `zensical build`, which `zensical serve` would repeat anyway. Leave it out for a deployable static site in `out/site/`:

```bash
dita -i guide.ditamap -f zensical -o out
```

## Build the plug-in ZIP

From the repository root, with the `zip` command installed, run:

```bash
rm -f com.redhat.zensical.zip
zip -r com.redhat.zensical.zip \
  plugin.xml build_zensical.xml conductor.xml \
  xsl python resources docs \
README.md INTERCHANGE.md LICENSE
```

This creates `com.redhat.zensical.zip` in the repository root, with `plugin.xml` at the archive root. The first command removes an earlier archive so it cannot retain files that have since been deleted. Install the ZIP with `dita install com.redhat.zensical.zip`. The GitHub release workflow packages the same files.

## Documentation and Pages

The DITA docs show how to build and style the site. They list the options and explain source links, code blocks, and how to add to the plugin. GitHub Actions sends the site to Pages on each push to `main`.

## Releases

To publish a release, tag the commit with the release version and push the tag. For example:

```bash
git tag VERSION
git push origin VERSION
```

Pushing any tag creates a GitHub release with `com.redhat.zensical.zip` attached. The archive keeps `plugin.xml` at its root so DITA-OT can install it directly.
