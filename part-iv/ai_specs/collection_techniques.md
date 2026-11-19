# Collection techniques
**Audience: Engineer + collect.py**

Inventory: `sources.json`, reviewed by the author, stores `id`, `title`, `url`, `license`, `evidence_class`, `file` and `trusted`. Target corpus: 17 verified SDD sources described in the report. **Do not invent entries to meet a quota.**

Current baseline: source text is reviewed and placed in `kdb/links/` as UTF-8 `.md` or `.txt`. Collection copies approved sources to `kdb/raw/` and records SHA-256 hashes in `.state/manifest.json`; unchanged content is not recopied. Missing, unsafe, untrusted or invalid entries are logged and skipped without stopping other sources. Reject path traversal and symlink sources. A future network fetcher must honor robots.txt, licenses, terms and rate limits; never fetch arbitrary URLs merely because they are in a manifest.
