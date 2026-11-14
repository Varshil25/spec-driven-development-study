# Collection Techniques

> **OpenOwls SD-KDP** — Read by `collect.py`'s maintainer and by the agent when a source fails to collect.
> How sources enter the knowledge base, and what is recorded about each one.

---

## The source list is the only way in

`corpus/sources.csv` lists every source with an ID, verdict, tier, evidence type, URL and licence.
`collect.py` reads only this file. A source is added by adding a row (with a reason in `why`) and
committing it — never by dropping a file into `raw/`.

- `verdict = rejected` rows are **never fetched**. They stay in the list so the rejection is on record.
- The standing rejection rules in `oracle.md` are checked by the author before a new row is marked
  `trusted`.

## Fetching

| Source type | How it is fetched | Text extraction |
| --- | --- | --- |
| arXiv paper (`arxiv.org/abs/<id>`) | The PDF at `arxiv.org/pdf/<id>` | `pdftotext -layout`; references section kept |
| GitHub file (`github.com/<o>/<r>/blob/<branch>/<path>`) | The raw file from `raw.githubusercontent.com` | As is (Markdown) |
| Web article | The page | Main content only: navigation, footers, cookie banners and comment threads removed |

**Fallback (`--from-dir DIR`).** Where the machine running the pipeline cannot reach a site, the
author or operator may place a fetched copy at `DIR/<id>.md` (or `.pdf`); `collect.py` imports it
exactly as if fetched, and records `fetched_via: import` in the manifest. Every import is listed in
`progress.md`. (The operator's cloud workspace can only reach GitHub and package registries, so the
first collection there uses this route, with pages fetched by a scraping service.)

## What is recorded (`state/manifest.json`)

For each source: `id`, `url`, `fetched_at` (UTC), `fetched_via` (`http` or `import`), `bytes`,
`sha256` of the extracted text, and `title_seen` (the title as found on the page, so a title in
`sources.csv` that was typed by hand can be checked).

## Change detection (incremental runs)

A source is passed on to distillation only if its `sha256` differs from the last distilled hash
recorded in the article's front matter (or it has no article yet). Re-running on an unchanged
corpus distils nothing. Living documents (tool docs) are expected to change; papers are not — a
changed arXiv hash is logged as a warning (usually a new version).

## Licences and storage

- Full texts stay in `raw/`, which is git-ignored and never published.
- The wiki may quote a source **at most twice per article, 25 words per quote**, always attributed.
- `licence` is copied into each article's front matter.

## Failure handling

A fetch that fails (network, 4xx/5xx, empty extraction under 500 characters) is retried once, then
recorded in the manifest with `status: failed` and the reason; the run continues with the other
sources and exits with status 1 so the batch log shows it.
