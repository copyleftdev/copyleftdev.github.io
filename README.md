# copyleftdev.github.io

The canonical, machine-readable answer to "who is copyleftdev?"

It exists because that question was previously answered by third parties. When eight
frontier models were asked it with web search enabled, they built their picture from
nine domains — four of which were stale mirrors (`explore.market.dev`, `lib.rs`, a
scraper mirror, and cached GitHub URLs for deleted repositories). Several confidently
described repos that no longer exist. This site is the authoritative source that
outranks them, and it regenerates itself so it can never become one of them.

## What it publishes

| Path | For | Contents |
|---|---|---|
| `index.html` | people, crawlers | Identity, disambiguation, categorized repo list, `schema.org/Person` JSON-LD |
| `llms.txt` | models | The same facts as plain markdown, no markup to parse |
| `repos.json` | pipelines | Structured index of every original public repo |
| `robots.txt` | crawlers | Explicit allow for AI crawlers, plus sitemap |

## How it stays true

`scripts/build.py` regenerates all three artifacts from the GitHub REST API. Forks are
excluded; renamed, archived, and deleted repos disappear on the next run. It refuses to
publish an empty list, so an API failure leaves the last good version in place.

Prose that isn't derived from the API — the headline, disambiguation, and areas of work
— lives in `scripts/identity.json`. That is the only file to hand-edit.

```sh
python3 scripts/build.py    # no dependencies, stdlib only
```

A scheduled Action reruns it daily and commits only when the output actually changed.

## Setup

1. Push to `copyleftdev/copyleftdev.github.io`.
2. Settings → Pages → deploy from `main`, root.
3. Settings → Actions → General → Workflow permissions → **Read and write**.

To also serve this at `codetestcode.io`: add a `CNAME` file containing the domain, point
an `ALIAS`/`A` record at GitHub Pages, and set the custom domain under Settings → Pages.
Don't add `CNAME` before the DNS exists — it takes the site offline until it resolves.
