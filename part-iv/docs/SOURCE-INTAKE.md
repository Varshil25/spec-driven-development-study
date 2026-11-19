# Reviewed corpus intake checklist

The study report describes 17 trusted sources, but this branch starts with `sources.json = []`. Do not invent bibliographic metadata or copy unlicensed full texts to fill the count.

For each source, verify its exact title, canonical URL, author, publication date, source type, license or allowed use, evidence class, and whether it is one of the Oracle's exclusions. Save the reviewed UTF-8 text locally under `kdb/links/<filename>.txt` (gitignored). Then append a JSON entry:

```json
{
  "id": "S08",
  "title": "Verified title from source page",
  "url": "https://verified-source.example/path",
  "license": "verified terms or permitted research use",
  "evidence_class": "documented",
  "file": "S08.txt",
  "trusted": true
}
```

The above is a **schema example only**, not a verified citation. Never use its placeholder URL in the real manifest.

Source categories expected from the report: 7 papers, 4 documentation/announcement sources, 6 practitioner analyses. Keep excluded items in a separate research log (not the trusted manifest). Confirm source permissions before saving or redistributing extracted text. Record failed downloads and changes in source content.
