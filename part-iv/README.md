# Part IV — OpenOwls SD-KDP: evidence-first SDD knowledge base

This implementation follows the OpenOwls *Learning From Your Oracle* guide, with seven underscore-named specs, an Oracle, and four pipeline stages (collect, distill, index, backup).

## Status
**Initial runnable, extractive baseline — not the final LLM distiller.** This baseline does not pretend to produce model-validated Oracle prose. It extracts source sentences with source attribution and indexes them for retrieval. Full 17-source ingestion, model voice review, OpenKB comparison and empirical RQ5 claims remain pending.

## Quick start
```bash
cd part-iv
python src/run_batch.py
python src/query.py "What is spec-driven development?"
python -m unittest discover -s tests -v
```
Add reviewed, locally saved UTF-8 documents under `kdb/links/` (one `.txt` or `.md` file per source), and register their filenames and metadata in `sources.json`. The starter inventory is deliberately empty: do not treat unverified sources as collected. Files in `kdb/` and `wiki/` are not committed. To rebuild all items, run `python src/run_batch.py --force`.

Read `CLAUDE.md`, the seven `ai_specs/` documents in order, then `progress.md` before making changes. Never commit secrets, downloaded source text, or generated knowledge articles.

## Design deviations / pending work
- A deterministic, citation-bearing extractive distiller is used until an approved model provider and verified source corpus are configured; it **does not** perform OpenOwls' LLM voice check.
- The retrieval index is a local token-frequency JSON index, not an embedding/vector store; upgrade and document the change before claiming vector retrieval.
- `kdb/links/` accepts locally reviewed source text rather than automated URL downloads; network fetching, robots/terms checks and PDF parsing are future work.
- Backup runs even after earlier-stage failures. Results should not be presented as full SD-KDP compliance until these gaps are closed.
