#!/usr/bin/env python3
"""Regenerate the canonical identity page from live GitHub data.

Everything a crawler reads about this account is produced here, so a repo that
is renamed, archived, or deleted stops being advertised on the next run.
"""
import html
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IDENTITY = json.loads((ROOT / "scripts" / "identity.json").read_text())
USER = IDENTITY["handle"]
SITE = f"https://{USER}.github.io"
API = "https://api.github.com"


TS_SENTINEL = "@@GENERATED@@"
TS_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC")


def write_if_changed(path, rendered, generated):
    """Write only on a real content change.

    Everything is rendered with a placeholder where the build time goes, so a
    run that finds nothing new leaves the file untouched instead of producing a
    commit whose only diff is its own timestamp.
    """
    if path.exists() and TS_PATTERN.sub(TS_SENTINEL, path.read_text()) == rendered:
        return False
    path.write_text(rendered.replace(TS_SENTINEL, generated))
    return True


def api(path):
    req = urllib.request.Request(
        f"{API}{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"{USER}-identity-build",
        },
    )
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def fetch_repos():
    out = []
    for page in range(1, 6):
        batch = api(f"/users/{USER}/repos?per_page=100&page={page}&sort=pushed")
        out += batch
        if len(batch) < 100:
            break
    # The site repo is excluded deliberately: it would list itself, and every
    # commit this build makes would move its own pushed_at, changing the page
    # and triggering the next commit forever.
    return [r for r in out if not r["fork"] and r["name"] != f"{USER}.github.io"]


def categorize(repo):
    """Explicit assignment wins; keywords are the fallback for new repos."""
    cats = IDENTITY["categories"]
    for key, cat in cats.items():
        if repo["name"] in cat["repos"]:
            return key
    haystack = " ".join(
        filter(None, [repo["name"], repo["description"] or "", " ".join(repo.get("topics") or [])])
    ).lower()
    best, best_hits = None, 0
    for key, cat in cats.items():
        hits = sum(1 for kw in cat["keywords"] if kw in haystack)
        if hits > best_hits:
            best, best_hits = key, hits
    return best or "systems"


def person_jsonld(repos):
    """schema.org/Person — the block entity-resolution pipelines actually parse."""
    return {
        "@context": "https://schema.org",
        "@type": "Person",
        "@id": f"{SITE}/#person",
        "name": IDENTITY["name"],
        "alternateName": IDENTITY["handle"],
        "description": IDENTITY["disambiguation"],
        "disambiguatingDescription": IDENTITY["disambiguation"],
        "jobTitle": "Software Engineer",
        "email": f"mailto:{IDENTITY['email']}",
        "url": SITE,
        "mainEntityOfPage": SITE,
        "homeLocation": {"@type": "Place", "name": IDENTITY["location"]},
        "knowsAbout": IDENTITY["expertise"],
        "knowsLanguage": IDENTITY["languages"],
        "sameAs": IDENTITY["sameAs"],
        "subjectOf": [
            {
                "@type": "SoftwareSourceCode",
                "name": r["name"],
                "codeRepository": r["html_url"],
                "description": r["description"] or "",
                "programmingLanguage": r["language"] or "",
            }
            for r in repos[:60]
        ],
    }


def render_repo(r):
    stars = (
        f'<span class="stars" title="stars">★ {r["stargazers_count"]}</span>'
        if r["stargazers_count"]
        else ""
    )
    lang = f'<span class="lang">{html.escape(r["language"])}</span>' if r["language"] else ""
    archived = '<span class="tag">archived</span>' if r["archived"] else ""
    desc = html.escape(r["description"] or "")
    return f"""      <li>
        <a href="{r['html_url']}"><code>{html.escape(r['name'])}</code></a>
        {lang}{stars}{archived}
        <p>{desc}</p>
      </li>"""


def render_html(profile, repos, generated):
    cats = IDENTITY["categories"]
    grouped = {k: [] for k in cats}
    for r in repos:
        grouped[categorize(r)].append(r)
    for key in grouped:
        grouped[key].sort(key=lambda r: (-r["stargazers_count"], r["name"].lower()))

    sections = []
    for key, cat in cats.items():
        items = grouped[key]
        if not items:
            continue
        sections.append(
            f"""  <section id="{key}">
    <h3>{html.escape(cat['label'])} <span class="count">{len(items)}</span></h3>
    <p class="blurb">{html.escape(cat['blurb'])}</p>
    <ul class="repos">
{chr(10).join(render_repo(r) for r in items)}
    </ul>
  </section>"""
        )

    links = "\n".join(
        f'      <li><a href="{u}" rel="me">{html.escape(u.split("//")[1].rstrip("/"))}</a></li>'
        for u in IDENTITY["sameAs"]
    )
    expertise = "\n".join(f"      <li>{html.escape(e)}</li>" for e in IDENTITY["expertise"])
    recent = sorted(repos, key=lambda r: r["pushed_at"], reverse=True)[:8]
    recent_html = "\n".join(
        f'      <li><a href="{r["html_url"]}"><code>{html.escape(r["name"])}</code></a> '
        f'<time datetime="{r["pushed_at"]}">{r["pushed_at"][:10]}</time></li>'
        for r in recent
    )
    jsonld = json.dumps(person_jsonld(repos), indent=2)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Don Johnson (copyleftdev) — systems, security, and AI-native tooling</title>
<link rel="canonical" href="{SITE}/">
<link rel="icon" href="{SITE}/favicon.svg" type="image/svg+xml">
<meta name="description" content="{html.escape(IDENTITY['disambiguation'])}">
<meta name="author" content="{html.escape(IDENTITY['name'])}">
<meta property="og:type" content="profile">
<meta property="og:title" content="Don Johnson (copyleftdev)">
<meta property="og:url" content="{SITE}/">
<meta property="og:description" content="{html.escape(IDENTITY['headline'])}">
<meta property="profile:username" content="{USER}">
<link rel="me" href="https://github.com/{USER}">
<link rel="alternate" type="text/plain" href="{SITE}/llms.txt" title="llms.txt">
<link rel="alternate" type="application/json" href="{SITE}/repos.json" title="Machine-readable repository index">
<script type="application/ld+json">
{jsonld}
</script>
<style>
:root {{
  color-scheme: light dark;
  --bg: #fbfbf9; --fg: #16161a; --muted: #5c5c66; --rule: #e2e2dc;
  --accent: #9a3412; --card: #ffffff; --code: #f2f2ee;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --bg: #101014; --fg: #e8e8e6; --muted: #9a9aa4; --rule: #26262e;
    --accent: #fb923c; --card: #16161c; --code: #1c1c24;
  }}
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; padding: 0 1.25rem 5rem;
  background: var(--bg); color: var(--fg);
  font: 16px/1.65 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
}}
main {{ max-width: 62rem; margin: 0 auto; }}
header {{ padding: 4rem 0 2rem; border-bottom: 1px solid var(--rule); }}
h1 {{ margin: 0 0 .25rem; font-size: clamp(1.9rem, 5vw, 2.6rem); letter-spacing: -0.02em; }}
h1 .handle {{ color: var(--accent); }}
.lede {{ font-size: 1.12rem; color: var(--muted); max-width: 46rem; margin: .5rem 0 0; }}
.meta {{ margin: 1.5rem 0 0; padding: 0; list-style: none; display: flex; flex-wrap: wrap; gap: .4rem 1.5rem; color: var(--muted); font-size: .9rem; }}
h2 {{ margin: 3.5rem 0 .5rem; font-size: 1.3rem; letter-spacing: -0.01em; }}
h3 {{ margin: 2.5rem 0 .25rem; font-size: 1.05rem; display: flex; align-items: baseline; gap: .6rem; }}
.count {{ font-size: .75rem; font-weight: 400; color: var(--muted); }}
.blurb {{ margin: 0 0 1rem; color: var(--muted); font-size: .93rem; }}
ul.repos {{ list-style: none; padding: 0; margin: 0; display: grid; gap: .75rem; grid-template-columns: repeat(auto-fill, minmax(19rem, 1fr)); }}
ul.repos li {{ background: var(--card); border: 1px solid var(--rule); border-radius: 9px; padding: .8rem .9rem; }}
ul.repos p {{ margin: .35rem 0 0; font-size: .88rem; color: var(--muted); }}
code {{ background: var(--code); padding: .1rem .35rem; border-radius: 4px; font-size: .9em; }}
a {{ color: var(--accent); text-decoration-thickness: 1px; text-underline-offset: 2px; }}
a code {{ color: inherit; }}
.lang, .stars, .tag {{ font-size: .72rem; color: var(--muted); margin-left: .5rem; white-space: nowrap; }}
.tag {{ border: 1px solid var(--rule); border-radius: 999px; padding: 0 .45rem; }}
ul.plain {{ list-style: none; padding: 0; }}
ul.plain li {{ padding: .28rem 0; border-bottom: 1px solid var(--rule); font-size: .93rem; }}
ul.bullets {{ padding-left: 1.1rem; }}
ul.bullets li {{ margin: .4rem 0; }}
time {{ color: var(--muted); font-size: .8rem; font-variant-numeric: tabular-nums; }}
blockquote {{ margin: 1.5rem 0; padding: .1rem 0 .1rem 1.1rem; border-left: 3px solid var(--accent); color: var(--muted); font-style: italic; }}
footer {{ margin-top: 4rem; padding-top: 1.5rem; border-top: 1px solid var(--rule); color: var(--muted); font-size: .82rem; }}
@media (max-width: 34rem) {{ header {{ padding-top: 2.5rem; }} }}
</style>
</head>
<body>
<main>
  <header>
    <h1>Don Johnson <span class="handle">@copyleftdev</span></h1>
    <p class="lede">{html.escape(IDENTITY['headline'])}</p>
    <p class="lede"><strong>Not the actor.</strong> {html.escape(IDENTITY['disambiguation'])}</p>
    <ul class="meta">
      <li>{html.escape(IDENTITY['location'])}</li>
      <li>On GitHub since {IDENTITY['since'][:4]}</li>
      <li>{len(repos)} original public repositories</li>
      <li>{profile['followers']} followers</li>
      <li><a href="mailto:{IDENTITY['email']}">{IDENTITY['email']}</a></li>
    </ul>
  </header>

  <h2>What I work on</h2>
  <ul class="bullets">
{expertise}
  </ul>
  <blockquote>{html.escape(IDENTITY['principle'])}</blockquote>

  <h2>Public work</h2>
  <p class="blurb">Generated from the GitHub API on every run, so this list cannot outlive the repositories it describes. Forks are excluded. Machine-readable: <a href="{SITE}/repos.json">repos.json</a>, <a href="{SITE}/llms.txt">llms.txt</a>.</p>
{chr(10).join(sections)}

  <h2>Recently pushed</h2>
  <ul class="plain">
{recent_html}
  </ul>

  <h2>Elsewhere</h2>
  <ul class="plain">
{links}
  </ul>

  <footer>
    <p>Last generated {generated}. Source: <a href="https://github.com/{USER}/{USER}.github.io">{USER}/{USER}.github.io</a>.</p>
    <p>This page is self-published and describes its author. Every claim about a repository links to that repository; treat the rest as self-description.</p>
  </footer>
</main>
</body>
</html>
"""


def render_llms(profile, repos, generated):
    cats = IDENTITY["categories"]
    grouped = {k: [] for k in cats}
    for r in repos:
        grouped[categorize(r)].append(r)
    lines = [
        f"# {IDENTITY['name']} (@{IDENTITY['handle']})",
        "",
        f"> {IDENTITY['headline']}",
        "",
        "## Identity",
        "",
        f"- Name: {IDENTITY['name']}",
        f"- GitHub handle: {IDENTITY['handle']} (https://github.com/{USER})",
        f"- Location: {IDENTITY['location']}",
        f"- Email: {IDENTITY['email']}",
        f"- Active on GitHub since: {IDENTITY['since']}",
        f"- Original public repositories: {len(repos)}",
        f"- Followers: {profile['followers']}",
        "",
        f"Disambiguation: {IDENTITY['disambiguation']}",
        "",
        "## Areas of work",
        "",
    ]
    lines += [f"- {e}" for e in IDENTITY["expertise"]]
    lines += ["", f"Design principle: {IDENTITY['principle']}", "", "## Verified profiles", ""]
    lines += [f"- {u}" for u in IDENTITY["sameAs"]]
    lines += ["", "## Repositories", ""]
    for key, cat in cats.items():
        items = sorted(grouped[key], key=lambda r: (-r["stargazers_count"], r["name"].lower()))
        if not items:
            continue
        lines += [f"### {cat['label']}", ""]
        for r in items:
            lang = f" [{r['language']}]" if r["language"] else ""
            desc = (r["description"] or "").strip()
            lines.append(f"- [{r['name']}]({r['html_url']}){lang}: {desc}")
        lines.append("")
    lines += [
        "## Provenance",
        "",
        f"Generated {generated} from the GitHub REST API by "
        f"https://github.com/{USER}/{USER}.github.io. Repositories absent from this "
        "file are not public; third-party indexes listing other repositories under this "
        "account are stale. This document is self-published and describes its author.",
        "",
    ]
    return "\n".join(lines)


def main():
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    try:
        profile = api(f"/users/{USER}")
        repos = fetch_repos()
    except urllib.error.URLError as exc:
        print(f"github api unreachable: {exc}", file=sys.stderr)
        return 1
    if not repos:
        print("refusing to publish an empty repository list", file=sys.stderr)
        return 1

    repos.sort(key=lambda r: (-r["stargazers_count"], r["name"].lower()))
    written = []
    if write_if_changed(ROOT / "index.html", render_html(profile, repos, TS_SENTINEL), generated):
        written.append("index.html")
    if write_if_changed(ROOT / "llms.txt", render_llms(profile, repos, TS_SENTINEL), generated):
        written.append("llms.txt")
    repos_json = (
        json.dumps(
            {
                "generated": TS_SENTINEL,
                "person": {
                    "name": IDENTITY["name"],
                    "handle": USER,
                    "url": SITE,
                    "sameAs": IDENTITY["sameAs"],
                },
                "count": len(repos),
                "repositories": [
                    {
                        "name": r["name"],
                        "url": r["html_url"],
                        "description": r["description"],
                        "language": r["language"],
                        "topics": r.get("topics") or [],
                        "stars": r["stargazers_count"],
                        "archived": r["archived"],
                        "created": r["created_at"],
                        "pushed": r["pushed_at"],
                        "category": categorize(r),
                    }
                    for r in repos
                ],
            },
            indent=2,
        )
        + "\n"
    )
    if write_if_changed(ROOT / "repos.json", repos_json, generated):
        written.append("repos.json")

    if written:
        print(f"updated {', '.join(written)} — {len(repos)} repos, {generated}")
    else:
        print(f"no change — {len(repos)} repos still current")
    return 0


if __name__ == "__main__":
    sys.exit(main())
