"""Per-page links to the DITA source in a git repository or an AEM Guides DAM.

Each interchange page records the URI of its source topic. A SourceLinks
instance maps that file to a path relative to a local root folder and turns
the path into a URL:

    git   the repository's web UI, for editing or viewing the file on a branch
    aem   a DAM URL root you supply; the path is appended, or replaces {path}

The URLs go into each page's front matter as source_edit_url and
source_view_url. Zensical renders them with its own page-action buttons,
through the partials/actions.html override in resources/overrides.

URL templates accept these placeholders: {path} (URL-encoded, '/' kept),
{raw_path}, {repo}, {branch} and {topic_id}.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import urllib.parse
import urllib.request
from dataclasses import dataclass

# Web UI URL patterns per git host, for each action
GIT_TEMPLATES = {
    "github":    {"edit": "{repo}/edit/{branch}/{path}",       "view": "{repo}/blob/{branch}/{path}"},
    "gitlab":    {"edit": "{repo}/-/edit/{branch}/{path}",     "view": "{repo}/-/blob/{branch}/{path}"},
    "bitbucket": {"edit": "{repo}/src/{branch}/{path}?mode=edit", "view": "{repo}/src/{branch}/{path}"},
    "gitea":     {"edit": "{repo}/_edit/{branch}/{path}",      "view": "{repo}/src/branch/{branch}/{path}"},
    # Azure Repos has no direct edit URL; the file view carries an Edit button
    "azure":     {"edit": "{repo}?path=/{path}&version=GB{branch}", "view": "{repo}?path=/{path}&version=GB{branch}"},
}

class SourceLinkError(Exception):
    """The source-link settings are incomplete or inconsistent."""


def uri_to_path(uri: str) -> pathlib.Path | None:
    parsed = urllib.parse.urlparse(uri)
    if parsed.scheme not in ("file", ""):
        return None
    return pathlib.Path(urllib.request.url2pathname(parsed.path)).resolve()


def _git(cwd, *args) -> str:
    try:
        result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return ""
    return result.stdout.strip()


def web_url_from_remote(remote: str) -> str:
    """git@host:owner/repo.git or ssh://git@host/owner/repo -> https://host/owner/repo"""
    remote = remote.strip()
    match = re.match(r"^[\w.-]+@([^:/]+):(.+)$", remote)
    if match:
        remote = "https://{}/{}".format(match.group(1), match.group(2))
    elif remote.startswith("ssh://"):
        parsed = urllib.parse.urlparse(remote)
        remote = "https://{}{}".format(parsed.hostname, parsed.path)
    else:
        parsed = urllib.parse.urlparse(remote)
        if parsed.username or parsed.password:  # never publish embedded credentials
            remote = parsed._replace(netloc=parsed.hostname + (":%d" % parsed.port if parsed.port else "")).geturl()
    return re.sub(r"\.git/?$", "", remote).rstrip("/")


def guess_git_host(url: str) -> str:
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    if "gitlab" in host:
        return "gitlab"
    if "bitbucket" in host:
        return "bitbucket"
    if host.endswith("dev.azure.com") or host.endswith("visualstudio.com"):
        return "azure"
    if any(name in host for name in ("gitea", "forgejo", "codeberg")):
        return "gitea"
    return "github"


ACTIONS = {"edit": ("edit",), "view": ("view",), "both": ("edit", "view")}


@dataclass
class SourceLinks:
    kind: str                    # "git" or "aem"
    templates: dict[str, str]    # action ("edit", "view") -> URL template
    root: pathlib.Path
    repo: str = ""
    branch: str = ""

    @property
    def actions(self) -> tuple[str, ...]:
        return tuple(a for a in ("edit", "view") if a in self.templates)

    @classmethod
    def configure(cls, kind, *, site_source="", root="", action="edit", template="", view_template="",
                  git_url="", git_branch="", git_host="auto", dam_url="", dam_view_url=""):
        if kind not in ("git", "aem"):
            raise SourceLinkError("source links must be git or aem, not {!r}".format(kind))
        if action not in ACTIONS:
            raise SourceLinkError("source link action must be edit, view or both, not {!r}".format(action))
        actions = ACTIONS[action]
        map_file = uri_to_path(site_source) if site_source else None
        map_dir = map_file.parent if map_file else pathlib.Path.cwd()
        overrides = {"edit": template, "view": view_template or template}

        if kind == "git":
            top = _git(map_dir, "rev-parse", "--show-toplevel")
            base = pathlib.Path(root).resolve() if root else (pathlib.Path(top) if top else None)
            if base is None:
                raise SourceLinkError("the map is not in a git checkout; set zensical.source.root")
            repo = web_url_from_remote(git_url or _git(map_dir, "remote", "get-url", "origin"))
            if not repo:
                raise SourceLinkError("no repository URL; set zensical.git.url or add an 'origin' remote")
            branch = git_branch or _git(map_dir, "rev-parse", "--abbrev-ref", "HEAD")
            if branch in ("", "HEAD"):  # detached checkout, as in many CI jobs: link to the commit
                branch = _git(map_dir, "rev-parse", "HEAD")
            if not branch:
                raise SourceLinkError("cannot tell the branch; set zensical.git.branch")
            host = guess_git_host(repo) if git_host in ("", "auto") else git_host
            if host not in GIT_TEMPLATES and not all(overrides[a] for a in actions):
                raise SourceLinkError("unknown git host {!r}; use one of {} or set a URL template".format(
                    host, ", ".join(sorted(GIT_TEMPLATES))))
            templates = {a: _checked(overrides[a] or GIT_TEMPLATES[host][a]) for a in actions}
            return cls(kind, templates, base, repo=repo, branch=branch)

        edit_url = template or dam_url
        view_url = view_template or dam_view_url or edit_url
        urls = {"edit": edit_url, "view": view_url}
        missing = [a for a in actions if not urls[a]]
        if missing:
            raise SourceLinkError("aem source links need the DAM URL root (zensical.aem.dam-url)")
        templates = {a: _checked(_with_path(urls[a])) for a in actions}
        base = pathlib.Path(root).resolve() if root else map_dir
        return cls(kind, templates, base)

    def relative_path(self, page) -> str | None:
        source = uri_to_path(page.meta.get("source", ""))
        if source is None:
            return None
        try:
            return source.relative_to(self.root).as_posix()
        except ValueError:
            return None

    def urls_for(self, page) -> dict[str, str]:
        """{"edit": url, "view": url} for the configured actions; empty when unmapped."""
        rel = self.relative_path(page)
        if rel is None:
            return {}
        fields = _Fields(path=urllib.parse.quote(rel, safe="/"), raw_path=rel, repo=self.repo,
                         branch=urllib.parse.quote(self.branch, safe="/"), topic_id=page.meta.get("id", ""))
        # Encode unsafe characters in the configured URL (a space in a DAM folder, say);
        # existing %xx escapes, URL syntax and {placeholders} are kept
        return {action: urllib.parse.quote(template, safe=":/?#[]@!$&'()*+,;=%{}~").format_map(fields)
                for action, template in self.templates.items()}


def _with_path(url: str) -> str:
    """A DAM URL root gets the topic path appended unless it places {path} itself."""
    if "{path}" in url or "{raw_path}" in url:
        return url
    return url.rstrip("/") + "/{path}"


def _checked(template: str) -> str:
    """Fail early, with a readable message, on unknown placeholders or stray braces."""
    try:
        template.format_map(_Fields(path="p", raw_path="p", repo="r", branch="b", topic_id="t"))
    except (ValueError, IndexError) as exc:
        raise SourceLinkError("malformed source URL template {!r}: {}".format(template, exc)) from None
    return template


class _Fields(dict):
    def __missing__(self, key):
        raise SourceLinkError("unknown placeholder {{{}}} in the source URL template".format(key))
